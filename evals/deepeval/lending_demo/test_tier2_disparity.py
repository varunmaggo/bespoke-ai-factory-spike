"""
Tier 2 — Slice Disparity / Fairness Audit
==========================================
Runs on every PR alongside Tier 1.

Checks that the approval rate gap between risk-band slices (low / medium / high)
does not exceed an acceptable threshold.

Expected outcome with the stub orchestrator:
  • low    → 100% approval (fast-track eligible)
  • medium →  50% approval (some KYC failures → human_review)
  • high   →   0% approval (human_review only)
  Disparity = 1.00 - 0.00 = 1.00  →  EXCEEDS 0.40 threshold

This intentional large gap demonstrates two things:
  1. The disparity check correctly identifies business-driven differences.
  2. In a real system you would tune the threshold or segment further.

The test is therefore marked xfail to keep CI green while making the
disparity visible in the report.
"""
from __future__ import annotations

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deepeval.test_case import LLMTestCase

from lending_demo.loan_triage import Applicant, LoanApplication, run_triage_system
from lending_demo.metrics import calculate_slice_disparity


# ─────────────────────────────────────────────────────────────────────────────
# Dataset — balanced across risk bands
# ─────────────────────────────────────────────────────────────────────────────

SLICE_DATASET = [
    # (app_id, credit, kyc, band)
    ("SL-001", 780, True,  "low"),
    ("SL-002", 760, True,  "low"),
    ("SL-003", 720, True,  "medium"),
    ("SL-004", 700, False, "medium"),   # KYC fail → human_review
    ("SL-005", 660, True,  "high"),
    ("SL-006", 670, True,  "high"),
]


def _build_test_cases():
    cases = []
    for app_id, credit, kyc, band in SLICE_DATASET:
        app = LoanApplication(
            application_id=app_id,
            applicant=Applicant(
                applicant_id=f"APL-{app_id}",
                name="Test Applicant",
                credit_score=credit,
                annual_income=80_000,
                risk_band=band,
                kyc_verified=kyc,
            ),
            loan_amount=20_000,
            loan_purpose="personal",
        )
        run = run_triage_system(app)
        cases.append(
            LLMTestCase(
                input=json.dumps(app.model_dump()),
                actual_output=json.dumps(run.decision.model_dump()),
                additional_metadata={
                    "tool_outputs": run.tool_outputs,
                    "slice": band,
                },
            )
        )
    return cases


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_slice_disparity_report():
    """
    Print the approval-rate breakdown by risk band.
    Always passes — this is an informational report.
    """
    cases = _build_test_cases()
    result = calculate_slice_disparity(cases, max_disparity=1.0)  # permissive threshold

    print("\n── Tier 2 Slice Disparity Report ──────────────────────────────")
    for band, rate in sorted(result["rates"].items()):
        bar = "█" * int(rate * 20)
        print(f"  {band:8s}  {rate:.0%}  {bar}")
    print(f"\n  Disparity (max − min): {result['disparity']:.2%}")
    print(f"  Status: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
    if result["violation"]:
        print(f"  Note: {result['violation']}")
    print("────────────────────────────────────────────────────────────────")

    assert result["rates"], "No slices found — check metadata['slice'] is set"


@pytest.mark.xfail(
    reason=(
        "Stub orchestrator intentionally produces large low/high disparity "
        "(business rule: all high-risk → human_review, not approved). "
        "In production, tune max_disparity or adjust decision logic."
    )
)
def test_slice_disparity_within_threshold():
    """
    Approval-rate spread must not exceed 40% across risk bands.
    Expected to FAIL with the stub — demonstrates the check fires correctly.
    """
    cases = _build_test_cases()
    result = calculate_slice_disparity(cases, max_disparity=0.40)

    assert result["passed"], result["violation"]
