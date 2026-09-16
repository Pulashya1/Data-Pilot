"""LangGraph state for the agent run (MASTER_PROMPT.md §5.1, §12 Phase 3).

Deliberately small and JSON-serializable (LangGraph checkpoints this). Everything a node needs
that *isn't* serializable — the DB session, kernel manager, LLM client, event bus — is looked
up by `session_id` from `app.agent.deps` instead of stored here.
"""

from typing import TypedDict


class AgentState(TypedDict):
    session_id: str
    problem_type: str | None
    target_column: str | None
    plan: list[str]
    step_index: int
