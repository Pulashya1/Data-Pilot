"""ORM model for a notebook cell (MASTER_PROMPT.md §6, §12 Phase 2).

The notebook is the session's single source of truth (MASTER_PROMPT.md core design
principle): every analysis action is a row here, in order, and the `.ipynb` export and the
live UI panel are both just views over this table.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CellType(str, enum.Enum):
    MARKDOWN = "markdown"
    CODE = "code"


class CellStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"


class NotebookCell(Base):
    __tablename__ = "notebook_cells"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    cell_type: Mapped[CellType] = mapped_column(Enum(CellType, native_enum=False))
    source: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outputs: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[CellStatus] = mapped_column(
        Enum(CellStatus, native_enum=False), default=CellStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
