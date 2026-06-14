"""
tests/unit/test_connectors.py — Unit tests for the RAG source connectors.
No network required: HTTP packages are stubbed via conftest.py and the
credential-less code paths use bundled sample data.
"""
import pytest

from services.rag.connectors import (
    available_sources,
    chunk_document,
    chunk_text,
    get_connector,
    html_to_text,
)
from services.rag.connectors.base import SourceDocument
from services.rag.connectors.confluence import ConfluenceConnector
from services.rag.connectors.sharepoint import SharePointConnector


# ── html_to_text ─────────────────────────────────────────────────────────────

class TestHtmlToText:
    def test_strips_tags(self):
        assert html_to_text("<p>Hello <strong>world</strong></p>") == "Hello world"

    def test_decodes_entities(self):
        assert html_to_text("<p>Travel &amp; Expense</p>") == "Travel & Expense"

    def test_block_tags_become_newlines(self):
        out = html_to_text("<p>one</p><p>two</p>")
        assert out.split("\n")[0] == "one"
        assert "two" in out

    def test_br_becomes_newline(self):
        assert "a\nb" in html_to_text("a<br/>b")

    def test_drops_confluence_macros(self):
        out = html_to_text('<ac:structured-macro ac:name="info"><p>note</p></ac:structured-macro>')
        assert out == "note"

    def test_empty_input(self):
        assert html_to_text("") == ""
        assert html_to_text(None) == ""

    def test_collapses_blank_lines(self):
        assert "\n\n\n" not in html_to_text("<p>a</p><br/><br/><br/><p>b</p>")


# ── chunking ─────────────────────────────────────────────────────────────────

class TestChunking:
    def test_splits_on_paragraphs(self):
        text = "first paragraph of content\n\nsecond paragraph of content"
        assert chunk_text(text) == ["first paragraph of content", "second paragraph of content"]

    def test_drops_tiny_chunks(self):
        assert chunk_text("hi\n\n" + "x" * 50, min_chars=20) == ["x" * 50]

    def test_splits_oversized_block_by_lines(self):
        block = "\n".join(["line " + str(i) * 100 for i in range(5)])
        chunks = chunk_text(block, max_chars=200)
        assert len(chunks) > 1
        assert all(len(c) <= 200 for c in chunks)

    def test_chunk_document_shape_matches_bulk_index(self):
        doc = SourceDocument(
            doc_id="42", title="Title",
            content="first body paragraph here\n\nsecond body paragraph here",
            source="confluence", url="http://x", metadata={"space": "ENG"},
        )
        chunks = chunk_document(doc)
        assert len(chunks) == 2
        first = chunks[0]
        assert set(first) == {"id", "content", "metadata"}     # bulk_index contract
        assert first["id"] == "confluence:42-0000"
        assert first["metadata"]["source"] == "confluence"
        assert first["metadata"]["title"] == "Title"
        assert first["metadata"]["space"] == "ENG"             # custom metadata preserved
        assert first["metadata"]["document_id"] == "confluence:42-0000"


# ── registry ─────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_lists_both_connectors(self):
        assert available_sources() == ["confluence", "sharepoint"]

    def test_get_connector_returns_instance(self):
        assert isinstance(get_connector("confluence"), ConfluenceConnector)
        assert isinstance(get_connector("sharepoint"), SharePointConnector)

    def test_unknown_source_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown source"):
            get_connector("notion")

    def test_options_forwarded_to_connector(self):
        c = get_connector("confluence", space="ENG", limit=10)
        assert c.space == "ENG"
        assert c.limit == 10


# ── ConfluenceConnector ──────────────────────────────────────────────────────

class TestConfluenceConnector:
    def test_not_live_without_credentials(self, monkeypatch):
        monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        assert ConfluenceConnector().is_live() is False

    def test_live_with_credentials(self):
        c = ConfluenceConnector(base_url="https://x.atlassian.net", api_token="tok")
        assert c.is_live() is True

    def test_fetch_falls_back_to_sample(self, monkeypatch):
        monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        docs = ConfluenceConnector().fetch()
        assert docs and all(isinstance(d, SourceDocument) for d in docs)
        assert all(d.source == "confluence" for d in docs)
        assert all(d.content for d in docs)

    def test_parse_results_extracts_text_from_storage_body(self):
        api_payload = [{
            "id": "555",
            "title": "Spec",
            "body": {"storage": {"value": "<p>Hybrid <strong>RAG</strong> design.</p>"}},
            "_links": {"webui": "/spaces/ENG/pages/555"},
        }]
        c = ConfluenceConnector(base_url="https://x.atlassian.net", api_token="t")
        docs = c._parse_results(api_payload)
        assert len(docs) == 1
        assert docs[0].doc_id == "555"
        assert "Hybrid RAG design." in docs[0].content
        assert docs[0].url.endswith("/spaces/ENG/pages/555")

    def test_parse_results_skips_empty_body(self):
        c = ConfluenceConnector(base_url="https://x", api_token="t")
        assert c._parse_results([{"id": "1", "title": "T", "html": ""}]) == []


# ── SharePointConnector ──────────────────────────────────────────────────────

class TestSharePointConnector:
    def test_not_live_without_credentials(self, monkeypatch):
        for var in ("SHAREPOINT_TENANT_ID", "SHAREPOINT_CLIENT_ID",
                    "SHAREPOINT_CLIENT_SECRET", "SHAREPOINT_SITE_ID"):
            monkeypatch.delenv(var, raising=False)
        assert SharePointConnector().is_live() is False

    def test_live_requires_all_four_credentials(self):
        c = SharePointConnector(tenant_id="t", client_id="c",
                                client_secret="s", site_id="site")
        assert c.is_live() is True
        partial = SharePointConnector(tenant_id="t", client_id="c", client_secret="s")
        assert partial.is_live() is False

    def test_fetch_falls_back_to_sample(self, monkeypatch):
        for var in ("SHAREPOINT_TENANT_ID", "SHAREPOINT_CLIENT_ID",
                    "SHAREPOINT_CLIENT_SECRET", "SHAREPOINT_SITE_ID"):
            monkeypatch.delenv(var, raising=False)
        docs = SharePointConnector().fetch()
        assert docs and all(d.source == "sharepoint" for d in docs)

    def test_parse_pages_normalises_graph_objects(self):
        graph_payload = [{
            "id": "p1",
            "title": "Policy",
            "webUrl": "https://contoso.sharepoint.com/p1",
            "description": "<p>Approvals over $10k need two signers.</p>",
        }]
        docs = SharePointConnector(site_id="s")._parse_pages(graph_payload)
        assert len(docs) == 1
        assert docs[0].title == "Policy"
        assert "two signers" in docs[0].content
        assert docs[0].url == "https://contoso.sharepoint.com/p1"
