"""
ATX Transform Service — FastAPI application
Exposes ATX pipeline execution as a REST API.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Optional
import logging, time, os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# ── Telemetry setup ──────────────────────────────────────────────────────────
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces"))
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("ai-factory.transform-service")

# ── Prometheus metrics ───────────────────────────────────────────────────────
TRANSFORM_DURATION = Histogram(
    "atx_transform_duration_seconds",
    "Duration of ATX transform pipeline execution",
    ["pipeline_id"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
TRANSFORM_ERRORS = Counter(
    "atx_transform_errors_total",
    "Total ATX transform errors",
    ["pipeline_id"],
)
TRANSFORM_REQUESTS = Counter(
    "atx_transform_requests_total",
    "Total ATX transform requests",
    ["pipeline_id"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ATX Transform Service",
    description="Composable deterministic transforms for AI pipelines",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
FastAPIInstrumentor.instrument_app(app)


# ── Schema ───────────────────────────────────────────────────────────────────
class TransformRequest(BaseModel):
    pipeline_id: str = Field(..., description="ID of the ATX pipeline to execute")
    payload: Any    = Field(..., description="Data to transform")
    options: dict   = Field(default_factory=dict)


class TransformResponse(BaseModel):
    pipeline_id:  str
    success:      bool
    result:       Any
    duration_ms:  float
    errors:       list[str] = []
    metadata:     dict = {}


# ── Pipeline registry ─────────────────────────────────────────────────────────
from pipelines.enterprise_context_normaliser import enterprise_context_normaliser
from pipelines.document_extractor import document_extractor_pipeline
from pipelines.pii_redactor import pii_redactor_pipeline

PIPELINES = {
    "enterprise-context-normaliser": enterprise_context_normaliser,
    "document-extractor":            document_extractor_pipeline,
    "pii-redactor":                  pii_redactor_pipeline,
}


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "pipelines": list(PIPELINES.keys())}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/pipelines")
async def list_pipelines():
    return {
        "pipelines": [
            {"id": pid, "transforms": [t.name for t in pipeline.transforms]}
            for pid, pipeline in PIPELINES.items()
        ]
    }


@app.post("/api/v1/transform", response_model=TransformResponse)
async def transform(request: TransformRequest):
    pipeline = PIPELINES.get(request.pipeline_id)
    if not pipeline:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline '{request.pipeline_id}' not found. "
                   f"Available: {list(PIPELINES.keys())}"
        )

    TRANSFORM_REQUESTS.labels(pipeline_id=request.pipeline_id).inc()

    with tracer.start_as_current_span(
        f"atx.pipeline.{request.pipeline_id}",
        attributes={"pipeline.id": request.pipeline_id},
    ) as span:
        start = time.monotonic()
        try:
            result = pipeline(request.payload)
            duration = (time.monotonic() - start) * 1000
            TRANSFORM_DURATION.labels(pipeline_id=request.pipeline_id).observe(duration / 1000)

            span.set_attribute("pipeline.success",     result.success)
            span.set_attribute("pipeline.duration_ms", duration)

            return TransformResponse(
                pipeline_id=request.pipeline_id,
                success=result.success,
                result=result.data,
                duration_ms=duration,
                errors=result.errors,
                metadata=result.metadata,
            )
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            TRANSFORM_ERRORS.labels(pipeline_id=request.pipeline_id).inc()
            span.record_exception(e)
            logger.error(f"Pipeline {request.pipeline_id} failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
