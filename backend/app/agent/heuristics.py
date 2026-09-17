"""Deterministic target/problem-type/Q&A heuristics (MASTER_PROMPT.md §5.8, §12 Phase 3/7).

Shared by two callers that must never depend on each other: `app/agent/llm.py`'s mock LLM
(`LLM_MODEL=mock`, §5.8 "Dev mode") and, for each heuristic, the real-LLM graceful-degradation
fallback in `app/agent/nodes.py`'s `understand` node / `app/agent/qa.py`'s `answer_question`.
Operates on plain dicts, not ORM objects, so it stays independently testable and pure.
"""

from typing import Any, Literal

from app.agent.tools.schemas import AnswerQuestion, ProposeTargetAndProblemType

_ProblemType = Literal[
    "regression", "binary_classification", "multiclass_classification", "clustering", "time_series"
]

_TARGET_NAME_HINTS = (
    "target",
    "label",
    "class",
    "outcome",
    "y",
    "price",
    "survived",
    "churn",
    "fraud",
    "default",
)


def classify_single_column(col: dict[str, Any]) -> _ProblemType:
    """Deterministic problem-type inference for one column's stats — the same rule the mock LLM
    and the graceful-degradation fallback use. Also used by `app.agent.nodes.understand_node` to
    resolve a user-overridden target column without a second LLM call (MASTER_PROMPT.md §5.5/§5.8
    cost minimization): whichever target column is finally confirmed, its problem type is derived
    from data, not re-guessed."""
    if col["semantic_type"] == "boolean" or col["unique_count"] == 2:
        return "binary_classification"
    if col["semantic_type"] == "categorical" and col["unique_count"] <= 20:
        return "multiclass_classification"
    return "regression"


def _classify(col: dict[str, Any], reasoning: str) -> ProposeTargetAndProblemType:
    return ProposeTargetAndProblemType(
        target_column=col["name"],
        problem_type=classify_single_column(col),
        reasoning=reasoning,
        confidence="medium",
    )


def propose_target_and_problem_type(columns: list[dict[str, Any]]) -> ProposeTargetAndProblemType:
    for col in columns:
        name_lower = col["name"].lower()
        if any(hint in name_lower for hint in _TARGET_NAME_HINTS):
            return _classify(
                col, f"Column name '{col['name']}' strongly suggests it's the prediction target."
            )

    candidates = [
        c
        for c in columns
        if c["semantic_type"] in ("categorical", "boolean") and 2 <= c["unique_count"] <= 20
    ]
    if candidates:
        col = candidates[-1]
        return _classify(
            col, f"'{col['name']}' is a low-cardinality categorical column, a plausible target."
        )

    return ProposeTargetAndProblemType(
        target_column=None,
        problem_type="clustering",
        reasoning="No obvious target column found; recommending unsupervised exploration.",
        confidence="low",
    )


def answer_question(
    question: str, referenced_cells: list[dict[str, Any]], column_names: list[str]
) -> AnswerQuestion:
    """Deterministic Q&A fallback (§5.8 mock mode / graceful degradation): never runs new code
    (a heuristic can't judge whether generated code is safe/correct), just grounds a plain
    answer in whatever context it was given — a real cell's last output if the question
    referenced one, otherwise the dataset's column list."""
    if referenced_cells:
        parts = [
            f"Cell '{cell['label'] or cell['cell_type']}' ({cell['status']}): "
            f"{cell['output_summary'] or 'no output captured'}"
            for cell in referenced_cells
        ]
        answer = " | ".join(parts)
    else:
        answer = (
            f"This dataset has {len(column_names)} column(s): {', '.join(column_names)}. "
            "Ask about a specific cell (e.g. '@cell-3') or column for more detail."
        )
    return AnswerQuestion(answer=answer, needs_computation=False, code=None, cell_purpose=None)
