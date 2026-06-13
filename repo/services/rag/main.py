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

from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

from .connectors import available_sources, chunk_document, get_connector
from .graph_store import EnterpriseKnowledgeGraph
from .orchestrator import AgentRAGOrchestrator
from .vector_store import EnterpriseVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Globals initialised in lifespan ──────────────────────────────────────────
vector_store: EnterpriseVectorStore | None = None
graph_store: EnterpriseKnowledgeGraph | None = None
orchestrator: AgentRAGOrchestrator | None = None


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

class IngestRequest(BaseModel):
    source: str
    options: Optional[dict] = None


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


@app.get("/sources")
def list_sources():
    """List source systems that can be connected for ingestion."""
    return {"sources": available_sources()}


@app.post("/ingest")
def ingest(req: IngestRequest):
    """Connect an internal system (e.g. Confluence, SharePoint) and index it.

    Fetches documents via the named connector, chunks them and bulk-indexes
    into the hybrid vector store. Connectors fall back to bundled sample data
    when no credentials are configured, so this works offline for the demo.
    """
    tracer = trace.get_tracer("rag-service")
    with tracer.start_as_current_span("rag.ingest") as span:
        span.set_attribute("ingest.source", req.source)
        try:
            connector = get_connector(req.source, **(req.options or {}))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        docs = connector.fetch()
        chunks = [chunk for doc in docs for chunk in chunk_document(doc)]
        if chunks:
            vector_store.bulk_index(chunks)
        span.set_attribute("ingest.live", connector.is_live())
        span.set_attribute("ingest.documents", len(docs))
        span.set_attribute("ingest.chunks", len(chunks))
        return {
            "source":    req.source,
            "live":      connector.is_live(),
            "documents": len(docs),
            "chunks":    len(chunks),
        }


# ── OTel setup ────────────────────────────────────────────────────────────────

def _setup_otel() -> None:
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: "rag-service"})
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)
