"""
evals/deepeval/test_rag_quality.py — Pytest-based CI evaluation suite.

Skipped by default (the `deepeval` marker is deselected in pytest.ini).
Run with:
    pytest evals/deepeval/test_rag_quality.py -v -m deepeval
"""
import json
import pathlib
import pytest

pytest.importorskip("deepeval", reason="deepeval not installed — runs in the eval-gate CI job")

import httpx  # noqa: E402

from .rag_evaluator import RAGEvaluator  # noqa: E402

pytestmark = pytest.mark.deepeval

RAG_SERVICE_URL = "http://localhost:8001"
GOLDEN_DATASET  = pathlib.Path(__file__).parent / "golden_dataset.json"


@pytest.fixture(scope="module")
def evaluator() -> RAGEvaluator:
    # Constructed lazily: RAGEvaluator() builds DeepEval metric clients that
    # require an LLM API key, which must not happen at collection time when
    # the deepeval marker is deselected (the pytest.ini default).
    return RAGEvaluator()


def load_golden_dataset() -> list[dict]:
    if GOLDEN_DATASET.exists():
        data = json.loads(GOLDEN_DATASET.read_text())
        return [tc for tc in data["test_cases"] if tc.get("status", "active") == "active"]
    # Minimal fallback for CI when dataset file is missing
    return [
        {
            "question": "What is the Q2 revenue forecast?",
            "answer": "The Q2 forecast is AUD 4.2M based on current pipeline.",
            "context": ["Q2 APAC forecast: AUD 4,200,000. Pipeline confirmed as of 2024-06-01."],
            "expected_output": "The Q2 revenue forecast is AUD 4.2M.",
        }
    ]


@pytest.mark.parametrize("test_case", load_golden_dataset())
def test_rag_quality(evaluator: RAGEvaluator, test_case: dict):
    """Each golden dataset case must pass all DeepEval metric thresholds."""
    report = evaluator.run_evaluation(
        question=test_case["question"],
        answer=test_case["answer"],
        context=test_case["context"] if isinstance(test_case["context"], list) else [test_case["context"]],
        expected_output=test_case.get("expected_output"),
    )
    assert report.passed, (
        f"Eval failed for '{test_case['question'][:60]}...': "
        + "; ".join(report.failures)
    )


@pytest.mark.integration
def test_live_query_eval(evaluator: RAGEvaluator):
    """Integration: hit the live RAG service and evaluate the response."""
    question = "What are our top Q3 priorities?"
    resp = httpx.post(f"{RAG_SERVICE_URL}/query", json={"query": question}, timeout=30)
    assert resp.status_code == 200, f"RAG service returned {resp.status_code}"
    data = resp.json()

    report = evaluator.run_evaluation(
        question=question,
        answer=data["answer"],
        context=[s.get("content", "") for s in data.get("sources", [])],
    )
    assert report.overall_score >= 0.70, (
        f"Live query score too low: {report.overall_score:.3f}. Failures: {report.failures}"
    )
