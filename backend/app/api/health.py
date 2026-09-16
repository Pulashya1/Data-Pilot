"""Health check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class LLMStatus(BaseModel):
    configured: bool
    model: str


class HealthResponse(BaseModel):
    status: str
    llm: LLMStatus


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        llm=LLMStatus(
            configured=settings.llm_model != "mock",
            model=settings.llm_model,
        ),
    )
