"""
services/rag/connectors/base.py — Connector framework for ingesting documents
from internal systems (Confluence, SharePoint, …) into the agentic RAG index.

A `Connector` knows how to `fetch()` documents from one source system and yield
normalised `SourceDocument`s. Connectors degrade gracefully: when no
credentials are configured they return a small set of bundled sample documents
so the demo runs offline (the same "local fallback" pattern the transform
service uses for the atx CLI).

`chunk_document` turns a `SourceDocument` into index-ready chunks in the shape
`EnterpriseVectorStore.bulk_index` expects (`{id, content, metadata}`).
"""
from __future__ import annotations

import html
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# ── Normalised document model ────────────────────────────────────────────────


@dataclass
class SourceDocument:
    """A single document pulled from a source system, normalised to plain text."""

    doc_id: str
    title: str
    content: str
    source: str                       # connector name, e.g. "confluence"
    url: str = ""
    metadata: dict = field(default_factory=dict)


# ── Connector interface ──────────────────────────────────────────────────────


class Connector(ABC):
    """Base class for source-system connectors."""

    #: short, stable identifier used by the registry and the /ingest API
    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[SourceDocument]:
        """Return normalised documents from the source system."""

    @abstractmethod
    def is_live(self) -> bool:
        """True when real credentials are configured; False uses sample data."""


# ── HTML → text ──────────────────────────────────────────────────────────────

# Block-level tags whose close should become a line break (Confluence storage
# format and SharePoint page HTML are both XHTML-ish).
_BLOCK_CLOSE = re.compile(
    r"</(p|div|li|h[1-6]|tr|table|ul|ol|section|article|blockquote)\s*>",
    re.IGNORECASE,
)
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS_LINE = re.compile(r"[ \t]+")
_MANY_NL = re.compile(r"\n{3,}")


def html_to_text(markup: str) -> str:
    """Strip HTML/XHTML (incl. Confluence ``ac:``/``ri:`` macros) to plain text."""
    if not markup:
        return ""
    text = _BR.sub("\n", markup)
    text = _BLOCK_CLOSE.sub("\n", text)
    text = _TAG.sub("", text)          # drop remaining tags & macros
    text = html.unescape(text)
    # tidy whitespace: trim each line, collapse runs of blank lines
    lines = [_WS_LINE.sub(" ", ln).strip() for ln in text.split("\n")]
    text = "\n".join(lines)
    return _MANY_NL.sub("\n\n", text).strip()


# ── Chunking (shared with scripts/seed_data.py) ──────────────────────────────


def chunk_text(content: str, max_chars: int = 1500, min_chars: int = 20) -> list[str]:
    """Split text into chunks on paragraph boundaries, capped at ``max_chars``."""
    raw = [c.strip() for c in content.split("\n\n") if c.strip()]
    chunks: list[str] = []
    for block in raw:
        if len(block) <= max_chars:
            chunks.append(block)
            continue
        # Oversized block: fall back to line-level splitting, packing lines
        buf = ""
        for line in (ln.strip() for ln in block.split("\n") if ln.strip()):
            if buf and len(buf) + len(line) + 1 > max_chars:
                chunks.append(buf)
                buf = line
            else:
                buf = f"{buf}\n{line}" if buf else line
        if buf:
            chunks.append(buf)
    return [c for c in chunks if len(c) >= min_chars]


def chunk_document(
    doc: SourceDocument,
    max_chars: int = 1500,
    min_chars: int = 20,
) -> list[dict]:
    """Convert a SourceDocument into index-ready chunks for ``bulk_index``."""
    chunks = chunk_text(doc.content, max_chars=max_chars, min_chars=min_chars)
    out: list[dict] = []
    for idx, chunk in enumerate(chunks):
        chunk_id = f"{doc.source}:{doc.doc_id}-{idx:04d}"
        out.append({
            "id": chunk_id,
            "content": chunk,
            "metadata": {
                "source":      doc.source,
                "connector":   doc.source,
                "title":       doc.title,
                "url":         doc.url,
                "document_id": chunk_id,
                "parent_id":   doc.doc_id,
                "chunk_idx":   idx,
                **doc.metadata,
            },
        })
    return out
