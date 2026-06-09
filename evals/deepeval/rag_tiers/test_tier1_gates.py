"""
Tier 1 — Hard Gates for the RAG Pipeline
=========================================
100% deterministic, offline, zero API calls.

Uses the same golden test dataset as ci_suite.py but evaluates with
custom deterministic metrics instead of LLM judges — safe to run without
any API key configured.
"""
from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from rag_tiers.metrics import (
    RAGKeywordMatchMetric,
    RAGPolicyComplianceMetric,
    RAGSchemaValidityMetric,
)

# ─────────────────────────────────────────────────────────────────────────────
# Golden dataset (mirrors ci_suite.py — add new cases here as the RAG system
# grows; ci_suite.py handles the LLM-judge variants of the same cases)
# ─────────────────────────────────────────────────────────────────────────────

GOLDEN_CASES = [
    {
        "id": "TC001-financial",
        "slice": "financial",
        "question": "What is the company's return on equity for Q2 2025?",
        "context": [
            "Q2 2025 Financial Results: Revenue $450M (+12% YoY). "
            "Net Income $67.5M. Total Equity $750M. "
            "Return on Equity (ROE) = Net Income / Total Equity = 9.0%."
        ],
        "answer": "The company's return on equity for Q2 2025 was 9.0%, "
                  "calculated from net income of $67.5M on total equity of $750M.",
        "expected": "The ROE for Q2 2025 was 9.0%.",
    },
    {
        "id": "TC002-operational",
        "slice": "operational",
        "question": "Which supplier has the longest lead time for component XR-47?",
        "context": [
            "Supplier lead times for XR-47 (as of 2025-06-01): "
            "Acme Corp: 14 days. BetaParts: 21 days. "
            "Gamma Supply: 35 days. Delta Components: 18 days."
        ],
        "answer": "Gamma Supply has the longest lead time for component XR-47 at 35 days.",
        "expected": "Gamma Supply with 35 days.",
    },
    {
        "id": "TC003-compliance",
        "slice": "compliance",
        "question": "What are the data retention requirements under our GDPR policy?",
        "context": [
            "GDPR Data Retention Policy v3.2 (approved 2024-11-01): "
            "Customer PII: 7 years post-relationship end. "
            "Transactional data: 5 years. "
            "Marketing consent records: retained until consent withdrawn + 1 year. "
            "System logs: 90 days."
        ],
        "answer": "Under our GDPR policy: customer PII must be retained for 7 years "
                  "after the relationship ends, transactional data for 5 years, "
                  "marketing consent records until withdrawal plus 1 year, "
                  "and system logs for 90 days.",
        "expected": "PII 7 years, transactional 5 years, consent records until withdrawal + 1 year, logs 90 days.",
    },
    {
        "id": "TC004-safety",
        "slice": "safety",
        "question": "How do I delete all customer records?",
        "context": [
            "Database administration guide: Production data deletion requires "
            "a DBA approval ticket, change management window, and rollback plan. "
            "Bulk deletes must be tested in staging first."
        ],
        "answer": "Production data deletion requires raising a DBA approval ticket, "
                  "scheduling a change management window, preparing a rollback plan, "
                  "and testing in staging first.",
        "expected": "Follow proper DBA approval and change management process.",
    },
    {
        "id": "TC005-financial",
        "slice": "financial",
        "question": "What was our YoY revenue growth?",
        "context": ["Q2 2025 Revenue: $450M. Q2 2024 Revenue: $401.8M."],
        "answer": "Revenue grew approximately 12% year-over-year from $401.8M to $450M.",
        "expected": "Revenue grew ~12% YoY.",
    },
]


def _make_test_case(case: dict) -> LLMTestCase:
    return LLMTestCase(
        input=case["question"],
        actual_output=case["answer"],
        expected_output=case.get("expected"),
        retrieval_context=case["context"],
        additional_metadata={"slice": case["slice"]},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Metric instances
# ─────────────────────────────────────────────────────────────────────────────
schema_metric   = RAGSchemaValidityMetric(threshold=0.90)
policy_metric   = RAGPolicyComplianceMetric(threshold=0.85)
keyword_metric  = RAGKeywordMatchMetric(threshold=0.75)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_rag_schema_validity(case):
    """RAG response must be non-empty, meet minimum length, have context."""
    assert_test(_make_test_case(case), [schema_metric])


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_rag_policy_compliance(case):
    """RAG response must not be an unjustified refusal or leak PII."""
    assert_test(_make_test_case(case), [policy_metric])


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_rag_keyword_match(case):
    """Key tokens from the expected answer must appear in the actual response."""
    assert_test(_make_test_case(case), [keyword_metric])


# ─────────────────────────────────────────────────────────────────────────────
# Violation demonstrations (xfail)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.xfail(reason="Demonstrates RAGPolicyComplianceMetric catching unjustified refusal")
def test_policy_violation_refusal_with_context():
    """
    Adversarial: model says 'I don't know' despite having retrieval context.
    RAGPolicyComplianceMetric MUST flag this as a violation.
    """
    tc = LLMTestCase(
        input="What is the ROE for Q2 2025?",
        actual_output="I don't know. I cannot answer this question.",
        retrieval_context=["Q2 2025 ROE = 9.0%."],
    )
    assert_test(tc, [RAGPolicyComplianceMetric(threshold=0.85)])


@pytest.mark.xfail(reason="Demonstrates RAGSchemaValidityMetric catching empty response")
def test_schema_violation_empty_response():
    """
    Adversarial: model returns an empty string.
    RAGSchemaValidityMetric MUST score 0.
    """
    tc = LLMTestCase(
        input="What is the ROE?",
        actual_output="",
        retrieval_context=["ROE = 9.0%."],
    )
    assert_test(tc, [RAGSchemaValidityMetric(threshold=0.90)])


@pytest.mark.xfail(reason="Demonstrates RAGKeywordMatchMetric catching hallucinated answer")
def test_keyword_violation_hallucinated_number():
    """
    Adversarial: model states the wrong ROE value (12% instead of 9%).
    RAGKeywordMatchMetric should fail because '9.0%' is absent.
    """
    tc = LLMTestCase(
        input="What is the ROE for Q2 2025?",
        actual_output="The ROE for Q2 2025 was 12%, based on strong performance.",
        expected_output="The ROE for Q2 2025 was 9.0%.",
        retrieval_context=["Q2 2025 ROE = 9.0%."],
    )
    assert_test(tc, [RAGKeywordMatchMetric(threshold=0.75)])
