"""SSE event schemas streamed from the agent run (MASTER_PROMPT.md §7, §8, §12 Phase 3).

`AgentEvent` is a discriminated union on `type`; `app.agent.events.SessionEventBus` publishes
these and `app.api.agent`'s `/stream` endpoint serializes each one as an SSE `data:` line.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class CellUpdateEvent(BaseModel):
    type: Literal["cell_update"] = "cell_update"
    cell_id: str
    status: Literal["pending", "success", "error"]
    label: str | None = None


class InsightEvent(BaseModel):
    type: Literal["insight"] = "insight"
    text: str
    severity: Literal["info", "warning", "critical"]
    related_cell_id: str | None = None


class PlanUpdateEvent(BaseModel):
    type: Literal["plan_update"] = "plan_update"
    steps: list[str]
    step_index: int


class DecisionEvent(BaseModel):
    type: Literal["decision"] = "decision"
    id: str
    kind: str
    question: str
    options: list[str]
    recommended_option: str | None
    selected_option: str | None
    reasoning: str | None
    auto_decided: bool


class LLMStatusEvent(BaseModel):
    type: Literal["llm_status"] = "llm_status"
    state: Literal["idle", "calling", "waiting_for_capacity", "error"]
    model: str
    calls_used: int
    calls_budget: int


class AgentStatusEvent(BaseModel):
    type: Literal["agent_status"] = "agent_status"
    status: Literal["running", "waiting_decision", "done", "error"]
    error_message: str | None = None


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    cell_id: str | None = None


AgentEvent = Annotated[
    CellUpdateEvent
    | InsightEvent
    | PlanUpdateEvent
    | DecisionEvent
    | LLMStatusEvent
    | AgentStatusEvent
    | ErrorEvent,
    Field(discriminator="type"),
]
