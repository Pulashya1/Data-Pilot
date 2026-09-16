"""Univariate distributions: histograms + skew/kurtosis for numeric, bar charts for
categorical (MASTER_PROMPT.md §5.3, all problem types)."""

from typing import Any

from app.analysis.templates.base import Template, categorical_columns, numeric_columns
from app.schemas.dataset import DatasetProfile


def render(params: dict[str, Any]) -> str:
    numeric_cols = params.get("numeric_columns", [])
    cat_cols = params.get("categorical_columns", [])
    return f"""_numeric_cols = {numeric_cols!r}
_categorical_cols = {cat_cols!r}
_dist_summary = {{}}

for col in _numeric_cols:
    if col not in df.columns:
        continue
    series = df[col].dropna()
    if series.empty:
        continue
    _dist_summary[col] = {{
        "skew": round(float(series.skew()), 3),
        "kurtosis": round(float(series.kurt()), 3),
    }}
    plt.figure(figsize=(6, 3))
    sns.histplot(series, kde=True)
    plt.title(f"Distribution of {{col}}")
    plt.tight_layout()
    plt.show()

for col in _categorical_cols:
    if col not in df.columns:
        continue
    plt.figure(figsize=(6, 3))
    df[col].value_counts().head(10).plot(kind="bar")
    plt.title(f"Top values of {{col}}")
    plt.tight_layout()
    plt.show()

print("##DATAPILOT_SUMMARY##" + json.dumps(_dist_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if not summary:
        return ["No numeric columns were available to profile."]
    skewed = [(col, stats["skew"]) for col, stats in summary.items() if abs(stats["skew"]) > 1]
    bullets = [f"Profiled distributions for {len(summary)} numeric column(s)."]
    if skewed:
        skewed.sort(key=lambda item: abs(item[1]), reverse=True)
        top = ", ".join(f"{col} (skew={skew:.2f})" for col, skew in skewed[:3])
        bullets.append(f"Notably skewed columns: {top} — consider a log or Box-Cox transform.")
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {
        "numeric_columns": numeric_columns(profile),
        "categorical_columns": categorical_columns(profile),
    }


TEMPLATE = Template(
    key="univariate_distributions",
    title="Univariate distributions",
    description="Histograms with skew/kurtosis for numeric columns, bar charts for categorical.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
