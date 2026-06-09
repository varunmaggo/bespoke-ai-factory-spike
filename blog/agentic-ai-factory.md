# Building a Bespoke Agentic AI Factory: AWS Kiro, ATX Transforms, Agentic RAG & Production-Grade LLM Evaluation for Java Spring Microservices

> **A comprehensive engineering blueprint** for teams ready to move beyond hobby AI integrations and operate intelligent systems at enterprise scale — with full observability, validated outputs, and automated CI/CD from day one.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [AWS Kiro — The Agentic Orchestration Core](#2-aws-kiro)
3. [ATX Custom Transforms](#3-atx-custom-transforms)
4. [Agentic RAG for Enterprise Data Sources](#4-agentic-rag)
5. [LLM Evaluation with DeepEval & LLM-as-Judge](#5-evaluation-framework)
6. [Java Spring Microservice Integration](#6-java-spring-microservices)
7. [Observability Stack](#7-observability-stack)
8. [GitHub CI/CD Pipelines](#8-cicd-pipelines)
9. [Running It All Together](#9-running-it-all-together)
10. [Lessons Learned & What's Next](#10-lessons-learned)

---

## 1. Architecture Overview

The **AI Factory** is not a single service — it is a composable, observable pipeline that turns raw enterprise data and user intent into validated, trustworthy AI outputs. The factory metaphor is intentional: raw materials (data, requests) enter one end; quality-checked products (answers, actions, documents) exit the other. Every station on the line is instrumented, tested, and replaceable.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC AI FACTORY                                       │
│                                                                                   │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────────────┐  │
│  │  Client  │──▶│  API Gateway │──▶│  AWS Kiro   │──▶│  ATX Transform Layer │  │
│  │  (Java   │   │  (Spring     │   │  Agentic    │   │  (Custom Pipelines)  │  │
│  │  Spring) │   │  Gateway)    │   │  Orchestr.  │   │                      │  │
│  └──────────┘   └──────────────┘   └──────┬──────┘   └──────────┬───────────┘  │
│                                           │                      │               │
│                         ┌─────────────────▼──────────────────────▼────────────┐ │
│                         │            Agentic RAG Engine                        │ │
│                         │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │ │
│                         │  │ Vector   │  │ Graph DB │  │ Enterprise Data   │  │ │
│                         │  │ Store    │  │ (Neo4j)  │  │ (S3/RDS/Redshift) │  │ │
│                         │  └──────────┘  └──────────┘  └──────────────────┘  │ │
│                         └──────────────────────────────────────────────────────┘ │
│                                           │                                       │
│                         ┌─────────────────▼──────────────────────────────────┐   │
│                         │           Evaluation & Validation Layer              │   │
│                         │  ┌────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│                         │  │  DeepEval  │  │ LLM-as-Judge│  │  Scorecards │ │   │
│                         │  └────────────┘  └─────────────┘  └─────────────┘ │   │
│                         └──────────────────────────────────────────────────────┘ │
│                                           │                                       │
│                         ┌─────────────────▼──────────────────────────────────┐   │
│                         │       Observability Stack (OpenTelemetry)            │   │
│                         │  Prometheus │ Grafana │ Jaeger │ CloudWatch          │   │
│                         └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Core Design Principles

**1. Every LLM call is a testable unit.** The factory treats every prompt → response pair as a software artifact. It is versioned, scored, and monitored exactly like any other service endpoint.

**2. Retrieval is a first-class citizen.** The RAG layer is not bolted on; it is the primary mechanism for grounding all generation in authoritative enterprise data.

**3. Transforms are composable.** The ATX layer lets data engineers define deterministic, auditable transformations that run before and after LLM calls — no magic "the model figured it out."

**4. Evaluation gates deployment.** No new prompt template, model version, or RAG configuration ships without clearing automated eval thresholds in CI.

**5. Observability is not optional.** Every token, every retrieval, every evaluation score emits structured telemetry. If you can't measure it, you can't trust it in production.

---

## 2. AWS Kiro — The Agentic Orchestration Core

[AWS Kiro](https://kiro.dev) is Anthropic-compatible agentic infrastructure that provides spec-driven agent authoring. Instead of imperative "do this, then do that" code, Kiro agents are declared as **specs** (YAML-first definitions of goals, tools, and constraints) that compile to executable agent graphs.

### Why Kiro over LangChain / custom agent loops?

| Concern | DIY Agent Loop | AWS Kiro |
|---|---|---|
| Spec-to-code traceability | Manual docs | Native spec linkage |
| Multi-agent coordination | Custom message bus | Built-in |
| Retry / circuit-breaker | You build it | Declarative policy |
| AWS service integration | SDK boilerplate | First-class hooks |
| Observability | Manual spans | Auto-instrumented |

### Kiro Agent Spec Example

```yaml
# kiro/specs/enterprise-rag-agent.kiro.yaml
apiVersion: kiro.dev/v1
kind: AgentSpec
metadata:
  name: enterprise-rag-agent
  namespace: ai-factory
spec:
  description: >
    Retrieve context from enterprise data sources, transform results,
    generate a grounded response, and validate it before returning.
  
  model:
    provider: anthropic
    id: claude-sonnet-4-20250514
    parameters:
      max_tokens: 4096
      temperature: 0.1

  tools:
    - name: vector_search
      description: Search the vector store for semantically similar documents
      type: function
      parameters:
        query: { type: string, required: true }
        top_k:  { type: integer, default: 10 }
        filters: { type: object }

    - name: graph_query
      description: Query the knowledge graph for entity relationships
      type: function
      parameters:
        cypher: { type: string, required: true }

    - name: atx_transform
      description: Apply a named ATX transform pipeline to data
      type: function
      parameters:
        pipeline_id: { type: string, required: true }
        payload:     { type: object, required: true }

    - name: eval_response
      description: Score the draft response before returning it
      type: function
      parameters:
        response: { type: string, required: true }
        context:  { type: array  }
        question: { type: string, required: true }

  steps:
    - id: retrieve
      tool: vector_search
      description: Retrieve relevant enterprise documents

    - id: enrich
      tool: graph_query
      description: Enrich retrieval with graph relationships
      dependsOn: [retrieve]

    - id: transform
      tool: atx_transform
      description: Normalise and clean retrieved context
      dependsOn: [enrich]
      config:
        pipeline_id: enterprise-context-normaliser

    - id: generate
      description: Generate a grounded response using retrieved context
      dependsOn: [transform]

    - id: validate
      tool: eval_response
      description: Score the response; retry if below threshold
      dependsOn: [generate]
      policy:
        retry:
          maxAttempts: 2
          condition: "score < 0.75"

  hooks:
    onStart:  emit_otel_span
    onFinish: emit_otel_span
    onError:  alert_pagerduty
```

### Kiro Hooks — Wiring to OpenTelemetry

```python
# kiro/hooks/otel_hook.py
from opentelemetry import trace
from opentelemetry.trace import SpanKind
import time

tracer = trace.get_tracer("ai-factory.kiro")

def emit_otel_span(event: dict):
    """Kiro lifecycle hook: emit a trace span for every agent step."""
    with tracer.start_as_current_span(
        name=f"kiro.{event['step_id']}",
        kind=SpanKind.INTERNAL,
        attributes={
            "agent.name":       event.get("agent_name"),
            "agent.step":       event.get("step_id"),
            "agent.run_id":     event.get("run_id"),
            "llm.model":        event.get("model_id", ""),
            "llm.input_tokens": event.get("input_tokens", 0),
            "llm.output_tokens":event.get("output_tokens", 0),
            "llm.latency_ms":   event.get("latency_ms", 0),
        }
    ) as span:
        if event.get("error"):
            span.record_exception(Exception(event["error"]))
            span.set_status(trace.StatusCode.ERROR)
```

---

## 3. ATX Custom Transforms

**ATX (Agent Transform eXtensions)** is our internal abstraction layer for deterministic data transformations that run inside the agentic pipeline. Think of it as a middleware rack for AI pipelines: every piece of data that enters or leaves an LLM call passes through a configurable chain of transforms.

### Why Transforms Matter

Raw enterprise data is messy:
- PII fields that must be redacted before reaching the LLM
- Dates in 14 different formats across legacy systems
- JSON blobs from SAP that need flattening
- Binary content that needs extracting to plain text

ATX handles all of this declaratively, with a Python SDK for custom transforms.

### ATX Transform Pipeline Architecture

```
Input Data
    │
    ▼
┌─────────────────────────────────────┐
│         ATX Pipeline Engine          │
│                                      │
│  ┌──────────┐  ┌──────────────────┐ │
│  │  Built-in │  │  Custom Plugins  │ │
│  │ Transforms│  │  (Python SDK)    │ │
│  └─────┬────┘  └────────┬─────────┘ │
│        │                │            │
│        └────────┬───────┘            │
│                 │                    │
│         ┌───────▼────────┐           │
│         │ Pipeline Runner │           │
│         │ (DAG execution) │           │
│         └───────┬────────┘           │
└─────────────────┼───────────────────┘
                  │
                  ▼
           Transformed Output
```

### ATX Pipeline Definition

```python
# atx/pipelines/enterprise_context_normaliser.py
from atx import Pipeline, Transform, schema

class RedactPII(Transform):
    """Remove PII fields before sending to LLM."""
    name = "redact_pii"

    SENSITIVE_KEYS = {
        "ssn", "social_security", "credit_card", "password",
        "api_key", "secret", "token", "dob", "date_of_birth"
    }

    def transform(self, data: dict) -> dict:
        def _redact(obj):
            if isinstance(obj, dict):
                return {
                    k: "[REDACTED]" if k.lower() in self.SENSITIVE_KEYS else _redact(v)
                    for k, v in obj.items()
                }
            if isinstance(obj, list):
                return [_redact(item) for item in obj]
            return obj
        return _redact(data)


class NormaliseDates(Transform):
    """Standardise all date strings to ISO-8601."""
    name = "normalise_dates"

    DATE_PATTERNS = [
        "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d",
        "%d-%b-%Y", "%B %d, %Y", "%d.%m.%Y"
    ]

    def transform(self, data: dict) -> dict:
        from datetime import datetime
        import re

        def _try_parse(value: str):
            for fmt in self.DATE_PATTERNS:
                try:
                    return datetime.strptime(value, fmt).date().isoformat()
                except ValueError:
                    continue
            return value  # Return original if no pattern matched

        def _walk(obj):
            if isinstance(obj, dict):
                return {k: _walk(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_walk(i) for i in obj]
            if isinstance(obj, str):
                # Heuristic: looks like a date
                if re.match(r'\d{1,4}[-/\.]\d{1,2}[-/\.]\d{2,4}', obj):
                    return _try_parse(obj)
            return obj
        return _walk(data)


class FlattenSAPPayload(Transform):
    """Flatten deeply nested SAP JSON structures."""
    name = "flatten_sap"

    def transform(self, data: dict) -> dict:
        import pandas as pd
        flat = pd.json_normalize(data, sep='.')
        return flat.to_dict(orient='records')[0]


class TruncateToContextWindow(Transform):
    """Ensure total token count fits the model's context window."""
    name = "truncate_context"

    def __init__(self, max_tokens: int = 100_000):
        self.max_tokens = max_tokens

    def transform(self, data: dict) -> dict:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")

        chunks = data.get("chunks", [])
        budget = self.max_tokens
        kept = []

        for chunk in sorted(chunks, key=lambda c: c.get("score", 0), reverse=True):
            tokens = len(enc.encode(chunk.get("text", "")))
            if tokens <= budget:
                kept.append(chunk)
                budget -= tokens
            if budget <= 0:
                break

        data["chunks"] = kept
        data["truncated"] = len(kept) < len(chunks)
        return data


# Register the pipeline
enterprise_context_normaliser = Pipeline(
    id="enterprise-context-normaliser",
    transforms=[
        RedactPII(),
        NormaliseDates(),
        FlattenSAPPayload(),
        TruncateToContextWindow(max_tokens=80_000),
    ],
    on_error="skip_and_log",  # or "fail_fast"
)
```

### ATX SDK: Building a Custom Transform Plugin

```python
# atx/sdk/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import logging, time

logger = logging.getLogger(__name__)

@dataclass
class TransformResult:
    data: Any
    success: bool
    duration_ms: float
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class Transform(ABC):
    """Base class for all ATX transforms."""

    name: str = "unnamed_transform"
    version: str = "1.0.0"

    @abstractmethod
    def transform(self, data: Any) -> Any:
        ...

    def __call__(self, data: Any) -> TransformResult:
        start = time.monotonic()
        try:
            result = self.transform(data)
            return TransformResult(
                data=result,
                success=True,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:
            logger.error(f"Transform {self.name} failed: {e}")
            return TransformResult(
                data=data,   # Pass-through on error
                success=False,
                duration_ms=(time.monotonic() - start) * 1000,
                errors=[str(e)],
            )
```

---

## 4. Agentic RAG for Enterprise Data Sources

Standard RAG is single-shot: embed the query, retrieve top-K, stuff context, generate. **Agentic RAG** is iterative: the agent decides *what* to retrieve, *when* to retrieve more, and *whether* the retrieved context is sufficient before generating.

### Retrieval Strategy: Adaptive Multi-Hop

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Agentic RAG Planner                         │
│                                                              │
│  1. Decompose query into sub-questions                       │
│  2. For each sub-question:                                   │
│     a. Vector search (dense embeddings)                      │
│     b. BM25 keyword search (sparse)                          │
│     c. Graph traversal (relationships)                       │
│  3. Rerank fused results                                     │
│  4. Assess sufficiency → if insufficient, re-query          │
│  5. Assemble final context window                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
LLM Generation (grounded, with citations)
```

### Vector Store Integration (AWS OpenSearch Serverless)

```python
# services/rag/vector_store.py
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class EnterpriseVectorStore:
    """Hybrid search over AWS OpenSearch Serverless."""

    def __init__(
        self,
        endpoint: str,
        index_name: str = "enterprise-docs",
        embedding_model: str = "BAAI/bge-large-en-v1.5",
        region: str = "ap-southeast-2",
    ):
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, region, "aoss")

        self.client = OpenSearch(
            hosts=[{"host": endpoint, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )
        self.index_name = index_name
        self.embedder = SentenceTransformer(embedding_model)
        logger.info(f"VectorStore connected to {endpoint}/{index_name}")

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
        alpha: float = 0.7,  # weight: 0=BM25 only, 1=vector only
    ) -> list[dict]:
        """
        Hybrid search combining dense vector similarity with BM25 keyword matching.
        Results are fused using Reciprocal Rank Fusion (RRF).
        """
        query_vector = self.embedder.encode(query).tolist()

        # Build the hybrid query
        knn_query = {
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": top_k * 2,  # Retrieve more for RRF
                }
            }
        }

        bm25_query = {
            "multi_match": {
                "query": query,
                "fields": ["content^2", "title^3", "metadata.*"],
                "type": "best_fields",
            }
        }

        if filters:
            knn_query = {"bool": {"must": [knn_query], "filter": filters}}
            bm25_query = {"bool": {"must": [bm25_query], "filter": filters}}

        # Execute both searches
        dense_hits = self.client.search(
            index=self.index_name,
            body={"size": top_k * 2, "query": knn_query, "_source": True}
        )["hits"]["hits"]

        sparse_hits = self.client.search(
            index=self.index_name,
            body={"size": top_k * 2, "query": bm25_query, "_source": True}
        )["hits"]["hits"]

        return self._rrf_fusion(dense_hits, sparse_hits, top_k, alpha)

    def _rrf_fusion(
        self, dense_hits, sparse_hits, top_k: int, alpha: float
    ) -> list[dict]:
        """Reciprocal Rank Fusion with configurable weighting."""
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}
        k = 60  # RRF constant

        for rank, hit in enumerate(dense_hits):
            doc_id = hit["_id"]
            scores[doc_id] = scores.get(doc_id, 0) + alpha * (1 / (k + rank + 1))
            docs[doc_id] = hit["_source"]

        for rank, hit in enumerate(sparse_hits):
            doc_id = hit["_id"]
            scores[doc_id] = scores.get(doc_id, 0) + (1 - alpha) * (1 / (k + rank + 1))
            docs[doc_id] = hit["_source"]

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            {"id": doc_id, "score": score, **docs[doc_id]}
            for doc_id, score in ranked
        ]

    def index_document(self, doc_id: str, text: str, metadata: dict) -> bool:
        """Embed and index a document."""
        embedding = self.embedder.encode(text).tolist()
        body = {
            "content":   text,
            "embedding": embedding,
            "metadata":  metadata,
        }
        response = self.client.index(
            index=self.index_name,
            id=doc_id,
            body=body,
        )
        return response["result"] in ("created", "updated")
```

### Graph-Augmented RAG (Neo4j)

```python
# services/rag/graph_store.py
from neo4j import GraphDatabase
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class EnterpriseKnowledgeGraph:
    """
    Graph-augmented retrieval for multi-hop entity relationships.
    Useful for: org hierarchies, product dependencies, compliance chains.
    """

    def __init__(self, uri: str, auth: tuple):
        self.driver = GraphDatabase.driver(uri, auth=auth)
        logger.info(f"KnowledgeGraph connected to {uri}")

    def get_related_entities(
        self,
        entity_ids: list[str],
        relationship_types: Optional[list[str]] = None,
        max_depth: int = 2,
    ) -> list[dict]:
        """
        Traverse the knowledge graph from seed entities.
        Returns enrichment context for the RAG pipeline.
        """
        rel_filter = ""
        if relationship_types:
            rel_types = "|".join(relationship_types)
            rel_filter = f":{rel_types}"

        cypher = f"""
        MATCH path = (start)-[r{rel_filter}*1..{max_depth}]-(related)
        WHERE start.id IN $entity_ids
        WITH DISTINCT related,
             [rel in relationships(path) | type(rel)] AS rel_chain,
             length(path) AS depth
        RETURN related.id   AS id,
               related.name AS name,
               related.type AS type,
               related.description AS description,
               rel_chain,
               depth
        ORDER BY depth, related.name
        LIMIT 50
        """
        with self.driver.session() as session:
            result = session.run(cypher, entity_ids=entity_ids)
            return [dict(record) for record in result]

    def extract_entity_ids(self, documents: list[dict]) -> list[str]:
        """Extract entity IDs from retrieved documents for graph traversal."""
        ids = set()
        for doc in documents:
            metadata = doc.get("metadata", {})
            if "entity_ids" in metadata:
                ids.update(metadata["entity_ids"])
            if "document_id" in metadata:
                ids.add(metadata["document_id"])
        return list(ids)
```

### Adaptive RAG Orchestrator

```python
# services/rag/orchestrator.py
import anthropic
import json
from dataclasses import dataclass
from typing import Optional
import logging

from .vector_store import EnterpriseVectorStore
from .graph_store import EnterpriseKnowledgeGraph
from ..atx import Pipeline

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    answer: str
    sources: list[dict]
    sufficiency_score: float
    hops: int
    metadata: dict


class AgentRAGOrchestrator:
    """
    Multi-hop agentic RAG that iteratively retrieves until
    the context is sufficient to answer the query confidently.
    """

    SUFFICIENCY_PROMPT = """
    You have been given a user question and some retrieved context.
    Assess whether the context is sufficient to answer the question accurately.

    Question: {question}

    Context:
    {context}

    Respond with JSON only:
    {{
      "sufficient": true/false,
      "confidence": 0.0-1.0,
      "missing_information": ["list of what's missing if insufficient"],
      "follow_up_queries": ["refined queries to get missing info"]
    }}
    """

    def __init__(
        self,
        vector_store: EnterpriseVectorStore,
        graph_store: EnterpriseKnowledgeGraph,
        atx_pipeline: Pipeline,
        max_hops: int = 3,
        sufficiency_threshold: float = 0.75,
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.atx_pipeline = atx_pipeline
        self.max_hops = max_hops
        self.threshold = sufficiency_threshold
        self.client = anthropic.Anthropic()

    def retrieve_and_generate(self, query: str, filters: Optional[dict] = None) -> RAGResult:
        all_chunks = []
        current_query = query
        hops = 0

        while hops < self.max_hops:
            # 1. Retrieve from vector store
            chunks = self.vector_store.hybrid_search(current_query, top_k=10, filters=filters)

            # 2. Enrich via graph
            entity_ids = self.graph_store.extract_entity_ids(chunks)
            if entity_ids:
                graph_context = self.graph_store.get_related_entities(entity_ids)
                for g in graph_context:
                    chunks.append({
                        "content": f"{g['name']} ({g['type']}): {g.get('description', '')}",
                        "score": 0.5,  # Graph results get a neutral baseline score
                        "source": "knowledge_graph",
                    })

            all_chunks.extend(chunks)
            hops += 1

            # 3. ATX transform to clean + truncate
            transformed = self.atx_pipeline({
                "chunks": all_chunks,
                "query": query,
            })
            context_str = self._format_context(transformed.get("chunks", all_chunks))

            # 4. Assess sufficiency
            assessment = self._assess_sufficiency(query, context_str)
            logger.info(
                f"Hop {hops}: sufficiency={assessment['confidence']:.2f}, "
                f"sufficient={assessment['sufficient']}"
            )

            if assessment["sufficient"] or assessment["confidence"] >= self.threshold:
                break

            # 5. Refine query for next hop
            follow_ups = assessment.get("follow_up_queries", [])
            if follow_ups:
                current_query = follow_ups[0]
                logger.info(f"Refining query for hop {hops+1}: {current_query}")

        # 6. Generate final answer
        answer = self._generate(query, context_str, all_chunks)
        return RAGResult(
            answer=answer,
            sources=all_chunks[:10],
            sufficiency_score=assessment["confidence"],
            hops=hops,
            metadata={"original_query": query, "final_query": current_query},
        )

    def _assess_sufficiency(self, question: str, context: str) -> dict:
        prompt = self.SUFFICIENCY_PROMPT.format(question=question, context=context[:8000])
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            return {"sufficient": True, "confidence": 0.6, "missing_information": [], "follow_up_queries": []}

    def _generate(self, query: str, context: str, sources: list) -> str:
        system = """You are an enterprise AI assistant. Answer the user's question
        using ONLY the provided context. If the context does not contain enough
        information, say so explicitly. Always cite your sources by referencing
        the document IDs in brackets like [DOC-123]."""

        user_content = f"""Context:
{context}

Question: {query}

Answer (with source citations):"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text

    def _format_context(self, chunks: list[dict]) -> str:
        parts = []
        for i, chunk in enumerate(chunks):
            doc_id = chunk.get("metadata", {}).get("document_id", f"DOC-{i}")
            source = chunk.get("source", "vector_store")
            text = chunk.get("content", "")
            parts.append(f"[{doc_id}] (source: {source})\n{text}")
        return "\n\n---\n\n".join(parts)
```

---

## 5. Evaluation Framework

Production AI requires continuous validation. We use a three-layer evaluation stack:

1. **DeepEval** — metric-based automated evaluation (faithfulness, answer relevancy, hallucination detection)
2. **LLM-as-Judge** — Claude scoring model responses against a rubric
3. **Human-in-the-loop scorecards** — for high-stakes or ambiguous cases

### DeepEval Integration

```python
# evals/deepeval/rag_evaluator.py
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    HallucinationMetric,
    ToxicityMetric,
    BiasMetric,
)
from deepeval.test_case import LLMTestCase
from deepeval.dataset import EvaluationDataset
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """
    Comprehensive RAG evaluation using DeepEval metrics.
    Designed to run in both CI (fast subset) and scheduled (full dataset).
    """

    # Thresholds that gate CI deployment
    CI_THRESHOLDS = {
        "answer_relevancy":      0.80,
        "faithfulness":          0.85,
        "contextual_precision":  0.75,
        "contextual_recall":     0.70,
        "hallucination":         0.10,  # Lower is better
        "toxicity":              0.05,  # Lower is better
        "bias":                  0.10,  # Lower is better
    }

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self.metrics = [
            AnswerRelevancyMetric(threshold=self.CI_THRESHOLDS["answer_relevancy"],
                                  model=model),
            FaithfulnessMetric(threshold=self.CI_THRESHOLDS["faithfulness"],
                               model=model),
            ContextualPrecisionMetric(threshold=self.CI_THRESHOLDS["contextual_precision"],
                                      model=model),
            ContextualRecallMetric(threshold=self.CI_THRESHOLDS["contextual_recall"],
                                   model=model),
            HallucinationMetric(threshold=self.CI_THRESHOLDS["hallucination"],
                                model=model),
            ToxicityMetric(threshold=self.CI_THRESHOLDS["toxicity"],
                           model=model),
            BiasMetric(threshold=self.CI_THRESHOLDS["bias"],
                       model=model),
        ]

    def build_test_cases(self, eval_data: list[dict]) -> list[LLMTestCase]:
        """Convert evaluation dataset rows to DeepEval test cases."""
        test_cases = []
        for row in eval_data:
            test_case = LLMTestCase(
                input=row["question"],
                actual_output=row["generated_answer"],
                expected_output=row.get("ground_truth"),
                retrieval_context=row.get("retrieved_chunks", []),
                context=row.get("retrieved_chunks", []),
            )
            test_cases.append(test_case)
        return test_cases

    def run_evaluation(
        self,
        eval_data: list[dict],
        run_async: bool = True,
    ) -> dict:
        """
        Run the full evaluation suite.
        Returns a results dict with per-metric scores and pass/fail.
        """
        test_cases = self.build_test_cases(eval_data)
        dataset = EvaluationDataset(test_cases=test_cases)

        logger.info(f"Running evaluation on {len(test_cases)} test cases...")
        results = evaluate(dataset, self.metrics, run_async=run_async)

        return self._summarise_results(results)

    def _summarise_results(self, results) -> dict:
        summary = {
            "passed": True,
            "metrics": {},
            "failures": [],
        }

        for metric_result in results.test_results:
            for metric in metric_result.metrics_data:
                name = metric.name.lower().replace(" ", "_")
                score = metric.score
                passed = metric.success

                summary["metrics"][name] = {
                    "score": score,
                    "passed": passed,
                    "threshold": self.CI_THRESHOLDS.get(name),
                }

                if not passed:
                    summary["passed"] = False
                    summary["failures"].append({
                        "metric": name,
                        "score": score,
                        "threshold": self.CI_THRESHOLDS.get(name),
                        "reason": metric.reason,
                    })

        return summary
```

### LLM-as-Judge

```python
# evals/llm_judge/judge.py
import anthropic
import json
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """
You are an expert evaluator of AI-generated responses for enterprise applications.
You assess responses on multiple quality dimensions with rigorous, consistent scoring.
You must respond ONLY with valid JSON matching the schema provided.
"""

JUDGE_RUBRIC = """
Evaluate the following AI response on these dimensions:

**Scoring Guide (0.0 - 1.0):**

1. **Groundedness** (0.0-1.0)
   - 1.0: Every factual claim is directly supported by the provided context
   - 0.5: Most claims supported but some extrapolation
   - 0.0: Response ignores context or makes up information

2. **Completeness** (0.0-1.0)
   - 1.0: Addresses all aspects of the question thoroughly
   - 0.5: Addresses main point but misses secondary aspects
   - 0.0: Does not address the question

3. **Clarity** (0.0-1.0)
   - 1.0: Clear, well-structured, easy for target audience to understand
   - 0.5: Understandable but could be clearer
   - 0.0: Confusing, poorly structured

4. **Conciseness** (0.0-1.0)
   - 1.0: Appropriately concise without omitting important information
   - 0.5: Some unnecessary verbosity
   - 0.0: Extremely verbose or padded

5. **Safety** (0.0-1.0)
   - 1.0: No harmful, biased, or inappropriate content
   - 0.0: Contains harmful, biased, or inappropriate content

---

Question: {question}

Context provided to the AI:
{context}

AI Response:
{response}

Expected answer (if available):
{expected_answer}

Respond with this JSON structure ONLY:
{{
  "scores": {{
    "groundedness":  <float>,
    "completeness":  <float>,
    "clarity":       <float>,
    "conciseness":   <float>,
    "safety":        <float>
  }},
  "overall_score": <float (weighted average)>,
  "passed": <boolean (overall_score >= 0.75)>,
  "critique": "<2-3 sentence summary of strengths and weaknesses>",
  "improvement_suggestions": ["<suggestion 1>", "<suggestion 2>"]
}}
"""


@dataclass
class JudgeResult:
    scores: dict[str, float]
    overall_score: float
    passed: bool
    critique: str
    improvement_suggestions: list[str]
    raw_response: str


class LLMJudge:
    """
    Claude-as-judge for evaluating RAG and agent responses.
    Implements self-consistency via multiple judge calls with majority voting.
    """

    WEIGHTS = {
        "groundedness": 0.35,
        "completeness": 0.25,
        "clarity":      0.20,
        "conciseness":  0.10,
        "safety":       0.10,
    }

    def __init__(self, model: str = "claude-sonnet-4-20250514", num_judges: int = 1):
        self.client = anthropic.Anthropic()
        self.model = model
        self.num_judges = num_judges  # Set >1 for self-consistency

    def judge(
        self,
        question: str,
        response: str,
        context: str,
        expected_answer: Optional[str] = None,
    ) -> JudgeResult:
        """Score a response. With num_judges > 1, averages multiple independent judgements."""
        all_results = [
            self._single_judge(question, response, context, expected_answer)
            for _ in range(self.num_judges)
        ]

        if len(all_results) == 1:
            return all_results[0]

        # Aggregate via averaging
        avg_scores = {}
        for dim in self.WEIGHTS:
            avg_scores[dim] = sum(r.scores[dim] for r in all_results) / len(all_results)

        overall = sum(avg_scores[d] * w for d, w in self.WEIGHTS.items())
        return JudgeResult(
            scores=avg_scores,
            overall_score=overall,
            passed=overall >= 0.75,
            critique=all_results[0].critique,  # Use first judge's narrative
            improvement_suggestions=all_results[0].improvement_suggestions,
            raw_response="aggregated",
        )

    def _single_judge(
        self,
        question: str,
        response: str,
        context: str,
        expected_answer: Optional[str],
    ) -> JudgeResult:
        prompt = JUDGE_RUBRIC.format(
            question=question,
            context=context[:4000],
            response=response,
            expected_answer=expected_answer or "Not provided",
        )
        api_response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = api_response.content[0].text

        try:
            parsed = json.loads(raw)
            scores = parsed["scores"]
            overall = sum(scores.get(d, 0) * w for d, w in self.WEIGHTS.items())
            return JudgeResult(
                scores=scores,
                overall_score=overall,
                passed=parsed.get("passed", overall >= 0.75),
                critique=parsed.get("critique", ""),
                improvement_suggestions=parsed.get("improvement_suggestions", []),
                raw_response=raw,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Judge response parse error: {e}\nRaw: {raw}")
            return JudgeResult(
                scores={d: 0.0 for d in self.WEIGHTS},
                overall_score=0.0,
                passed=False,
                critique="Judge response parse error",
                improvement_suggestions=[],
                raw_response=raw,
            )

    def batch_judge(self, test_cases: list[dict]) -> list[JudgeResult]:
        """Evaluate a batch of test cases. Returns results in the same order."""
        return [
            self.judge(
                question=tc["question"],
                response=tc["response"],
                context=tc.get("context", ""),
                expected_answer=tc.get("expected_answer"),
            )
            for tc in test_cases
        ]
```

---

## 6. Java Spring Microservice Integration

The Java Spring side of the factory exposes a clean REST API that the AI orchestration layer calls. Spring AI provides the integration primitives; we wrap them with circuit breakers, observability, and validation gates.

### Spring Boot AI Factory Client

```java
// src/main/java/com/aifactory/service/AIFactoryService.java
package com.aifactory.service;

import com.aifactory.dto.*;
import com.aifactory.metrics.AIFactoryMetrics;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import io.micrometer.core.instrument.Timer;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.anthropic.AnthropicChatModel;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.SystemPromptTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;

@Service
public class AIFactoryService {

    private static final Logger log = LoggerFactory.getLogger(AIFactoryService.class);

    private final AnthropicChatModel chatModel;
    private final WebClient ragClient;
    private final WebClient evalClient;
    private final AIFactoryMetrics metrics;
    private final Tracer tracer;

    @Value("${ai.factory.eval.threshold:0.75}")
    private double evalThreshold;

    @Autowired
    public AIFactoryService(
        AnthropicChatModel chatModel,
        WebClient.Builder webClientBuilder,
        AIFactoryMetrics metrics,
        Tracer tracer,
        @Value("${ai.factory.rag.url}") String ragUrl,
        @Value("${ai.factory.eval.url}") String evalUrl
    ) {
        this.chatModel    = chatModel;
        this.ragClient    = webClientBuilder.baseUrl(ragUrl).build();
        this.evalClient   = webClientBuilder.baseUrl(evalUrl).build();
        this.metrics      = metrics;
        this.tracer       = tracer;
    }

    @CircuitBreaker(name = "ai-factory", fallbackMethod = "generateFallback")
    @Retry(name = "ai-factory")
    public AIFactoryResponse query(AIFactoryRequest request) {
        Span span = tracer.spanBuilder("ai-factory.query")
            .setAttribute("query.length", request.getQuery().length())
            .setAttribute("user.id", request.getUserId())
            .startSpan();

        Timer.Sample timer = metrics.startQueryTimer();

        try (Scope scope = span.makeCurrent()) {

            // 1. Retrieve context via Agentic RAG
            RAGResponse ragResponse = retrieveContext(request);
            span.setAttribute("rag.hops",    ragResponse.getHops());
            span.setAttribute("rag.sources", ragResponse.getSources().size());

            // 2. Build grounded prompt
            String groundedPrompt = buildGroundedPrompt(
                request.getQuery(),
                ragResponse.getContext()
            );

            // 3. Generate response
            String response = chatModel.call(new Prompt(groundedPrompt))
                .getResult()
                .getOutput()
                .getContent();

            // 4. Evaluate before returning
            EvalResult evalResult = evaluateResponse(
                request.getQuery(),
                response,
                ragResponse.getContext()
            );

            span.setAttribute("eval.score",  evalResult.getOverallScore());
            span.setAttribute("eval.passed", evalResult.isPassed());
            metrics.recordEvalScore(evalResult.getOverallScore());

            if (!evalResult.isPassed()) {
                log.warn("Response below eval threshold: score={}, threshold={}",
                    evalResult.getOverallScore(), evalThreshold);
                metrics.incrementLowQualityResponses();
            }

            return AIFactoryResponse.builder()
                .answer(response)
                .sources(ragResponse.getSources())
                .evalScore(evalResult.getOverallScore())
                .evalPassed(evalResult.isPassed())
                .hops(ragResponse.getHops())
                .build();

        } catch (Exception e) {
            span.recordException(e);
            metrics.incrementErrors();
            throw e;
        } finally {
            span.end();
            metrics.stopQueryTimer(timer);
        }
    }

    private RAGResponse retrieveContext(AIFactoryRequest request) {
        return ragClient.post()
            .uri("/api/v1/retrieve")
            .bodyValue(Map.of(
                "query",   request.getQuery(),
                "filters", request.getFilters(),
                "top_k",   10
            ))
            .retrieve()
            .bodyToMono(RAGResponse.class)
            .timeout(Duration.ofSeconds(30))
            .block();
    }

    private EvalResult evaluateResponse(String query, String response, String context) {
        return evalClient.post()
            .uri("/api/v1/judge")
            .bodyValue(Map.of(
                "question", query,
                "response", response,
                "context",  context
            ))
            .retrieve()
            .bodyToMono(EvalResult.class)
            .timeout(Duration.ofSeconds(15))
            .onErrorReturn(EvalResult.defaultPassed())  // Don't block on eval failure
            .block();
    }

    private String buildGroundedPrompt(String query, String context) {
        return """
            You are an enterprise assistant. Use ONLY the following context to answer.
            If the context is insufficient, say so.

            Context:
            %s

            Question: %s

            Answer:
            """.formatted(context, query);
    }

    public AIFactoryResponse generateFallback(AIFactoryRequest request, Exception ex) {
        log.error("AI Factory circuit breaker open, using fallback: {}", ex.getMessage());
        metrics.incrementCircuitBreakerTrips();
        return AIFactoryResponse.builder()
            .answer("I'm temporarily unable to process your request. Please try again shortly.")
            .evalPassed(false)
            .evalScore(0.0)
            .build();
    }
}
```

### Spring Actuator + Micrometer Custom Metrics

```java
// src/main/java/com/aifactory/metrics/AIFactoryMetrics.java
package com.aifactory.metrics;

import io.micrometer.core.instrument.*;
import org.springframework.stereotype.Component;

@Component
public class AIFactoryMetrics {

    private final MeterRegistry registry;
    private final Counter errorCounter;
    private final Counter lowQualityCounter;
    private final Counter circuitBreakerCounter;
    private final Timer queryTimer;
    private final DistributionSummary evalScoreDistribution;

    public AIFactoryMetrics(MeterRegistry registry) {
        this.registry = registry;

        this.errorCounter = Counter.builder("ai_factory_errors_total")
            .description("Total AI Factory errors")
            .register(registry);

        this.lowQualityCounter = Counter.builder("ai_factory_low_quality_responses_total")
            .description("Responses that failed evaluation threshold")
            .register(registry);

        this.circuitBreakerCounter = Counter.builder("ai_factory_circuit_breaker_trips_total")
            .description("Circuit breaker open events")
            .register(registry);

        this.queryTimer = Timer.builder("ai_factory_query_duration_seconds")
            .description("End-to-end query latency")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(registry);

        this.evalScoreDistribution = DistributionSummary.builder("ai_factory_eval_score")
            .description("Distribution of LLM-as-judge evaluation scores")
            .publishPercentiles(0.5, 0.75, 0.95)
            .minimumExpectedValue(0.0)
            .maximumExpectedValue(1.0)
            .register(registry);
    }

    public Timer.Sample startQueryTimer()        { return Timer.start(registry); }
    public void stopQueryTimer(Timer.Sample s)   { s.stop(queryTimer); }
    public void incrementErrors()                { errorCounter.increment(); }
    public void incrementLowQualityResponses()   { lowQualityCounter.increment(); }
    public void incrementCircuitBreakerTrips()   { circuitBreakerCounter.increment(); }
    public void recordEvalScore(double score)    { evalScoreDistribution.record(score); }
}
```

---

## 7. Observability Stack

The observability stack is built on the OpenTelemetry Collector, with Prometheus for metrics, Jaeger for traces, and Grafana for dashboards. Every layer — Java Spring, Python RAG service, Kiro agents, ATX transforms — emits structured telemetry via the same OTLP pipeline.

### OpenTelemetry Collector Configuration

```yaml
# observability/otel-collector/config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

  prometheus:
    config:
      scrape_configs:
        - job_name: ai-factory-java
          scrape_interval: 15s
          static_configs:
            - targets: ["spring-service:8080"]
          metrics_path: /actuator/prometheus

        - job_name: ai-factory-python
          scrape_interval: 15s
          static_configs:
            - targets: ["rag-service:9090", "eval-service:9091"]

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024

  memory_limiter:
    limit_mib: 512

  resource:
    attributes:
      - key: deployment.environment
        value: ${ENVIRONMENT}
        action: upsert
      - key: service.version
        from_attribute: BUILD_VERSION
        action: insert

  # Redact PII from trace attributes
  attributes/redact_pii:
    actions:
      - key: user.email
        action: delete
      - key: user.name
        action: hash
      - key: http.request.body
        action: delete

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true

  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: ai_factory

  awscloudwatch:
    namespace: AI/Factory
    region: ${AWS_REGION}
    log_group_name: /ai-factory/otel
    dimension_rollup_option: NoDimensionRollup

  logging:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers:  [otlp]
      processors: [memory_limiter, batch, resource, attributes/redact_pii]
      exporters:  [jaeger, awscloudwatch]

    metrics:
      receivers:  [otlp, prometheus]
      processors: [memory_limiter, batch, resource]
      exporters:  [prometheus, awscloudwatch]

    logs:
      receivers:  [otlp]
      processors: [batch, resource, attributes/redact_pii]
      exporters:  [awscloudwatch, logging]
```

### Grafana Dashboard Definitions

```json
// observability/grafana/dashboards/ai-factory-overview.json (excerpt)
{
  "title": "AI Factory — Production Overview",
  "panels": [
    {
      "title": "Query Latency (p50/p95/p99)",
      "type": "timeseries",
      "targets": [
        {
          "expr": "histogram_quantile(0.50, rate(ai_factory_query_duration_seconds_bucket[5m]))",
          "legendFormat": "p50"
        },
        {
          "expr": "histogram_quantile(0.95, rate(ai_factory_query_duration_seconds_bucket[5m]))",
          "legendFormat": "p95"
        },
        {
          "expr": "histogram_quantile(0.99, rate(ai_factory_query_duration_seconds_bucket[5m]))",
          "legendFormat": "p99"
        }
      ]
    },
    {
      "title": "Eval Score Distribution",
      "type": "histogram",
      "targets": [
        {
          "expr": "rate(ai_factory_eval_score_bucket[5m])",
          "legendFormat": "{{le}}"
        }
      ]
    },
    {
      "title": "Low Quality Response Rate",
      "type": "stat",
      "targets": [
        {
          "expr": "rate(ai_factory_low_quality_responses_total[5m]) / rate(ai_factory_query_duration_seconds_count[5m])",
          "legendFormat": "Low Quality %"
        }
      ],
      "thresholds": {
        "steps": [
          { "color": "green",  "value": 0    },
          { "color": "yellow", "value": 0.05 },
          { "color": "red",    "value": 0.10 }
        ]
      }
    },
    {
      "title": "Circuit Breaker Events",
      "type": "stat",
      "targets": [
        {
          "expr": "increase(ai_factory_circuit_breaker_trips_total[1h])",
          "legendFormat": "Trips (1h)"
        }
      ]
    },
    {
      "title": "RAG Hop Distribution",
      "type": "piechart",
      "targets": [
        {
          "expr": "sum by (hops) (increase(ai_factory_rag_hops_total[1h]))",
          "legendFormat": "{{hops}} hops"
        }
      ]
    }
  ]
}
```

### Prometheus Alert Rules

```yaml
# observability/prometheus/alerts.yaml
groups:
  - name: ai_factory_alerts
    interval: 30s
    rules:

      - alert: HighEvalFailureRate
        expr: |
          rate(ai_factory_low_quality_responses_total[10m])
          / rate(ai_factory_query_duration_seconds_count[10m]) > 0.10
        for: 5m
        labels:
          severity: warning
          team: ai-platform
        annotations:
          summary: "AI Factory eval failure rate > 10%"
          description: >
            {{ $value | humanizePercentage }} of responses are failing
            evaluation thresholds. Review recent prompt or model changes.
          runbook: https://wiki.company.com/runbooks/ai-factory/eval-failures

      - alert: HighQueryLatency
        expr: |
          histogram_quantile(0.95,
            rate(ai_factory_query_duration_seconds_bucket[5m])) > 30
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "AI Factory p95 latency > 30s"

      - alert: CircuitBreakerOpen
        expr: increase(ai_factory_circuit_breaker_trips_total[5m]) > 3
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AI Factory circuit breaker tripping repeatedly"
          description: "{{ $value }} circuit breaker trips in last 5 minutes"

      - alert: RAGServiceDown
        expr: up{job="ai-factory-python"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "RAG or Eval service is down"
```

---

## 8. GitHub CI/CD Pipelines

Every change to the AI Factory — whether a new prompt template, a model upgrade, a RAG config change, or a Java service update — runs through the same automated pipeline: lint → build → unit test → eval gate → deploy.

### CI: Pull Request Validation

```yaml
# .github/workflows/ci.yml
name: AI Factory CI

on:
  pull_request:
    branches: [main, develop]
    types: [opened, synchronize, reopened]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: "3.12"
  JAVA_VERSION:   "21"
  REGISTRY:       ghcr.io
  IMAGE_BASE:     ghcr.io/${{ github.repository }}

jobs:
  # ──────────────────────────────────────────────
  # 1. Python Services (RAG, ATX, Eval)
  # ──────────────────────────────────────────────
  python-lint-test:
    name: Python — Lint & Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt

      - name: Ruff lint
        run: ruff check . --output-format=github

      - name: MyPy type check
        run: mypy services/ evals/ --ignore-missing-imports

      - name: Pytest unit tests
        run: |
          pytest tests/unit \
            --cov=services \
            --cov=evals \
            --cov-report=xml \
            --cov-report=term-missing \
            -v
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          flags: python

  # ──────────────────────────────────────────────
  # 2. Java Spring Microservice
  # ──────────────────────────────────────────────
  java-build-test:
    name: Java — Build & Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: temurin
          cache: maven

      - name: Maven build & test
        run: |
          mvn clean verify \
            -Dspring.profiles.active=test \
            -Dmaven.test.failure.ignore=false \
            --no-transfer-progress
        working-directory: services/spring-service

      - name: JaCoCo coverage report
        run: |
          mvn jacoco:report --no-transfer-progress
        working-directory: services/spring-service

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: services/spring-service/target/site/jacoco/jacoco.xml
          flags: java

      - name: Check coverage threshold
        run: |
          mvn jacoco:check \
            -Djacoco.haltOnFailure=true \
            -Djacoco.minimum.line.coverage=0.80 \
            --no-transfer-progress
        working-directory: services/spring-service

  # ──────────────────────────────────────────────
  # 3. LLM Evaluation Gate
  # ──────────────────────────────────────────────
  eval-gate:
    name: LLM Eval Gate
    runs-on: ubuntu-latest
    needs: [python-lint-test]
    if: |
      contains(github.event.pull_request.changed_files, 'services/rag') ||
      contains(github.event.pull_request.changed_files, 'evals') ||
      contains(github.event.pull_request.changed_files, 'kiro')
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install eval deps
        run: pip install -r requirements-eval.txt

      - name: Run DeepEval CI suite
        run: |
          python -m pytest evals/ci_suite.py \
            --deepeval \
            --junitxml=eval-results.xml \
            -v
        env:
          ANTHROPIC_API_KEY:       ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY:          ${{ secrets.OPENAI_API_KEY }}
          DEEPEVAL_TELEMETRY_OPT_OUT: "YES"

      - name: Upload eval results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: eval-results
          path: eval-results.xml

      - name: Comment eval results on PR
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: eval-results.xml
          comment_title: "🧪 LLM Evaluation Results"

  # ──────────────────────────────────────────────
  # 4. Docker Build & Push (on PR to main)
  # ──────────────────────────────────────────────
  docker-build:
    name: Docker Build
    runs-on: ubuntu-latest
    needs: [python-lint-test, java-build-test, eval-gate]
    if: always() && !failure()
    permissions:
      contents: read
      packages: write
    strategy:
      matrix:
        service:
          - rag-service
          - eval-service
          - transform-service
          - spring-service
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE_BASE }}/${{ matrix.service }}
          tags: |
            type=sha,prefix=pr-${{ github.event.number }}-
            type=ref,event=pr

      - name: Build & push
        uses: docker/build-push-action@v5
        with:
          context: services/${{ matrix.service }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to:   type=gha,mode=max
          build-args: |
            BUILD_VERSION=${{ github.sha }}
            BUILD_DATE=${{ github.event.repository.updated_at }}
```

### CD: Deploy to AWS

```yaml
# .github/workflows/cd.yml
name: AI Factory CD

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment
        required: true
        type: choice
        options: [staging, production]
        default: staging

env:
  AWS_REGION: ap-southeast-2

jobs:
  # ──────────────────────────────────────────────
  # 1. Build & Tag Release Images
  # ──────────────────────────────────────────────
  release-images:
    name: Build Release Images
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
      packages: write
    outputs:
      image-tag: ${{ steps.tag.outputs.tag }}
    steps:
      - uses: actions/checkout@v4

      - name: Determine tag
        id: tag
        run: echo "tag=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume:    arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/github-actions-ai-factory
          aws-region:        ${{ env.AWS_REGION }}

      - name: Log in to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build & push all services
        run: |
          for service in rag-service eval-service transform-service spring-service; do
            docker build \
              -t ${{ steps.login-ecr.outputs.registry }}/ai-factory/$service:${{ steps.tag.outputs.tag }} \
              -t ${{ steps.login-ecr.outputs.registry }}/ai-factory/$service:latest \
              --build-arg BUILD_VERSION=${{ steps.tag.outputs.tag }} \
              services/$service
            docker push ${{ steps.login-ecr.outputs.registry }}/ai-factory/$service:${{ steps.tag.outputs.tag }}
            docker push ${{ steps.login-ecr.outputs.registry }}/ai-factory/$service:latest
          done

  # ──────────────────────────────────────────────
  # 2. Deploy to Staging
  # ──────────────────────────────────────────────
  deploy-staging:
    name: Deploy → Staging
    runs-on: ubuntu-latest
    needs: [release-images]
    environment:
      name: staging
      url: https://ai-factory.staging.company.com
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/github-actions-ai-factory
          aws-region:     ${{ env.AWS_REGION }}

      - name: Terraform plan (staging)
        working-directory: infrastructure/terraform/environments/staging
        run: |
          terraform init -backend-config="key=ai-factory/staging.tfstate"
          terraform plan \
            -var="image_tag=${{ needs.release-images.outputs.image-tag }}" \
            -var="environment=staging" \
            -out=tfplan

      - name: Terraform apply (staging)
        working-directory: infrastructure/terraform/environments/staging
        run: terraform apply -auto-approve tfplan

      - name: Wait for ECS service stable
        run: |
          aws ecs wait services-stable \
            --cluster ai-factory-staging \
            --services rag-service eval-service transform-service spring-service \
            --region ${{ env.AWS_REGION }}

  # ──────────────────────────────────────────────
  # 3. Smoke Tests on Staging
  # ──────────────────────────────────────────────
  smoke-tests:
    name: Smoke Tests (Staging)
    runs-on: ubuntu-latest
    needs: [deploy-staging]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install test deps
        run: pip install pytest httpx

      - name: Run smoke tests
        run: |
          pytest tests/smoke \
            --base-url=https://ai-factory.staging.company.com \
            -v
        env:
          SMOKE_API_KEY: ${{ secrets.STAGING_API_KEY }}

  # ──────────────────────────────────────────────
  # 4. Deploy to Production (manual approval)
  # ──────────────────────────────────────────────
  deploy-production:
    name: Deploy → Production
    runs-on: ubuntu-latest
    needs: [smoke-tests]
    environment:
      name: production
      url: https://ai-factory.company.com
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/github-actions-ai-factory-prod
          aws-region:     ${{ env.AWS_REGION }}

      - name: Terraform apply (production)
        working-directory: infrastructure/terraform/environments/production
        run: |
          terraform init -backend-config="key=ai-factory/production.tfstate"
          terraform apply -auto-approve \
            -var="image_tag=${{ needs.release-images.outputs.image-tag }}" \
            -var="environment=production"

      - name: Wait for ECS service stable
        run: |
          aws ecs wait services-stable \
            --cluster ai-factory-production \
            --services rag-service eval-service transform-service spring-service \
            --region ${{ env.AWS_REGION }}

      - name: Notify Slack
        uses: slackapi/slack-github-action@v1.26.0
        with:
          channel-id: C-AI-PLATFORM-DEPLOYMENTS
          slack-message: |
            ✅ AI Factory deployed to *production*
            Version: `${{ needs.release-images.outputs.image-tag }}`
            Deployed by: ${{ github.actor }}
            Workflow: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### Reusable CI Templates

```yaml
# .github/workflows/templates/eval-template.yml
# Call this from any service that modifies AI prompts or models
name: Reusable LLM Eval

on:
  workflow_call:
    inputs:
      suite-path:
        required: true
        type: string
        description: Path to the eval test suite
      threshold:
        required: false
        type: number
        default: 0.75
        description: Minimum overall eval score to pass
    secrets:
      anthropic-api-key:
        required: true

jobs:
  run-evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - run: pip install deepeval anthropic

      - name: Run eval suite
        run: |
          python -m pytest ${{ inputs.suite-path }} \
            --deepeval \
            --threshold=${{ inputs.threshold }} \
            --junitxml=eval-results.xml
        env:
          ANTHROPIC_API_KEY:              ${{ secrets.anthropic-api-key }}
          DEEPEVAL_TELEMETRY_OPT_OUT:     "YES"
          AI_FACTORY_EVAL_THRESHOLD:      ${{ inputs.threshold }}

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: eval-results-${{ github.run_number }}
          path: eval-results.xml
```

---

## 9. Running It All Together

### Docker Compose (Local Development)

```yaml
# docker-compose.yml
services:
  # ── AI Services ──────────────────────────────
  rag-service:
    build: ./services/rag-service
    ports: ["8001:8001"]
    environment:
      ANTHROPIC_API_KEY:  ${ANTHROPIC_API_KEY}
      OPENSEARCH_URL:     http://opensearch:9200
      NEO4J_URI:          bolt://neo4j:7687
      NEO4J_AUTH:         neo4j/password
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
    depends_on: [opensearch, neo4j]

  eval-service:
    build: ./services/eval-service
    ports: ["8002:8002"]
    environment:
      ANTHROPIC_API_KEY:  ${ANTHROPIC_API_KEY}
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318

  transform-service:
    build: ./services/transform-service
    ports: ["8003:8003"]
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318

  spring-service:
    build: ./services/spring-service
    ports: ["8080:8080"]
    environment:
      SPRING_AI_ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      RAG_SERVICE_URL:    http://rag-service:8001
      EVAL_SERVICE_URL:   http://eval-service:8002
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
      SPRING_PROFILES_ACTIVE: local
    depends_on: [rag-service, eval-service]

  # ── Data Stores ──────────────────────────────
  opensearch:
    image: opensearchproject/opensearch:2.13.0
    ports: ["9200:9200"]
    environment:
      discovery.type: single-node
      DISABLE_SECURITY_PLUGIN: "true"
    volumes: [opensearch-data:/usr/share/opensearch/data]

  neo4j:
    image: neo4j:5.20
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/password
    volumes: [neo4j-data:/data]

  # ── Observability ────────────────────────────
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.102.1
    ports:
      - "4317:4317"
      - "4318:4318"
      - "8889:8889"
    volumes:
      - ./observability/otel-collector/config.yaml:/etc/otelcol-contrib/config.yaml

  prometheus:
    image: prom/prometheus:v2.52.0
    ports: ["9090:9090"]
    volumes:
      - ./observability/prometheus:/etc/prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=30d

  grafana:
    image: grafana/grafana:10.4.0
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_AUTH_ANONYMOUS_ENABLED:  "true"
    volumes:
      - ./observability/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./observability/grafana/datasources:/etc/grafana/provisioning/datasources

  jaeger:
    image: jaegertracing/all-in-one:1.57
    ports:
      - "16686:16686"
      - "14250:14250"

volumes:
  opensearch-data:
  neo4j-data:
```

### Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/your-org/ai-factory.git
cd ai-factory
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# 2. Start all services
docker compose up -d

# 3. Wait for health checks
docker compose ps   # All should show "healthy"

# 4. Index some sample documents
python scripts/seed_data.py --source ./data/sample-docs/

# 5. Run a query
curl -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our Q2 revenue forecast?", "userId": "user-123"}'

# 6. View dashboards
open http://localhost:3000   # Grafana (admin/admin)
open http://localhost:16686  # Jaeger traces
open http://localhost:9090   # Prometheus

# 7. Run the eval suite locally
pytest evals/ -v --deepeval
```

---

## 10. Lessons Learned & What's Next

### What We Got Right

**Evaluation as a first-class deployment gate** — the single highest-leverage change was blocking deployments on eval regressions. In the first month alone it caught 3 prompt changes that would have degraded response quality significantly.

**ATX as the great decoupler** — putting all data transformation logic in ATX pipelines (rather than inside prompts) made it dramatically easier to debug failures. When a response is wrong, you can inspect the exact context the LLM received after all transforms ran.

**Hybrid retrieval (dense + sparse + graph)** — vector-only retrieval consistently missed exact-match queries (product codes, part numbers, employee IDs). Adding BM25 and graph traversal improved retrieval precision by ~23% on our enterprise dataset.

**Kiro specs as living documentation** — the YAML spec for each agent is automatically linked to the code and test results. Non-engineers can read it and understand what the agent does without reading the implementation.

### What Was Harder Than Expected

**Eval dataset maintenance** — keeping the golden eval dataset up to date as enterprise data evolves is an ongoing operational cost. We now treat it as a product backlog item with quarterly reviews.

**Prompt regression testing at scale** — even small wording changes can shift scores unpredictably. We've moved to A/B prompt deployments with canary traffic before full rollout.

**Token cost at volume** — LLM-as-judge is expensive. We now use DeepEval's local models for fast CI checks and reserve Claude-as-judge for the full nightly suite and production spot-checks.

### Roadmap

- **Prompt versioning with semantic diff** — automatically summarise what changed between prompt versions in plain English
- **Streaming eval** — evaluate responses as they stream rather than post-hoc
- **Self-healing agents** — Kiro agents that detect eval degradation in production and trigger automated rollback
- **Multi-model routing** — route queries to smaller, cheaper models when the judge predicts the task doesn't need frontier capability
- **Federated RAG** — retrieval across multiple enterprise tenants with strict data isolation

---

*The complete source code for this post is available in the companion repository. Every component shown here is production-deployable; the repo includes Terraform modules, Helm charts, and a one-command local setup.*

*Questions or war stories from your own AI factory? Open an issue or reach out.*
