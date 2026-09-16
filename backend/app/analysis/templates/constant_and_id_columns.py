"""Constant and ID-like column detection (MASTER_PROMPT.md §5.3, all problem types)."""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_CODE = """_nunique = df.nunique(dropna=False)
_constant_cols = _nunique[_nunique <= 1].index.tolist()
_n = max(len(df), 1)
_id_like_cols = [
    c for c in df.columns
    if _nunique.get(c, 0) > 1 and (_nunique.get(c, 0) / _n) > 0.98
]
_uniqueness_df = pd.DataFrame(
    {"unique_count": _nunique, "unique_ratio": (_nunique / _n).round(3)}
).sort_values("unique_ratio", ascending=False)
display(_uniqueness_df.head(15))

_const_id_summary = {
    "constant_columns": [str(c) for c in _constant_cols],
    "id_like_columns": [str(c) for c in _id_like_cols],
}
print("##DATAPILOT_SUMMARY##" + json.dumps(_const_id_summary))
"""


def render(params: dict[str, Any]) -> str:
    return _CODE


def summarize(summary: dict[str, Any]) -> list[str]:
    bullets = []
    if summary["constant_columns"]:
        cols = ", ".join(summary["constant_columns"])
        bullets.append(f"Constant columns (a single value throughout): {cols}.")
    else:
        bullets.append("No constant columns found.")
    if summary["id_like_columns"]:
        bullets.append(
            f"ID-like columns (>98% unique values): {', '.join(summary['id_like_columns'])} — "
            "consider dropping these before modeling."
        )
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="constant_and_id_columns",
    title="Constant & ID-like columns",
    description="Flags constant/near-constant columns and high-cardinality ID-like columns.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
