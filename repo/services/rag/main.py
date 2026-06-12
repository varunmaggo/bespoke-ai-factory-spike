"""
services/rag/main.py — FastAPI RAG microservice.

Endpoints:
  POST /retrieve   — hybrid search (vector + graph)
  POST /query      — full RAG pipeline (retrieve → transform → generate)
  POST /index      — index a document chunk
  GET  /health
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

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

from .graph_store import EnterpriseKnowledgeGraph
from .orchestrator import AgentRAGOrchestrator
from .vector_store import EnterpriseVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Globals initialised in lifespan ──────────────────────────────────────────
vector_store: EnterpriseVectorStore | None = None
graph_store: EnterpriseKnowledgeGraph | None = None
orchestrator: AgentRAGOrchestrator | None = None
sufficiency_score_histogram: metrics.Histogram | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, graph_store, orchestrator
    _setup_otel()
    vector_store = EnterpriseVectorStore()
    graph_store  = EnterpriseKnowledgeGraph()
    orchestrator = AgentRAGOrchestrator(vector_store, graph_store)
    logger.info("RAG service ready")
    yield
    graph_store.close()
    logger.info("RAG service shutdown")


app = FastAPI(title="AI Factory — RAG Service", version="1.0.0", lifespan=lifespan)


# ── Models ────────────────────────────────────────────────────────────────────

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: Optional[dict] = None

class IndexRequest(BaseModel):
    doc_id: str
    content: str
    metadata: Optional[dict] = None

class QueryRequest(BaseModel):
    query: str
    filters: Optional[dict] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "rag"}


@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    tracer = trace.get_tracer("rag-service")
    with tracer.start_as_current_span("rag.retrieve") as span:
        span.set_attribute("query.length", len(req.query))
        chunks = vector_store.hybrid_search(req.query, top_k=req.top_k, filters=req.filters)
        span.set_attribute("results.count", len(chunks))
        return {"chunks": chunks, "count": len(chunks)}


@app.post("/query")
def query(req: QueryRequest):
    tracer = trace.get_tracer("rag-service")
    with tracer.start_as_current_span("rag.query") as span:
        span.set_attribute("query.length", len(req.query))
        result = orchestrator.retrieve_and_generate(req.query, filters=req.filters)
        span.set_attribute("rag.hops",              result.hops)
        span.set_attribute("rag.sufficiency_score", result.sufficiency_score)
        sufficiency_score_histogram.record(result.sufficiency_score)
        return {
            "answer":             result.answer,
            "sources":            result.sources,
            "sufficiency_score":  result.sufficiency_score,
            "hops":               result.hops,
            "transform_metadata": result.transform_metadata,
        }


@app.post("/index")
def index_document(req: IndexRequest):
    vector_store.index_document(req.doc_id, req.content, req.metadata)
    return {"indexed": req.doc_id}


# ── OTel setup ────────────────────────────────────────────────────────────────

def _setup_otel() -> None:
    global sufficiency_score_histogram

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    resource = Resource.create({SERVICE_NAME: "rag-service"})

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True))
    )
    trace.set_tracer_provider(trace_provider)

    # Sufficiency score is a 0-1 ratio — replace the default ms-scale
    # histogram buckets with ones suited to that range.
    score_view = View(
        instrument_name="rag.sufficiency_score",
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

    sufficiency_score_histogram = metrics.get_meter("rag-service").create_histogram(
        "rag.sufficiency_score",
        unit="1",
        description="Agentic RAG retrieval-sufficiency score per query",
    )
