"""Typed tool schemas the agent's structured LLM calls are bound to (MASTER_PROMPT.md §5.2).

Only the schemas Phase 3 actually uses — `run_code`/`ask_user`/`emit_insight`/etc. arrive with
the phases that wire them up (§12). Kept flat (no nested models, no `$ref`) per §5.2's
cross-provider tool-schema compatibility note.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ProposeTargetAndProblemType(BaseModel):
    """Propose a prediction target column (or none) and the problem type, from the dataset's
    schema and statistics only — never raw data."""

    target_column: str | None = Field(
        default=None, description="Exact column name to predict, or null for no target."
    )
    problem_type: Literal[
        "regression",
        "binary_classification",
        "multiclass_classification",
        "clustering",
        "time_series",
    ]
    reasoning: str = Field(description="One or two sentences grounded in the actual columns.")
    confidence: Literal["low", "medium", "high"]


class CodeRepair(BaseModel):
    """A corrected version of a notebook cell that failed to execute."""

    code: str = Field(description="The full corrected cell source, not a diff.")
    explanation: str = Field(description="One sentence on what was wrong and what changed.")
