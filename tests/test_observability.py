"""Tests for observability setup and endpoints."""

from app.services.observability import pipeline_span, get_tracer


def test_get_tracer_returns_tracer():
    tracer = get_tracer()
    assert tracer is not None


def test_pipeline_span_creates_span():
    """Pipeline span context manager works without error."""
    with pipeline_span("test_stage", {"key": "value"}) as span:
        assert span is not None


def test_pipeline_span_no_attributes():
    with pipeline_span("test_stage") as span:
        assert span is not None


async def test_observability_endpoint(client):
    resp = await client.get("/api/observability")
    assert resp.status_code == 200
    body = resp.json()
    assert body["opentelemetry"]["enabled"] is True
    assert "incident.triage" in body["opentelemetry"]["pipeline_spans"]
    assert "incident.guardrail" in body["opentelemetry"]["pipeline_spans"]
    assert "incident.dispatch" in body["opentelemetry"]["pipeline_spans"]
