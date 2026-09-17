"""FastAPI application entrypoint."""

import asyncio
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if sys.platform == "win32":
    # psycopg (app/agent/checkpoint.py's LangGraph checkpointer) can't run in async mode on
    # Windows' default ProactorEventLoop — must be set before any event loop is created, so
    # this has to happen at import time here, not inside an async function.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.agent.checkpoint import start_checkpointer, stop_checkpointer
from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.notebook import router as notebook_router
from app.api.sessions import router as sessions_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.execution.kernel_manager import get_kernel_manager

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    kernel_manager = get_kernel_manager()
    kernel_manager.start_reaper()
    await start_checkpointer(settings)
    try:
        yield
    finally:
        await kernel_manager.stop_reaper()
        await kernel_manager.shutdown_all()
        await stop_checkpointer()


app = FastAPI(title="DataPilot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(notebook_router)
app.include_router(agent_router)
