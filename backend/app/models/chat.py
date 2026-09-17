"""ORM model for the Q&A chat history (MASTER_PROMPT.md §5.6, §7, §8, §12 Phase 7).

One row per turn (user question or assistant answer), not paired — mirrors `NotebookCell`'s
"one row per fact" shape and keeps `GET /sessions/{id}/messages` a plain ordered list. See
`app.agent.qa`'s module docstring for why Q&A is a plain request/response flow rather than a
LangGraph node.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole, native_enum=False))
    content: Mapped[str] = mapped_column(Text)
    # `@cell-<position>` references parsed out of a user message (app.agent.qa); null for an
    # assistant message or a user message with none.
    referenced_cell_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Set on an assistant message when answering it required running a new exploratory cell.
    exploratory_cell_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("notebook_cells.id", ondelete="SET NULL"), nullable=True
    )
    # True when the LLM was unavailable/over budget and a deterministic heuristic answered
    # instead (same graceful-degradation shape as `app.agent.nodes.understand_node`).
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
