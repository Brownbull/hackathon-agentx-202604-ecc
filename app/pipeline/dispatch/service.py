"""Dispatch service — creates ticket and sends notifications after triage.

This is a mock/log-based implementation per hackathon scope (V3: Deliver, Don't Design).
Real integrations (Jira, PagerDuty, SendGrid) would implement the same interface.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident
from app.models.notification import Notification, NotificationType
from app.models.ticket import Ticket, TicketStatus

logger = logging.getLogger(__name__)

# Mock on-call roster — in production, this would come from PagerDuty/OpsGenie
ONCALL_ROSTER = {
    "payments-team": "payments-oncall@example.com",
    "platform-team": "platform-oncall@example.com",
    "frontend-team": "frontend-oncall@example.com",
    "infrastructure-team": "infra-oncall@example.com",
    "security-team": "security-oncall@example.com",
    "fulfillment-team": "fulfillment-oncall@example.com",
}

CHAT_CHANNEL = "#incidents"

SEVERITY_EMOJI = {"P1": "\u2757", "P2": "\u26a0\ufe0f", "P3": "\u2139\ufe0f", "P4": "\u25cb"}


@dataclass(frozen=True)
class DispatchResult:
    """Result of dispatching an incident."""
    ticket_id: str
    email_sent: bool
    email_recipient: str
    chat_sent: bool
    chat_channel: str


def _severity_str(severity) -> str:
    """Extract severity string whether it's an enum or raw string."""
    if severity is None:
        return "P?"
    return severity.value if hasattr(severity, "value") else str(severity)


def _build_ticket_title(incident: Incident) -> str:
    severity = _severity_str(incident.severity)
    category = incident.category or "unknown"
    # Take first sentence of description as short summary
    short = incident.description.split(".")[0][:80]
    return f"[{severity}] {category}: {short}"


def _short_id(incident: Incident) -> str:
    """First 8 chars of the incident UUID."""
    return str(incident.id)[:8]


def _build_ticket_body(incident: Incident) -> str:
    parts: list[str] = []

    parts.append(f"**Incident ID:** `{incident.id}`")

    if incident.technical_summary:
        parts.append(f"## Technical Summary\n\n{incident.technical_summary}")

    if incident.root_cause_hypothesis:
        parts.append(f"## Root Cause Hypothesis\n\n{incident.root_cause_hypothesis}")

    if incident.recommended_actions:
        actions = "\n".join(f"- {a}" for a in incident.recommended_actions)
        parts.append(f"## Recommended Actions\n\n{actions}")

    if incident.related_files:
        files = "\n".join(
            f"- `{f['path']}` — {f.get('relevance', '')}"
            if isinstance(f, dict) else f"- `{f}`"
            for f in incident.related_files
        )
        parts.append(f"## Related Files\n\n{files}")

    parts.append(f"\n---\n*Reporter: {incident.reporter_email}*")
    return "\n\n".join(parts)


async def dispatch_incident(
    incident: Incident,
    db: AsyncSession,
) -> DispatchResult:
    """Create ticket and send notifications for a triaged incident.

    Args:
        incident: The triaged incident (must have severity/category populated).
        db: Database session.

    Returns:
        DispatchResult with ticket and notification details.
    """
    # --- Create ticket ---
    title = _build_ticket_title(incident)
    body = _build_ticket_body(incident)
    assignee = incident.suggested_assignee

    ticket = Ticket(
        incident_id=incident.id,
        title=title,
        body=body,
        status=TicketStatus.OPEN,
        labels={"severity": _severity_str(incident.severity),
                "category": incident.category},
        assignee=assignee,
    )
    db.add(ticket)
    await db.flush()  # get ticket ID

    logger.info(
        "Ticket created: %s — %s (assigned: %s)",
        ticket.id, title, assignee,
    )

    # --- Email notification to on-call ---
    oncall_email = ONCALL_ROSTER.get(assignee or "", "sre-oncall@example.com")
    severity_str = _severity_str(incident.severity)
    short = _short_id(incident)
    email_subject = f"[{severity_str}] INC-{short}: {title[:50]}"
    # Mock URLs — in production these would be real app URLs
    ack_url = f"https://sre-triage.example.com/api/incidents/{incident.id}/acknowledge"
    reject_url = f"https://sre-triage.example.com/incidents/{incident.id}#reject"
    detail_url = f"https://sre-triage.example.com/incidents/{incident.id}"

    email_body = (
        f"A new {severity_str} incident has been triaged and assigned to your team.\n\n"
        f"Incident ID: {incident.id}\n"
        f"Short ref:   INC-{short}\n"
        f"Ticket:      {ticket.id}\n"
        f"Category:    {incident.category}\n"
        f"Component:   {incident.affected_component}\n\n"
        f"{incident.technical_summary or incident.description[:500]}\n\n"
        f"Recommended actions:\n"
    )
    if incident.recommended_actions:
        email_body += "\n".join(f"  - {a}" for a in incident.recommended_actions)

    email_body += (
        f"\n\n"
        f"─────────────────────────────────────────────\n"
        f"ACTION REQUIRED\n\n"
        f"  [✓ ACKNOWLEDGE] {ack_url}\n"
        f"  [✗ NOT MY TEAM] {reject_url}\n\n"
        f"  View incident:  {detail_url}\n"
        f"─────────────────────────────────────────────\n"
    )

    email_notification = Notification(
        incident_id=incident.id,
        type=NotificationType.EMAIL,
        recipient=oncall_email,
        subject=email_subject,
        body=email_body,
        sent=True,  # Mock: always succeeds
        sent_at=datetime.now(timezone.utc),
    )
    db.add(email_notification)

    logger.info("Email notification sent to %s: %s", oncall_email, email_subject)

    # --- Chat notification ---
    emoji = SEVERITY_EMOJI.get(severity_str, "")
    chat_body = (
        f"{emoji} *{severity_str} Incident* — INC-{short}\n"
        f"Category: {incident.category}\n"
        f"Component: {incident.affected_component}\n"
        f"Assigned: {assignee}\n"
        f"Incident: {incident.id}\n"
        f"Ticket: {ticket.id}\n"
        f"Confidence: {(incident.confidence or 0) * 100:.0f}%\n"
        f"\n"
        f"[✓ Acknowledge]({ack_url}) · "
        f"[✗ Not my team]({reject_url}) · "
        f"[View details]({detail_url})"
    )

    chat_notification = Notification(
        incident_id=incident.id,
        type=NotificationType.CHAT,
        recipient=CHAT_CHANNEL,
        subject=None,
        body=chat_body,
        sent=True,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(chat_notification)

    logger.info("Chat notification sent to %s", CHAT_CHANNEL)

    await db.commit()

    return DispatchResult(
        ticket_id=str(ticket.id),
        email_sent=True,
        email_recipient=oncall_email,
        chat_sent=True,
        chat_channel=CHAT_CHANNEL,
    )