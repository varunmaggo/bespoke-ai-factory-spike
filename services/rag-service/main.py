"""
Agentic RAG Service — FastAPI application
Multi-hop hybrid retrieval over enterprise data sources.
"""
import os, logging, time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from rag.orchestrator import AgentRAGOrchestrator
from rag.vector_store import EnterpriseVectorStore
from rag.graph_store import EnterpriseKnowledgeGraph

OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces"))
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("ai-factory.rag-service")

RAG_LATENCY = Histogram(
    "rag_retrieval_duration_seconds",
    "RAG retrieval latency",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
RAG_HOPS = Counter("rag_hops_total", "Total retrieval hops", ["hop_count"])
RAG_ERRORS = Counter("rag_errors_total", "RAG errors")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agentic RAG Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
FastAPIInstrumentor.instrument_app(app)

# ── Dependency initialisation ────────────────────────────────────────────────
vector_store = EnterpriseVectorStore(
    endpoint=os.environ["OPENSEARCH_URL"],
    index_name=os.getenv("OPENSEARCH_INDEX", "enterprise-docs"),
)
graph_store = EnterpriseKnowledgeGraph(
    uri=os.environ["NEO4J_URI"],
    auth=(
        os.getenv("NEO4J_USER", "neo4j"),
        os.environ["NEO4J_PASSWORD"],
    ),
)
orchestrator = AgentRAGOrchestrator(
    vector_store=vector_store,
    graph_store=graph_store,
    max_hops=int(os.getenv("RAG_MAX_HOPS", "3")),
    sufficiency_threshold=float(os.getenv("RAG_SUFFICIENCY_THRESHOLD", "0.75")),
)


# ── Schema ───────────────────────────────────────────────────────────────────
class RetrieveRequest(BaseModel):
    query:   str          = Field(..., min_length=1)
    top_k:   int          = Field(default=10, ge=1, le=50)
    filters: Optional[dict] = None


class IndexRequest(BaseModel):
    doc_id:   str
    text:     str
    metadata: dict = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/retrieve")
async def retrieve(request: RetrieveRequest):
    with tracer.start_as_current_span(
        "rag.retrieve",
        attributes={"query.length": len(request.query)},
    ) as span:
        start = time.monotonic()
        try:
            result = orchestrator.retrieve_and_generate(
                query=request.query,
                filters=request.filters,
            )
            duration = time.monotonic() - start
            RAG_LATENCY.observe(duration)
            RAG_HOPS.labels(hop_count=str(result.hops)).inc()

            span.set_attribute("rag.hops",            result.hops)
            span.set_attribute("rag.sources_count",   len(result.sources))
            span.set_attribute("rag.sufficiency",     result.sufficiency_score)

            return {
                "answer":           result.answer,
                "context":          _build_context_string(result.sources),
                "sources":          result.sources[:5],  # Return top 5 for attribution
                "hops":             result.hops,
                "sufficiency_score":result.sufficiency_score,
                "metadata":         result.metadata,
            }
        except Exception as e:
            RAG_ERRORS.inc()
            span.record_exception(e)
            logger.error(f"RAG retrieval error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/search")
async def search(request: RetrieveRequest):
    """Vector-only search without generation — for diagnostics."""
    results = vector_store.hybrid_search(
        query=request.query,
        top_k=request.top_k,
        filters=request.filters,
    )
    return {"results": results, "count": len(results)}


@app.post("/api/v1/index")
async def index_document(request: IndexRequest):
    success = vector_store.index_document(
        doc_id=request.doc_id,
        text=request.text,
        metadata=request.metadata,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Indexing failed")
    return {"indexed": True, "doc_id": request.doc_id}


def _build_context_string(sources: list[dict]) -> str:
    parts = []
    for i, src in enumerate(sources):
        doc_id = src.get("metadata", {}).get("document_id", f"DOC-{i}")
        parts.append(f"[{doc_id}]\n{src.get('content', '')}")
    return "\n\n---\n\n".join(parts)
