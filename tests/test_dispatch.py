"""Tests for the dispatch service and triage+dispatch integration."""

from unittest.mock import AsyncMock, patch

from app.pipeline.triage.agent import TriageResult


def _mock_triage_result() -> TriageResult:
    return TriageResult(
        severity="P1",
        category="payment-processing",
        affected_component="Spree::Payment#process!",
        technical_summary="Critical payment gateway failure causing 502 errors during checkout.",
        root_cause_hypothesis="Stripe webhook handler timeout due to missing retry logic.",
        suggested_assignee="payments-team",
        confidence=0.92,
        recommended_actions=[
            "Check Stripe dashboard for webhook delivery failures",
            "Review payment timeout configuration",
            "Add circuit breaker to payment gateway calls",
        ],
        related_files=[
            {"path": "app/models/spree/payment.rb", "relevance": "Payment processing"},
            {"path": "app/services/stripe_gateway.rb", "relevance": "Stripe integration"},
        ],
        tokens_in=1500,
        tokens_out=500,
    )


async def test_triage_creates_ticket(client, monkeypatch):
    """Triage auto-creates a ticket after successful analysis."""
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")

    create_resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "oncall@example.com",
            "description": "Payment gateway returning 502 — all checkout attempts failing for the last 10 minutes.",
        },
    )
    incident_id = create_resp.json()["id"]

    with patch(
        "app.routes.incidents.run_triage",
        new_callable=AsyncMock,
        return_value=_mock_triage_result(),
    ):
        resp = await client.post(f"/api/incidents/{incident_id}/triage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dispatched"
    assert body["severity"] == "P1"

    # Verify dispatch panel shows on detail page
    detail_resp = await client.get(f"/incidents/{incident_id}")
    assert detail_resp.status_code == 200
    html = detail_resp.text
    assert "Dispatch Actions" in html
    assert "Ticket created" in html
    assert "payments-team" in html

    # Verify incident ID appears in dispatch outputs
    short_id = incident_id[:8]
    assert f"INC-{short_id}" in html or incident_id in html


async def test_triage_creates_notifications(client, monkeypatch):
    """Triage auto-sends email and chat notifications."""
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")

    create_resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "sre@example.com",
            "description": "Inventory count mismatch — products showing as in-stock but orders failing with out-of-stock errors.",
        },
    )
    incident_id = create_resp.json()["id"]

    result = _mock_triage_result()

    with patch(
        "app.routes.incidents.run_triage",
        new_callable=AsyncMock,
        return_value=result,
    ):
        resp = await client.post(f"/api/incidents/{incident_id}/triage")

    assert resp.status_code == 200

    # Check dispatch panel shows notifications with incident ID
    detail_resp = await client.get(f"/incidents/{incident_id}")
    html = detail_resp.text
    assert "Dispatch Actions" in html
    assert "Email sent" in html
    assert "Chat notification sent" in html
    assert "#incidents" in html
    assert "Mock integrations" in html
    assert incident_id in html  # Full ID appears in dispatch details


async def test_full_e2e_flow(client, monkeypatch):
    """Full E2E: submit incident → triage → ticket + notifications."""
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")

    # Step 1: Submit incident
    create_resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "user@shop.com",
            "description": "Users report that the search function returns no results for any query since the last deployment.",
        },
    )
    assert create_resp.status_code == 201
    incident_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "submitted"

    # Step 2: Triage
    with patch(
        "app.routes.incidents.run_triage",
        new_callable=AsyncMock,
        return_value=_mock_triage_result(),
    ):
        triage_resp = await client.post(f"/api/incidents/{incident_id}/triage")

    assert triage_resp.status_code == 200
    assert triage_resp.json()["status"] == "dispatched"
    assert triage_resp.json()["severity"] == "P1"
    assert triage_resp.json()["confidence"] == 0.92

    # Step 3: Verify full detail page
    detail_resp = await client.get(f"/incidents/{incident_id}")
    assert detail_resp.status_code == 200
    html = detail_resp.text

    # All sections should be visible
    assert "Triage Results" in html
    assert "payment-processing" in html
    assert "Dispatch Actions" in html
    assert "Ticket created" in html
    assert "Mock integrations" in html
    assert "92" in html  # confidence percentage

    # Step 4: API shows triage results
    api_resp = await client.get(f"/api/incidents/{incident_id}")
    body = api_resp.json()
    assert body["severity"] == "P1"
    assert len(body["recommended_actions"]) == 3
    assert len(body["related_files"]) == 2
