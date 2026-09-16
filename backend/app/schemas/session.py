"""Pydantic schemas for the session API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.session import FileType, SessionStatus
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


class SheetSelectionRequest(BaseModel):
    sheet_name: str


class PreviewResponse(BaseModel):
    total_available: int
    offset: int
    limit: int
    rows: list[dict[str, Any]]
