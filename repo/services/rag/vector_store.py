"""
services/rag/vector_store.py — Enterprise hybrid vector store using AWS OpenSearch Serverless.
Dense BGE embeddings + BM25 sparse, fused via Reciprocal Rank Fusion (RRF).
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWSV4SignerAuth

logger = logging.getLogger(__name__)

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
INDEX_NAME      = os.getenv("OPENSEARCH_INDEX", "enterprise-knowledge")
AWS_REGION      = os.getenv("AWS_REGION", "ap-southeast-2")


def _build_client() -> OpenSearch:
    """Create OpenSearch client with AWS SigV4 auth (Serverless) or basic auth (local)."""
    use_aws = os.getenv("OPENSEARCH_USE_AWS", "false").lower() == "true"
    if use_aws:
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, AWS_REGION, "aoss")
        return OpenSearch(
            hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False,
    )


class EnterpriseVectorStore:
    """Hybrid dense + sparse retrieval with RRF fusion."""

    RRF_K = 60  # standard RRF constant

    def __init__(self, embedding_model_name: str = "BAAI/bge-large-en-v1.5"):
        self.client = _build_client()
        self._ensure_index()
        self._load_embedder(embedding_model_name)

    def _load_embedder(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(model_name)
            logger.info("Loaded embedding model: %s", model_name)
        except ImportError:
            logger.warning("sentence-transformers not installed — embedding disabled")
            self.embedder = None

    def _ensure_index(self) -> None:
        if not self.client.indices.exists(index=INDEX_NAME):
            self.client.indices.create(
                index=INDEX_NAME,
                body={
                    "settings": {"index.knn": True},
                    "mappings": {
                        "properties": {
                            "content":   {"type": "text"},
                            "embedding": {"type": "knn_vector", "dimension": 1024,
                                          "method": {"name": "hnsw", "space_type": "cosinesimil",
                                                     "engine": "faiss"}},
                            "metadata":  {"type": "object"},
                            "document_id": {"type": "keyword"},
                            "source":    {"type": "keyword"},
                        }
                    },
                },
            )
            logger.info("Created index: %s", INDEX_NAME)

    def index_document(self, doc_id: str, content: str, metadata: dict | None = None) -> None:
        """Index a document chunk with dense vector embedding."""
        embedding = self._embed(content)
        body = {
            "document_id": doc_id,
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
            "source": (metadata or {}).get("source", "unknown"),
        }
        self.client.index(index=INDEX_NAME, id=doc_id, body=body)

    def bulk_index(self, docs: list[dict]) -> None:
        """Bulk index documents. Each doc: {id, content, metadata}."""
        actions = [
            {
                "_index": INDEX_NAME,
                "_id": d["id"],
                "_source": {
                    "document_id": d["id"],
                    "content": d["content"],
                    "embedding": self._embed(d["content"]),
                    "metadata": d.get("metadata", {}),
                    "source": d.get("metadata", {}).get("source", "unknown"),
                },
            }
            for d in docs
        ]
        success, errors = helpers.bulk(self.client, actions, raise_on_error=False)
        if errors:
            logger.warning("Bulk index errors: %s", errors[:3])
        logger.info("Indexed %d documents", success)

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
        dense_weight: float = 0.7,
    ) -> list[dict]:
        """
        Hybrid search: dense KNN + BM25 text, fused via Reciprocal Rank Fusion.

        Args:
            query:        Natural language search query.
            top_k:        Final number of results to return.
            filters:      Optional metadata filters e.g. {"department": "finance"}.
            dense_weight: RRF weight for dense results (1-dense_weight = BM25 weight).
        """
        embedding = self._embed(query)
        filter_clause = (
            {"filter": {"term": filters}} if filters else {}
        )

        # Dense KNN query
        dense_results = self.client.search(
            index=INDEX_NAME,
            body={
                "size": top_k * 2,
                "query": {
                    "knn": {"embedding": {"vector": embedding, "k": top_k * 2, **filter_clause}}
                },
            },
        )

        # BM25 text query
        bm25_query: dict = {"match": {"content": {"query": query}}}
        if filters:
            bm25_query = {"bool": {"must": bm25_query, "filter": {"term": filters}}}
        bm25_results = self.client.search(
            index=INDEX_NAME,
            body={"size": top_k * 2, "query": bm25_query},
        )

        return self._rrf_fusion(
            dense_results["hits"]["hits"],
            bm25_results["hits"]["hits"],
            top_k,
            dense_weight,
        )

    def _rrf_fusion(
        self,
        dense_hits: list,
        bm25_hits: list,
        top_k: int,
        dense_weight: float,
    ) -> list[dict]:
        scores: dict[str, float] = {}
        sources: dict[str, dict] = {}

        for rank, hit in enumerate(dense_hits):
            doc_id = hit["_source"]["document_id"]
            scores[doc_id] = scores.get(doc_id, 0) + dense_weight / (self.RRF_K + rank + 1)
            sources[doc_id] = hit["_source"]

        bm25_weight = 1.0 - dense_weight
        for rank, hit in enumerate(bm25_hits):
            doc_id = hit["_source"]["document_id"]
            scores[doc_id] = scores.get(doc_id, 0) + bm25_weight / (self.RRF_K + rank + 1)
            if doc_id not in sources:
                sources[doc_id] = hit["_source"]

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            {
                "content":     sources[doc_id]["content"],
                "score":       score,
                "document_id": doc_id,
                "metadata":    sources[doc_id].get("metadata", {}),
                "source":      sources[doc_id].get("source", "unknown"),
            }
            for doc_id, score in ranked
        ]

    def _embed(self, text: str) -> list[float]:
        if self.embedder is None:
            return [0.0] * 1024
        return self.embedder.encode(text, normalize_embeddings=True).tolist()
