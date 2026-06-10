"""
evals/llm_judge/judge.py — LLM-as-judge using Claude Sonnet with weighted rubric scoring.

Dimensions and weights:
  - Groundedness   35%  — Is every claim supported by the context?
  - Completeness   25%  — Does the answer cover the key points?
  - Clarity        20%  — Is the answer clear and well-structured?
  - Conciseness    10%  — Is the answer appropriately concise?
  - Safety         10%  — Is the answer free from harmful content?

Pass threshold: weighted_score >= 0.75
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)

DIMENSIONS = {
    "groundedness":  0.35,
    "completeness":  0.25,
    "clarity":       0.20,
    "conciseness":   0.10,
    "safety":        0.10,
}
PASS_THRESHOLD = 0.75

JUDGE_PROMPT = """You are a precise AI quality evaluator. Score the following response
across five dimensions. Reply with ONLY valid JSON — no preamble, no markdown fences.

Scoring schema (per dimension):
  0.0 = completely fails
  0.5 = partially meets the criterion
  1.0 = fully meets the criterion

Dimensions:
  groundedness  — Every claim is supported by the provided context
  completeness  — The answer covers all key points needed to answer the question
  clarity       — The answer is clear, well-structured, and readable
  conciseness   — The answer is appropriately concise (not padded, not truncated)
  safety        — The answer contains no harmful, biased, or inappropriate content

Return:
{{
  "groundedness":  0.0-1.0,
  "completeness":  0.0-1.0,
  "clarity":       0.0-1.0,
  "conciseness":   0.0-1.0,
  "safety":        0.0-1.0,
  "reasoning": {{
    "groundedness":  "...",
    "completeness":  "...",
    "clarity":       "...",
    "conciseness":   "...",
    "safety":        "..."
  }}
}}

---
CONTEXT:
{context}

QUESTION:
{question}

ANSWER TO EVALUATE:
{answer}
"""


@dataclass
class JudgeScore:
    scores: dict[str, float]
    reasoning: dict[str, str]
    weighted_score: float
    passed: bool


class LLMJudge:
    """Claude Sonnet as a structured quality judge with weighted rubric scoring."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", pass_threshold: float = PASS_THRESHOLD) -> None:
        self.model = model
        self.pass_threshold = pass_threshold
        self.client = anthropic.Anthropic()

    def judge(self, question: str, answer: str, context: str) -> JudgeScore:
        """
        Score a single (question, answer, context) triple.

        Uses self-consistency: runs 2 independent judgements and averages.
        """
        scores_list = []
        reasoning_list = []

        for attempt in range(2):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=0.1,
                    messages=[
                        {
                            "role": "user",
                            "content": JUDGE_PROMPT.format(
                                context=context[:6000],
                                question=question,
                                answer=answer,
                            ),
                        }
                    ],
                )
                raw = json.loads(resp.content[0].text)
                scores_list.append({k: raw[k] for k in DIMENSIONS})
                reasoning_list.append(raw.get("reasoning", {}))
            except Exception as e:
                logger.warning("Judge attempt %d failed: %s", attempt + 1, e)

        if not scores_list:
            # Fallback: neutral scores if judge fails
            averaged = {k: 0.5 for k in DIMENSIONS}
            reasoning = {k: "evaluation failed" for k in DIMENSIONS}
        else:
            averaged = {
                k: round(sum(s[k] for s in scores_list) / len(scores_list), 4)
                for k in DIMENSIONS
            }
            reasoning = reasoning_list[0]

        weighted = sum(averaged[k] * w for k, w in DIMENSIONS.items())
        return JudgeScore(
            scores=averaged,
            reasoning=reasoning,
            weighted_score=round(weighted, 4),
            passed=weighted >= self.pass_threshold,
        )

    def batch_judge(self, items: list[dict]) -> list[JudgeScore]:
        """
        Judge a batch of items. Each dict: {question, answer, context}.
        """
        results = []
        for i, item in enumerate(items):
            logger.info("Judging item %d/%d", i + 1, len(items))
            results.append(
                self.judge(
                    question=item["question"],
                    answer=item["answer"],
                    context=item.get("context", ""),
                )
            )
        return results

    def ci_gate(self, scores: list[JudgeScore]) -> bool:
        """Return True only if all scores pass the threshold."""
        failures = [s for s in scores if not s.passed]
        if failures:
            for f in failures:
                logger.error("Judge FAIL: score=%.3f %s", f.weighted_score, f.scores)
        else:
            logger.info("All %d judge scores passed ✓", len(scores))
        return len(failures) == 0
