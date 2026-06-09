"""
Tier 1 — Hard Gate Tests
========================
Deterministic, offline, zero API calls. Runs on every PR.

Three sub-suites:
  1. Happy-path — stub orchestrator produces correct decisions → all pass.
  2. Regression  — known golden Q&A; ExactMatchMetric verifies calibration.
  3. Violations  — hardcoded adversarial outputs demonstrating the metrics
                   catch policy breaches (marked xfail so CI stays green
                   while the violation is visible in the report).
"""
from __future__ import annotations

import json
import sys
import os
import pytest

# Allow imports from the lending_demo package when running pytest from any cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from lending_demo.loan_triage import (
    Applicant,
    LoanApplication,
    run_triage_system,
)
from lending_demo.metrics import (
    ExactMatchMetric,
    PolicyComplianceMetric,
    SchemaValidityMetric,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_application(
    app_id: str,
    credit_score: int,
    kyc_verified: bool,
    risk_band: str = "medium",
    annual_income: float = 80_000,
    loan_amount: float = 20_000,
) -> LoanApplication:
    return LoanApplication(
        application_id=app_id,
        applicant=Applicant(
            applicant_id=f"APL-{app_id}",
            name="Test Applicant",
            credit_score=credit_score,
            annual_income=annual_income,
            risk_band=risk_band,
            kyc_verified=kyc_verified,
        ),
        loan_amount=loan_amount,
        loan_purpose="home improvement",
    )


def _run_to_test_case(
    application: LoanApplication,
    expected: dict | None = None,
) -> LLMTestCase:
    """Execute the pipeline and wrap the result in an LLMTestCase."""
    run = run_triage_system(application)
    return LLMTestCase(
        input=json.dumps(application.model_dump()),
        actual_output=json.dumps(run.decision.model_dump()),
        expected_output=json.dumps(expected) if expected else None,
        additional_metadata={
            "tool_outputs": run.tool_outputs,
            "risk_band": run.decision.risk_band,
            "slice": application.applicant.risk_band,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suite 1 — Happy-Path (should all PASS)
# ─────────────────────────────────────────────────────────────────────────────

HAPPY_PATH_CASES = [
    ("APP-001", 780, True, "low",    "approve_fast_track", "low"),
    ("APP-002", 720, True, "medium", "approve",            "medium"),
    ("APP-003", 590, True, "medium", "reject",             "high"),
    ("APP-004", 700, False,"medium", "human_review",       "medium"),
    ("APP-005", 710, True, "high",   "human_review",       "high"),
]


@pytest.mark.parametrize(
    "app_id,credit,kyc,band,exp_rec,exp_risk",
    HAPPY_PATH_CASES,
    ids=[c[0] for c in HAPPY_PATH_CASES],
)
def test_schema_validity(app_id, credit, kyc, band, exp_rec, exp_risk):
    """Every orchestrator output must conform to the required JSON schema."""
    tc = _run_to_test_case(_make_application(app_id, credit, kyc, band))
    assert_test(tc, [SchemaValidityMetric(threshold=0.90)])


@pytest.mark.parametrize(
    "app_id,credit,kyc,band,exp_rec,exp_risk",
    HAPPY_PATH_CASES,
    ids=[c[0] for c in HAPPY_PATH_CASES],
)
def test_policy_compliance(app_id, credit, kyc, band, exp_rec, exp_risk):
    """Every orchestrator output must satisfy hard business rules."""
    tc = _run_to_test_case(_make_application(app_id, credit, kyc, band))
    assert_test(tc, [PolicyComplianceMetric(threshold=0.85)])


# ─────────────────────────────────────────────────────────────────────────────
# Suite 2 — Calibration Regression (ExactMatch)
# ─────────────────────────────────────────────────────────────────────────────

REGRESSION_CASES = [
    {
        "id": "REG-001",
        "credit": 780, "kyc": True,  "band": "low",
        "expected": {"recommendation": "approve_fast_track", "risk_band": "low"},
    },
    {
        "id": "REG-002",
        "credit": 590, "kyc": True,  "band": "medium",
        "expected": {"recommendation": "reject", "risk_band": "high"},
    },
    {
        "id": "REG-003",
        "credit": 700, "kyc": False, "band": "low",
        "expected": {"recommendation": "human_review", "risk_band": "low"},
    },
]


@pytest.mark.parametrize("case", REGRESSION_CASES, ids=[c["id"] for c in REGRESSION_CASES])
def test_exact_match_regression(case):
    """Key decision fields must exactly match the calibration baseline."""
    app = _make_application(case["id"], case["credit"], case["kyc"], case["band"])
    tc = _run_to_test_case(app, expected=case["expected"])
    assert_test(tc, [ExactMatchMetric(threshold=0.90)])


# ─────────────────────────────────────────────────────────────────────────────
# Suite 3 — Violation Demonstrations (xfail — metrics SHOULD catch these)
# ─────────────────────────────────────────────────────────────────────────────
# These tests use hardcoded *wrong* agent outputs to prove the metrics fire.
# They are marked xfail so the CI suite stays green.

@pytest.mark.xfail(reason="Demonstrates PolicyComplianceMetric catching Rule 1 violation")
def test_policy_violation_low_credit_approved():
    """
    Adversarial scenario: credit score 580 but agent recommends 'approve'.
    PolicyComplianceMetric MUST score 0 and block this.
    """
    bad_output = json.dumps({
        "application_id": "ADVERSARIAL-001",
        "recommendation": "approve",          # ← policy violation
        "status": "complete",
        "risk_band": "medium",
        "reasons": ["Applicant has good income"],
    })
    tc = LLMTestCase(
        input="{}",
        actual_output=bad_output,
        additional_metadata={
            "tool_outputs": {
                "credit_agent": {"credit_score": 580, "passed": False},
                "kyc_agent":    {"verified": True},
            }
        },
    )
    assert_test(tc, [PolicyComplianceMetric(threshold=0.85)])


@pytest.mark.xfail(reason="Demonstrates PolicyComplianceMetric catching Rule 2 violation")
def test_policy_violation_unverified_kyc_approved():
    """
    Adversarial scenario: KYC unverified but agent recommends 'approve'.
    PolicyComplianceMetric MUST score 0 and block this.
    """
    bad_output = json.dumps({
        "application_id": "ADVERSARIAL-002",
        "recommendation": "approve",          # ← policy violation
        "status": "complete",
        "risk_band": "low",
        "reasons": ["Excellent credit score"],
    })
    tc = LLMTestCase(
        input="{}",
        actual_output=bad_output,
        additional_metadata={
            "tool_outputs": {
                "credit_agent": {"credit_score": 780, "passed": True},
                "kyc_agent":    {"verified": False},  # ← KYC not done
            }
        },
    )
    assert_test(tc, [PolicyComplianceMetric(threshold=0.85)])


@pytest.mark.xfail(reason="Demonstrates SchemaValidityMetric catching missing required fields")
def test_schema_violation_missing_fields():
    """
    Adversarial scenario: Decision Agent returns partial JSON.
    SchemaValidityMetric MUST score below threshold.
    """
    bad_output = json.dumps({
        "recommendation": "approve",
        # missing: application_id, status, risk_band, reasons
    })
    tc = LLMTestCase(input="{}", actual_output=bad_output)
    assert_test(tc, [SchemaValidityMetric(threshold=0.90)])
