"""
services/rag/connectors — pluggable connectors that ingest documents from
internal systems (Confluence, SharePoint, …) into the agentic RAG index.
"""
from .base import Connector, SourceDocument, chunk_document, chunk_text, html_to_text
from .registry import available_sources, get_connector

__all__ = [
    "Connector",
    "SourceDocument",
    "chunk_document",
    "chunk_text",
    "html_to_text",
    "available_sources",
    "get_connector",
]
