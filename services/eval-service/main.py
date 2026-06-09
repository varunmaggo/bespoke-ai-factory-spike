"""
Evaluation Service — FastAPI application
Exposes LLM-as-judge and DeepEval metrics as REST endpoints.
"""
import os, logging, time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from llm_judge.judge import LLMJudge, JudgeResult
from deepeval_runner.rag_evaluator import RAGEvaluator

OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces"))
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("ai-factory.eval-service")

JUDGE_LATENCY = Histogram(
    "eval_judge_duration_seconds",
    "LLM-as-judge latency",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 20.0],
)
JUDGE_SCORE = Summary("eval_judge_score", "Judge overall score distribution")
JUDGE_PASS = Counter("eval_judge_passed_total", "Responses that passed evaluation")
JUDGE_FAIL = Counter("eval_judge_failed_total", "Responses that failed evaluation")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Factory Eval Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
FastAPIInstrumentor.instrument_app(app)

judge = LLMJudge(
    model=os.getenv("JUDGE_MODEL", "claude-sonnet-4-20250514"),
    num_judges=int(os.getenv("NUM_JUDGES", "1")),
)
evaluator = RAGEvaluator(model=os.getenv("EVAL_MODEL", "claude-sonnet-4-20250514"))


# ── Schema ───────────────────────────────────────────────────────────────────
class JudgeRequest(BaseModel):
    question:        str
    response:        str
    context:         str = ""
    expected_answer: Optional[str] = None


class JudgeResponse(BaseModel):
    scores:                  dict[str, float]
    overall_score:           float
    passed:                  bool
    critique:                str
    improvement_suggestions: list[str]


class BatchEvalRequest(BaseModel):
    test_cases: list[dict] = Field(..., min_length=1)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "model": judge.model}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/judge", response_model=JudgeResponse)
async def judge_response(request: JudgeRequest):
    with tracer.start_as_current_span(
        "eval.judge",
        attributes={"response.length": len(request.response)},
    ) as span:
        start = time.monotonic()
        try:
            result: JudgeResult = judge.judge(
                question=request.question,
                response=request.response,
                context=request.context,
                expected_answer=request.expected_answer,
            )
            duration = time.monotonic() - start
            JUDGE_LATENCY.observe(duration)
            JUDGE_SCORE.observe(result.overall_score)

            if result.passed:
                JUDGE_PASS.inc()
            else:
                JUDGE_FAIL.inc()

            span.set_attribute("eval.score",  result.overall_score)
            span.set_attribute("eval.passed", result.passed)

            return JudgeResponse(
                scores=result.scores,
                overall_score=result.overall_score,
                passed=result.passed,
                critique=result.critique,
                improvement_suggestions=result.improvement_suggestions,
            )
        except Exception as e:
            span.record_exception(e)
            logger.error(f"Judge error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/judge/batch")
async def batch_judge(request: BatchEvalRequest, background_tasks: BackgroundTasks):
    """Async batch evaluation — returns immediately, results stored in background."""
    results = judge.batch_judge(request.test_cases)
    return {
        "total":  len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "avg_score": sum(r.overall_score for r in results) / len(results),
        "results": [
            {
                "overall_score": r.overall_score,
                "passed":        r.passed,
                "critique":      r.critique,
            }
            for r in results
        ],
    }


@app.post("/api/v1/deepeval")
async def deepeval_run(request: BatchEvalRequest):
    """Run the DeepEval metric suite on a set of test cases."""
    try:
        summary = evaluator.run_evaluation(request.test_cases)
        return summary
    except Exception as e:
        logger.error(f"DeepEval error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
