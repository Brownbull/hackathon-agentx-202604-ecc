import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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


async def _ensure_seed(db: AsyncSession) -> None:
    """Re-seed if DB is empty in development mode."""
    if settings.app_env != "development":
        return
    count_result = await db.execute(select(func.count(Incident.id)))
    if count_result.scalar_one() == 0:
        await seed_database(db)


async def _recent_incidents(db: AsyncSession, limit: int = 6) -> list[Incident]:
    """Fetch recent incidents for sidebar."""
    query = (
        select(Incident)
        .order_by(Incident.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


def _base_context(page: str, recent: list[Incident]) -> dict:
    """Common template context for all dashboard pages."""
    has_anthropic = bool(settings.anthropic_api_key)
    has_langchain = bool(settings.google_api_key or settings.groq_api_key)
    return {
        "page": page,
        "recent_incidents": recent,
        "triage_provider": getattr(settings, "triage_provider", "anthropic"),
        "has_anthropic": has_anthropic,
        "has_langchain": has_langchain,
        "now": datetime.now(timezone.utc),
    }


@router.get("/")
async def index(db: AsyncSession = Depends(get_db)):
    """Home page — redirect to incident list."""
    await _ensure_seed(db)
    return RedirectResponse(url="/incidents", status_code=302)


PAGE_SIZE = 20

# Allowed sort columns and their ORM attributes
_SORT_COLUMNS = {
    "id": Incident.id,
    "status": Incident.status,
    "severity": Incident.severity,
    "description": Incident.description,
    "engine": Incident.triage_engine,
    "reporter": Incident.reporter_email,
    "created": Incident.created_at,
}


@router.get("/incidents", response_class=HTMLResponse)
async def incident_list_page(
    request: Request,
    page: int = 1,
    sort: str = "created",
    order: str = "desc",
    status: str = "",
    severity: str = "",
    engine: str = "",
    db: AsyncSession = Depends(get_db),
):
    """List incidents with pagination, sorting, and filtering."""
    await _ensure_seed(db)

    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE

    # Base query
    query = select(Incident).options(selectinload(Incident.attachments))
    count_query = select(func.count(Incident.id))

    # Filters
    if status:
        query = query.where(Incident.status == status)
        count_query = count_query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
        count_query = count_query.where(Incident.severity == severity)
    if engine:
        query = query.where(Incident.triage_engine == engine)
        count_query = count_query.where(Incident.triage_engine == engine)

    # Sorting
    sort_col = _SORT_COLUMNS.get(sort, Incident.created_at)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Total count (filtered)
    total = (await db.execute(count_query)).scalar_one()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)

    # Paginate
    query = query.offset(offset).limit(PAGE_SIZE)
    result = await db.execute(query)
    incidents = result.scalars().all()

    recent = await _recent_incidents(db)

    return templates.TemplateResponse(
        request,
        "incidents/dashboard_list.html",
        context={
            **_base_context("list", recent),
            "incidents": incidents,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "page_size": PAGE_SIZE,
            "sort": sort,
            "order": order,
            "filter_status": status,
            "filter_severity": severity,
            "filter_engine": engine,
        },
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
    q = "".join(c for c in q.strip() if c.isalnum() or c == "-")[:8]

    if q:
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

    recent = await _recent_incidents(db)

    return templates.TemplateResponse(
        request,
        "incidents/dashboard_list.html",
        context={
            **_base_context("list", recent),
            "incidents": incidents,
            "total": len(incidents),
            "page": 1,
            "total_pages": 1,
            "page_size": PAGE_SIZE,
            "sort": "created",
            "order": "desc",
            "filter_status": "",
            "filter_severity": "",
            "filter_engine": "",
            "search_query": q,
        },
    )


@router.get("/incidents/new", response_class=HTMLResponse)
async def incident_new_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Submit a new incident form."""
    recent = await _recent_incidents(db)
    return templates.TemplateResponse(
        request,
        "incidents/dashboard_submit.html",
        context=_base_context("new", recent),
    )


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail_page(
    request: Request,
    incident_id: uuid.UUID,
    view: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Incident detail page (detail or chat view)."""
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

    recent = await _recent_incidents(db)

    if not incident:
        return templates.TemplateResponse(
            request,
            "incidents/dashboard_not_found.html",
            context=_base_context("detail", recent),
            status_code=404,
        )

    template = "incidents/dashboard_chat.html" if view == "chat" else "incidents/dashboard_detail.html"

    # Build explanation layers for triaged incidents
    explanations = None
    if incident.severity:
        from app.pipeline.explain import build_explanations
        explanations = build_explanations(incident)

    return templates.TemplateResponse(
        request,
        template,
        context={
            **_base_context("detail", recent),
            "incident": incident,
            "explanations": explanations,
        },
    )
