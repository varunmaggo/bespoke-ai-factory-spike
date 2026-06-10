"""
evals/deepeval/rag_evaluator.py — DeepEval-based RAG quality evaluation.

Metrics:
  - AnswerRelevancy        ≥ 0.80
  - Faithfulness           ≥ 0.85
  - ContextualRecall       ≥ 0.70
  - Hallucination          ≤ 0.10
  - Toxicity               ≤ 0.05
  - Bias                   ≤ 0.10

CI thresholds block deployment if any metric is violated.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from deepeval.metrics import (
    AnswerRelevancyMetric,
    BiasMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
    HallucinationMetric,
    ToxicityMetric,
)
from deepeval.test_case import LLMTestCase

logger = logging.getLogger(__name__)

# CI thresholds
THRESHOLDS = {
    "answer_relevancy":  ("min", 0.80),
    "faithfulness":      ("min", 0.85),
    "contextual_recall": ("min", 0.70),
    "hallucination":     ("max", 0.10),
    "toxicity":          ("max", 0.05),
    "bias":              ("max", 0.10),
}


@dataclass
class EvalReport:
    passed: bool
    scores: dict[str, float]
    failures: list[str]
    overall_score: float


class RAGEvaluator:
    """Run DeepEval metrics against RAG outputs."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        # DeepEval uses OpenAI by default; override for Anthropic via env
        self.model = model
        self.metrics = {
            "answer_relevancy":  AnswerRelevancyMetric(threshold=0.80, model=self.model),
            "faithfulness":      FaithfulnessMetric(threshold=0.85, model=self.model),
            "contextual_recall": ContextualRecallMetric(threshold=0.70, model=self.model),
            "hallucination":     HallucinationMetric(threshold=0.10, model=self.model),
            "toxicity":          ToxicityMetric(threshold=0.10, model=self.model),
            "bias":              BiasMetric(threshold=0.10, model=self.model),
        }

    def run_evaluation(
        self,
        question: str,
        answer: str,
        context: list[str],
        expected_output: str | None = None,
    ) -> EvalReport:
        """
        Evaluate a single (question, answer, context) triple.

        Args:
            question:        The user query.
            answer:          The generated response to evaluate.
            context:         List of retrieved context strings.
            expected_output: Optional golden answer for recall metrics.
        """
        test_case = LLMTestCase(
            input=question,
            actual_output=answer,
            retrieval_context=context,
            expected_output=expected_output or answer,
        )

        scores: dict[str, float] = {}
        failures: list[str] = []

        for name, metric in self.metrics.items():
            try:
                metric.measure(test_case)
                score = metric.score
                scores[name] = round(score, 4)

                direction, threshold = THRESHOLDS[name]
                failed = (score < threshold) if direction == "min" else (score > threshold)
                if failed:
                    failures.append(
                        f"{name}: {score:.3f} {'<' if direction == 'min' else '>'} {threshold}"
                    )
            except Exception as e:
                logger.warning("Metric %s failed: %s", name, e)
                scores[name] = 0.0
                failures.append(f"{name}: evaluation_error ({e})")

        # Weighted overall score (invert capped metrics)
        overall = (
            scores.get("answer_relevancy", 0) * 0.35
            + scores.get("faithfulness", 0) * 0.30
            + scores.get("contextual_recall", 0) * 0.20
            + (1 - scores.get("hallucination", 1)) * 0.10
            + (1 - scores.get("toxicity", 1)) * 0.025
            + (1 - scores.get("bias", 1)) * 0.025
        )

        return EvalReport(
            passed=len(failures) == 0,
            scores=scores,
            failures=failures,
            overall_score=round(overall, 4),
        )

    def run_batch(self, test_cases: list[dict]) -> list[EvalReport]:
        """
        Evaluate a batch of test cases from the golden dataset.

        Each dict: {question, answer, context: [...], expected_output?}
        """
        return [
            self.run_evaluation(
                question=tc["question"],
                answer=tc["answer"],
                context=tc["context"] if isinstance(tc["context"], list) else [tc["context"]],
                expected_output=tc.get("expected_output"),
            )
            for tc in test_cases
        ]

    def ci_gate(self, reports: list[EvalReport]) -> bool:
        """
        Return True (pass) only if ALL reports pass all metric thresholds.
        Logs failures for CI output.
        """
        all_passed = True
        for i, report in enumerate(reports):
            if not report.passed:
                all_passed = False
                logger.error(
                    "Test case %d FAILED (score=%.3f): %s",
                    i, report.overall_score, "; ".join(report.failures)
                )
        if all_passed:
            logger.info("All %d eval cases passed CI gate ✓", len(reports))
        return all_passed
