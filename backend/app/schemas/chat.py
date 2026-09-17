"""Pydantic schemas for the Q&A chat API (MASTER_PROMPT.md §5.6, §8, §12 Phase 7)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.chat import ChatRole


class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: ChatRole
    content: str
    referenced_cell_ids: list[str] | None
    exploratory_cell_id: str | None
    degraded: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AskQuestionRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
