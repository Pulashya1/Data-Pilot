"""MASTER_PROMPT.md §5.1 `plan` / §12 Phase 5: problem-type -> template-order lookup."""

from app.agent.planning import EDA_PLAN_TEMPLATE_KEYS, build_plan
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


def test_generic_core_runs_first_for_every_problem_type() -> None:
    for problem_type in (
        "regression",
        "binary_classification",
        "multiclass_classification",
        "clustering",
        "time_series",
    ):
        steps = build_plan(problem_type)
        assert steps[: len(_GENERIC_CORE)] == _GENERIC_CORE


def test_classification_appends_class_balance_and_leakage() -> None:
    for problem_type in ("binary_classification", "multiclass_classification"):
        steps = build_plan(problem_type)
        assert steps[len(_GENERIC_CORE) :] == [
            "class_balance",
            "classification_feature_analysis",
            "leakage_checks",
        ]


def test_regression_appends_target_analysis_and_leakage() -> None:
    steps = build_plan("regression")
    assert steps[len(_GENERIC_CORE) :] == ["regression_target_analysis", "leakage_checks"]


def test_clustering_appends_clustering_analysis_and_has_no_leakage_step() -> None:
    steps = build_plan("clustering")
    assert steps[len(_GENERIC_CORE) :] == ["clustering_analysis"]
    assert "leakage_checks" not in steps


def test_time_series_appends_time_series_analysis_and_has_no_leakage_step() -> None:
    steps = build_plan("time_series")
    assert steps[len(_GENERIC_CORE) :] == ["time_series_analysis"]
    assert "leakage_checks" not in steps


def test_no_target_falls_back_to_clustering_plan() -> None:
    assert build_plan(None) == build_plan("clustering")


def test_unknown_problem_type_falls_back_to_generic_core() -> None:
    assert build_plan("not-a-real-problem-type") == _GENERIC_CORE


def test_every_planned_step_is_a_known_template() -> None:
    for problem_type in (
        None,
        "regression",
        "binary_classification",
        "multiclass_classification",
        "clustering",
        "time_series",
    ):
        for key in build_plan(problem_type):
            assert key in TEMPLATES


# --- Phase 6: feature engineering & baseline (MASTER_PROMPT.md §5.1 steps 5/6, §12) ---------
# These are separate graph steps with their own dedicated decisions
# (`app.agent.nodes.feature_engineering_node`/`baseline_node`), not editable EDA-plan steps.


def test_feature_engineering_and_baseline_are_not_plan_options() -> None:
    assert "feature_engineering" not in EDA_PLAN_TEMPLATE_KEYS
    assert "baseline_model" not in EDA_PLAN_TEMPLATE_KEYS
    for problem_type in (None, "regression", "binary_classification", "clustering"):
        assert "feature_engineering" not in build_plan(problem_type)
        assert "baseline_model" not in build_plan(problem_type)


def test_feature_engineering_and_baseline_are_still_registered_templates() -> None:
    assert "feature_engineering" in TEMPLATES
    assert "baseline_model" in TEMPLATES
