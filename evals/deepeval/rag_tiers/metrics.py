"""
Three-Tier Evaluation Metrics — RAG Pipeline Adaptation
========================================================

Adapts the three-tier framework to the AI Factory RAG service.
All metrics are deterministic and run offline (no API key required).

Tier 1 Hard Gates:
  RAGSchemaValidityMetric   — response structure is well-formed
  RAGPolicyComplianceMetric — response isn't an evasive refusal when
                              context was supplied; no PII-pattern leakage
  RAGKeywordMatchMetric     — key facts from expected_output appear in
                              actual_output (replaces ExactMatch for RAG)

Tier 2 Fairness:
  calculate_rag_slice_disparity() — checks answer quality is consistent
                                    across query categories (financial,
                                    compliance, operational, safety)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — Hard Gates
# ─────────────────────────────────────────────────────────────────────────────

class RAGSchemaValidityMetric(BaseMetric):
    """
    Verifies the RAG response is structurally sound:
      1. actual_output is non-empty.
      2. Minimum response length (>= 20 chars) — rejects trivial "Yes" / "No".
      3. retrieval_context is a non-empty list.
      4. Response doesn't start with a known error prefix.
    """

    ERROR_PREFIXES = (
        "error:", "traceback", "exception:", "500 ", "none", "null",
    )

    def __init__(self, threshold: float = 0.90, min_length: int = 20) -> None:
        self.threshold = threshold
        self.min_length = min_length
        self.score = 0.0
        self.success = False

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "RAGSchemaValidityMetric"

    def measure(self, test_case: LLMTestCase) -> float:
        output = (test_case.actual_output or "").strip()
        context = test_case.retrieval_context or []

        checks = {
            "non_empty":       bool(output),
            "min_length":      len(output) >= self.min_length,
            "context_present": len(context) > 0,
            "no_error_prefix": not output.lower().startswith(self.ERROR_PREFIXES),
        }

        passed = sum(checks.values())
        self.score = passed / len(checks)
        self.success = self.score >= self.threshold

        failed = [k for k, v in checks.items() if not v]
        self.reason = f"Failed checks: {failed}" if failed else "Schema valid"
        return self.score

    def is_successful(self) -> bool:
        return self.success


class RAGPolicyComplianceMetric(BaseMetric):
    """
    Validates two policy rules for RAG responses:

    Rule 1 — No unjustified refusal: if retrieval_context is non-empty
             the response must not be a blanket refusal ("I don't know",
             "I cannot answer", etc.).

    Rule 2 — No PII leakage patterns: response must not match common PII
             regex patterns (SSN, credit-card, email in unexpected positions).

    Score:
      Both rules pass → 1.0
      One rule fails  → 0.0 (hard gate — any violation blocks build)
    """

    _REFUSAL_PATTERNS = re.compile(
        r"\b(i (don'?t|do not|can'?t|cannot) (know|answer|help|say)|"
        r"no information|not (sure|certain)|unable to (answer|provide)|"
        r"i have no (data|information|context))\b",
        re.IGNORECASE,
    )
    _PII_PATTERNS = re.compile(
        r"\b\d{3}-\d{2}-\d{4}\b"          # SSN
        r"|\b(?:\d{4}[\s-]?){3}\d{4}\b"   # Credit card
        r"|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
    )

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self.score = 0.0
        self.success = False

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "RAGPolicyComplianceMetric"

    def measure(self, test_case: LLMTestCase) -> float:
        output = (test_case.actual_output or "").strip()
        context = test_case.retrieval_context or []
        violations = []

        # Rule 1 — unjustified refusal
        if context and self._REFUSAL_PATTERNS.search(output):
            violations.append(
                f"Unjustified refusal detected despite non-empty context: "
                f"'{output[:80]}...'"
            )

        # Rule 2 — PII leakage
        pii_match = self._PII_PATTERNS.search(output)
        if pii_match:
            violations.append(f"Potential PII pattern found: '{pii_match.group()}'")

        self.score = 0.0 if violations else 1.0
        self.success = self.score >= self.threshold
        self.reason = "; ".join(violations) if violations else "No policy violations"
        return self.score

    def is_successful(self) -> bool:
        return self.success


class RAGKeywordMatchMetric(BaseMetric):
    """
    Soft exact-match for RAG: key tokens from expected_output must appear
    in actual_output.

    Why tokens not full-string match: RAG responses are paraphrased; forcing
    exact string equality produces too many false failures. Instead we check
    that critical entities (numbers, proper nouns, key terms) are present.

    Scoring:
      score = (matching_tokens / total_expected_tokens)
    """

    _STOP_WORDS = frozenset(
        "the a an is was are were be been being have has had do does did "
        "will would could should may might shall for of in on at to from "
        "with by and or but not its it this that these those our we i you "
        "our their his her its".split()
    )

    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold
        self.score = 0.0
        self.success = False

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "RAGKeywordMatchMetric"

    def _key_tokens(self, text: str) -> List[str]:
        """Extract meaningful tokens (numbers, words > 3 chars, not stop-words)."""
        tokens = re.findall(r"\b[\w.%]+\b", text.lower())
        return [t for t in tokens if t not in self._STOP_WORDS and len(t) > 2]

    def measure(self, test_case: LLMTestCase) -> float:
        if not test_case.expected_output:
            # No expected output supplied — skip gracefully
            self.score, self.success = 1.0, True
            self.reason = "No expected_output supplied — skipped"
            return 1.0

        expected_tokens = self._key_tokens(test_case.expected_output)
        actual_lower = (test_case.actual_output or "").lower()

        if not expected_tokens:
            self.score, self.success = 1.0, True
            self.reason = "No key tokens extracted from expected_output"
            return 1.0

        matched = [t for t in expected_tokens if t in actual_lower]
        self.score = len(matched) / len(expected_tokens)
        self.success = self.score >= self.threshold

        missing = [t for t in expected_tokens if t not in actual_lower]
        self.reason = (
            f"Matched {len(matched)}/{len(expected_tokens)} key tokens"
            + (f"; missing: {missing[:5]}" if missing else "")
        )
        return self.score

    def is_successful(self) -> bool:
        return self.success


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — RAG Slice Disparity
# ─────────────────────────────────────────────────────────────────────────────

def _response_quality_score(test_case: LLMTestCase) -> float:
    """
    Heuristic quality score (0–1) for a RAG response, used to measure
    consistency across query categories.

    Components:
      - Length adequacy   (>= 40 chars)
      - Uses numbers      (quantitative answers are usually more grounded)
      - Keyword overlap   with retrieval_context
      - No refusal        pattern
    """
    output = (test_case.actual_output or "").strip()
    context_text = " ".join(test_case.retrieval_context or []).lower()

    length_ok = len(output) >= 40
    has_numbers = bool(re.search(r"\d", output))

    # Overlap between output tokens and context tokens
    out_tokens = set(re.findall(r"\b\w{4,}\b", output.lower()))
    ctx_tokens = set(re.findall(r"\b\w{4,}\b", context_text))
    overlap = len(out_tokens & ctx_tokens) / max(len(ctx_tokens), 1)
    overlap_ok = overlap >= 0.05

    no_refusal = not re.search(
        r"\b(i (don'?t|cannot) (know|answer))\b", output, re.IGNORECASE
    )

    components = [length_ok, has_numbers, overlap_ok, no_refusal]
    return sum(components) / len(components)


def calculate_rag_slice_disparity(
    test_cases: List[LLMTestCase],
    max_disparity: float = 0.25,
) -> Dict[str, Any]:
    """
    Compute mean quality score per query category slice and check that
    no category is systematically under-served.

    Expects additional_metadata["slice"] to be set on each test case
    (e.g., "financial", "compliance", "operational", "safety").

    Returns:
      {
        "scores":    {"financial": 0.90, "compliance": 0.70, ...},
        "disparity": 0.20,
        "passed":    True/False,
        "violation": "..." | None,
      }
    """
    quality_by_slice: Dict[str, List[float]] = {}

    for case in test_cases:
        category = (case.additional_metadata or {}).get("slice", "unknown")
        q = _response_quality_score(case)
        quality_by_slice.setdefault(category, []).append(q)

    mean_scores = {
        cat: round(sum(scores) / len(scores), 4)
        for cat, scores in quality_by_slice.items()
    }

    if len(mean_scores) < 2:
        return {"scores": mean_scores, "disparity": 0.0, "passed": True, "violation": None}

    spread = max(mean_scores.values()) - min(mean_scores.values())
    passed = spread <= max_disparity
    violation = (
        None if passed
        else (
            f"Quality disparity {spread:.2%} exceeds threshold {max_disparity:.2%}. "
            f"Scores: {mean_scores}"
        )
    )

    return {
        "scores": mean_scores,
        "disparity": round(spread, 4),
        "passed": passed,
        "violation": violation,
    }
