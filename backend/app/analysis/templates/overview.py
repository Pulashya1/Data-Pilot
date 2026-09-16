"""Shape, dtypes, and memory overview (MASTER_PROMPT.md §5.3, all problem types)."""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_CODE = """df.info()
display(df.describe(include="all").transpose())

_overview_summary = {
    "n_rows": int(df.shape[0]),
    "n_columns": int(df.shape[1]),
    "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1e6, 2),
    "dtype_counts": {str(k): int(v) for k, v in df.dtypes.astype(str).value_counts().items()},
}
print("##DATAPILOT_SUMMARY##" + json.dumps(_overview_summary))
"""


def render(params: dict[str, Any]) -> str:
    return _CODE


def summarize(summary: dict[str, Any]) -> list[str]:
    dtypes = ", ".join(f"{k} ({v})" for k, v in summary["dtype_counts"].items())
    return [
        f"The dataset has {summary['n_rows']:,} rows and {summary['n_columns']} columns "
        f"(~{summary['memory_mb']:.1f} MB in memory).",
        f"Column types: {dtypes}.",
    ]


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="overview",
    title="Shape & dtypes overview",
    description="Row/column counts, memory usage, and dtype breakdown.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
