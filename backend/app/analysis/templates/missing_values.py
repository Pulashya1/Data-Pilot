"""Missing-value matrix and per-column missingness (MASTER_PROMPT.md §5.3, all problem types)."""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_CODE = """_missing_counts = df.isna().sum()
_n = len(df)
_missing_pct = (100 * _missing_counts / _n).round(2) if _n else _missing_counts.astype(float)
_missing_df = pd.DataFrame({"missing_count": _missing_counts, "missing_pct": _missing_pct})
_missing_df = _missing_df[_missing_df["missing_count"] > 0]
_missing_df = _missing_df.sort_values("missing_pct", ascending=False)
display(_missing_df)

if not df.empty:
    plt.figure(figsize=(10, min(6, 0.3 * len(df.columns) + 2)))
    sns.heatmap(df.isna(), cbar=False, yticklabels=False)
    plt.title("Missing value matrix")
    plt.show()

_missing_summary = {
    "columns_with_missing": int((_missing_counts > 0).sum()),
    "total_missing_cells": int(_missing_counts.sum()),
    "worst_column": (str(_missing_pct.idxmax()) if _missing_pct.max() > 0 else None),
    "worst_pct": float(_missing_pct.max()) if len(_missing_pct) else 0.0,
}
print("##DATAPILOT_SUMMARY##" + json.dumps(_missing_summary))
"""


def render(params: dict[str, Any]) -> str:
    return _CODE


def summarize(summary: dict[str, Any]) -> list[str]:
    if summary["columns_with_missing"] == 0:
        return ["No missing values were found in any column."]
    bullets = [
        f"{summary['columns_with_missing']} column(s) have missing values, "
        f"{summary['total_missing_cells']:,} missing cells in total.",
    ]
    if summary["worst_column"]:
        col, pct = summary["worst_column"], summary["worst_pct"]
        bullets.append(f"'{col}' is the worst offender at {pct:.1f}% missing.")
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="missing_values",
    title="Missing values",
    description="Missing-value matrix and a per-column missingness breakdown.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
