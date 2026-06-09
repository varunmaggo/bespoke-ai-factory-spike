"""
Stub Orchestrator — simulates a multi-agent lending triage pipeline.

Replaces the real LLM-driven orchestrator for local eval testing.
Each specialist agent is a simple rule-based function; the Decision
Agent applies the same hard business rules that the eval metrics audit.
"""
from __future__ import annotations

import uuid
from .schemas import (
    AgentMessage,
    AgentRun,
    LoanApplication,
    RunMemory,
    TriageDecision,
)


class Orchestrator:
    def process(self, application_data: dict, memory: RunMemory) -> dict:
        app = LoanApplication(**application_data)

        # ── Credit Agent ──────────────────────────────────────────────────────
        credit_score = app.applicant.credit_score
        credit_output = {
            "credit_score": credit_score,
            "credit_tier": (
                "A" if credit_score >= 750
                else "B" if credit_score >= 700
                else "C" if credit_score >= 650
                else "D"
            ),
            "passed": credit_score >= 650,
        }
        memory.tool_outputs["credit_agent"] = credit_output
        memory.messages.append(
            AgentMessage(agent="credit_agent", content=f"Score {credit_score} evaluated")
        )

        # ── KYC Agent ─────────────────────────────────────────────────────────
        kyc_verified = app.applicant.kyc_verified
        kyc_output = {
            "verified": kyc_verified,
            "checks_passed": ["identity", "address"] if kyc_verified else [],
        }
        memory.tool_outputs["kyc_agent"] = kyc_output
        memory.messages.append(
            AgentMessage(
                agent="kyc_agent",
                content=f"KYC {'verified' if kyc_verified else 'UNVERIFIED'}",
            )
        )

        # ── Risk Agent ────────────────────────────────────────────────────────
        dti = app.loan_amount / max(app.applicant.annual_income * 0.4, 1)
        risk_output = {"risk_band": app.applicant.risk_band, "dti_ratio": round(dti, 2)}
        memory.tool_outputs["risk_agent"] = risk_output

        # ── Decision Agent ────────────────────────────────────────────────────
        if credit_score < 650:
            recommendation = "reject"
            risk_band = "high"
            reasons = [f"Credit score {credit_score} below mandatory minimum of 650"]
        elif not kyc_verified:
            recommendation = "human_review"
            risk_band = app.applicant.risk_band
            reasons = ["KYC verification incomplete — manual review required"]
        elif credit_score >= 750 and app.applicant.risk_band == "low":
            recommendation = "approve_fast_track"
            risk_band = "low"
            reasons = ["Excellent credit score", "Low risk profile — fast-track eligible"]
        elif app.applicant.risk_band == "high":
            recommendation = "human_review"
            risk_band = "high"
            reasons = ["High risk band — underwriter review required"]
        else:
            recommendation = "approve"
            risk_band = app.applicant.risk_band
            reasons = [
                "Credit score meets threshold",
                "KYC verified",
                "Risk band within acceptable range",
            ]

        decision = {
            "application_id": app.application_id,
            "recommendation": recommendation,
            "status": "complete",
            "risk_band": risk_band,
            "reasons": reasons,
        }
        memory.messages.append(
            AgentMessage(agent="decision_agent", content=f"Decision: {recommendation}")
        )
        return {"decision": decision}


def run_triage_system(application: LoanApplication) -> AgentRun:
    """Execute the full pipeline and return a structured AgentRun."""
    memory = RunMemory(
        run_id=str(uuid.uuid4()),
        application_id=application.application_id,
    )
    orchestrator = Orchestrator()
    result = orchestrator.process(application.model_dump(), memory)
    memory.mark_complete()

    return AgentRun(
        run_id=memory.run_id,
        application_id=application.application_id,
        decision=TriageDecision(**result["decision"]),
        messages=memory.messages,
        tool_outputs=memory.tool_outputs,
    )
