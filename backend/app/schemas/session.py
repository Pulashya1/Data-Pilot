"""Pydantic schemas for the session API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.session import AgentStatus, FileType, ProblemType, SessionStatus
from app.schemas.dataset import DatasetProfile


class SessionSummary(BaseModel):
    id: str
    original_filename: str
    file_type: FileType
    status: SessionStatus
    size_bytes: int
    row_count: int | None
    column_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetail(SessionSummary):
    sheet_names: list[str] | None
    selected_sheet: str | None
    error_message: str | None
    profile: DatasetProfile | None

    # Agent state (Phase 3)
    problem_type: ProblemType | None
    target_column: str | None
    agent_status: AgentStatus
    agent_error_message: str | None
    plan_steps: list[str] | None
    llm_calls_used: int
    auto_decide: bool


class SheetSelectionRequest(BaseModel):
    sheet_name: str


class SessionSettingsRequest(BaseModel):
    auto_decide: bool


class UsageOut(BaseModel):
    calls_used: int
    calls_budget: int
    tokens_used: int
    models_used: list[str]


class PreviewResponse(BaseModel):
    total_available: int
    offset: int
    limit: int
    rows: list[dict[str, Any]]
