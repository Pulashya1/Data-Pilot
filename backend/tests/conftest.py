"""Shared pytest fixtures: a real Postgres test database, a fake in-memory
storage backend (no MinIO needed for most tests), and a TestClient wired to both.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import BinaryIO

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://datapilot:datapilot@localhost:5432/datapilot_test"
)
# `app.main`'s lifespan starts a LangGraph Postgres checkpointer straight off `Settings`
# (app/agent/checkpoint.py) — not through the `get_db` override below — so it must be pointed
# at the test database too, and that has to happen before `app.core.config` is first imported
# anywhere (Settings is `@lru_cache`d).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.agent.events import get_event_bus  # noqa: E402
from app.agent.llm import get_llm_client  # noqa: E402
from app.agent.runner import AgentRunner, get_agent_runner  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, get_db  # noqa: E402
from app.core.storage import StorageBackend, get_storage_backend  # noqa: E402
from app.execution.kernel_manager import (  # noqa: E402
    KernelManager,
    get_execution_backend,
    get_kernel_manager,
)
from app.main import app  # noqa: E402
from app.models.chat import ChatMessage  # noqa: E402
from app.models.decision import Decision  # noqa: E402
from app.models.notebook import NotebookCell  # noqa: E402
from app.models.session import UploadSession  # noqa: E402
from tests.fakes import FakeExecutionBackend  # noqa: E402

# NullPool: asyncpg connections are bound to the event loop that created them,
# and pytest-asyncio gives each test its own loop. Pooling would reuse a
# connection across loops and blow up with "Event loop is closed".
_test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
_TestSessionLocal = async_sessionmaker(_test_engine, expire_on_commit=False)


class FakeStorageBackend:
    """In-memory stand-in for `StorageBackend`, used so most tests don't need MinIO."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, key: str, body: BinaryIO, content_type: str) -> None:
        self.objects[key] = body.read()

    def download(self, key: str) -> bytes:
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest.fixture(scope="session", autouse=True)
def _setup_database() -> Generator[None]:
    async def _create() -> None:
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())
    yield

    async def _teardown() -> None:
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await _test_engine.dispose()

    asyncio.run(_teardown())


@pytest_asyncio.fixture(autouse=True)
async def _clean_sessions_table() -> AsyncGenerator[None]:
    yield
    async with _TestSessionLocal() as session:
        await session.execute(delete(ChatMessage))
        await session.execute(delete(NotebookCell))
        await session.execute(delete(Decision))
        await session.execute(delete(UploadSession))
        await session.commit()


async def _override_get_db() -> AsyncGenerator[AsyncSession]:
    async with _TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with _TestSessionLocal() as session:
        yield session


@pytest.fixture
def fake_storage() -> FakeStorageBackend:
    return FakeStorageBackend()


@pytest.fixture
def fake_execution_backend() -> FakeExecutionBackend:
    return FakeExecutionBackend()


@pytest.fixture
def kernel_manager(fake_execution_backend: FakeExecutionBackend) -> KernelManager:
    return KernelManager(
        fake_execution_backend, idle_timeout_minutes=30, default_cell_timeout_seconds=30
    )


@pytest.fixture
def client(
    fake_storage: FakeStorageBackend,
    fake_execution_backend: FakeExecutionBackend,
    kernel_manager: KernelManager,
) -> Generator[TestClient]:
    def _override_get_storage() -> StorageBackend:
        return fake_storage

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage_backend] = _override_get_storage
    app.dependency_overrides[get_execution_backend] = lambda: fake_execution_backend
    app.dependency_overrides[get_kernel_manager] = lambda: kernel_manager
    # `AgentRunner` (app/agent/runner.py) isn't itself request-scoped — it resolves its
    # dependencies once, eagerly, when first constructed — so overriding the individual
    # `get_storage_backend`/`get_execution_backend`/`get_kernel_manager` FastAPI dependencies
    # above doesn't reach it. Build it from the same fakes and override its own factory too.
    app.dependency_overrides[get_agent_runner] = lambda: AgentRunner(
        fake_storage,
        fake_execution_backend,
        kernel_manager,
        get_llm_client(),
        get_event_bus(),
        get_settings(),
        session_maker=_TestSessionLocal,
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
