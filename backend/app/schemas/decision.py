"""Pydantic schemas for the human-in-the-loop decision API.

MASTER_PROMPT.md §5.4, §8, §12 Phase 4.
"""

from datetime import datetime

from pydantic import BaseModel

from app.agent.decisions import ALLOWS_FREE_TEXT
from app.models.decision import Decision, DecisionKind


class DecisionOut(BaseModel):
    id: str
    kind: DecisionKind
    question: str
    options: list[str]
    recommended_option: str | None
    selected_option: str | None
    reasoning: str | None
    auto_decided: bool
    allow_free_text: bool
    created_at: datetime

    @classmethod
    def from_decision(cls, decision: Decision) -> "DecisionOut":
        return cls(
            id=decision.id,
            kind=decision.kind,
            question=decision.question,
            options=decision.options,
            recommended_option=decision.recommended_option,
            selected_option=decision.selected_option,
            reasoning=decision.reasoning,
            auto_decided=decision.auto_decided,
            allow_free_text=ALLOWS_FREE_TEXT.get(decision.kind, False),
            created_at=decision.created_at,
        )


class AnswerDecisionRequest(BaseModel):
    selected_option: str


class EditPlanRequest(BaseModel):
    steps: list[str]
