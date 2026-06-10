"""
services/transform/main.py — FastAPI wrapper around AWS Transform Custom.

Executes a transformation definition via the `atx` CLI when it is installed;
otherwise falls back to the local Python implementation in normaliser.py
(currently only enterprise-context-normaliser has a local fallback).

Endpoints:
  POST /transform     — apply a transformation definition to a JSON payload
  GET  /definitions   — list available transformation definitions
  GET  /health
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import subprocess
import tempfile

from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

from .normaliser import normalise

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFINITIONS_DIR = pathlib.Path(
    os.getenv("TRANSFORM_DEFINITIONS_DIR", "/app/transformation_definitions")
)
DEFAULT_DEFINITION = "enterprise-context-normaliser"

# Definitions with a local Python fallback when atx is unavailable
LOCAL_FALLBACKS = {DEFAULT_DEFINITION}


def _setup_otel() -> None:
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: "transform-service"})
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)


_setup_otel()

app = FastAPI(title="AI Factory — Transform Service", version="1.0.0")


# ── Models ────────────────────────────────────────────────────────────────────

class TransformRequest(BaseModel):
    payload: dict
    definition: str = DEFAULT_DEFINITION
    max_tokens: int = 80_000


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "transform",
        "atx_available": shutil.which("atx") is not None,
    }


@app.get("/definitions")
def list_definitions():
    if not DEFINITIONS_DIR.exists():
        return {"definitions": [], "directory": str(DEFINITIONS_DIR)}
    definitions = sorted(
        d.name for d in DEFINITIONS_DIR.iterdir()
        if d.is_dir() and (d / "transformation_definition.md").exists()
    )
    return {"definitions": definitions, "directory": str(DEFINITIONS_DIR)}


@app.post("/transform")
def transform(req: TransformRequest):
    tracer = trace.get_tracer("transform-service")
    with tracer.start_as_current_span("transform.exec") as span:
        span.set_attribute("transform.definition", req.definition)

        result, engine = _run_transform(req)

        span.set_attribute("transform.engine", engine)
        return {"result": result, "engine": engine, "definition": req.definition}


def _run_transform(req: TransformRequest) -> tuple[dict, str]:
    """Try atx CLI first; fall back to the local normaliser implementation."""
    if shutil.which("atx"):
        try:
            return _run_atx(req.definition, req.payload), "atx"
        except subprocess.CalledProcessError as e:
            logger.error("atx exec failed (%s): %s", e.returncode, (e.stderr or "")[:500])
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error("atx exec failed: %s", e)

    if req.definition in LOCAL_FALLBACKS:
        logger.info("Using local fallback for %s", req.definition)
        return normalise(req.payload, max_tokens=req.max_tokens), "local-fallback"

    raise HTTPException(
        status_code=503,
        detail=(
            f"atx CLI unavailable and no local fallback exists for "
            f"definition {req.definition!r}"
        ),
    )


def _run_atx(definition: str, payload: dict) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(payload, f, default=str)
        src_path = pathlib.Path(f.name)

    out_path = src_path.parent / f"transformed_{src_path.stem}.json"
    try:
        subprocess.run(
            [
                "atx", "custom", "def", "exec",
                "--definition",  definition,
                "--source-path", str(src_path),
                "--output-path", str(out_path),
                "--trust-all-tools",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return json.loads(out_path.read_text())
    finally:
        src_path.unlink(missing_ok=True)
        if out_path.exists():
            out_path.unlink()
