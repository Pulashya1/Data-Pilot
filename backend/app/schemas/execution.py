"""Pydantic schemas for kernel execution results (MASTER_PROMPT.md §5.2 `run_code`, §12 Phase 2)."""

from typing import Any, Literal

from pydantic import BaseModel

ExecutionStatus = Literal["ok", "error", "timeout"]


class ExecutionResult(BaseModel):
    status: ExecutionStatus
    outputs: list[dict[str, Any]]
    execution_count: int | None = None
    error_message: str | None = None
