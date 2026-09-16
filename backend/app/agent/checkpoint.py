"""Postgres-backed LangGraph checkpointer lifecycle (MASTER_PROMPT.md §2, §3, §12 Phase 3).

Started/stopped once from `app.main`'s lifespan, alongside the kernel manager's reaper.
`AsyncPostgresSaver` needs a plain `postgresql://` DSN — psycopg and SQLAlchemy's `asyncpg`
driver want different URL forms for the same database, so `_psycopg_dsn` strips the
`+asyncpg` suffix `Settings.database_url` uses; without this the pool can't connect at all,
so don't "clean it up" thinking it's a leftover.
"""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import Settings

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


def _psycopg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


async def start_checkpointer(settings: Settings) -> AsyncPostgresSaver:
    global _pool, _checkpointer
    _pool = AsyncConnectionPool(
        conninfo=_psycopg_dsn(settings.database_url),
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
        max_size=5,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(conn=_pool)
    await _checkpointer.setup()
    return _checkpointer


async def stop_checkpointer() -> None:
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
    _pool = None
    _checkpointer = None


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not started — call start_checkpointer() during app startup."
        )
    return _checkpointer
