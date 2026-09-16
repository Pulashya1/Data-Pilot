"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    try:
        yield
    finally:
        await kernel_manager.stop_reaper()
        await kernel_manager.shutdown_all()


app = FastAPI(title="DataPilot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(notebook_router)
