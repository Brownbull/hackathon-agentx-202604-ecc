"""Managed Agents triage provider — Anthropic cloud-hosted autonomous agent.

The agent provisions a container, clones the codebase, explores files with
Glob/Grep, follows import chains, and submits a structured triage via
custom tool_use. Takes 3-5 minutes but finds things single-call engines can't.

Falls back to a keyword-based stub when MANAGED_AGENT_ID is not configured.
"""

import asyncio
import logging

import httpx

from app.config import settings
from app.pipeline.triage.agent import TriageResult

logger = logging.getLogger(__name__)

API_BASE = "https://api.anthropic.com/v1"
POLL_INTERVAL_S = 3
MAX_POLL_S = 420  # 7 minute timeout (agent takes 3-5min with Haiku)


class ManagedProvider:
    """Triage provider using Anthropic Managed Agents API (or keyword stub fallback)."""

    async def triage(
        self,
        description: str,
        codebase_context: str,
        attachment_descriptions: list[str] | None = None,
    ) -> TriageResult:
        if settings.managed_agent_id and settings.managed_environment_id and settings.anthropic_api_key:
            return await self._run_managed(description, codebase_context, attachment_descriptions)
        return self._run_stub(description)

    async def _run_managed(
        self,
        description: str,
        codebase_context: str,
        attachment_descriptions: list[str] | None = None,
    ) -> TriageResult:
        """Run triage via Anthropic Managed Agents REST API."""
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "managed-agents-2026-04-01",
            "content-type": "application/json",
        }

        # Build the incident message
        parts = [f"## Incident Report\n\n{description}"]
        if attachment_descriptions:
            parts.append("\n## Attached Files\n" + "\n".join(f"- {d}" for d in attachment_descriptions))
        parts.append(f"\n## Codebase Context\n\n{codebase_context}")
        parts.append(
            "\nAnalyze this incident against the codebase. "
            "Use your tools to explore the repository, then submit your triage assessment "
            "using the submit_triage tool."
        )
        message_text = "\n".join(parts)

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            # 1. Create session
            logger.info("ManagedProvider: creating session (agent=%s)", settings.managed_agent_id)
            session_resp = await client.post(
                f"{API_BASE}/sessions",
                headers=headers,
                json={
                    "agent": settings.managed_agent_id,
                    "environment_id": settings.managed_environment_id,
                },
            )
            if session_resp.status_code != 200:
                body = session_resp.text
                logger.error("Managed agent session creation failed: %d %s", session_resp.status_code, body)
                raise RuntimeError(f"Managed agent session creation failed ({session_resp.status_code}): {body}")

            session = session_resp.json()
            sid = session["id"]
            logger.info("ManagedProvider: session created: %s", sid)

            # 2. Send incident
            await client.post(
                f"{API_BASE}/sessions/{sid}/events",
                headers=headers,
                json={
                    "events": [{"type": "user.message", "content": [{"type": "text", "text": message_text}]}]
                },
            )
            logger.info("ManagedProvider: incident sent, polling for completion...")

            # 3. Poll until idle (agent clones repo, reads files, submits triage)
            elapsed = 0.0
            while elapsed < MAX_POLL_S:
                await asyncio.sleep(POLL_INTERVAL_S)
                elapsed += POLL_INTERVAL_S

                status_resp = await client.get(f"{API_BASE}/sessions/{sid}", headers=headers)
                status_resp.raise_for_status()
                status = status_resp.json().get("status", "")

                if status == "idle":
                    logger.info("ManagedProvider: agent completed after %.0fs", elapsed)
                    break
                elif status in ("error", "failed", "terminated"):
                    raise RuntimeError(f"Managed agent session failed: {status}")
                elif int(elapsed) % 30 == 0:
                    logger.info("ManagedProvider: still running (%.0fs elapsed, status=%s)", elapsed, status)
            else:
                raise TimeoutError(f"Managed agent timed out after {MAX_POLL_S}s")

            # 4. Extract submit_triage from events
            events_resp = await client.get(f"{API_BASE}/sessions/{sid}/events", headers=headers)
            events_resp.raise_for_status()
            events = events_resp.json().get("data", [])

            for event in events:
                etype = event.get("type", "")
                if etype in ("agent.custom_tool_use", "agent.tool_use") and event.get("name") == "submit_triage":
                    data = event.get("input", {})
                    return TriageResult(
                        severity=data["severity"],
                        category=data["category"],
                        affected_component=data["affected_component"],
                        technical_summary=data["technical_summary"],
                        root_cause_hypothesis=data["root_cause_hypothesis"],
                        suggested_assignee=data["suggested_assignee"],
                        confidence=data["confidence"],
                        recommended_actions=data["recommended_actions"],
                        related_files=data.get("related_files", []),
                        tokens_in=0,
                        tokens_out=0,
                        engine="managed",
                    )

            raise ValueError("Managed agent did not produce a submit_triage tool_use result")

    def _run_stub(self, description: str) -> TriageResult:
        """Fallback: keyword-based stub when Managed Agent is not configured."""
        logger.info("ManagedProvider: using keyword stub (no MANAGED_AGENT_ID configured)")

        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["outage", "down", "critical", "502", "crash"]):
            severity, category, team = "P1", "infrastructure", "infrastructure-team"
        elif any(kw in desc_lower for kw in ["payment", "checkout", "stripe", "order"]):
            severity, category, team = "P2", "payment-processing", "payments-team"
        elif any(kw in desc_lower for kw in ["auth", "login", "session", "password"]):
            severity, category, team = "P2", "authentication", "security-team"
        else:
            severity, category, team = "P3", "other", "platform-team"

        return TriageResult(
            severity=severity,
            category=category,
            affected_component="Solidus Core (managed assessment)",
            technical_summary=(
                f"[Managed Agent — Stub] Deterministic triage based on keyword matching. "
                f"Patterns consistent with {category} issues detected. "
                f"Configure MANAGED_AGENT_ID and MANAGED_ENVIRONMENT_ID for autonomous agent analysis."
            ),
            root_cause_hypothesis=(
                f"Keyword-based analysis suggests a {category} issue. "
                f"The full Managed Agent would clone the repo and explore files autonomously."
            ),
            suggested_assignee=team,
            confidence=0.40,
            recommended_actions=[
                "Review incident description for key indicators",
                "Check relevant service dashboards",
                "Verify recent deployments for related changes",
                "Escalate to on-call engineer if severity warrants",
                "Configure MANAGED_AGENT_ID for autonomous codebase analysis",
            ],
            related_files=[
                {"path": "core/lib/spree/core.rb", "relevance": "Core framework entry point"},
                {"path": "api/app/controllers/spree/api/base_controller.rb", "relevance": "API base controller"},
            ],
            tokens_in=0,
            tokens_out=0,
            engine="managed",
        )
