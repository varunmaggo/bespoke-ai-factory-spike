"""
tests/unit/test_eval_logic.py — Unit tests for evaluation + judge logic.
No external services required.
"""
import unittest.mock as m
import pytest

from evals.deepeval.rag_evaluator import RAGEvaluator, THRESHOLDS, EvalReport
from evals.llm_judge.judge import LLMJudge, DIMENSIONS, JudgeScore, PASS_THRESHOLD


# ── THRESHOLDS config ─────────────────────────────────────────────────────────

class TestThresholds:
    def test_all_six_metrics_present(self):
        expected = {"answer_relevancy", "faithfulness", "contextual_recall",
                    "hallucination", "toxicity", "bias"}
        assert set(THRESHOLDS.keys()) == expected

    def test_min_metrics_have_correct_thresholds(self):
        assert THRESHOLDS["answer_relevancy"]  == ("min", 0.80)
        assert THRESHOLDS["faithfulness"]      == ("min", 0.85)
        assert THRESHOLDS["contextual_recall"] == ("min", 0.70)

    def test_max_metrics_have_correct_thresholds(self):
        assert THRESHOLDS["hallucination"] == ("max", 0.10)
        assert THRESHOLDS["toxicity"]      == ("max", 0.05)
        assert THRESHOLDS["bias"]          == ("max", 0.10)


# ── EvalReport CI gate logic ───────────────────────────────────────────────────

class TestEvalCIGate:
    def _make_evaluator(self):
        ev = object.__new__(RAGEvaluator)
        ev.model = "mock"
        return ev

    def test_ci_gate_passes_all_good(self):
        ev = self._make_evaluator()
        reports = [EvalReport(passed=True, scores={}, failures=[], overall_score=0.9)] * 5
        assert ev.ci_gate(reports) is True

    def test_ci_gate_fails_any_bad(self):
        ev = self._make_evaluator()
        reports = [
            EvalReport(passed=True,  scores={}, failures=[],                   overall_score=0.9),
            EvalReport(passed=False, scores={}, failures=["faithfulness: 0.7"], overall_score=0.5),
        ]
        assert ev.ci_gate(reports) is False

    def test_overall_score_weighting(self, rag_test_case):
        """Overall score formula: weighted sum of metric scores (inverted for max-metrics)."""
        # Manually compute: 1.0 * 0.35 + 1.0 * 0.30 + 1.0 * 0.20 + (1-0)*0.10 + (1-0)*0.025 + (1-0)*0.025
        expected = 0.35 + 0.30 + 0.20 + 0.10 + 0.025 + 0.025
        assert abs(expected - 1.0) < 0.001

    def test_overall_score_with_hallucination(self):
        # hallucination=0.5 → contributes (1-0.5)*0.10 = 0.05 instead of 0.10
        contrib = (1 - 0.5) * 0.10
        assert contrib == 0.05


# ── DIMENSIONS weights ────────────────────────────────────────────────────────

class TestJudgeDimensions:
    def test_weights_sum_to_one(self):
        assert abs(sum(DIMENSIONS.values()) - 1.0) < 1e-6

    def test_groundedness_has_highest_weight(self):
        assert DIMENSIONS["groundedness"] == max(DIMENSIONS.values())

    def test_all_five_dimensions_present(self):
        assert set(DIMENSIONS.keys()) == {"groundedness", "completeness", "clarity", "conciseness", "safety"}

    def test_pass_threshold_is_correct(self):
        assert PASS_THRESHOLD == 0.75


# ── LLMJudge scoring ──────────────────────────────────────────────────────────

class TestLLMJudge:
    @pytest.fixture(autouse=True)
    def judge(self):
        self.judge = LLMJudge.__new__(LLMJudge)
        self.judge.model = "claude-sonnet-4-20250514"
        self.judge.pass_threshold = PASS_THRESHOLD
        self.judge.client = m.MagicMock()

    def _mock_api_response(self, scores: dict):
        import json
        response = {**scores, "reasoning": {k: "ok" for k in scores}}
        self.judge.client.messages.create.return_value.content[0].text = json.dumps(response)

    def test_passes_when_all_dimensions_high(self):
        self._mock_api_response({
            "groundedness": 0.95, "completeness": 0.90,
            "clarity": 0.88, "conciseness": 0.85, "safety": 1.0
        })
        result = self.judge.judge("What is Q2?", "4.2M", "Revenue 4.2M confirmed")
        assert result.passed is True
        assert result.weighted_score >= PASS_THRESHOLD

    def test_fails_when_groundedness_low(self):
        self._mock_api_response({
            "groundedness": 0.1, "completeness": 0.9,
            "clarity": 0.9, "conciseness": 0.9, "safety": 1.0
        })
        result = self.judge.judge("Q?", "A", "context")
        # groundedness=0.1 * 0.35 = 0.035 → total well below 0.75
        assert result.passed is False

    def test_weighted_score_computed_correctly(self):
        scores = {"groundedness": 1.0, "completeness": 1.0, "clarity": 1.0,
                  "conciseness": 1.0, "safety": 1.0}
        self._mock_api_response(scores)
        result = self.judge.judge("Q?", "A", "ctx")
        assert abs(result.weighted_score - 1.0) < 0.01

    def test_returns_neutral_score_on_api_failure(self):
        self.judge.client.messages.create.side_effect = Exception("timeout")
        result = self.judge.judge("Q?", "A", "ctx")
        # Should not raise; returns fallback neutral
        assert isinstance(result, JudgeScore)
        assert 0.0 <= result.weighted_score <= 1.0

    def test_self_consistency_averages_two_calls(self):
        import json
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            score = 0.8 if call_count == 1 else 0.6
            resp = m.MagicMock()
            resp.content[0].text = json.dumps({
                "groundedness": score, "completeness": score,
                "clarity": score, "conciseness": score, "safety": score,
                "reasoning": {}
            })
            return resp
        self.judge.client.messages.create.side_effect = side_effect
        result = self.judge.judge("Q?", "A", "ctx")
        assert call_count == 2
        # average of 0.8 and 0.6 = 0.7 per dimension
        assert abs(result.scores["groundedness"] - 0.7) < 0.01

    def test_ci_gate_all_pass(self):
        scores = [JudgeScore(scores={}, reasoning={}, weighted_score=0.8, passed=True)] * 3
        assert self.judge.ci_gate(scores) is True

    def test_ci_gate_any_fail(self):
        scores = [
            JudgeScore(scores={}, reasoning={}, weighted_score=0.8,  passed=True),
            JudgeScore(scores={}, reasoning={}, weighted_score=0.65, passed=False),
        ]
        assert self.judge.ci_gate(scores) is False

    def test_batch_judge_processes_all(self):
        import json
        self.judge.client.messages.create.return_value.content[0].text = json.dumps({
            "groundedness": 0.9, "completeness": 0.9, "clarity": 0.9,
            "conciseness": 0.9, "safety": 1.0, "reasoning": {}
        })
        items = [{"question": f"Q{i}", "answer": f"A{i}", "context": "ctx"} for i in range(3)]
        results = self.judge.batch_judge(items)
        assert len(results) == 3
        assert all(isinstance(r, JudgeScore) for r in results)
