"""
scripts/seed_data.py — Seed the RAG index and knowledge graph with sample documents.

Usage:
    python scripts/seed_data.py --source ./data/sample-docs/ [--rag-url http://localhost:8001]
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import logging

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_RAG_URL = "http://localhost:8001"


def load_docs(source_dir: pathlib.Path) -> list[dict]:
    """Load .txt and .md files from source_dir as indexable chunks."""
    docs = []
    for path in sorted(source_dir.rglob("*.txt")) + sorted(source_dir.rglob("*.md")):
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            continue
        # Simple chunking: split on double newlines, max 1500 chars per chunk
        raw_chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
        for i, chunk in enumerate(raw_chunks):
            if len(chunk) > 1500:
                # Further split on single newlines
                sub = [s.strip() for s in chunk.split("\n") if s.strip()]
                raw_chunks[i:i+1] = sub

        for j, chunk in enumerate(raw_chunks):
            if len(chunk) < 20:
                continue
            doc_id = f"{path.stem}-{j:04d}"
            docs.append({
                "doc_id": doc_id,
                "content": chunk,
                "metadata": {
                    "source":    str(path),
                    "filename":  path.name,
                    "chunk_idx": j,
                    "document_id": doc_id,
                },
            })
    return docs


def seed(source_dir: pathlib.Path, rag_url: str) -> None:
    docs = load_docs(source_dir)
    if not docs:
        logger.warning("No documents found in %s", source_dir)
        return

    logger.info("Seeding %d chunks from %s → %s", len(docs), source_dir, rag_url)
    success = 0
    with httpx.Client(timeout=30) as client:
        for doc in docs:
            try:
                resp = client.post(f"{rag_url}/index", json=doc)
                resp.raise_for_status()
                success += 1
            except httpx.HTTPStatusError as e:
                logger.error("Failed to index %s: %s", doc["doc_id"], e.response.text[:200])
            except httpx.RequestError as e:
                logger.error("Connection error: %s — is the RAG service running?", e)
                sys.exit(1)

    logger.info("Seeded %d/%d chunks ✓", success, len(docs))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the AI Factory RAG index")
    parser.add_argument("--source",  type=pathlib.Path, default=pathlib.Path("./data/sample-docs"))
    parser.add_argument("--rag-url", default=DEFAULT_RAG_URL)
    args = parser.parse_args()

    if not args.source.exists():
        logger.error("Source directory does not exist: %s", args.source)
        sys.exit(1)

    seed(args.source, args.rag_url)


if __name__ == "__main__":
    main()
