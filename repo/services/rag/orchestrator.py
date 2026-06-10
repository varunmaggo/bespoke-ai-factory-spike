"""
services/rag/orchestrator.py — Agentic multi-hop RAG orchestrator.

Flow:
  1. Decompose query into sub-questions
  2. Vector + graph retrieval
  3. AWS Transform: normalise context (PII redaction, date normalise, truncate)
  4. Assess sufficiency via Claude
  5. If insufficient (and hops < max), refine query and repeat
  6. Generate grounded answer
"""
from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import tempfile
from dataclasses import dataclass, field

import anthropic

from .vector_store import EnterpriseVectorStore
from .graph_store import EnterpriseKnowledgeGraph

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    answer: str
    sources: list[dict]
    sufficiency_score: float
    hops: int
    transform_metadata: dict = field(default_factory=dict)


class AgentRAGOrchestrator:
    """
    Multi-hop agentic RAG with AWS Transform for context preparation.

    Uses Anthropic Claude to assess context sufficiency and decide when
    enough context has been retrieved — or when to refine the search query.
    """

    SUFFICIENCY_PROMPT = """Assess whether the retrieved context is sufficient to answer the question.

Reply with ONLY valid JSON matching this schema:
{{
  "sufficient": true|false,
  "confidence": 0.0-1.0,
  "missing_information": ["...", "..."],
  "follow_up_queries": ["...", "..."]
}}

Question: {question}

Retrieved context (first 8000 chars):
{context}
"""

    def __init__(
        self,
        vector_store: EnterpriseVectorStore,
        graph_store: EnterpriseKnowledgeGraph,
        max_hops: int = 3,
        sufficiency_threshold: float = 0.75,
        transform_definition: str = "enterprise-context-normaliser",
    ) -> None:
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.max_hops = max_hops
        self.threshold = sufficiency_threshold
        self.transform_definition = transform_definition
        self.client = anthropic.Anthropic()

    def retrieve_and_generate(
        self,
        query: str,
        filters: dict | None = None,
    ) -> RAGResult:
        all_chunks: list[dict] = []
        current_query = query
        assessment: dict = {}
        transform_meta: dict = {}

        for hop in range(self.max_hops):
            logger.info("RAG hop %d/%d: query=%r", hop + 1, self.max_hops, current_query[:80])

            # ── 1. Vector retrieval ─────────────────────────────────────────
            chunks = self.vector_store.hybrid_search(current_query, top_k=10, filters=filters)

            # ── 2. Graph enrichment ─────────────────────────────────────────
            entity_ids = self.graph_store.extract_entity_ids(chunks)
            if entity_ids:
                related = self.graph_store.get_related_entities(entity_ids)
                chunks += [
                    {
                        "content":     f"{r['name']} ({r['type']}): {r.get('description', '')}",
                        "score":       0.5,
                        "document_id": r.get("source_doc", f"GRAPH-{r['id']}"),
                        "source":      "knowledge_graph",
                        "metadata":    {"entity_id": r["id"], "entity_type": r["type"]},
                    }
                    for r in related
                ]

            all_chunks = _merge_deduplicate(all_chunks, chunks)

            # ── 3. AWS Transform ────────────────────────────────────────────
            transformed_chunks, transform_meta = self._run_aws_transform(all_chunks)
            context_str = self._format_context(transformed_chunks)

            # ── 4. Sufficiency check ────────────────────────────────────────
            assessment = self._assess_sufficiency(query, context_str)
            logger.info(
                "Hop %d: sufficient=%s confidence=%.2f",
                hop + 1,
                assessment.get("sufficient"),
                assessment.get("confidence", 0),
            )

            if assessment.get("sufficient") or assessment.get("confidence", 0) >= self.threshold:
                break

            follow_ups = assessment.get("follow_up_queries", [])
            if follow_ups:
                current_query = follow_ups[0]

        # ── 5. Generate answer ──────────────────────────────────────────────
        answer = self._generate(query, context_str)

        return RAGResult(
            answer=answer,
            sources=all_chunks[:10],
            sufficiency_score=assessment.get("confidence", 0.6),
            hops=min(hop + 1, self.max_hops),  # type: ignore[possibly-undefined]
            transform_metadata=transform_meta,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _run_aws_transform(self, chunks: list[dict]) -> tuple[list[dict], dict]:
        """
        Call the AWS Transform CLI to normalise the retrieved chunks.
        Falls back gracefully if atx is not installed.
        """
        payload = {"chunks": chunks}

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(payload, f, default=str)
            src_path = pathlib.Path(f.name)

        out_path = src_path.parent / f"transformed_{src_path.stem}.json"

        try:
            subprocess.run(
                [
                    "atx", "custom", "def", "exec",
                    "--definition",   self.transform_definition,
                    "--source-path",  str(src_path),
                    "--output-path",  str(out_path),
                    "--trust-all-tools",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            result = json.loads(out_path.read_text())
            transformed_chunks = result.get("chunks", chunks)
            metadata = result.get("_transform_metadata", {})
            logger.info("AWS Transform applied: %s", metadata)
            return transformed_chunks, metadata

        except FileNotFoundError:
            logger.warning("atx CLI not found — skipping AWS Transform (install it from AWS)")
            return chunks, {"skipped": True, "reason": "atx_not_installed"}
        except subprocess.CalledProcessError as e:
            logger.error("AWS Transform failed: %s\n%s", e.returncode, e.stderr[:500])
            return chunks, {"error": str(e), "stderr": e.stderr[:200]}
        finally:
            src_path.unlink(missing_ok=True)
            if out_path.exists():
                out_path.unlink()

    def _assess_sufficiency(self, question: str, context: str) -> dict:
        """Ask Claude to assess whether the context is sufficient."""
        try:
            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[
                    {
                        "role": "user",
                        "content": self.SUFFICIENCY_PROMPT.format(
                            question=question, context=context[:8000]
                        ),
                    }
                ],
            )
            return json.loads(resp.content[0].text)
        except Exception as e:
            logger.warning("Sufficiency assessment failed: %s", e)
            return {"sufficient": True, "confidence": 0.6, "follow_up_queries": []}

    def _generate(self, query: str, context: str) -> str:
        """Generate a grounded answer from the normalised context."""
        resp = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=(
                "You are a precise enterprise assistant. "
                "Answer the question using ONLY the provided context. "
                "Cite sources using their document IDs like [DOC-123]. "
                "If the context is insufficient to answer fully, state what is missing."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {query}",
                }
            ],
        )
        return resp.content[0].text

    def _format_context(self, chunks: list[dict]) -> str:
        parts = []
        for i, c in enumerate(chunks):
            doc_id = (
                c.get("document_id")
                or c.get("metadata", {}).get("document_id")
                or f"DOC-{i}"
            )
            parts.append(f"[{doc_id}]\n{c.get('content', '')}")
        return "\n\n---\n\n".join(parts)


def _merge_deduplicate(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge new chunks into existing list, deduplicating by document_id."""
    seen = {c.get("document_id") for c in existing if c.get("document_id")}
    merged = list(existing)
    for c in new:
        doc_id = c.get("document_id")
        if doc_id not in seen:
            merged.append(c)
            if doc_id:
                seen.add(doc_id)
    # Sort by score descending
    return sorted(merged, key=lambda x: x.get("score", 0), reverse=True)
