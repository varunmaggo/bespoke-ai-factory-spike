"""
services/eval/main.py — FastAPI evaluation microservice.

Thin wrapper around evals/deepeval/rag_evaluator.py and evals/llm_judge/judge.py.

Endpoints:
  POST /evaluate   — DeepEval metrics + LLM-as-judge scoring for a (query, answer, context) triple
  GET  /health
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

from evals.deepeval.rag_evaluator import RAGEvaluator
from evals.llm_judge.judge import LLMJudge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Globals initialised in lifespan ──────────────────────────────────────────
evaluator: RAGEvaluator | None = None
judge: LLMJudge | None = None
gate_failure_counter: metrics.Counter | None = None
weighted_score_histogram: metrics.Histogram | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global evaluator, judge
    _setup_otel()
    evaluator = RAGEvaluator(model=os.getenv("DEEPEVAL_MODEL", "gpt-4o-mini"))
    judge = LLMJudge(model=os.getenv("JUDGE_MODEL", "claude-sonnet-4-20250514"))
    logger.info("Eval service ready")
    yield
    logger.info("Eval service shutdown")


app = FastAPI(title="AI Factory — Eval Service", version="1.0.0", lifespan=lifespan)


# ── Models ────────────────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    query: str
    answer: str
    context: str | list[str]
    expected_output: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "eval"}


@app.post("/evaluate")
def evaluate(req: EvaluateRequest):
    tracer = trace.get_tracer("eval-service")
    with tracer.start_as_current_span("eval.evaluate") as span:
        context_list = req.context if isinstance(req.context, list) else [req.context]
        context_str = req.context if isinstance(req.context, str) else "\n\n---\n\n".join(req.context)

        judge_score = judge.judge(req.query, req.answer, context_str)
        eval_report = evaluator.run_evaluation(
            question=req.query,
            answer=req.answer,
            context=context_list,
            expected_output=req.expected_output,
        )

        passed = judge_score.passed and eval_report.passed

        span.set_attribute("eval.weighted_score", judge_score.weighted_score)
        span.set_attribute("eval.overall_score", eval_report.overall_score)
        span.set_attribute("eval.passed", passed)

        weighted_score_histogram.record(judge_score.weighted_score)
        if not passed:
            if not judge_score.passed and not eval_report.passed:
                reason = "both"
            elif not judge_score.passed:
                reason = "judge"
            else:
                reason = "deepeval"
            gate_failure_counter.add(1, {"reason": reason})

        return {
            "weighted_score": judge_score.weighted_score,
            "passed": judge_score.passed and eval_report.passed,
            "judge": {
                "scores": judge_score.scores,
                "reasoning": judge_score.reasoning,
                "weighted_score": judge_score.weighted_score,
                "passed": judge_score.passed,
            },
            "deepeval": {
                "passed": eval_report.passed,
                "scores": eval_report.scores,
                "failures": eval_report.failures,
                "overall_score": eval_report.overall_score,
            },
        }


# ── OTel setup ────────────────────────────────────────────────────────────────

def _setup_otel() -> None:
    global gate_failure_counter, weighted_score_histogram

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    resource = Resource.create({SERVICE_NAME: "eval-service"})

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True))
    )
    trace.set_tracer_provider(trace_provider)

    # Scores are 0-1 ratios — replace the default ms-scale histogram buckets
    # with ones suited to that range.
    score_view = View(
        instrument_name="eval.weighted_score",
        aggregation=ExplicitBucketHistogramAggregation(
            boundaries=(0.0, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)
        ),
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otel_endpoint, insecure=True))
        ],
        views=[score_view],
    )
    metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter("eval-service")
    gate_failure_counter = meter.create_counter(
        "eval.gate.failures",
        unit="1",
        description="Responses that failed the AI-quality eval gate (judge and/or DeepEval)",
    )
    weighted_score_histogram = meter.create_histogram(
        "eval.weighted_score",
        unit="1",
        description="LLM-judge weighted score per evaluation",
    )
