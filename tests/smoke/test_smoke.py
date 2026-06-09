"""
Smoke tests — run against staging after every deployment.
These are end-to-end HTTP tests, not unit tests.
"""
import pytest
import httpx
import os
import time

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")
API_KEY  = os.environ.get("SMOKE_API_KEY", "")

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"} if API_KEY else {}


@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=60.0)


def test_health(client):
    """Service must be healthy."""
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "UP"


def test_basic_query(client):
    """A simple factual query must return a non-empty answer."""
    r = client.post("/api/v1/query", json={
        "query": "What is this system?",
        "userId": "smoke-test",
    })
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert len(body["answer"]) > 10
    # Eval headers must be present
    assert "X-Eval-Score" in r.headers
    assert "X-Eval-Passed" in r.headers


def test_eval_score_present(client):
    """Response must include an eval score > 0."""
    r = client.post("/api/v1/query", json={
        "query": "Summarise the main features of this service.",
        "userId": "smoke-test",
    })
    assert r.status_code == 200
    score = float(r.headers.get("X-Eval-Score", "0"))
    assert score > 0.0, f"Eval score unexpectedly zero: {score}"


def test_query_latency(client):
    """p95 query latency must be < 30 seconds."""
    latencies = []
    for _ in range(3):
        start = time.monotonic()
        client.post("/api/v1/query", json={
            "query": "Hello, are you working?",
            "userId": "smoke-latency",
        })
        latencies.append(time.monotonic() - start)

    p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1]
    assert p95 < 30, f"p95 latency {p95:.1f}s exceeds 30s threshold"


def test_rag_service_reachable():
    """RAG service health endpoint must be reachable."""
    rag_url = os.environ.get("RAG_SERVICE_URL", "http://rag-service:8001")
    r = httpx.get(f"{rag_url}/health", timeout=10.0)
    assert r.status_code == 200


def test_eval_service_reachable():
    """Eval service health endpoint must be reachable."""
    eval_url = os.environ.get("EVAL_SERVICE_URL", "http://eval-service:8002")
    r = httpx.get(f"{eval_url}/health", timeout=10.0)
    assert r.status_code == 200
