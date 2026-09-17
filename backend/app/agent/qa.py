"""Q&A over the notebook (MASTER_PROMPT.md §5.1 "qa", §5.6, §12 Phase 7).

Deliberately **not** a LangGraph node: the main agent graph (`app/agent/graph.py`) models a
fixed pipeline with `interrupt()`-based pauses on one checkpointed thread per session, driven
by exactly one active `asyncio.Task` at a time (`app/agent/runner.py`). A chat message needs to
be answerable "at any time" — while the agent is running, paused, or done — via a normal
synchronous request, not by injecting an event into that single active graph run (which
LangGraph has no clean mechanism for here, short of modeling every possible question as its
own interrupt point). So `answer_question` below is a plain async function called directly
from the API layer (`app/api/agent.py`), building its own `NodeDeps` per-request rather than
going through `app.agent.deps`'s session-keyed registry — that registry is for the background
agent-run task and must not be touched by a concurrent request for the same `session_id`.

Grounding (§5.6): the question is checked for `@cell-<position>` references first (the
frontend's "Ask about this cell" button pre-fills exactly this, keyed on `NotebookCell.position`
since cell ids are opaque UUIDs, not the small sequential numbers §5.6's example implies) and,
if any resolve, only those cells' code/output ground the answer. Otherwise recent insight
bullets fill in, so a generic question still has *something* concrete to point at instead of
silently falling back to "the whole notebook" (§5.5: only send what's relevant, not everything).

Exploratory computation (§5.1, §5.6): if the LLM decides it needs new code to answer, that code
runs in the session's live kernel as a cell flagged `is_exploratory=True` — excluded from
`.ipynb` export by default (`app/notebook/export.py`). Skipped (with a plain-text note instead)
while the main agent graph is actively `RUNNING`: `KernelManager.run_cell` only locks the
kernel-*start* path, not the execute call itself (see its module docstring), so a concurrent
`run_cell` from here while the agent's own `execute_step` is mid-flight could race inside the
same live kernel process — the same hazard `app/api/notebook.py`'s `revert_to_cell` already
guards against for a different reason. `WAITING_DECISION` is fine (the kernel is idle then).
"""

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.agent import heuristics
from app.agent.context import build_qa_context
from app.agent.deps import NodeDeps
from app.agent.llm import LLMBudgetExceededError, LLMUnavailableError
from app.agent.tools.schemas import AnswerQuestion
from app.core.logging import get_logger
from app.execution.backend import KernelComputeBudgetExceededError, KernelStartupError
from app.models.chat import ChatMessage, ChatRole
from app.models.decision import Decision
from app.models.notebook import CellStatus, CellType, NotebookCell
from app.models.session import AgentStatus, UploadSession
from app.notebook import builder
from app.notebook.seed import make_on_start_hook
from app.schemas.dataset import DatasetProfile

logger = get_logger(__name__)

_CELL_REF = re.compile(r"@cell-(\d+)")

_BASE_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")

_EXPERTISE_INSTRUCTIONS = {
    "beginner": (
        "The user is a beginner: explain in plain language, define any statistical term you "
        "use, and avoid unexplained jargon."
    ),
    "intermediate": (
        "The user is comfortable with basic statistics and pandas: be concise, light on "
        "definitions, but still explain non-obvious reasoning."
    ),
    "expert": (
        "The user is an expert: be terse and precise, use exact statistical terminology, and "
        "skip explanations of basic concepts."
    ),
}


def _system_prompt(expertise_level: str) -> str:
    instruction = _EXPERTISE_INSTRUCTIONS.get(
        expertise_level, _EXPERTISE_INSTRUCTIONS["intermediate"]
    )
    return (
        f"{_BASE_SYSTEM_PROMPT}\n\n"
        "You are now answering a user question about their dataset/notebook (MASTER_PROMPT.md "
        "§5.6). Ground your answer only in the JSON context you're given — referenced cells, "
        "recent insights, decisions, dataset schema/stats — never the raw dataset, and never a "
        "number you didn't actually compute or that isn't in that context. If the context "
        "doesn't contain the answer, say so and only then request new computation via "
        "`needs_computation`/`code`. "
        f"{instruction}"
    )


def resolve_cell_references(question: str, cells: list[NotebookCell]) -> list[NotebookCell]:
    """Parses `@cell-<position>` references out of `question` and resolves them against
    `cells` by `NotebookCell.position` (stable, user-facing — unlike the opaque UUID `id`)."""
    positions = sorted({int(match) for match in _CELL_REF.findall(question)})
    by_position = {cell.position: cell for cell in cells}
    return [by_position[p] for p in positions if p in by_position]


def _recent_insight_bullets(cells: list[NotebookCell], limit: int = 10) -> list[str]:
    bullets: list[str] = []
    for cell in cells:
        if cell.cell_type == CellType.MARKDOWN and cell.source.startswith("**Insights:**"):
            bullets += [line[2:] for line in cell.source.splitlines() if line.startswith("- ")]
    return bullets[-limit:]


async def answer_question(deps: NodeDeps, session: UploadSession, content: str) -> ChatMessage:
    user_message = ChatMessage(session_id=session.id, role=ChatRole.USER, content=content)
    deps.db.add(user_message)
    await deps.db.flush()

    cells = await builder.get_cells(deps.db, session.id)
    referenced = resolve_cell_references(content, cells)
    referenced_ids = [cell.id for cell in referenced] or None
    user_message.referenced_cell_ids = referenced_ids

    decisions_result = await deps.db.execute(
        select(Decision).where(Decision.session_id == session.id)
    )
    decisions: list[dict[str, Any]] = [
        {
            "question": d.question,
            "selected_option": d.selected_option,
            "reasoning": d.reasoning,
        }
        for d in decisions_result.scalars().all()
    ]

    profile = DatasetProfile.model_validate(session.profile)
    context = build_qa_context(
        question=content,
        expertise_level=session.expertise_level.value,
        problem_type=session.problem_type.value if session.problem_type else None,
        target_column=session.target_column,
        profile=profile,
        referenced_cells=referenced,
        recent_insight_bullets=_recent_insight_bullets(cells),
        decisions=decisions,
        max_output_chars=deps.settings.qa_max_output_chars,
    )
    messages = [
        {"role": "system", "content": _system_prompt(session.expertise_level.value)},
        {"role": "user", "content": context},
    ]

    degraded = False
    try:
        result = await deps.llm_client.complete_structured(
            messages, AnswerQuestion, db=deps.db, session_id=session.id
        )
    except (LLMUnavailableError, LLMBudgetExceededError) as exc:
        # §5.8 graceful degradation, same shape as understand_node's fallback: never leave the
        # user without an answer just because the LLM is unavailable/over budget.
        logger.warning("qa_llm_fallback", session_id=session.id, error=str(exc))
        payload = json.loads(context)
        result = heuristics.answer_question(
            payload["question"], payload["referenced_cells"], payload["column_names"]
        )
        degraded = True

    answer_text = result.answer
    exploratory_cell_id: str | None = None
    if result.needs_computation and result.code:
        if session.agent_status == AgentStatus.RUNNING:
            answer_text += (
                "\n\n(Answering fully would need to run new code, but the agent is actively "
                "running right now — ask again once it's done or paused on a decision.)"
            )
        else:
            cell = await builder.add_code_cell(
                deps.db,
                session.id,
                result.code,
                label=result.cell_purpose or "Q&A",
                is_exploratory=True,
            )
            await deps.db.flush()
            on_start = make_on_start_hook(
                session, deps.db, deps.storage, deps.backend, deps.settings
            )
            try:
                exec_result = await deps.kernel_manager.run_cell(
                    session.id, result.code, on_start=on_start
                )
            except (KernelStartupError, KernelComputeBudgetExceededError) as exc:
                cell.status = CellStatus.ERROR
                cell.error_message = str(exc)
                await deps.db.flush()
                exploratory_cell_id = cell.id
                answer_text += f"\n\n(Tried to run new code to answer this, but couldn't: {exc})"
            else:
                builder.apply_execution_result(cell, exec_result)
                await deps.db.flush()
                exploratory_cell_id = cell.id
                if cell.status == CellStatus.ERROR:
                    answer_text += (
                        f"\n\n(Tried to run new code to answer this, but it failed: "
                        f"{cell.error_message})"
                    )

    assistant_message = ChatMessage(
        session_id=session.id,
        role=ChatRole.ASSISTANT,
        content=answer_text,
        referenced_cell_ids=referenced_ids,
        exploratory_cell_id=exploratory_cell_id,
        degraded=degraded,
    )
    deps.db.add(assistant_message)
    await deps.db.commit()
    return assistant_message
