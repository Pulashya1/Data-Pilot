"""Catalog of available analysis templates (MASTER_PROMPT.md §5.3, §12 Phase 2/5)."""

from app.analysis.templates.base import Template
from app.analysis.templates.baseline_model import TEMPLATE as BASELINE_MODEL
from app.analysis.templates.class_balance import TEMPLATE as CLASS_BALANCE
from app.analysis.templates.classification_feature_analysis import (
    TEMPLATE as CLASSIFICATION_FEATURE_ANALYSIS,
)
from app.analysis.templates.clustering_analysis import TEMPLATE as CLUSTERING_ANALYSIS
from app.analysis.templates.constant_and_id_columns import TEMPLATE as CONSTANT_AND_ID_COLUMNS
from app.analysis.templates.correlations import TEMPLATE as CORRELATIONS
from app.analysis.templates.duplicates import TEMPLATE as DUPLICATES
from app.analysis.templates.feature_engineering import TEMPLATE as FEATURE_ENGINEERING
from app.analysis.templates.leakage_checks import TEMPLATE as LEAKAGE_CHECKS
from app.analysis.templates.missing_values import TEMPLATE as MISSING_VALUES
from app.analysis.templates.outliers import TEMPLATE as OUTLIERS
from app.analysis.templates.overview import TEMPLATE as OVERVIEW
from app.analysis.templates.regression_target_analysis import (
    TEMPLATE as REGRESSION_TARGET_ANALYSIS,
)
from app.analysis.templates.time_series_analysis import TEMPLATE as TIME_SERIES_ANALYSIS
from app.analysis.templates.univariate_distributions import TEMPLATE as UNIVARIATE_DISTRIBUTIONS

TEMPLATES: dict[str, Template] = {
    t.key: t
    for t in (
        OVERVIEW,
        MISSING_VALUES,
        DUPLICATES,
        CONSTANT_AND_ID_COLUMNS,
        UNIVARIATE_DISTRIBUTIONS,
        OUTLIERS,
        CORRELATIONS,
        # Problem-type-specific (MASTER_PROMPT.md §5.3, §12 Phase 5) — app.agent.planning picks
        # which of these run, and in what order, per confirmed problem type.
        CLASS_BALANCE,
        CLASSIFICATION_FEATURE_ANALYSIS,
        REGRESSION_TARGET_ANALYSIS,
        LEAKAGE_CHECKS,
        CLUSTERING_ANALYSIS,
        TIME_SERIES_ANALYSIS,
        # Feature engineering & baseline (MASTER_PROMPT.md §5.1 steps 5/6, §12 Phase 6) — run by
        # app.agent.nodes.feature_engineering_node/baseline_node, not app.agent.planning's
        # per-problem-type EDA plan (they're separate graph steps, not plan_approval options).
        FEATURE_ENGINEERING,
        BASELINE_MODEL,
    )
}
