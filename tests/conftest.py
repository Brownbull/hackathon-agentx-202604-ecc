import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.models import Base
from app.services.codebase_indexer import CodebaseIndex

# Test engine: NullPool avoids asyncpg connection conflicts across event loops
_test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_test_session = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with _test_session() as session:
        yield session


@pytest.fixture
async def client():
    # Import app here to avoid lifespan issues
    from app.main import app

    app.dependency_overrides[get_db] = _override_get_db

    # Set up empty codebase index (lifespan doesn't run in test transport)
    app.state.codebase_index = CodebaseIndex(repo_path="/tmp/test-repo")

    # Ensure tables exist
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup
    async with _test_engine.begin() as conn:
        for table in ["incident_attachments", "notifications", "tickets", "incidents"]:
            await conn.execute(text(f"DELETE FROM {table}"))

    app.dependency_overrides.clear()


@pytest.fixture
async def db_session():
    """Provide a clean async DB session for unit tests (no HTTP client needed)."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _test_session() as session:
        yield session

    async with _test_engine.begin() as conn:
        for table in ["incident_attachments", "notifications", "tickets", "incidents"]:
            await conn.execute(text(f"DELETE FROM {table}"))
