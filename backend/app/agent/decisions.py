"""Shared human-in-the-loop primitive for agent decision points (MASTER_PROMPT.md §5.1, §5.4,
§12 Phase 4).

This is the `ask_user` concept from §5.2, built directly on LangGraph's `interrupt()`: a node
creates (or finds) a `Decision` row, then calls `resolve_decision` to get the user's answer,
pausing the graph if the session isn't in auto-decide mode.

**Replay safety is the whole design constraint here.** LangGraph replays a node's entire
function body from the top every time the graph resumes into it (verified against
langgraph==1.2.11: a node that calls `interrupt()` re-executes every line before that call on
resume, not just the call itself). So any code that must run exactly once per decision — the
LLM/heuristic proposal, creating the `Decision` row, writing its markdown cell, incrementing LLM
usage — has to be guarded by "does a `Decision` of this kind already exist for this session?"
(see `get_decision`) before doing that work, in every node that uses this module. Once a
decision exists, `resolve_decision` itself is safe to call on every replay: if it's already
answered (the API endpoint writes the answer to the DB *before* triggering the resume), it
returns immediately without calling `interrupt()` again.
"""

# langgraph.types.interrupt pauses graph execution here and returns the resume value once the
# graph is re-invoked with `Command(resume=...)` (see `app.agent.runner.AgentRunner.resume`).
import json

from langgraph.types import interrupt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.deps import NodeDeps
from app.models.decision import Decision, DecisionKind
from app.models.session import AgentStatus, UploadSession
from app.schemas.events import AgentStatusEvent, DecisionEvent

# Only `plan_approval` and `feature_engineering_approval` answers can be more than one of the
# enumerated `options` (a delimited step list, or a JSON override object respectively);
# `target_confirmation` and `baseline_approval` answers must be exactly one of `options`. Kept
# here (not a DB column) since it's a fixed property of the decision kind, not per-row data.
ALLOWS_FREE_TEXT: dict[DecisionKind, bool] = {
    DecisionKind.TARGET_CONFIRMATION: False,
    DecisionKind.PLAN_APPROVAL: True,
    DecisionKind.FEATURE_ENGINEERING_APPROVAL: True,
    DecisionKind.BASELINE_APPROVAL: False,
}

# `feature_engineering_node` (app/agent/nodes.py) merges a validated override object straight
# into the `feature_engineering` template's params (MASTER_PROMPT.md §12 Phase 6) — keep this in
# sync with that template's `default_params`/`render` keys in
# `app/analysis/templates/feature_engineering.py`.
_FEATURE_ENGINEERING_OVERRIDE_KEYS = {
    "numeric_impute",
    "categorical_impute",
    "scaling",
    "high_cardinality_threshold",
    "test_size",
    "drop_columns",
}


class InvalidAnswerError(ValueError):
    """Raised by `validate_answer` for a malformed or out-of-range answer — callers (the API
    layer) turn this into a 400, so an unanswerable decision never reaches `interrupt()`."""


def validate_answer(decision: Decision, raw_answer: str) -> str:
    """Normalizes and validates a candidate answer for `decision`, returning the exact string
    that should be written to `Decision.selected_option` and passed to `Command(resume=...)`."""
    answer = raw_answer.strip()
    if not answer:
        raise InvalidAnswerError("An answer is required.")

    if decision.kind == DecisionKind.PLAN_APPROVAL:
        steps = [step.strip() for step in answer.split(",") if step.strip()]
        if not steps:
            raise InvalidAnswerError("At least one analysis step is required.")
        unknown = [step for step in steps if step not in decision.options]
        if unknown:
            raise InvalidAnswerError(f"Unknown analysis step(s): {', '.join(unknown)}")
        return ",".join(steps)

    if decision.kind == DecisionKind.FEATURE_ENGINEERING_APPROVAL:
        if answer in decision.options:
            return answer
        try:
            overrides = json.loads(answer)
        except json.JSONDecodeError as exc:
            raise InvalidAnswerError(
                "Answer must be 'recommended' or a JSON object of overrides."
            ) from exc
        if not isinstance(overrides, dict):
            raise InvalidAnswerError("JSON override must be an object.")
        unknown_keys = set(overrides) - _FEATURE_ENGINEERING_OVERRIDE_KEYS
        if unknown_keys:
            raise InvalidAnswerError(
                f"Unknown feature engineering option(s): {', '.join(sorted(unknown_keys))}"
            )
        return answer

    if answer not in decision.options:
        raise InvalidAnswerError(f"'{answer}' is not one of the available options.")
    return answer


def decision_event(decision: Decision) -> DecisionEvent:
    return DecisionEvent(
        id=decision.id,
        kind=decision.kind.value,
        question=decision.question,
        options=decision.options,
        recommended_option=decision.recommended_option,
        selected_option=decision.selected_option,
        reasoning=decision.reasoning,
        auto_decided=decision.auto_decided,
    )


async def get_decision(db: AsyncSession, session_id: str, kind: DecisionKind) -> Decision | None:
    result = await db.execute(
        select(Decision)
        .where(Decision.session_id == session_id, Decision.kind == kind)
        .order_by(Decision.created_at.desc())
    )
    return result.scalars().first()


async def create_or_get_decision(
    deps: NodeDeps,
    session: UploadSession,
    *,
    kind: DecisionKind,
    question: str,
    options: list[str],
    recommended_option: str,
    reasoning: str | None,
) -> Decision:
    """Creates the `Decision` row the first time this decision point is reached. Callers must
    only invoke this from inside an `if (await get_decision(...)) is None:` guard — see the
    module docstring — so it never runs twice for the same decision."""
    decision = Decision(
        session_id=session.id,
        kind=kind,
        question=question,
        options=options,
        recommended_option=recommended_option,
        selected_option=recommended_option if session.auto_decide else None,
        reasoning=reasoning,
        auto_decided=session.auto_decide,
    )
    deps.db.add(decision)
    await deps.db.flush()
    await deps.db.commit()
    await deps.bus.publish(session.id, decision_event(decision))
    return decision


async def resolve_decision(deps: NodeDeps, session: UploadSession, decision: Decision) -> str:
    """Returns `decision.selected_option`, pausing the graph via `interrupt()` first if it isn't
    answered yet. Safe to call on every pass of a node: if the decision is already answered
    (auto-decided at creation, or answered by the user before a resume), this returns
    immediately without interrupting."""
    if decision.selected_option is None:
        session.agent_status = AgentStatus.WAITING_DECISION
        await deps.db.commit()
        await deps.bus.publish(session.id, AgentStatusEvent(status="waiting_decision"))

        answer: str = interrupt(
            {
                "decision_id": decision.id,
                "kind": decision.kind.value,
                "question": decision.question,
                "options": decision.options,
                "recommended_option": decision.recommended_option,
            }
        )

        # The `/decisions/{id}` endpoint already writes the answer to the DB before triggering
        # this resume, but `decision` here is the replayed node's own local object, not
        # guaranteed to be the same Python instance — re-apply defensively so callers can trust
        # the return value either way.
        decision.selected_option = answer
        decision.auto_decided = False
        session.agent_status = AgentStatus.RUNNING
        await deps.db.commit()
        await deps.bus.publish(session.id, decision_event(decision))

    assert decision.selected_option is not None
    return decision.selected_option
