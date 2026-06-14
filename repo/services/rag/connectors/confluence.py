"""
services/rag/connectors/confluence.py — Atlassian Confluence connector.

Pulls pages from a Confluence space via the REST API
(``/wiki/rest/api/content?expand=body.storage``) using an email + API token,
converts the storage-format XHTML body to plain text, and yields normalised
``SourceDocument``s.

Offline fallback: when ``CONFLUENCE_BASE_URL`` / ``CONFLUENCE_API_TOKEN`` are
not set, returns a small bundle of sample pages so the pipeline is demoable
without a live Confluence instance.
"""
from __future__ import annotations

import logging
import os

from .base import Connector, SourceDocument, html_to_text

logger = logging.getLogger(__name__)


# Sample pages used when no credentials are configured (offline demo).
_SAMPLE = [
    {
        "id": "100001",
        "title": "Engineering Onboarding",
        "url": "https://example.atlassian.net/wiki/spaces/ENG/pages/100001",
        "html": "<h1>Engineering Onboarding</h1><p>New engineers should request "
                "access to the <strong>AI Factory</strong> repo and run "
                "<code>docker compose up</code> locally.</p>"
                "<p>Escalate access issues to the platform team.</p>",
    },
    {
        "id": "100002",
        "title": "Incident Response Runbook",
        "url": "https://example.atlassian.net/wiki/spaces/ENG/pages/100002",
        "html": "<h1>Incident Response</h1><p>Sev-1 incidents page the on-call "
                "engineer within 5 minutes.</p><ul><li>Open a war room</li>"
                "<li>Post status updates every 30 minutes</li></ul>",
    },
]


class ConfluenceConnector(Connector):
    """Ingest Confluence pages into the agentic RAG index."""

    name = "confluence"

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        space: str | None = None,
        limit: int = 50,
        client=None,
    ) -> None:
        self.base_url = (base_url or os.getenv("CONFLUENCE_BASE_URL", "")).rstrip("/")
        self.email = email or os.getenv("CONFLUENCE_EMAIL", "")
        self.api_token = api_token or os.getenv("CONFLUENCE_API_TOKEN", "")
        self.space = space or os.getenv("CONFLUENCE_SPACE", "")
        self.limit = int(limit)
        self._client = client

    def is_live(self) -> bool:
        return bool(self.base_url and self.api_token)

    def fetch(self) -> list[SourceDocument]:
        if not self.is_live():
            logger.info("Confluence: no credentials — using %d sample pages", len(_SAMPLE))
            return self._parse_results(_SAMPLE)
        payload = self._get_pages()
        results = payload.get("results", [])
        logger.info("Confluence: fetched %d pages from %s", len(results), self.base_url)
        return self._parse_results(results)

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _get_pages(self) -> dict:
        import httpx

        params = {"type": "page", "expand": "body.storage", "limit": self.limit}
        if self.space:
            params["spaceKey"] = self.space
        client = self._client or httpx.Client(timeout=30, auth=(self.email, self.api_token))
        try:
            resp = client.get(f"{self.base_url}/wiki/rest/api/content", params=params)
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._client is None:
                client.close()

    # ── Parsing (pure, unit-tested) ────────────────────────────────────────────

    def _parse_results(self, results: list[dict]) -> list[SourceDocument]:
        """Normalise Confluence API page objects (or sample dicts) to documents."""
        docs: list[SourceDocument] = []
        for page in results:
            page_id = str(page.get("id", ""))
            title = page.get("title", "Untitled")
            # Live API: body.storage.value; sample fixtures: flat "html" key.
            body = (
                page.get("body", {}).get("storage", {}).get("value")
                or page.get("html", "")
            )
            url = page.get("url") or self._page_url(page)
            text = html_to_text(body)
            if not text:
                continue
            docs.append(SourceDocument(
                doc_id=page_id,
                title=title,
                content=f"{title}\n\n{text}" if title not in text else text,
                source=self.name,
                url=url,
                metadata={"space": self.space or page.get("space", {}).get("key", "")},
            ))
        return docs

    def _page_url(self, page: dict) -> str:
        webui = page.get("_links", {}).get("webui", "")
        return f"{self.base_url}/wiki{webui}" if webui and self.base_url else ""
