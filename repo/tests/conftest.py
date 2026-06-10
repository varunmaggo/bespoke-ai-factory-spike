"""
tests/conftest.py — shared pytest fixtures.
All external services (OpenSearch, Neo4j, Anthropic, AWS) are mocked
so unit tests run without any infrastructure.
"""
import sys
import unittest.mock as m
import pytest

# ── Stub all network-dependent packages ──────────────────────────────────────
_STUBS = [
    "anthropic",
    "boto3", "botocore", "botocore.credentials",
    "neo4j", "neo4j.time",
    "opensearchpy", "opensearchpy.helpers",
    "requests_aws4auth",
    "sentence_transformers",
    "deepeval", "deepeval.metrics", "deepeval.test_case",
    "fastapi", "fastapi.responses",
    "uvicorn",
    "pydantic",
    "httpx",
    "opentelemetry",
    "opentelemetry.sdk",
    "opentelemetry.sdk.trace",
    "opentelemetry.sdk.resources",
    "opentelemetry.sdk.trace.export",
    "opentelemetry.trace",
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    "opentelemetry.instrumentation.fastapi",
]

for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = m.MagicMock()

# tiktoken gets a functional stub (≈1 token per whitespace-separated word) so the
# normaliser's truncation logic stays testable without the real dependency.
try:
    import tiktoken  # noqa: F401
except ImportError:
    _fake_tiktoken = m.MagicMock()
    _fake_tiktoken.get_encoding.return_value.encode.side_effect = lambda s: str(s).split()
    sys.modules["tiktoken"] = _fake_tiktoken

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_chunks():
    return [
        {"document_id": "DOC-001", "content": "Q2 APAC revenue forecast is AUD 4.2M.", "score": 0.92, "source": "finance/q2.pdf", "metadata": {"department": "finance"}},
        {"document_id": "DOC-002", "content": "AWS Transform enables agentic code modernisation at scale.", "score": 0.85, "source": "tech/aws.pdf", "metadata": {"department": "tech"}},
        {"document_id": "DOC-003", "content": "Neo4j knowledge graph stores entity relationships.", "score": 0.78, "source": "tech/graph.pdf", "metadata": {"department": "tech"}},
    ]

@pytest.fixture
def sample_dense_hits():
    return [
        {"_source": {"document_id": f"DENSE-{i}", "content": f"Dense result {i}", "metadata": {}, "source": "dense"}}
        for i in range(5)
    ]

@pytest.fixture
def sample_bm25_hits():
    return [
        {"_source": {"document_id": f"BM25-{i}", "content": f"BM25 result {i}", "metadata": {}, "source": "bm25"}}
        for i in range(5)
    ]

@pytest.fixture
def rag_test_case():
    return {
        "question":        "What is our Q2 revenue forecast?",
        "answer":          "The Q2 APAC revenue forecast is AUD 4.2M based on confirmed pipeline.",
        "context":         ["Q2 APAC revenue forecast is AUD 4,200,000. Pipeline confirmed June 2024."],
        "expected_output": "The Q2 revenue forecast is AUD 4.2M.",
    }
