"""Pydantic schemas for the notebook & template-run API (MASTER_PROMPT.md §8, §12 Phase 2)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.notebook import CellStatus, CellType


class NotebookCellOut(BaseModel):
    id: str
    session_id: str
    position: int
    cell_type: CellType
    source: str
    label: str | None
    outputs: list[dict[str, Any]] | None
    execution_count: int | None
    status: CellStatus
    error_message: str | None
    is_exploratory: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateInfo(BaseModel):
    key: str
    title: str
    description: str


class KernelStatusOut(BaseModel):
    status: str
