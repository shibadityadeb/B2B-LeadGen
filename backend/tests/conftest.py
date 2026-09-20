"""Test fixtures.

Tests run against an in-memory SQLite database so they need no external
services. The models are dialect-neutral (JSONB is applied as a PostgreSQL
variant only), so the same schema is exercised.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
# Tests must not pay the real politeness delay between queries.
os.environ["SEARCH_DELAY_SECONDS"] = "0"
os.environ["CRAWL_DELAY_SECONDS"] = "0"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_session
from app.main import app
from app.models import Base
from app.workers.queue import JobQueue, get_job_queue


class RecordingJobQueue(JobQueue):
    """Captures enqueued jobs instead of running them, so API tests stay fast
    and deterministic. Pipeline behaviour is tested directly in test_discovery."""

    name = "recording"

    def __init__(self):
        self.jobs: list[tuple[str, dict]] = []

    async def enqueue(self, name: str, **payload) -> None:
        self.jobs.append((name, payload))

    async def shutdown(self) -> None:
        self.jobs.clear()

    @property
    def pending(self) -> int:
        return 0


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session


@pytest.fixture
def job_queue() -> RecordingJobQueue:
    return RecordingJobQueue()


@pytest.fixture
async def client(session, job_queue):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_job_queue] = lambda: job_queue
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
