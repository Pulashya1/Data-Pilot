"""Class balance for classification targets (MASTER_PROMPT.md §5.3 Classification).

Reports class counts/proportions and flags imbalance with a concrete resampling/class-weight
suggestion. No-ops (empty summary) when there's no confirmed target, so the generic
`test_template_renders_and_runs` parametrization (which calls `default_params` without a
target) still produces exactly one summary marker.
"""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile


def render(params: dict[str, Any]) -> str:
    target = params.get("target_column")
    return f"""_target = {target!r}
_balance_summary: dict = {{"target": _target}}

if _target and _target in df.columns:
    _counts = df[_target].value_counts(dropna=False)
    _pct = (100 * _counts / _counts.sum()).round(2)
    _balance_df = pd.DataFrame({{"count": _counts, "pct": _pct}})
    display(_balance_df)

    plt.figure(figsize=(6, 3))
    _counts.plot(kind="bar")
    plt.title(f"Class balance of {{_target}}")
    plt.tight_layout()
    plt.show()

    _majority_count = int(_counts.max())
    _minority_count = int(_counts.min())
    _imbalance_ratio = round(_majority_count / _minority_count, 2) if _minority_count else None
    _balance_summary.update({{
        "class_counts": {{str(k): int(v) for k, v in _counts.items()}},
        "n_classes": int(_counts.shape[0]),
        "majority_class": str(_counts.idxmax()),
        "minority_class": str(_counts.idxmin()),
        "minority_pct": float(_pct.min()),
        "imbalance_ratio": _imbalance_ratio,
    }})

print("##DATAPILOT_SUMMARY##" + json.dumps(_balance_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if not summary.get("class_counts"):
        return ["No confirmed classification target — skipping class balance."]
    ratio = summary.get("imbalance_ratio")
    bullets = [
        f"Target '{summary['target']}' has {summary['n_classes']} classes; "
        f"minority class '{summary['minority_class']}' is {summary['minority_pct']:.1f}% "
        "of the data."
    ]
    if ratio is not None and ratio >= 3:
        severity = "Severe" if ratio >= 10 else "Moderate"
        bullets.append(
            f"{severity} class imbalance (majority:minority ratio {ratio:.1f}:1) — consider "
            "`class_weight='balanced'`, or resampling (SMOTE/undersampling via "
            "imbalanced-learn), and prefer PR-AUC/F1 over accuracy."
        )
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="class_balance",
    title="Class balance",
    description="Class counts/proportions for the target with an imbalance warning.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
