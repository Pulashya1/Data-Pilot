"""ORM model for an agent decision (MASTER_PROMPT.md §5.4, §12 Phase 3/4).

Phase 3 auto-decides at every decision point and records the choice here so Phase 4 can add
real `interrupt()`-based pausing and a Decisions panel against data that already exists,
without a schema change.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DecisionKind(str, enum.Enum):
    TARGET_CONFIRMATION = "target_confirmation"
    PLAN_APPROVAL = "plan_approval"
    FEATURE_ENGINEERING_APPROVAL = "feature_engineering_approval"
    BASELINE_APPROVAL = "baseline_approval"


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[DecisionKind] = mapped_column(Enum(DecisionKind, native_enum=False))
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(JSON)
    recommended_option: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_option: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_decided: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
