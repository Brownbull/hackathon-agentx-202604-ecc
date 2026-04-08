import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, async_session
from app.models import Base
from app.routes.incidents import router as incidents_api_router
from app.routes.pages import router as pages_router
from app.services.codebase_indexer import build_index
from app.services.observability import setup_telemetry
from app.services.seed_data import seed_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate required config
    if settings.app_env != "development" and not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required in non-development environments")
    # Initialize OpenTelemetry
    setup_telemetry()

    # Startup: create tables (dev convenience — production uses alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Build codebase index at startup
    logger.info("Building codebase index from %s", settings.ecommerce_repo_path)
    app.state.codebase_index = build_index(settings.ecommerce_repo_path)
    logger.info("Codebase index ready: %d files", app.state.codebase_index.file_count)

    # Seed sample data in development
    if settings.app_env == "development":
        async with async_session() as db:
            await seed_database(db)

    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="SRE Triage Agent",
    description="AI-powered SRE Incident Intake & Triage Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# API routes
app.include_router(incidents_api_router)

# HTML page routes (must come after API so /api/incidents takes priority)
app.include_router(pages_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sre-triage-agent"}


@app.get("/api/observability")
async def observability_status():
    """Show observability configuration status."""
    from app.services.observability import get_langfuse
    langfuse = get_langfuse()
    return {
        "opentelemetry": {
            "enabled": True,
            "service_name": settings.otel_service_name,
            "instrumented": ["fastapi", "sqlalchemy", "httpx"],
            "pipeline_spans": ["incident.guardrail", "incident.triage", "incident.dispatch"],
        },
        "langfuse": {
            "enabled": langfuse is not None,
            "host": settings.langfuse_host if langfuse else None,
            "dashboard": f"{settings.langfuse_host}" if langfuse else "Not configured",
        },
        "traces": {
            "description": "Pipeline stages emit OpenTelemetry spans. "
                           "LLM calls are traced via Langfuse with token usage and latency.",
        },
    }
