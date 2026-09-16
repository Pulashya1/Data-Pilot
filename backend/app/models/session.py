"""ORM model for an upload session."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FileType(str, enum.Enum):
    CSV = "csv"
    TSV = "tsv"
    EXCEL = "excel"
    JSON = "json"
    JSON_LINES = "json_lines"
    PARQUET = "parquet"


class SessionStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    NEEDS_SHEET_SELECTION = "needs_sheet_selection"
    PROFILING = "profiling"
    READY = "ready"
    ERROR = "error"


class ProblemType(str, enum.Enum):
    REGRESSION = "regression"
    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    CLUSTERING = "clustering"
    TIME_SERIES = "time_series"


class AgentStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    WAITING_DECISION = "waiting_decision"
    DONE = "done"
    ERROR = "error"


class UploadSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[FileType] = mapped_column(Enum(FileType, native_enum=False))
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, native_enum=False), default=SessionStatus.UPLOADED
    )
    sheet_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    selected_sheet: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    profile: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    preview_rows: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Agent state (Phase 3, MASTER_PROMPT.md §12)
    problem_type: Mapped[ProblemType | None] = mapped_column(
        Enum(ProblemType, native_enum=False), nullable=True
    )
    target_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, native_enum=False), default=AgentStatus.NOT_STARTED
    )
    agent_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_steps: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    plan_step_index: Mapped[int] = mapped_column(Integer, default=0)
    llm_calls_used: Mapped[int] = mapped_column(Integer, default=0)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    llm_models_used: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Human-in-the-loop (Phase 4, MASTER_PROMPT.md §5.4, §12)
    auto_decide: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
