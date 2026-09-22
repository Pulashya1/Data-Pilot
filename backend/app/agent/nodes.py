"""LangGraph node implementations for the agent run (MASTER_PROMPT.md §5.1, §12 Phase 3/4).

Each node looks up its non-serializable dependencies (DB session, kernel manager, LLM client,
event bus) from `app.agent.deps` by `session_id` — see that module's docstring for why.
`understand_node` and `plan_node` pause for real user input via `app.agent.decisions` (Phase 4)
unless the session's `auto_decide` toggle is on, in which case they resolve immediately and
still record a `Decision` row, same as Phase 3. See `app.agent.decisions`'s module docstring for
the replay-safety rules both nodes below follow.
"""

import json
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select

from app.agent import deps as deps_module
from app.agent import heuristics
from app.agent.context import build_understand_context
from app.agent.decisions import create_or_get_decision, get_decision, resolve_decision
from app.agent.deps import NodeDeps
from app.agent.insight_severity import classify_severity
from app.agent.llm import LLMBudgetExceededError, LLMUnavailableError
from app.agent.planning import EDA_PLAN_TEMPLATE_KEYS, build_plan
from app.agent.semantic_types import infer_semantic_types
from app.agent.state import AgentState
from app.agent.tools.schemas import CodeRepair, ProposeTargetAndProblemType
from app.analysis.templates.base import extract_summary
from app.analysis.templates.registry import TEMPLATES
from app.core.logging import get_logger
from app.models.decision import Decision, DecisionKind
from app.models.notebook import CellStatus, NotebookCell
from app.models.session import AgentStatus, ProblemType, UploadSession
from app.notebook import builder
from app.notebook.seed import (
    make_on_start_hook,
    render_and_run_template_step,
    run_pending_seed_cells,
)
from app.schemas.dataset import DatasetProfile
from app.schemas.events import (
    AgentStatusEvent,
    CellUpdateEvent,
    ErrorEvent,
    InsightEvent,
    LLMStatusEvent,
    PlanUpdateEvent,
)

logger = get_logger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")
_MAX_REPAIR_ATTEMPTS = 3


async def ingest_node(state: AgentState) -> dict[str, Any]:
    deps = deps_module.get(state["session_id"])
    session = await deps.db.get(UploadSession, state["session_id"])
    assert session is not None

    await builder.seed_notebook(deps.db, session)
    await deps.db.flush()
    await run_pending_seed_cells(
        session, deps.db, deps.storage, deps.backend, deps.kernel_manager, deps.settings
    )
    await deps.db.commit()
    return {}


async def understand_node(state: AgentState) -> dict[str, Any]:
    deps = deps_module.get(state["session_id"])
    session_id = state["session_id"]
    session = await deps.db.get(UploadSession, session_id)
    assert session is not None

    # Pure/deterministic — cheap to recompute on every replay (see app.agent.decisions).
    profile = DatasetProfile.model_validate(session.profile)
    semantic_types = infer_semantic_types(profile)

    decision = await get_decision(deps.db, session_id, DecisionKind.TARGET_CONFIRMATION)
    if decision is None:
        # First time only: the LLM/heuristic call, the Decision row, and the markdown cell must
        # never repeat on replay — guarded by `decision is None` per app.agent.decisions.
        context = build_understand_context(
            profile, session.preview_rows or [], deps.settings.llm_sample_rows
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        async def status_callback(call_state: str) -> None:
            await deps.bus.publish(
                session_id,
                LLMStatusEvent(
                    state=call_state,  # type: ignore[arg-type]
                    model=deps.settings.llm_model,
                    calls_used=session.llm_calls_used,
                    calls_budget=deps.settings.llm_max_calls_per_session,
                ),
            )

        try:
            proposal = await deps.llm_client.complete_structured(
                messages,
                ProposeTargetAndProblemType,
                db=deps.db,
                session_id=session_id,
                status_callback=status_callback,
            )
        except (LLMUnavailableError, LLMBudgetExceededError) as exc:
            # §5.8 graceful degradation: fall back to the same deterministic heuristic the mock
            # LLM uses, so the graph still completes without a working LLM provider.
            logger.warning("understand_llm_fallback", session_id=session_id, error=str(exc))
            payload = json.loads(context)
            proposal = heuristics.propose_target_and_problem_type(payload["columns"])

        recommended = proposal.target_column or "(no target)"
        options = [col.name for col in profile.columns] + ["(no target)"]
        decision = await create_or_get_decision(
            deps,
            session,
            kind=DecisionKind.TARGET_CONFIRMATION,
            question="What's the prediction target and problem type?",
            options=options,
            recommended_option=recommended,
            reasoning=proposal.reasoning,
        )

        markdown = (
            "## Problem type & target\n\n"
            f"- **Proposed target column:** "
            f"{proposal.target_column or '_none — unsupervised exploration_'}\n"
            f"- **Proposed problem type:** {proposal.problem_type}\n"
            f"- **Reasoning:** {proposal.reasoning}"
        )
        await builder.add_markdown_cell(deps.db, session.id, markdown)
        await deps.db.commit()
        await status_callback("idle")

    # §5.1 INTERRUPT (unless auto-decide is on): pauses here until the user confirms or picks a
    # different target. Resumes with the same answer whether accepted-as-is or overridden.
    answer = await resolve_decision(deps, session, decision)

    if answer == "(no target)":
        session.problem_type = None
        session.target_column = None
    else:
        col = next((c for c in profile.columns if c.name == answer), None)
        session.target_column = answer
        if col is None:
            # Should be unreachable — the API validates the answer against `decision.options`
            # before triggering the resume — but never crash the graph over a bad answer.
            session.problem_type = None
        else:
            col_dict = {
                "name": col.name,
                "semantic_type": semantic_types[col.name],
                "unique_count": col.unique_count,
            }
            session.problem_type = ProblemType(heuristics.classify_single_column(col_dict))
    await deps.db.commit()

    return {
        "problem_type": session.problem_type.value if session.problem_type else None,
        "target_column": session.target_column,
    }


async def plan_node(state: AgentState) -> dict[str, Any]:
    deps = deps_module.get(state["session_id"])
    session_id = state["session_id"]
    session = await deps.db.get(UploadSession, session_id)
    assert session is not None

    decision = await get_decision(deps.db, session_id, DecisionKind.PLAN_APPROVAL)
    if decision is None:
        steps = build_plan(state.get("problem_type"))
        decision = await create_or_get_decision(
            deps,
            session,
            kind=DecisionKind.PLAN_APPROVAL,
            question="Which analysis steps should run, and in what order?",
            options=EDA_PLAN_TEMPLATE_KEYS,
            recommended_option=",".join(steps),
            reasoning="Deterministic template order for the confirmed problem type.",
        )

    # §5.1 INTERRUPT (unless auto-decide is on): pauses here until the user approves, reorders,
    # skips, or adds steps. The answer is a comma-separated, ordered list of template keys — see
    # `POST /sessions/{id}/plan` (app/api/agent.py) for the structured editing endpoint that
    # builds this string.
    answer = await resolve_decision(deps, session, decision)
    steps = [key.strip() for key in answer.split(",") if key.strip() in TEMPLATES]
    if not steps:
        # Should be unreachable — the API validates every step against `TEMPLATES` before
        # triggering the resume — but never leave the plan empty.
        steps = build_plan(state.get("problem_type"))

    session.plan_steps = steps
    session.plan_step_index = 0
    await deps.db.commit()

    await deps.bus.publish(session_id, PlanUpdateEvent(steps=steps, step_index=0))
    return {"plan": steps, "step_index": 0}


async def _run_template_and_report(
    deps: NodeDeps,
    session: UploadSession,
    template_key: str,
    *,
    extra_params: dict[str, Any] | None = None,
) -> None:
    """Shared by `execute_step_node`, `feature_engineering_node`, and `baseline_node`: render +
    run `template_key`'s cell, publish its cell/insight events, and repair-and-retry on error.
    Callers apply any state mutation of their own (e.g. `plan_step_index`) to `session` *before*
    calling this, since it's the one that commits."""
    template = TEMPLATES[template_key]
    new_cells, summary = await render_and_run_template_step(
        deps.db,
        session,
        deps.storage,
        deps.backend,
        deps.kernel_manager,
        deps.settings,
        template,
        extra_params=extra_params,
    )
    await deps.db.commit()

    code_cell = new_cells[0]
    for cell in new_cells:
        await deps.bus.publish(
            session.id,
            CellUpdateEvent(cell_id=cell.id, status=cell.status.value, label=cell.label),
        )

    if code_cell.status == CellStatus.ERROR:
        await _repair_and_retry(deps, session, code_cell, template_key)
    elif summary is not None:
        severity = classify_severity(template_key, summary)
        insight_cell = new_cells[-1] if len(new_cells) > 1 else None
        for text in template.summarize(summary):
            await deps.bus.publish(
                session.id,
                InsightEvent(
                    text=text,
                    severity=severity,
                    related_cell_id=insight_cell.id if insight_cell else None,
                ),
            )


async def execute_step_node(state: AgentState) -> dict[str, Any]:
    deps = deps_module.get(state["session_id"])
    session_id = state["session_id"]
    session = await deps.db.get(UploadSession, session_id)
    assert session is not None

    index = state["step_index"]
    template_key = state["plan"][index]
    session.plan_step_index = index + 1
    await _run_template_and_report(deps, session, template_key)
    # step_index is the number of plan steps completed so far, so the UI can show progress.
    await deps.bus.publish(session_id, PlanUpdateEvent(steps=state["plan"], step_index=index + 1))
    return {"step_index": index + 1}


async def feature_engineering_node(state: AgentState) -> dict[str, Any]:
    """MASTER_PROMPT.md §5.1 step 5, §12 Phase 6: build the preprocessing Pipeline from either
    the deterministic defaults or a JSON override the user supplied when answering the decision
    (`app.agent.decisions.validate_answer` validates the shape). Always runs — unlike the
    baseline, a preprocessing pipeline is useful even for clustering/no-target sessions."""
    deps = deps_module.get(state["session_id"])
    session_id = state["session_id"]
    session = await deps.db.get(UploadSession, session_id)
    assert session is not None

    decision = await get_decision(deps.db, session_id, DecisionKind.FEATURE_ENGINEERING_APPROVAL)
    if decision is None:
        decision = await create_or_get_decision(
            deps,
            session,
            kind=DecisionKind.FEATURE_ENGINEERING_APPROVAL,
            question="Build a preprocessing pipeline with the recommended defaults?",
            options=["recommended"],
            recommended_option="recommended",
            reasoning=(
                "Median/most-frequent imputation, standard-scaled numeric features, one-hot "
                "encoded low-cardinality categoricals, and dropped constant/ID-like columns. "
                "Reply with a JSON object to override any of "
                "numeric_impute, categorical_impute, scaling, high_cardinality_threshold, "
                "test_size, drop_columns instead of 'recommended'."
            ),
        )

    answer = await resolve_decision(deps, session, decision)
    extra_params: dict[str, Any] = {} if answer == "recommended" else json.loads(answer)
    await _run_template_and_report(deps, session, "feature_engineering", extra_params=extra_params)
    return {}


async def baseline_node(state: AgentState) -> dict[str, Any]:
    """MASTER_PROMPT.md §5.1 step 6, §12 Phase 6: "baseline (optional, ask first)". Only
    meaningful for a confirmed classification/regression target — skipped entirely (no decision,
    no cell) for clustering/time-series/no-target sessions, same as `baseline_model`'s own
    no-target degradation, just one level up so we don't even ask the question."""
    deps = deps_module.get(state["session_id"])
    session_id = state["session_id"]
    session = await deps.db.get(UploadSession, session_id)
    assert session is not None

    if session.target_column is None or session.problem_type not in (
        ProblemType.REGRESSION,
        ProblemType.BINARY_CLASSIFICATION,
        ProblemType.MULTICLASS_CLASSIFICATION,
    ):
        return {}

    decision = await get_decision(deps.db, session_id, DecisionKind.BASELINE_APPROVAL)
    if decision is None:
        decision = await create_or_get_decision(
            deps,
            session,
            kind=DecisionKind.BASELINE_APPROVAL,
            question=(
                "Train a quick baseline model and report metrics, feature importance, and a "
                "SHAP summary?"
            ),
            options=["yes", "no"],
            recommended_option="yes",
            reasoning="Gives a reference point before deeper feature engineering or tuning.",
        )

    answer = await resolve_decision(deps, session, decision)
    if answer == "no":
        return {}

    await _run_template_and_report(deps, session, "baseline_model")
    return {}


async def _repair_and_retry(
    deps: NodeDeps, session: UploadSession, cell: NotebookCell, template_key: str
) -> None:
    """§5.1: on error, read the traceback, fix the code, and retry (max 3 attempts). Only the
    final version is kept in the notebook — failed attempts are logged, never written."""
    attempts = 0
    while cell.status == CellStatus.ERROR and attempts < _MAX_REPAIR_ATTEMPTS:
        attempts += 1
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"code": cell.source, "error": cell.error_message}),
            },
        ]
        try:
            repair = await deps.llm_client.complete_structured(
                messages, CodeRepair, db=deps.db, session_id=session.id
            )
        except (LLMUnavailableError, LLMBudgetExceededError) as exc:
            logger.warning(
                "repair_llm_unavailable", session_id=session.id, cell_id=cell.id, error=str(exc)
            )
            break

        logger.info(
            "repair_attempt",
            session_id=session.id,
            cell_id=cell.id,
            template_key=template_key,
            attempt=attempts,
            explanation=repair.explanation,
        )
        cell.source = repair.code
        on_start = make_on_start_hook(session, deps.db, deps.storage, deps.backend, deps.settings)
        result = await deps.kernel_manager.run_cell(session.id, repair.code, on_start=on_start)
        extract_summary(result)
        builder.apply_execution_result(cell, result)
        await deps.db.flush()

    await deps.db.commit()
    await deps.bus.publish(
        session.id, CellUpdateEvent(cell_id=cell.id, status=cell.status.value, label=cell.label)
    )
    if cell.status == CellStatus.ERROR:
        await deps.bus.publish(
            session.id,
            ErrorEvent(
                message=cell.error_message or "cell failed after repair attempts",
                cell_id=cell.id,
            ),
        )


async def summarize_node(state: AgentState) -> dict[str, Any]:
    deps = deps_module.get(state["session_id"])
    session_id = state["session_id"]
    session = await deps.db.get(UploadSession, session_id)
    assert session is not None

    decisions = (
        (await deps.db.execute(select(Decision).where(Decision.session_id == session_id)))
        .scalars()
        .all()
    )
    cells = await builder.get_cells(deps.db, session_id)

    problem_type_text = (
        session.problem_type.value if session.problem_type else "unsupervised / no target"
    )
    lines = [
        "## Summary",
        "",
        f"**Problem type:** {problem_type_text}",
        f"**Target column:** {session.target_column or '_none_'}",
        "",
        "### Decisions made",
    ]
    for decision in decisions:
        auto = "auto-decided" if decision.auto_decided else "user-decided"
        lines.append(
            f"- {decision.question} → **{decision.selected_option}** ({auto}): "
            f"{decision.reasoning or ''}"
        )

    lines += ["", "### Key findings"]
    for cell in cells:
        if cell.cell_type.value == "markdown" and cell.source.startswith("**Insights:**"):
            lines += [line for line in cell.source.splitlines() if line.startswith("- ")]

    lines += [
        "",
        "### Next steps",
        "- Revisit any decision above from the Decisions panel, or revert to an earlier cell "
        "and re-run.",
    ]
    await builder.add_markdown_cell(deps.db, session_id, "\n".join(lines))

    session.agent_status = AgentStatus.DONE
    await deps.db.commit()
    await deps.bus.publish(session_id, AgentStatusEvent(status="done"))
    return {}


def route_after_step(state: AgentState) -> Literal["continue", "done"]:
    if state["step_index"] < len(state["plan"]):
        return "continue"
    return "done"
