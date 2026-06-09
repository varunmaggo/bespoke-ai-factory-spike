"""
Pydantic schemas for the stub loan triage pipeline.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Applicant(BaseModel):
    applicant_id: str
    name: str
    credit_score: int
    annual_income: float
    risk_band: str          # "low" | "medium" | "high"
    kyc_verified: bool


class LoanApplication(BaseModel):
    application_id: str
    applicant: Applicant
    loan_amount: float
    loan_purpose: str


class TriageDecision(BaseModel):
    application_id: str
    recommendation: str     # "approve" | "approve_fast_track" | "reject" | "human_review"
    status: str
    risk_band: str
    reasons: List[str]


class AgentMessage(BaseModel):
    agent: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class RunMemory(BaseModel):
    run_id: str
    application_id: str
    messages: List[AgentMessage] = Field(default_factory=list)
    tool_outputs: Dict[str, Any] = Field(default_factory=dict)
    completed: bool = False

    def mark_complete(self) -> None:
        self.completed = True


class AgentRun(BaseModel):
    run_id: str
    application_id: str
    decision: TriageDecision
    messages: List[AgentMessage] = Field(default_factory=list)
    tool_outputs: Dict[str, Any] = Field(default_factory=dict)
