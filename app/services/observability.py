"""Observability setup — OpenTelemetry tracing + Langfuse LLM observability.

Instruments FastAPI, SQLAlchemy, and HTTPX automatically.
Provides custom span helpers for pipeline stages.
"""

import logging
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from app.config import settings

logger = logging.getLogger(__name__)

# Global tracer
_tracer: trace.Tracer | None = None


def setup_telemetry() -> None:
    """Initialize OpenTelemetry with console exporter + auto-instrumentation."""
    global _tracer

    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": "0.1.0",
        "deployment.environment": settings.app_env,
    })

    provider = TracerProvider(resource=resource)

    # Console exporter for dev visibility (logs spans to stdout)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("sre-triage-agent", "0.1.0")

    # Auto-instrument FastAPI
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument()
        logger.info("FastAPI auto-instrumented with OpenTelemetry")
    except Exception:
        logger.debug("FastAPI instrumentation skipped (may already be instrumented)")

    # Auto-instrument SQLAlchemy
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
        logger.info("SQLAlchemy auto-instrumented with OpenTelemetry")
    except Exception:
        logger.debug("SQLAlchemy instrumentation skipped")

    # Auto-instrument HTTPX (for Claude API calls)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX auto-instrumented with OpenTelemetry")
    except Exception:
        logger.debug("HTTPX instrumentation skipped")

    logger.info("OpenTelemetry initialized: service=%s, env=%s",
                settings.otel_service_name, settings.app_env)


def get_tracer() -> trace.Tracer:
    """Get the configured tracer (or a no-op tracer if not initialized)."""
    return _tracer or trace.get_tracer("sre-triage-agent")


@contextmanager
def pipeline_span(stage: str, attributes: dict[str, Any] | None = None):
    """Create a traced span for a pipeline stage.

    Usage:
        with pipeline_span("guardrail", {"injection_score": 0.1}):
            result = validate_input(text)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(f"incident.{stage}") as span:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(f"incident.{stage}.{key}", str(value))
        yield span


# --- Langfuse integration for LLM tracing ---

_langfuse_client = None


def get_langfuse():
    """Get or create the Langfuse client (lazy init)."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.langfuse_secret_key or not settings.langfuse_public_key:
        logger.info("Langfuse keys not configured — LLM tracing disabled")
        return None

    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            secret_key=settings.langfuse_secret_key,
            public_key=settings.langfuse_public_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse initialized: host=%s", settings.langfuse_host)
        return _langfuse_client
    except Exception:
        logger.warning("Langfuse initialization failed — LLM tracing disabled", exc_info=True)
        return None


def trace_llm_call(
    incident_id: str,
    model: str,
    input_text: str,
    output_data: dict[str, Any],
    tokens_in: int,
    tokens_out: int,
    duration_ms: float,
) -> None:
    """Record an LLM call in Langfuse for observability."""
    langfuse = get_langfuse()
    if langfuse is None:
        return

    try:
        langfuse_trace = langfuse.trace(
            name="incident-triage",
            metadata={"incident_id": incident_id, "model": model},
        )
        langfuse_trace.generation(
            name="triage-generation",
            model=model,
            input=input_text[:2000],  # cap to avoid huge payloads
            output=str(output_data)[:2000],
            usage={
                "input": tokens_in,
                "output": tokens_out,
                "total": tokens_in + tokens_out,
            },
            metadata={
                "incident_id": incident_id,
                "severity": output_data.get("severity"),
                "category": output_data.get("category"),
                "confidence": output_data.get("confidence"),
                "duration_ms": duration_ms,
            },
        )
        langfuse.flush()
    except Exception:
        logger.warning("Langfuse trace failed", exc_info=True)
