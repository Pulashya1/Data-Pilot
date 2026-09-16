"""Catalog of available analysis templates (MASTER_PROMPT.md §5.3, §12 Phase 2)."""

from app.analysis.templates.base import Template
from app.analysis.templates.constant_and_id_columns import TEMPLATE as CONSTANT_AND_ID_COLUMNS
from app.analysis.templates.correlations import TEMPLATE as CORRELATIONS
from app.analysis.templates.duplicates import TEMPLATE as DUPLICATES
from app.analysis.templates.missing_values import TEMPLATE as MISSING_VALUES
from app.analysis.templates.outliers import TEMPLATE as OUTLIERS
from app.analysis.templates.overview import TEMPLATE as OVERVIEW
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
    )
}
