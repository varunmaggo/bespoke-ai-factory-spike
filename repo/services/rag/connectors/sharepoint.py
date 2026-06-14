"""
services/rag/connectors/sharepoint.py — Microsoft SharePoint connector.

Pulls site pages via the Microsoft Graph API
(``/sites/{site-id}/pages``) using an Azure AD app registration
(client-credentials flow), normalises each page's title + text content, and
yields ``SourceDocument``s.

Offline fallback: when the Azure AD / Graph credentials are not set, returns a
small bundle of sample pages so the pipeline is demoable without a live tenant.
"""
from __future__ import annotations

import logging
import os

from .base import Connector, SourceDocument, html_to_text

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_LOGIN = "https://login.microsoftonline.com"


# Sample pages used when no credentials are configured (offline demo).
_SAMPLE = [
    {
        "id": "page-001",
        "title": "Travel & Expense Policy",
        "webUrl": "https://contoso.sharepoint.com/sites/HR/SitePages/Travel.aspx",
        "html": "<h1>Travel &amp; Expense Policy</h1><p>Economy fares only for "
                "flights under 6 hours. Submit receipts within 30 days via the "
                "Expenses portal.</p>",
    },
    {
        "id": "page-002",
        "title": "Procurement Approval Matrix",
        "webUrl": "https://contoso.sharepoint.com/sites/Finance/SitePages/Procurement.aspx",
        "html": "<h1>Procurement Approvals</h1><p>Purchases over $10,000 require "
                "two approvers. Software contracts also require security review.</p>",
    },
]


class SharePointConnector(Connector):
    """Ingest SharePoint site pages into the agentic RAG index."""

    name = "sharepoint"

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        site_id: str | None = None,
        limit: int = 50,
        client=None,
        token: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id or os.getenv("SHAREPOINT_TENANT_ID", "")
        self.client_id = client_id or os.getenv("SHAREPOINT_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("SHAREPOINT_CLIENT_SECRET", "")
        self.site_id = site_id or os.getenv("SHAREPOINT_SITE_ID", "")
        self.limit = int(limit)
        self._client = client
        self._token = token

    def is_live(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret and self.site_id)

    def fetch(self) -> list[SourceDocument]:
        if not self.is_live():
            logger.info("SharePoint: no credentials — using %d sample pages", len(_SAMPLE))
            return self._parse_pages(_SAMPLE)
        payload = self._get_pages()
        pages = payload.get("value", [])
        logger.info("SharePoint: fetched %d pages from site %s", len(pages), self.site_id)
        return self._parse_pages(pages)

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _acquire_token(self) -> str:
        if self._token:
            return self._token
        import httpx

        resp = httpx.post(
            f"{_LOGIN}/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _get_pages(self) -> dict:
        import httpx

        token = self._acquire_token()
        client = self._client or httpx.Client(timeout=30)
        try:
            resp = client.get(
                f"{GRAPH_BASE}/sites/{self.site_id}/pages",
                params={"$top": self.limit},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._client is None:
                client.close()

    # ── Parsing (pure, unit-tested) ────────────────────────────────────────────

    def _parse_pages(self, pages: list[dict]) -> list[SourceDocument]:
        """Normalise Graph page objects (or sample dicts) to documents."""
        docs: list[SourceDocument] = []
        for page in pages:
            page_id = str(page.get("id", ""))
            title = page.get("title") or page.get("name") or "Untitled"
            # Graph exposes body text via title/description; richer page content
            # (canvasLayout web parts) is an optional follow-up. Sample fixtures
            # carry an "html" key.
            raw = page.get("html") or page.get("description", "")
            text = html_to_text(raw)
            body = f"{title}\n\n{text}".strip() if text else title
            docs.append(SourceDocument(
                doc_id=page_id,
                title=title,
                content=body,
                source=self.name,
                url=page.get("webUrl", ""),
                metadata={"site_id": self.site_id},
            ))
        return docs
