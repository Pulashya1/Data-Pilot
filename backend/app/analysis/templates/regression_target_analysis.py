"""Regression target analysis (MASTER_PROMPT.md §5.3 Regression): target distribution +
transform suggestion, top-correlated-feature scatter plots, mutual information, and a quick
Breusch-Pagan heteroscedasticity check on a small linear fit of the top features.
"""

from typing import Any

from app.analysis.templates.base import Template, numeric_columns
from app.schemas.dataset import DatasetProfile


def render(params: dict[str, Any]) -> str:
    numeric_cols = params.get("numeric_columns", [])
    target = params.get("target_column")
    return f"""_target = {target!r}
_numeric_cols = {numeric_cols!r}
_reg_summary: dict = {{"target": _target}}

if _target and _target in df.columns:
    _y_series = df[_target].dropna()
    _skew = float(_y_series.skew()) if len(_y_series) else 0.0
    _min_val = float(_y_series.min()) if len(_y_series) else 0.0

    plt.figure(figsize=(6, 3))
    sns.histplot(_y_series, kde=True)
    plt.title(f"Distribution of {{_target}}")
    plt.tight_layout()
    plt.show()

    _transform = None
    if abs(_skew) > 1:
        if _min_val > 0:
            _transform = "log"
        elif _min_val >= 0:
            _transform = "Box-Cox (after adding a small positive offset) or Yeo-Johnson"
        else:
            _transform = "Yeo-Johnson"

    _numeric_features = [c for c in _numeric_cols if c != _target and c in df.columns]
    _correlations = {{}}
    for col in _numeric_features:
        _valid = df[[col, _target]].dropna()
        if len(_valid) > 5:
            _corr = _valid[col].corr(_valid[_target])
            if pd.notna(_corr):
                _correlations[col] = round(float(_corr), 4)

    _top_features = sorted(_correlations.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    for col, _ in _top_features:
        plt.figure(figsize=(5, 4))
        plt.scatter(df[col], df[_target], alpha=0.4, s=10)
        plt.xlabel(col)
        plt.ylabel(_target)
        plt.title(f"{{_target}} vs {{col}}")
        plt.tight_layout()
        plt.show()

    _mi_scores = {{}}
    if _numeric_features:
        from sklearn.feature_selection import mutual_info_regression

        _valid_mask = df[_target].notna()
        _X = df.loc[_valid_mask, _numeric_features].copy()
        for col in _numeric_features:
            _X[col] = _X[col].fillna(_X[col].median())
        if len(_X) > 5:
            _mi = mutual_info_regression(_X, df.loc[_valid_mask, _target], random_state=42)
            _mi_scores = {{
                col: round(float(v), 4) for col, v in zip(_numeric_features, _mi, strict=True)
            }}

    _bp_pvalue = None
    _feature_set = [c for c, _ in _top_features]
    if _feature_set:
        import statsmodels.api as sm
        from statsmodels.stats.diagnostic import het_breuschpagan

        _model_df = df[[*_feature_set, _target]].dropna()
        if len(_model_df) > 10:
            _X_design = sm.add_constant(_model_df[_feature_set])
            _ols = sm.OLS(_model_df[_target], _X_design).fit()
            _bp_stat, _bp_pvalue = het_breuschpagan(_ols.resid, _X_design)[:2]
            _bp_pvalue = round(float(_bp_pvalue), 5)

    _reg_summary.update({{
        "skew": round(_skew, 3),
        "suggested_transform": _transform,
        "top_correlated_features": _top_features,
        "mutual_info": _mi_scores,
        "breusch_pagan_p_value": _bp_pvalue,
    }})

print("##DATAPILOT_SUMMARY##" + json.dumps(_reg_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if summary.get("skew") is None:
        return ["No confirmed regression target — skipping target analysis."]

    bullets = [f"Target skew: {summary['skew']:.2f}."]
    if summary.get("suggested_transform"):
        bullets.append(
            f"Target distribution is notably skewed — consider a {summary['suggested_transform']} "
            "transform."
        )
    top = summary.get("top_correlated_features") or []
    if top:
        desc = ", ".join(f"{c} (r={v:.2f})" for c, v in top)
        bullets.append(f"Features most correlated with the target: {desc}.")
    bp_p = summary.get("breusch_pagan_p_value")
    if bp_p is not None and bp_p < 0.05:
        bullets.append(
            f"Breusch-Pagan test on a quick linear fit of the top features suggests "
            f"heteroscedasticity (p={bp_p:.4f}) — consider a transform or a tree-based model."
        )
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {"numeric_columns": numeric_columns(profile)}


TEMPLATE = Template(
    key="regression_target_analysis",
    title="Regression target analysis",
    description="Target distribution/transform suggestion, top feature scatter plots, mutual "
    "information, and a heteroscedasticity check.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
