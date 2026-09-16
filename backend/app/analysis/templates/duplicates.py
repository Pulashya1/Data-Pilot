"""Exact duplicate row detection (MASTER_PROMPT.md §5.3, all problem types)."""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_CODE = """_dup_mask = df.duplicated(keep=False)
_dup_count = int(df.duplicated().sum())
_dup_pct = round(100 * _dup_count / len(df), 2) if len(df) else 0.0
if _dup_count:
    display(df[_dup_mask].sort_values(list(df.columns)).head(20))

_dup_summary = {"duplicate_rows": _dup_count, "duplicate_pct": _dup_pct}
print("##DATAPILOT_SUMMARY##" + json.dumps(_dup_summary))
"""


def render(params: dict[str, Any]) -> str:
    return _CODE


def summarize(summary: dict[str, Any]) -> list[str]:
    if summary["duplicate_rows"] == 0:
        return ["No exact duplicate rows were found."]
    rows, pct = summary["duplicate_rows"], summary["duplicate_pct"]
    return [f"{rows:,} exact duplicate rows ({pct:.1f}% of the data)."]


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="duplicates",
    title="Duplicate rows",
    description="Counts and previews exact duplicate rows.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
