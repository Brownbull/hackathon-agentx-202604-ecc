import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import cast, select, func, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.incident import Incident
from app.services.seed_data import seed_database

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

_seed_checked = False


async def _ensure_seed(db: AsyncSession) -> None:
    """Re-seed if DB is empty in development mode. Runs once per process."""
    global _seed_checked
    if _seed_checked or settings.app_env != "development":
        return
    _seed_checked = True
    count_result = await db.execute(select(func.count(Incident.id)))
    if count_result.scalar_one() == 0:
        await seed_database(db)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    """Home page — shows recent incidents."""
    await _ensure_seed(db)
    query = (
        select(Incident)
        .options(selectinload(Incident.attachments))
        .order_by(Incident.created_at.desc())
        .limit(20)
    )
    result = await db.execute(query)
    incidents = result.scalars().all()

    count_result = await db.execute(select(func.count(Incident.id)))
    total = count_result.scalar_one()
    return templates.TemplateResponse(
        request,
        "incidents/list.html",
        context={"incidents": incidents, "total": total, "page": "list"},
    )


@router.get("/incidents", response_class=HTMLResponse)
async def incident_list_page(request: Request, db: AsyncSession = Depends(get_db)):
    """List all incidents."""
    await _ensure_seed(db)
    query = (
        select(Incident)
        .options(selectinload(Incident.attachments))
        .order_by(Incident.created_at.desc())
        .limit(100)
    )
    result = await db.execute(query)
    incidents = result.scalars().all()

    count_result = await db.execute(select(func.count(Incident.id)))
    total = count_result.scalar_one()

    return templates.TemplateResponse(
        request,
        "incidents/list.html",
        context={"incidents": incidents, "total": total, "page": "list"},
    )


@router.get("/incidents/search", response_class=HTMLResponse)
async def incident_search_page(
    request: Request,
    q: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Search incidents by partial ID (first 1-8 chars of UUID)."""
    await _ensure_seed(db)
    incidents = []
    # Sanitize: strip, remove spaces, cap at 8 chars, alphanumeric only
    q = "".join(c for c in q.strip() if c.isalnum() or c == "-")[:8]

    if q:
        # Search by partial UUID (cast to text and ILIKE)
        pattern = f"{q}%"
        query = (
            select(Incident)
            .options(selectinload(Incident.attachments))
            .where(cast(Incident.id, String).ilike(pattern))
            .order_by(Incident.created_at.desc())
            .limit(20)
        )
        result = await db.execute(query)
        incidents = list(result.scalars().all())

    return templates.TemplateResponse(
        request,
        "incidents/list.html",
        context={
            "incidents": incidents,
            "total": len(incidents),
            "page": "list",
            "search_query": q,
        },
    )


@router.get("/incidents/new", response_class=HTMLResponse)
async def incident_new_page(request: Request):
    """Submit a new incident form."""
    return templates.TemplateResponse(
        request,
        "incidents/submit.html",
        context={"page": "new"},
    )


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail_page(
    request: Request,
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Incident detail page."""
    query = (
        select(Incident)
        .options(
            selectinload(Incident.attachments),
            selectinload(Incident.ticket),
            selectinload(Incident.notifications),
        )
        .where(Incident.id == incident_id)
    )
    result = await db.execute(query)
    incident = result.scalar_one_or_none()

    if not incident:
        return templates.TemplateResponse(
            request,
            "incidents/not_found.html",
            context={"page": "detail"},
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "incidents/detail.html",
        context={"incident": incident, "page": "detail"},
    )
