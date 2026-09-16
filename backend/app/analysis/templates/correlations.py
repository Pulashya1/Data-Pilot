"""Correlations: Pearson/Spearman + VIF for numeric, Cramér's V for categorical
(MASTER_PROMPT.md §5.3, all problem types)."""

from typing import Any

from app.analysis.templates.base import Template, categorical_columns, numeric_columns
from app.schemas.dataset import DatasetProfile


def render(params: dict[str, Any]) -> str:
    numeric_cols = params.get("numeric_columns", [])
    cat_cols = params.get("categorical_columns", [])
    return f"""_numeric_cols = {numeric_cols!r}
_categorical_cols = {cat_cols!r}
_corr_summary = {{}}

_numeric_df = df[[c for c in _numeric_cols if c in df.columns]].dropna()
if _numeric_df.shape[1] >= 2:
    _pearson = _numeric_df.corr(method="pearson")
    _spearman = _numeric_df.corr(method="spearman")
    plt.figure(figsize=(6, 5))
    sns.heatmap(_pearson, annot=True, fmt=".2f", cmap="coolwarm", center=0)
    plt.title("Pearson correlation")
    plt.tight_layout()
    plt.show()
    plt.figure(figsize=(6, 5))
    sns.heatmap(_spearman, annot=True, fmt=".2f", cmap="coolwarm", center=0)
    plt.title("Spearman correlation")
    plt.tight_layout()
    plt.show()

    _pairs = _pearson.where(~np.eye(len(_pearson), dtype=bool)).abs().unstack().dropna()
    if len(_pairs):
        _top_a, _top_b = _pairs.idxmax()
        _corr_summary["strongest_pearson_pair"] = [str(_top_a), str(_top_b)]
        _corr_summary["strongest_pearson_value"] = round(float(_pearson.loc[_top_a, _top_b]), 3)

    from statsmodels.stats.outliers_influence import variance_inflation_factor
    _vif_input = _numeric_df.assign(_const=1.0).to_numpy()
    _vif = pd.Series(
        [variance_inflation_factor(_vif_input, i) for i in range(_numeric_df.shape[1])],
        index=_numeric_df.columns,
    ).sort_values(ascending=False)
    display(_vif.to_frame("VIF"))
    _corr_summary["high_vif_columns"] = [str(c) for c in _vif[_vif > 10].index]

from scipy.stats import chi2_contingency

def _cramers_v(a, b):
    ct = pd.crosstab(a, b)
    if ct.empty:
        return 0.0
    chi2 = chi2_contingency(ct)[0]
    n = ct.to_numpy().sum()
    r, k = ct.shape
    denom = max(min(r - 1, k - 1), 1)
    return float(np.sqrt((chi2 / n) / denom)) if n else 0.0

_cat_cols_present = [c for c in _categorical_cols if c in df.columns]
if len(_cat_cols_present) >= 2:
    _cramers = pd.DataFrame(index=_cat_cols_present, columns=_cat_cols_present, dtype=float)
    for a in _cat_cols_present:
        for b in _cat_cols_present:
            _cramers.loc[a, b] = 1.0 if a == b else _cramers_v(df[a], df[b])
    plt.figure(figsize=(6, 5))
    sns.heatmap(_cramers.astype(float), annot=True, fmt=".2f", cmap="viridis")
    plt.title("Cramer's V (categorical association)")
    plt.tight_layout()
    plt.show()

print("##DATAPILOT_SUMMARY##" + json.dumps(_corr_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    bullets = []
    pair = summary.get("strongest_pearson_pair")
    value = summary.get("strongest_pearson_value")
    if pair and value is not None:
        bullets.append(f"Strongest correlation: {pair[0]} vs {pair[1]} (Pearson r={value:.2f}).")
    high_vif = summary.get("high_vif_columns") or []
    if high_vif:
        cols = ", ".join(high_vif)
        bullets.append(
            f"High multicollinearity (VIF > 10): {cols} — consider dropping or combining these."
        )
    return bullets or ["Not enough numeric or categorical columns to compute correlations."]


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {
        "numeric_columns": numeric_columns(profile),
        "categorical_columns": categorical_columns(profile),
    }


TEMPLATE = Template(
    key="correlations",
    title="Correlations & multicollinearity",
    description="Pearson/Spearman heatmaps, Cramer's V for categoricals, and a VIF table.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
