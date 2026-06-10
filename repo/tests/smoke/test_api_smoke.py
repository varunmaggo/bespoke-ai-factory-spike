"""
tests/smoke/test_api_smoke.py — Smoke tests against live services.

Requires docker compose up -d to be running.
Run with:  pytest tests/smoke/ -v -m smoke

Environment overrides:
  SPRING_URL=http://localhost:8080  (default)
  RAG_URL=http://localhost:8001
  EVAL_URL=http://localhost:8002
"""
import os
import pytest
import httpx

SPRING_URL = os.getenv("SPRING_URL", "http://localhost:8080")
RAG_URL    = os.getenv("RAG_URL",    "http://localhost:8001")
EVAL_URL   = os.getenv("EVAL_URL",   "http://localhost:8002")
TIMEOUT    = 30


pytestmark = pytest.mark.smoke


# ── Health checks ─────────────────────────────────────────────────────────────

def test_rag_service_healthy():
    r = httpx.get(f"{RAG_URL}/health", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_eval_service_healthy():
    r = httpx.get(f"{EVAL_URL}/health", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_spring_service_healthy():
    r = httpx.get(f"{SPRING_URL}/actuator/health", timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") in ("UP", "ok")


# ── RAG Service ───────────────────────────────────────────────────────────────

def test_rag_retrieve_returns_chunks():
    r = httpx.post(
        f"{RAG_URL}/retrieve",
        json={"query": "revenue forecast", "top_k": 3},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    body = r.json()
    assert "chunks" in body
    assert isinstance(body["chunks"], list)


def test_rag_retrieve_respects_top_k():
    r = httpx.post(
        f"{RAG_URL}/retrieve",
        json={"query": "AWS Transform", "top_k": 2},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    assert len(r.json()["chunks"]) <= 2


def test_rag_query_returns_answer():
    r = httpx.post(
        f"{RAG_URL}/query",
        json={"query": "What is our Q2 revenue forecast?"},
        timeout=60,
    )
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert len(body["answer"]) > 10
    assert "hops" in body
    assert body["hops"] >= 1


def test_rag_query_includes_sources():
    r = httpx.post(
        f"{RAG_URL}/query",
        json={"query": "AWS Transform definitions"},
        timeout=60,
    )
    assert r.status_code == 200
    body = r.json()
    assert "sources" in body
    assert isinstance(body["sources"], list)


def test_rag_query_includes_transform_metadata():
    r = httpx.post(
        f"{RAG_URL}/query",
        json={"query": "enterprise data schema"},
        timeout=60,
    )
    assert r.status_code == 200
    body = r.json()
    # transform_metadata present (may be empty if atx not installed)
    assert "transform_metadata" in body


# ── Spring API ────────────────────────────────────────────────────────────────

def test_spring_query_returns_200():
    r = httpx.post(
        f"{SPRING_URL}/api/v1/query",
        json={"query": "What are the Q3 priorities?", "userId": "smoke-test"},
        timeout=60,
    )
    assert r.status_code == 200


def test_spring_response_has_eval_score():
    r = httpx.post(
        f"{SPRING_URL}/api/v1/query",
        json={"query": "Summarise the AI Factory architecture", "userId": "smoke-test"},
        timeout=60,
    )
    assert r.status_code == 200
    body = r.json()
    assert "answer"    in body
    assert "evalScore" in body
    assert 0.0 <= body["evalScore"] <= 1.0


def test_spring_eval_passed_field_present():
    r = httpx.post(
        f"{SPRING_URL}/api/v1/query",
        json={"query": "What is AWS Transform?", "userId": "smoke-test"},
        timeout=60,
    )
    assert r.status_code == 200
    body = r.json()
    assert "evalPassed" in body
    assert isinstance(body["evalPassed"], bool)


def test_spring_empty_query_returns_400():
    r = httpx.post(
        f"{SPRING_URL}/api/v1/query",
        json={"query": "", "userId": "smoke-test"},
        timeout=TIMEOUT,
    )
    assert r.status_code in (400, 422)


# ── Full pipeline: index → retrieve → answer ──────────────────────────────────

def test_index_then_retrieve_pipeline():
    """Index a unique document, then verify it's retrievable."""
    unique_content = "SMOKE_TEST_UNIQUE_TOKEN_XYZ: The bespoke factory uses AWS Transform for normalization."
    doc_id = "smoke-test-doc-001"

    # 1. Index
    idx = httpx.post(
        f"{RAG_URL}/index",
        json={"doc_id": doc_id, "content": unique_content,
              "metadata": {"source": "smoke-test", "department": "test"}},
        timeout=TIMEOUT,
    )
    assert idx.status_code == 200, f"Index failed: {idx.text}"

    # 2. Retrieve — the unique token should come back
    ret = httpx.post(
        f"{RAG_URL}/retrieve",
        json={"query": "SMOKE_TEST_UNIQUE_TOKEN_XYZ", "top_k": 5},
        timeout=TIMEOUT,
    )
    assert ret.status_code == 200
    doc_ids = [c.get("document_id") for c in ret.json()["chunks"]]
    assert doc_id in doc_ids, f"Indexed doc {doc_id!r} not found in: {doc_ids}"
