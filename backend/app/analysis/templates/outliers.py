"""Outlier detection via IQR and z-score (MASTER_PROMPT.md §5.3, all problem types)."""

from typing import Any

from app.analysis.templates.base import Template, numeric_columns
from app.schemas.dataset import DatasetProfile


def render(params: dict[str, Any]) -> str:
    numeric_cols = params.get("numeric_columns", [])
    return f"""_numeric_cols = {numeric_cols!r}
_outlier_summary = {{}}

for col in _numeric_cols:
    if col not in df.columns:
        continue
    series = df[col].dropna()
    if len(series) < 5:
        continue
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    iqr_outliers = int(((series < lower) | (series > upper)).sum())
    std = series.std(ddof=0)
    z_outliers = int(((series - series.mean()).abs() > 3 * std).sum()) if std else 0
    _outlier_summary[col] = {{
        "iqr_outliers": iqr_outliers,
        "iqr_outlier_pct": round(100 * iqr_outliers / len(series), 2),
        "z_score_outliers": z_outliers,
    }}

_present_cols = [c for c in _numeric_cols if c in df.columns]
if _present_cols:
    plt.figure(figsize=(max(6, len(_present_cols) * 1.2), 4))
    sns.boxplot(data=df[_present_cols])
    plt.xticks(rotation=45, ha="right")
    plt.title("Boxplots (IQR outliers)")
    plt.tight_layout()
    plt.show()

print("##DATAPILOT_SUMMARY##" + json.dumps(_outlier_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if not summary:
        return ["No numeric columns were available to check for outliers."]
    worst = sorted(summary.items(), key=lambda item: item[1]["iqr_outlier_pct"], reverse=True)
    bullets = []
    for col, stats in worst[:3]:
        if stats["iqr_outliers"] == 0:
            continue
        bullets.append(
            f"'{col}': {stats['iqr_outliers']} IQR outliers ({stats['iqr_outlier_pct']:.1f}%), "
            f"{stats['z_score_outliers']} points beyond 3 standard deviations."
        )
    return bullets or ["No significant outliers detected by IQR or z-score."]


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {"numeric_columns": numeric_columns(profile)}


TEMPLATE = Template(
    key="outliers",
    title="Outliers (IQR & z-score)",
    description="Flags outliers per numeric column using both the IQR rule and z-scores.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
