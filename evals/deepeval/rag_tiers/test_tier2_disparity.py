"""
Tier 2 — RAG Slice Disparity / Fairness Audit
==============================================
Checks that answer quality is consistent across query categories
(financial, compliance, operational, safety).

A large disparity could indicate the RAG system is better indexed for
some document types than others — a signal to re-chunk or rebalance
your knowledge base.
"""
from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deepeval.test_case import LLMTestCase

from rag_tiers.metrics import calculate_rag_slice_disparity

# ─────────────────────────────────────────────────────────────────────────────
# Extended dataset — more cases per slice for meaningful averages
# ─────────────────────────────────────────────────────────────────────────────

EXTENDED_CASES = [
    # financial slice
    LLMTestCase(
        input="What is our gross margin?",
        actual_output="The gross margin for Q2 2025 was 35%, up from 33% in Q2 2024.",
        retrieval_context=["Q2 2025 gross margin: 35%. Q2 2024: 33%."],
        additional_metadata={"slice": "financial"},
    ),
    LLMTestCase(
        input="What is EBITDA this quarter?",
        actual_output="EBITDA was $90M for Q2 2025, a 15% improvement year-over-year.",
        retrieval_context=["Q2 2025 EBITDA: $90M (+15% YoY)."],
        additional_metadata={"slice": "financial"},
    ),
    # compliance slice
    LLMTestCase(
        input="What is the GDPR retention period for system logs?",
        actual_output="System logs must be retained for 90 days under our GDPR policy.",
        retrieval_context=["GDPR Policy v3.2: System logs retention = 90 days."],
        additional_metadata={"slice": "compliance"},
    ),
    LLMTestCase(
        input="Who must approve a bulk data deletion?",
        actual_output="A DBA approval ticket is required before any bulk data deletion in production.",
        retrieval_context=["Bulk deletes require a DBA approval ticket and change management window."],
        additional_metadata={"slice": "compliance"},
    ),
    # operational slice
    LLMTestCase(
        input="What is the lead time for XR-47 from Gamma Supply?",
        actual_output="Gamma Supply's lead time for component XR-47 is 35 days.",
        retrieval_context=["Gamma Supply lead time for XR-47: 35 days."],
        additional_metadata={"slice": "operational"},
    ),
    LLMTestCase(
        input="How many days does BetaParts need for XR-47?",
        actual_output="BetaParts requires 21 days to deliver component XR-47.",
        retrieval_context=["BetaParts lead time for XR-47: 21 days."],
        additional_metadata={"slice": "operational"},
    ),
    # safety slice
    LLMTestCase(
        input="Can I delete production records directly?",
        actual_output=(
            "No. Production data deletion must follow the change management process: "
            "raise a DBA ticket, schedule a maintenance window, prepare a rollback "
            "plan, and test in staging first."
        ),
        retrieval_context=[
            "Production data deletion requires DBA approval ticket, "
            "change management window, rollback plan, and staging test."
        ],
        additional_metadata={"slice": "safety"},
    ),
    LLMTestCase(
        input="What happens if I bypass the staging test for bulk deletes?",
        actual_output=(
            "Bypassing the staging test for bulk deletes violates our data "
            "management policy and may result in irreversible data loss."
        ),
        retrieval_context=["Bulk deletes must be tested in staging first."],
        additional_metadata={"slice": "safety"},
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_rag_slice_quality_report():
    """
    Print a quality-score breakdown by query category.
    Always passes — this is an informational report.
    """
    result = calculate_rag_slice_disparity(EXTENDED_CASES, max_disparity=1.0)

    print("\n── Tier 2 RAG Slice Quality Report ─────────────────────────────")
    for category, score in sorted(result["scores"].items()):
        bar = "█" * int(score * 20)
        print(f"  {category:12s}  {score:.0%}  {bar}")
    print(f"\n  Disparity (max − min): {result['disparity']:.2%}")
    print(f"  Status: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
    if result["violation"]:
        print(f"  Note: {result['violation']}")
    print("────────────────────────────────────────────────────────────────")

    assert result["scores"], "No slices found — check additional_metadata['slice'] is set"


def test_rag_slice_disparity_within_threshold():
    """
    Quality-score spread across categories must not exceed 25%.
    A failure here means some query types are significantly under-served.
    """
    result = calculate_rag_slice_disparity(EXTENDED_CASES, max_disparity=0.25)
    assert result["passed"], result["violation"]
