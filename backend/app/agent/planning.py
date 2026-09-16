"""Deterministic problem-type -> template-order plan (MASTER_PROMPT.md §5.1 `plan`, §12 Phase 3).

No LLM call: the template catalog (`app/analysis/templates/registry.py`) is small and fixed
today, so picking an order is a lookup, not a generation task — keeps this node free (§5.5,
§5.8). Every problem type currently maps to the same generic order since problem-type-specific
templates (classification/regression/clustering/time-series) land in Phase 5; this is a Phase 3
assumption, not a bug, and will read from `app.analysis.templates.registry.TEMPLATES` correctly
whichever way that catalog grows.
"""

from app.analysis.templates.registry import TEMPLATES

_GENERIC_ORDER = [
    "overview",
    "duplicates",
    "constant_and_id_columns",
    "missing_values",
    "univariate_distributions",
    "outliers",
    "correlations",
]

PROBLEM_TYPE_TEMPLATE_ORDER: dict[str, list[str]] = {
    problem_type: [key for key in _GENERIC_ORDER if key in TEMPLATES]
    for problem_type in (
        "regression",
        "binary_classification",
        "multiclass_classification",
        "clustering",
        "time_series",
    )
}


def build_plan(problem_type: str | None) -> list[str]:
    if problem_type is None:
        return PROBLEM_TYPE_TEMPLATE_ORDER["clustering"]
    default = [key for key in _GENERIC_ORDER if key in TEMPLATES]
    return PROBLEM_TYPE_TEMPLATE_ORDER.get(problem_type, default)
