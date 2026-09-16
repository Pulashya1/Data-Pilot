"""Deterministic semantic column type inference (MASTER_PROMPT.md §5.1, §12 Phase 3).

Runs before the `understand` node's LLM call so the target/problem-type proposal is grounded
in more than raw dtypes. Pure function over the `DatasetProfile` already built in Phase 1/2 —
no new persistence, no migration.
"""

from app.schemas.dataset import DatasetProfile

SemanticType = str  # one of the literals below, kept as `str` to stay JSON/tool-schema friendly

NUMERIC = "numeric"
CATEGORICAL = "categorical"
BOOLEAN = "boolean"
DATETIME = "datetime"
TEXT = "text"
ID_LIKE = "id_like"
CONSTANT = "constant"


def infer_semantic_types(profile: DatasetProfile) -> dict[str, SemanticType]:
    n_rows = max(profile.n_rows, 1)
    constant_columns = set(profile.constant_columns)
    result: dict[str, SemanticType] = {}

    for col in profile.columns:
        if col.name in constant_columns:
            result[col.name] = CONSTANT
        elif col.dtype.startswith("datetime"):
            result[col.name] = DATETIME
        elif col.dtype == "bool" or (col.unique_count == 2 and col.numeric_stats is None):
            result[col.name] = BOOLEAN
        elif n_rows > 1 and col.unique_count >= n_rows * 0.98:
            result[col.name] = ID_LIKE
        elif col.numeric_stats is not None:
            result[col.name] = NUMERIC
        elif col.unique_count / n_rows > 0.5:
            result[col.name] = TEXT
        else:
            result[col.name] = CATEGORICAL

    return result
