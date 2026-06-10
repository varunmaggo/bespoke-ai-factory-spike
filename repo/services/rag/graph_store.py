"""
services/rag/graph_store.py — Neo4j knowledge graph for entity-relationship retrieval.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme")


class EnterpriseKnowledgeGraph:
    """Neo4j graph store for entity context enrichment."""

    def __init__(self) -> None:
        self.driver: Driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        self._ensure_constraints()

    def _ensure_constraints(self) -> None:
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT entity_id IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT doc_id IF NOT EXISTS "
                "FOR (d:Document) REQUIRE d.id IS UNIQUE"
            )

    def close(self) -> None:
        self.driver.close()

    # ── Read operations ────────────────────────────────────────────────────────

    def get_related_entities(
        self,
        entity_ids: list[str],
        max_hops: int = 2,
        limit: int = 20,
    ) -> list[dict]:
        """
        Multi-hop graph traversal: find entities related to the given entity IDs.

        Returns list of {id, name, type, description, source_doc, relationship_path}.
        """
        query = """
        MATCH (seed:Entity)-[:RELATED_TO*1..$hops]-(related:Entity)
        WHERE seed.id IN $entity_ids
          AND NOT related.id IN $entity_ids
        OPTIONAL MATCH (related)-[:MENTIONED_IN]->(doc:Document)
        WITH DISTINCT related, doc
        RETURN related.id         AS id,
               related.name       AS name,
               related.type       AS type,
               related.description AS description,
               doc.id             AS source_doc
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(
                query,
                entity_ids=entity_ids,
                hops=max_hops,
                limit=limit,
            )
            return [dict(record) for record in result]

    def get_entity_documents(self, entity_name: str) -> list[dict]:
        """Return documents that mention a named entity."""
        query = """
        MATCH (e:Entity {name: $name})-[:MENTIONED_IN]->(d:Document)
        RETURN d.id AS doc_id, d.title AS title, d.source AS source
        ORDER BY d.updated_at DESC
        LIMIT 10
        """
        with self.driver.session() as session:
            result = session.run(query, name=entity_name)
            return [dict(record) for record in result]

    def extract_entity_ids(self, chunks: list[dict]) -> list[str]:
        """
        Extract entity IDs from retrieved chunks by querying the graph
        for entities mentioned in those documents.
        """
        doc_ids = list({
            c.get("document_id") or c.get("metadata", {}).get("document_id")
            for c in chunks
            if c.get("document_id") or c.get("metadata", {})
        })
        if not doc_ids:
            return []

        query = """
        MATCH (e:Entity)-[:MENTIONED_IN]->(d:Document)
        WHERE d.id IN $doc_ids
        RETURN DISTINCT e.id AS id
        LIMIT 50
        """
        with self.driver.session() as session:
            result = session.run(query, doc_ids=doc_ids)
            return [record["id"] for record in result]

    # ── Write operations ───────────────────────────────────────────────────────

    def upsert_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        description: str = "",
    ) -> None:
        query = """
        MERGE (e:Entity {id: $id})
        SET e.name        = $name,
            e.type        = $type,
            e.description = $description
        """
        with self.driver.session() as session:
            session.run(query, id=entity_id, name=name, type=entity_type, description=description)

    def link_entity_to_document(self, entity_id: str, doc_id: str) -> None:
        query = """
        MATCH (e:Entity {id: $entity_id})
        MERGE (d:Document {id: $doc_id})
        MERGE (e)-[:MENTIONED_IN]->(d)
        """
        with self.driver.session() as session:
            session.run(query, entity_id=entity_id, doc_id=doc_id)

    def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str = "RELATED_TO",
        properties: Optional[dict] = None,
    ) -> None:
        props_str = ""
        if properties:
            props_str = " {" + ", ".join(f"{k}: ${k}" for k in properties) + "}"
        query = f"""
        MATCH (a:Entity {{id: $from_id}})
        MATCH (b:Entity {{id: $to_id}})
        MERGE (a)-[:{rel_type}{props_str}]->(b)
        """
        params = {"from_id": from_id, "to_id": to_id, **(properties or {})}
        with self.driver.session() as session:
            session.run(query, **params)
