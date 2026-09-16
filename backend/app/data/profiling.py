"""Deterministic dataset profiling: shape, dtypes, missingness, stats, data quality score.

MASTER_PROMPT.md §5.1 (ingest) and §12 (Phase 1). No LLM involved.
"""

import math

import numpy as np
import pandas as pd

from app.schemas.dataset import ColumnProfile, DataQualityScore, DatasetProfile, TopValue

_NUMERIC_STAT_NAMES = ["mean", "std", "min", "25%", "50%", "75%", "max", "skew", "kurtosis"]


def _clean_float(value: float) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return float(value)


def _json_safe_scalar(value: object) -> object:
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def _column_profile(series: pd.Series, n_rows: int) -> ColumnProfile:
    missing_count = int(series.isna().sum())
    numeric_stats: dict[str, float] | None = None
    top_values: list[TopValue] | None = None

    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        described = series.describe()
        stats: dict[str, float] = {}
        for name in _NUMERIC_STAT_NAMES:
            if name == "skew":
                raw = series.skew()
            elif name == "kurtosis":
                raw = series.kurt()
            else:
                raw = described.get(name)
            cleaned = _clean_float(raw) if raw is not None else None
            if cleaned is not None:
                stats[name] = cleaned
        numeric_stats = stats
    else:
        counts = series.value_counts(dropna=True).head(5)
        top_values = [
            TopValue(value=_json_safe_scalar(value), count=int(count))
            for value, count in counts.items()
        ]

    return ColumnProfile(
        name=str(series.name),
        dtype=str(series.dtype),
        missing_count=missing_count,
        missing_pct=round(100 * missing_count / n_rows, 2) if n_rows else 0.0,
        unique_count=int(series.nunique(dropna=True)),
        numeric_stats=numeric_stats,
        top_values=top_values,
    )


def compute_data_quality_score(
    *,
    n_rows: int,
    n_columns: int,
    total_missing_cells: int,
    duplicate_pct: float,
    constant_columns: list[str],
    columns: list[ColumnProfile],
    is_sampled: bool,
    total_rows: int,
) -> DataQualityScore:
    total_cells = max(1, n_rows * max(1, n_columns))
    completeness = 100 * (1 - total_missing_cells / total_cells)
    uniqueness = max(0.0, 100 - duplicate_pct)
    constant_fraction = len(constant_columns) / max(1, n_columns)
    consistency = 100 * (1 - constant_fraction)

    overall = 0.5 * completeness + 0.3 * uniqueness + 0.2 * consistency

    issues: list[str] = []
    for col in columns:
        if col.missing_pct > 20:
            issues.append(f"Column '{col.name}' has {col.missing_pct:.1f}% missing values.")
    if duplicate_pct > 5:
        issues.append(f"{duplicate_pct:.1f}% of rows are exact duplicates.")
    for name in constant_columns:
        issues.append(f"Column '{name}' has a single constant value across all rows.")
    if is_sampled:
        issues.append(
            f"Profiled a random sample of {n_rows:,} rows out of {total_rows:,} total; "
            "duplicate and constant-column checks are approximate."
        )

    return DataQualityScore(
        overall=round(max(0.0, min(100.0, overall)), 1),
        breakdown={
            "completeness": round(max(0.0, min(100.0, completeness)), 1),
            "uniqueness": round(max(0.0, min(100.0, uniqueness)), 1),
            "consistency": round(max(0.0, min(100.0, consistency)), 1),
        },
        issues=issues,
    )


def rows_to_json_safe(df: pd.DataFrame) -> list[dict[str, object]]:
    """Convert a DataFrame slice into JSON-serializable records (NaN -> None)."""
    records: list[dict[str, object]] = []
    for row in df.itertuples(index=False, name=None):
        records.append(
            {
                str(col): (
                    None
                    if isinstance(value, float) and math.isnan(value)
                    else _json_safe_scalar(value)
                )
                for col, value in zip(df.columns, row, strict=True)
            }
        )
    return records


def build_profile(
    df: pd.DataFrame,
    *,
    total_rows: int,
    is_sampled: bool,
    sample_size: int | None,
) -> DatasetProfile:
    n_rows = len(df)
    n_columns = df.shape[1]

    columns = [_column_profile(df[col], n_rows) for col in df.columns]
    total_missing_cells = sum(c.missing_count for c in columns)

    n_duplicate_rows = int(df.duplicated().sum())
    duplicate_pct = round(100 * n_duplicate_rows / n_rows, 2) if n_rows else 0.0
    constant_columns = [str(col) for col in df.columns if df[col].nunique(dropna=False) <= 1]

    data_quality = compute_data_quality_score(
        n_rows=n_rows,
        n_columns=n_columns,
        total_missing_cells=total_missing_cells,
        duplicate_pct=duplicate_pct,
        constant_columns=constant_columns,
        columns=columns,
        is_sampled=is_sampled,
        total_rows=total_rows,
    )

    return DatasetProfile(
        n_rows=total_rows,
        n_columns=n_columns,
        memory_usage_bytes=int(df.memory_usage(deep=True).sum()),
        is_sampled=is_sampled,
        sample_size=sample_size,
        columns=columns,
        n_duplicate_rows=n_duplicate_rows,
        duplicate_pct=duplicate_pct,
        constant_columns=constant_columns,
        data_quality=data_quality,
    )
