"""
scripts/ingest_sources.py — Connect an internal system and ingest it into RAG.

Triggers the RAG service's /ingest endpoint for a named connector. Connectors
fall back to bundled sample documents when no credentials are configured, so
this runs offline for the demo.

Usage:
    python scripts/ingest_sources.py --source confluence
    python scripts/ingest_sources.py --source sharepoint --option site_id=abc123
    python scripts/ingest_sources.py --list
"""
from __future__ import annotations

import argparse
import logging
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_RAG_URL = "http://localhost:8001"


def _parse_options(pairs: list[str]) -> dict:
    """Turn ['k=v', ...] CLI options into a dict."""
    options: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            logger.error("Invalid --option '%s' (expected key=value)", pair)
            sys.exit(2)
        key, value = pair.split("=", 1)
        options[key.strip()] = value.strip()
    return options


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest an internal source into the RAG index")
    parser.add_argument("--source", help="Connector name, e.g. confluence | sharepoint")
    parser.add_argument("--option", action="append", default=[],
                        metavar="KEY=VALUE", help="Connector option (repeatable)")
    parser.add_argument("--rag-url", default=DEFAULT_RAG_URL)
    parser.add_argument("--list", action="store_true", help="List available sources and exit")
    args = parser.parse_args()

    try:
        if args.list:
            resp = httpx.get(f"{args.rag_url}/sources", timeout=30)
            resp.raise_for_status()
            logger.info("Available sources: %s", ", ".join(resp.json()["sources"]))
            return

        if not args.source:
            parser.error("--source is required (or use --list)")

        payload = {"source": args.source, "options": _parse_options(args.option)}
        logger.info("Ingesting from '%s' → %s", args.source, args.rag_url)
        resp = httpx.post(f"{args.rag_url}/ingest", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        mode = "live" if result["live"] else "sample (offline fallback)"
        logger.info(
            "Ingested %d documents → %d chunks from '%s' [%s] ✓",
            result["documents"], result["chunks"], result["source"], mode,
        )
    except httpx.HTTPStatusError as e:
        logger.error("Ingest failed (%s): %s", e.response.status_code, e.response.text[:300])
        sys.exit(1)
    except httpx.RequestError as e:
        logger.error("Connection error: %s — is the RAG service running?", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
