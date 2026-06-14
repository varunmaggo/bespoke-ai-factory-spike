"""
services/rag/connectors/registry.py — Connector registry.

Maps a source name (e.g. ``"confluence"``) to its connector class so the
``/ingest`` API and the CLI can instantiate connectors by name.
"""
from __future__ import annotations

from .base import Connector
from .confluence import ConfluenceConnector
from .sharepoint import SharePointConnector

_CONNECTORS: dict[str, type[Connector]] = {
    ConfluenceConnector.name: ConfluenceConnector,
    SharePointConnector.name: SharePointConnector,
}


def available_sources() -> list[str]:
    """Return the sorted list of registered source names."""
    return sorted(_CONNECTORS)


def get_connector(source: str, **options) -> Connector:
    """Instantiate the connector for ``source``, forwarding ``options`` to it."""
    try:
        connector_cls = _CONNECTORS[source]
    except KeyError:
        raise ValueError(
            f"Unknown source '{source}'. Available: {', '.join(available_sources())}"
        ) from None
    return connector_cls(**options)
