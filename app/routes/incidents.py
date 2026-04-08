import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.incident import Incident, IncidentAttachment, IncidentStatus
from app.pipeline.dispatch import dispatch_incident
from app.pipeline.triage import run_triage
from app.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse
from app.services.codebase_indexer import CodebaseIndex

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

    incident = Incident(
        reporter_name=data.reporter_name,
        reporter_email=data.reporter_email,
        description=data.description,
        status=IncidentStatus.SUBMITTED,
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
    db: AsyncSession = Depends(get_db),
) -> Incident:
    """Run AI triage on an incident. Updates the incident with triage results."""
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

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Triage unavailable: ANTHROPIC_API_KEY not configured",
        )

    # Update status to triaging
    incident.status = IncidentStatus.TRIAGING
    await db.commit()

    # Get codebase index from app state
    codebase_index: CodebaseIndex = request.app.state.codebase_index

    # Build attachment descriptions for context
    attachment_descriptions: list[str] = []
    for att in incident.attachments:
        attachment_descriptions.append(f"{att.filename} ({att.mime_type}, {att.file_size} bytes)")

    try:
        triage_result = await run_triage(
            description=incident.description,
            codebase_index=codebase_index,
            attachment_descriptions=attachment_descriptions or None,
        )
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
    incident.related_files = triage_result.related_files
    incident.status = IncidentStatus.DISPATCHED

    await db.flush()

    # Auto-dispatch: create ticket + notifications
    dispatch_result = await dispatch_incident(incident, db)

    await db.refresh(incident)
    await db.refresh(incident, attribute_names=["attachments"])

    logger.info(
        "Triage+dispatch complete for %s: severity=%s, confidence=%.2f, "
        "ticket=%s, tokens=%d/%d",
        incident_id,
        triage_result.severity,
        triage_result.confidence,
        dispatch_result.ticket_id,
        triage_result.tokens_in,
        triage_result.tokens_out,
    )

    return incident
