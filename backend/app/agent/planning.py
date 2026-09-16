"""Deterministic problem-type -> template-order plan (MASTER_PROMPT.md §5.1 `plan`, §12 Phase 3/5).

No LLM call: the template catalog (`app/analysis/templates/registry.py`) is small and fixed
today, so picking an order is a lookup, not a generation task — keeps this node free (§5.5,
§5.8). The generic EDA core runs for every problem type; each problem type then appends its
own templates from `app/analysis/templates/registry.py` (MASTER_PROMPT.md §5.3) — classification
and regression both get the leakage checks ("always run" whenever there's a target), clustering
and time series don't (there's no row-level supervised-leakage concept without one).
"""

from app.analysis.templates.registry import TEMPLATES

_GENERIC_CORE = [
    "overview",
    "duplicates",
    "constant_and_id_columns",
    "missing_values",
    "univariate_distributions",
    "outliers",
    "correlations",
]

_PROBLEM_TYPE_EXTRA: dict[str, list[str]] = {
    "regression": ["regression_target_analysis", "leakage_checks"],
    "binary_classification": ["class_balance", "classification_feature_analysis", "leakage_checks"],
    "multiclass_classification": [
        "class_balance",
        "classification_feature_analysis",
        "leakage_checks",
    ],
    "clustering": ["clustering_analysis"],
    "time_series": ["time_series_analysis"],
}

PROBLEM_TYPE_TEMPLATE_ORDER: dict[str, list[str]] = {
    problem_type: [key for key in _GENERIC_CORE + extra if key in TEMPLATES]
    for problem_type, extra in _PROBLEM_TYPE_EXTRA.items()
}

# Templates offered as `plan_approval` options (MASTER_PROMPT.md §5.1 step 3's editable EDA
# plan). `feature_engineering`/`baseline_model` (§12 Phase 6) are deliberately excluded: they're
# separate graph steps with their own dedicated decisions (`app.agent.nodes.
# feature_engineering_node`/`baseline_node`), not EDA-plan steps, so they'd otherwise be
# addable twice.
_NON_PLAN_TEMPLATE_KEYS = {"feature_engineering", "baseline_model"}
EDA_PLAN_TEMPLATE_KEYS: list[str] = [key for key in TEMPLATES if key not in _NON_PLAN_TEMPLATE_KEYS]


def build_plan(problem_type: str | None) -> list[str]:
    if problem_type is None:
        return PROBLEM_TYPE_TEMPLATE_ORDER["clustering"]
    default = [key for key in _GENERIC_CORE if key in TEMPLATES]
    return PROBLEM_TYPE_TEMPLATE_ORDER.get(problem_type, default)
