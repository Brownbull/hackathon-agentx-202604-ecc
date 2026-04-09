import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.incident import Incident, IncidentAttachment, IncidentStatus
from app.models.notification import Notification, NotificationType
from app.models.ticket import TicketStatus
from app.pipeline.dispatch import dispatch_incident
from app.pipeline.guardrail import validate_input
from app.pipeline.guardrail.rate_limit import check_rate_limit, record_submission
from app.pipeline.triage import run_triage
from app.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse
from app.services.codebase_indexer import CodebaseIndex, search_files
from app.services.observability import pipeline_span, trace_triage_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "text/plain",
    "application/pdf",
    "application/json",
    "text/csv",
}
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    reporter_email: str = Form(...),
    description: str = Form(...),
    reporter_name: str | None = Form(None),
    files: list[UploadFile] | None = None,
    db: AsyncSession = Depends(get_db),
) -> Incident:
    """Create a new incident with optional file attachments."""
    # Validate input via schema
    try:
        data = IncidentCreate(
            reporter_name=reporter_name,
            reporter_email=reporter_email,
            description=description,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Rate limiting
    rate_result = check_rate_limit(data.reporter_email)
    if not rate_result.allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({rate_result.limit}/hour). "
                   f"Retry after {rate_result.retry_after_seconds}s.",
        )

    # Guardrail checks
    with pipeline_span("guardrail", {"reporter": data.reporter_email}):
        guardrail = validate_input(data.description)
    if guardrail.rejected:
        raise HTTPException(status_code=400, detail=guardrail.rejection_reason)

    # Record submission for rate limiting
    record_submission(data.reporter_email)

    incident = Incident(
        reporter_name=data.reporter_name,
        reporter_email=data.reporter_email,
        description=data.description,
        status=IncidentStatus.SUBMITTED,
        validation_flags={"flags": guardrail.flags, "passed": guardrail.passed},
        injection_score=guardrail.injection_score,
    )
    db.add(incident)
    await db.flush()  # Get the ID

    # Handle file uploads
    if files:
        upload_dir = Path(settings.upload_dir) / str(incident.id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Validate all files before writing any to disk
        validated_files: list[tuple[str, bytes, str]] = []
        for upload_file in files:
            if not upload_file.filename:
                continue

            content_type = upload_file.content_type or "application/octet-stream"
            if content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{content_type}' not allowed. Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
                )

            content = await upload_file.read()
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{upload_file.filename}' exceeds {settings.max_upload_size_mb}MB limit",
                )

            validated_files.append((upload_file.filename, content, content_type))

        # Write validated files to disk
        for original_name, content, content_type in validated_files:
            safe_filename = f"{uuid.uuid4().hex}_{Path(original_name).name}"
            file_path = upload_dir / safe_filename
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            attachment = IncidentAttachment(
                incident_id=incident.id,
                filename=original_name,
                file_path=str(file_path),
                mime_type=content_type,
                file_size=len(content),
            )
            db.add(attachment)

    await db.commit()
    await db.refresh(incident, attribute_names=["attachments"])
    return incident


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all incidents, newest first."""
    # Count
    count_result = await db.execute(select(func.count(Incident.id)))
    total = count_result.scalar_one()

    # Fetch
    query = (
        select(Incident)
        .options(selectinload(Incident.attachments))
        .order_by(Incident.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    incidents = result.scalars().all()

    return {"incidents": incidents, "total": total}


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Incident:
    """Get incident details by ID."""
    query = (
        select(Incident)
        .options(selectinload(Incident.attachments))
        .where(Incident.id == incident_id)
    )
    result = await db.execute(query)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return incident


@router.post("/{incident_id}/triage", response_model=IncidentResponse)
async def triage_incident(
    incident_id: uuid.UUID,
    request: Request,
    provider: str = "",
    db: AsyncSession = Depends(get_db),
) -> Incident:
    """Run AI triage on an incident. Updates the incident with triage results.

    Args:
        provider: Optional override — "anthropic", "langchain", or "managed".
                  Falls back to TRIAGE_PROVIDER env var if empty.
    """
    query = (
        select(Incident)
        .options(selectinload(Incident.attachments))
        .where(Incident.id == incident_id)
    )
    result = await db.execute(query)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status in (IncidentStatus.DISPATCHED, IncidentStatus.RESOLVED):
        raise HTTPException(
            status_code=409,
            detail="Incident already triaged",
        )

    # Resolve which provider to use
    triage_provider = provider if provider in ("anthropic", "langchain", "managed") else settings.triage_provider

    # API key check only needed for anthropic provider
    if triage_provider == "anthropic" and not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Triage unavailable: ANTHROPIC_API_KEY not configured",
        )
    if triage_provider == "langchain" and not settings.google_api_key and not settings.groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="LangChain provider requires GOOGLE_API_KEY or GROQ_API_KEY",
        )

    # Update status to triaging
    incident.status = IncidentStatus.TRIAGING
    await db.commit()

    # Get codebase index and knowledge loader from app state
    codebase_index: CodebaseIndex = request.app.state.codebase_index
    knowledge_loader = getattr(request.app.state, "knowledge_loader", None)

    # Build attachment descriptions for context
    attachment_descriptions: list[str] = []
    for att in incident.attachments:
        attachment_descriptions.append(f"{att.filename} ({att.mime_type}, {att.file_size} bytes)")

    # --- Pipeline stage 1: Guardrail (already ran at submission) ---
    guardrail_data = {
        "description": incident.description[:500],
        "passed": (incident.validation_flags or {}).get("passed", True),
        "injection_score": incident.injection_score or 0.0,
        "flags": (incident.validation_flags or {}).get("flags", []),
    }

    # --- Pipeline stage 2: Context retrieval ---
    context_files = search_files(codebase_index, incident.description, max_results=5)
    context_data = {
        "search_query": incident.description[:200],
        "total_indexed_files": codebase_index.file_count,
        "files_found": len(context_files),
        "files": [
            {"path": f.path, "extension": f.extension, "size_lines": len(f.first_lines.splitlines())}
            for f in context_files
        ],
    }

    # --- Pipeline stage 3: Triage (LLM call) ---
    import time as _time

    try:
        t0 = _time.monotonic()
        with pipeline_span("triage", {"incident_id": str(incident_id)}):
            triage_result = await run_triage(
                description=incident.description,
                codebase_index=codebase_index,
                attachment_descriptions=attachment_descriptions or None,
                provider_override=triage_provider,
                knowledge_loader=knowledge_loader,
            )
        triage_ms = (_time.monotonic() - t0) * 1000
    except Exception:
        logger.exception("Triage failed for incident %s", incident_id)
        incident.status = IncidentStatus.SUBMITTED  # revert status
        await db.commit()
        raise HTTPException(status_code=502, detail="Triage agent failed")

    # Update incident with triage results
    incident.severity = triage_result.severity
    incident.category = triage_result.category
    incident.affected_component = triage_result.affected_component
    incident.technical_summary = triage_result.technical_summary
    incident.root_cause_hypothesis = triage_result.root_cause_hypothesis
    incident.suggested_assignee = triage_result.suggested_assignee
    incident.confidence = triage_result.confidence
    incident.recommended_actions = triage_result.recommended_actions
    incident.related_files = [f.model_dump() for f in triage_result.related_files]
    incident.triage_engine = triage_result.engine
    incident.triage_tokens_in = triage_result.tokens_in
    incident.triage_tokens_out = triage_result.tokens_out
    incident.status = IncidentStatus.DISPATCHED

    await db.flush()

    # --- Pipeline stage 4: Dispatch ---
    with pipeline_span("dispatch", {"incident_id": str(incident_id)}):
        dispatch_result = await dispatch_incident(incident, db)

    # --- Record full pipeline trace in Langfuse ---
    trace_triage_pipeline(
        str(incident_id),
        guardrail=guardrail_data,
        context_retrieval=context_data,
        generation={
            "model": triage_result.engine,
            "input": incident.description,
            "output": str({
                "severity": triage_result.severity,
                "category": triage_result.category,
                "confidence": triage_result.confidence,
                "affected_component": triage_result.affected_component,
                "technical_summary": triage_result.technical_summary[:300],
                "root_cause_hypothesis": triage_result.root_cause_hypothesis[:200],
                "recommended_actions_count": len(triage_result.recommended_actions),
                "related_files_count": len(triage_result.related_files),
            }),
            "tokens_in": triage_result.tokens_in,
            "tokens_out": triage_result.tokens_out,
            "duration_ms": triage_ms,
            "severity": triage_result.severity,
            "category": triage_result.category,
            "confidence": triage_result.confidence,
            "affected_component": triage_result.affected_component,
            "suggested_assignee": triage_result.suggested_assignee,
            "engine": triage_result.engine,
            "attachments": attachment_descriptions,
        },
        dispatch={
            "ticket_id": dispatch_result.ticket_id,
            "email_sent": dispatch_result.email_sent,
            "email_recipient": dispatch_result.email_recipient,
            "chat_sent": dispatch_result.chat_sent,
            "chat_channel": dispatch_result.chat_channel,
        },
    )

    await db.refresh(incident)
    await db.refresh(incident, attribute_names=["attachments"])

    logger.info(
        "Triage+dispatch complete for %s: severity=%s, confidence=%.2f, "
        "ticket=%s, tokens=%d/%d, triage_ms=%.0f",
        incident_id,
        triage_result.severity,
        triage_result.confidence,
        dispatch_result.ticket_id,
        triage_result.tokens_in,
        triage_result.tokens_out,
        triage_ms,
    )

    return incident


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
async def acknowledge_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Incident:
    """Acknowledge a dispatched incident — moves ticket to in_progress."""
    query = (
        select(Incident)
        .options(
            selectinload(Incident.attachments),
            selectinload(Incident.ticket),
        )
        .where(Incident.id == incident_id)
    )
    result = await db.execute(query)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status != IncidentStatus.DISPATCHED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot acknowledge incident in '{incident.status.value}' status",
        )

    if incident.ticket:
        incident.ticket.status = TicketStatus.IN_PROGRESS

    await db.commit()
    await db.refresh(incident)
    await db.refresh(incident, attribute_names=["attachments"])

    logger.info("Incident %s acknowledged", incident_id)
    return incident


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    resolution_type: str = Form("fix"),
    resolution_notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> Incident:
    """Resolve an incident — closes ticket and notifies reporter."""
    query = (
        select(Incident)
        .options(
            selectinload(Incident.attachments),
            selectinload(Incident.ticket),
        )
        .where(Incident.id == incident_id)
    )
    result = await db.execute(query)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status not in (IncidentStatus.DISPATCHED, IncidentStatus.TRIAGING):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot resolve incident in '{incident.status.value}' status",
        )

    # Update incident
    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = datetime.now(timezone.utc)
    incident.resolution_type = resolution_type
    incident.resolution_notes = resolution_notes or None

    # Close ticket
    if incident.ticket:
        incident.ticket.status = TicketStatus.RESOLVED

    # Notify reporter
    short_id = str(incident.id)[:8]
    reporter_notification = Notification(
        incident_id=incident.id,
        type=NotificationType.EMAIL,
        recipient=incident.reporter_email,
        subject=f"[Resolved] INC-{short_id}: Your incident has been resolved",
        body=(
            f"Your incident INC-{short_id} has been resolved.\n\n"
            f"Resolution: {resolution_type}\n"
            f"{('Notes: ' + resolution_notes) if resolution_notes else ''}\n\n"
            f"If the issue persists, please submit a new incident."
        ),
        sent=True,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(reporter_notification)

    await db.commit()
    await db.refresh(incident)
    await db.refresh(incident, attribute_names=["attachments"])

    logger.info("Incident %s resolved: type=%s", incident_id, resolution_type)
    return incident


@router.get("/{incident_id}/attachments/{attachment_id}")
async def get_attachment(
    incident_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve an attachment file by ID."""
    query = select(IncidentAttachment).where(
        IncidentAttachment.id == attachment_id,
        IncidentAttachment.incident_id == incident_id,
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Attachment file missing")

    return FileResponse(
        path=str(file_path),
        media_type=attachment.mime_type,
        filename=attachment.filename,
    )
