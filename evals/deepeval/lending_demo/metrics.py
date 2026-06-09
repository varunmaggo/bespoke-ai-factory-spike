"""
Three-Tier Evaluation Metrics — Lending Demo
=============================================

Tier 1  (Hard Gates)         — PolicyComplianceMetric, SchemaValidityMetric,
                                ExactMatchMetric
Tier 2  (Fairness Auditing)  — calculate_slice_disparity()
Tier 3  (LLM Judges)         — skipped when no API key is present;
                                see ci_suite.py for GEval examples.

All Tier 1/2 metrics are 100% deterministic and run offline.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — Hard Gates
# ─────────────────────────────────────────────────────────────────────────────

class PolicyComplianceMetric(BaseMetric):
    """
    Re-audits the Decision Agent's output against hard business rules,
    using the raw specialist agent tool_outputs stored in metadata.

    Rules evaluated:
      1. Credit score < 650  →  must result in "reject".
      2. KYC unverified      →  must result in "reject" or "human_review".
    """

    threshold: float = 0.85

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self.score = 0.0
        self.success = False

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "PolicyComplianceMetric"

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            actual = json.loads(test_case.actual_output)
            tool_outputs: Dict[str, Any] = (
                test_case.additional_metadata or {}
            ).get("tool_outputs", {})
        except (json.JSONDecodeError, TypeError):
            self.score, self.success = 0.0, False
            return 0.0

        self.score = self._evaluate_rules(tool_outputs, actual)
        self.success = self.score >= self.threshold
        return self.score

    def is_successful(self) -> bool:
        return self.success

    def _evaluate_rules(
        self, tool_outputs: Dict[str, Any], decision: Dict[str, Any]
    ) -> float:
        recommendation = decision.get("recommendation", "")

        # Rule 1 — credit floor
        credit = tool_outputs.get("credit_agent", {})
        if credit.get("credit_score", 999) < 650 and recommendation != "reject":
            self.reason = (
                f"VIOLATION: credit_score={credit.get('credit_score')} < 650 "
                f"but recommendation='{recommendation}' (expected 'reject')"
            )
            return 0.0

        # Rule 2 — KYC gate
        kyc = tool_outputs.get("kyc_agent", {})
        if not kyc.get("verified", True) and recommendation not in (
            "reject", "human_review"
        ):
            self.reason = (
                f"VIOLATION: KYC unverified but recommendation='{recommendation}' "
                "(expected 'reject' or 'human_review')"
            )
            return 0.0

        self.reason = "All policy rules passed"
        return 1.0


class SchemaValidityMetric(BaseMetric):
    """
    Verifies that the Decision Agent emits valid JSON conforming to the
    expected response schema.

    Required fields: application_id, recommendation, status, risk_band, reasons
    Additional check: reasons must be a non-empty list of strings.
    """

    threshold: float = 0.90

    def __init__(self, threshold: float = 0.90) -> None:
        self.threshold = threshold
        self.score = 0.0
        self.success = False

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "SchemaValidityMetric"

    REQUIRED_FIELDS = ["application_id", "recommendation", "status", "risk_band", "reasons"]

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            actual = json.loads(test_case.actual_output)
        except (json.JSONDecodeError, TypeError):
            self.score, self.success = 0.0, False
            self.reason = "Output is not valid JSON"
            return 0.0

        present = sum(1 for f in self.REQUIRED_FIELDS if f in actual)
        reasons_ok = isinstance(actual.get("reasons"), list) and len(actual.get("reasons", [])) > 0
        recommendation_ok = actual.get("recommendation") in (
            "approve", "approve_fast_track", "reject", "human_review"
        )

        checks = present + int(reasons_ok) + int(recommendation_ok)
        total = len(self.REQUIRED_FIELDS) + 2
        self.score = checks / total
        self.success = self.score >= self.threshold

        if self.score < self.threshold:
            missing = [f for f in self.REQUIRED_FIELDS if f not in actual]
            self.reason = f"Schema issues — missing: {missing}, reasons_ok={reasons_ok}, recommendation_ok={recommendation_ok}"
        else:
            self.reason = "Schema valid"

        return self.score

    def is_successful(self) -> bool:
        return self.success


class ExactMatchMetric(BaseMetric):
    """
    Exact-match calibration: verifies that recommendation and risk_band in
    actual_output match the expected_output for regression test cases.
    """

    threshold: float = 0.90

    def __init__(self, threshold: float = 0.90) -> None:
        self.threshold = threshold
        self.score = 0.0
        self.success = False

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "ExactMatchMetric"

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            actual = json.loads(test_case.actual_output)
            expected = json.loads(test_case.expected_output)
        except (json.JSONDecodeError, TypeError):
            self.score, self.success = 0.0, False
            self.reason = "Could not parse JSON"
            return 0.0

        rec_match = actual.get("recommendation") == expected.get("recommendation")
        band_match = actual.get("risk_band") == expected.get("risk_band")
        self.score = float(rec_match and band_match)
        self.success = self.score >= self.threshold

        if not self.success:
            self.reason = (
                f"Mismatch — recommendation: {actual.get('recommendation')!r} "
                f"(expected {expected.get('recommendation')!r}), "
                f"risk_band: {actual.get('risk_band')!r} "
                f"(expected {expected.get('risk_band')!r})"
            )
        else:
            self.reason = "Exact match"

        return self.score

    def is_successful(self) -> bool:
        return self.success


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — Fairness / Slice Disparity
# ─────────────────────────────────────────────────────────────────────────────

def calculate_slice_disparity(
    test_cases: List[LLMTestCase],
    max_disparity: float = 0.40,
) -> Dict[str, Any]:
    """
    Compute approval-rate disparity across applicant risk-band slices.

    Args:
        test_cases:     List of LLMTestCase objects with additional_metadata["slice"].
        max_disparity:  Allowed spread between the highest and lowest band
                        approval rates before the check fails.

    Returns:
        {
          "rates":       {"low": 1.0, "medium": 0.5, "high": 0.0},
          "disparity":   0.50,          # max - min approval rate
          "passed":      True/False,
          "violation":   "..." | None,
        }
    """
    approvals: Dict[str, int] = {}
    totals: Dict[str, int] = {}

    for case in test_cases:
        try:
            actual = json.loads(case.actual_output)
        except (json.JSONDecodeError, TypeError):
            continue

        band = (case.additional_metadata or {}).get("slice", "unknown")
        totals[band] = totals.get(band, 0) + 1
        if actual.get("recommendation") in ("approve", "approve_fast_track"):
            approvals[band] = approvals.get(band, 0) + 1

    rates = {
        band: approvals.get(band, 0) / count
        for band, count in totals.items()
    }

    if len(rates) < 2:
        return {
            "rates": rates,
            "disparity": 0.0,
            "passed": True,
            "violation": None,
        }

    spread = max(rates.values()) - min(rates.values())
    passed = spread <= max_disparity
    violation = (
        None
        if passed
        else (
            f"Approval-rate disparity {spread:.2%} exceeds threshold {max_disparity:.2%}. "
            f"Rates by band: {rates}"
        )
    )

    return {
        "rates": rates,
        "disparity": round(spread, 4),
        "passed": passed,
        "violation": violation,
    }
