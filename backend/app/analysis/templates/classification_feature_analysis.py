"""Feature-target association for classification (MASTER_PROMPT.md §5.3 Classification):
mutual information, chi-square for categoricals, ANOVA F-test for numeric features, and
box plots of the strongest numeric features by class.
"""

from typing import Any

from app.analysis.templates.base import Template, categorical_columns, numeric_columns
from app.schemas.dataset import DatasetProfile


def render(params: dict[str, Any]) -> str:
    numeric_cols = params.get("numeric_columns", [])
    cat_cols = params.get("categorical_columns", [])
    target = params.get("target_column")
    return f"""_target = {target!r}
_numeric_cols = {numeric_cols!r}
_categorical_cols = {cat_cols!r}
_cls_summary: dict = {{"target": _target}}

if _target and _target in df.columns:
    _numeric_features = [c for c in _numeric_cols if c != _target and c in df.columns]
    _cat_features = [c for c in _categorical_cols if c != _target and c in df.columns]
    _y = df[_target]

    from scipy.stats import chi2_contingency, f_oneway

    _anova_results = {{}}
    for col in _numeric_features:
        _valid = df[[col, _target]].dropna()
        if _valid[_target].nunique() < 2:
            continue
        _groups = [g[col].to_numpy() for _, g in _valid.groupby(_target) if len(g) > 1]
        if len(_groups) < 2:
            continue
        _stat, _p = f_oneway(*_groups)
        if pd.notna(_stat) and pd.notna(_p):
            _anova_results[col] = {{
                "f_stat": round(float(_stat), 3), "p_value": round(float(_p), 5)
            }}

    _chi2_results = {{}}
    for col in _cat_features:
        _ct = pd.crosstab(df[col], _y)
        if _ct.shape[0] < 2 or _ct.shape[1] < 2:
            continue
        _chi2, _p = chi2_contingency(_ct)[:2]
        _chi2_results[col] = {{"chi2": round(float(_chi2), 3), "p_value": round(float(_p), 5)}}

    _mi_scores = {{}}
    if _numeric_features:
        from sklearn.feature_selection import mutual_info_classif
        from sklearn.preprocessing import LabelEncoder

        _valid_mask = _y.notna()
        _X = df.loc[_valid_mask, _numeric_features].copy()
        for col in _numeric_features:
            _X[col] = _X[col].fillna(_X[col].median())
        if len(_X) > 5:
            _y_enc = LabelEncoder().fit_transform(_y[_valid_mask].astype(str))
            _mi = mutual_info_classif(_X, _y_enc, random_state=42)
            _mi_scores = {{
                col: round(float(v), 4) for col, v in zip(_numeric_features, _mi, strict=True)
            }}

    _top_numeric = sorted(
        _anova_results.items(), key=lambda kv: kv[1]["f_stat"], reverse=True
    )[:3]
    for col, _ in _top_numeric:
        plt.figure(figsize=(6, 3))
        sns.boxplot(data=df, x=_target, y=col)
        plt.title(f"{{col}} by {{_target}}")
        plt.tight_layout()
        plt.show()

    _cls_summary.update({{
        "anova": _anova_results,
        "chi_square": _chi2_results,
        "mutual_info": _mi_scores,
    }})

print("##DATAPILOT_SUMMARY##" + json.dumps(_cls_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    anova = summary.get("anova") or {}
    chi_square = summary.get("chi_square") or {}
    mutual_info = summary.get("mutual_info") or {}
    if not anova and not chi_square and not mutual_info:
        return ["No confirmed classification target, or no usable features — skipping."]

    bullets = []
    sig_anova = sorted(
        ((c, s) for c, s in anova.items() if s["p_value"] < 0.05),
        key=lambda kv: kv[1]["f_stat"],
        reverse=True,
    )
    if sig_anova:
        top = ", ".join(
            f"{c} (F={s['f_stat']:.1f}, p={s['p_value']:.4f})" for c, s in sig_anova[:3]
        )
        bullets.append(f"Numeric features most associated with the target (ANOVA): {top}.")

    sig_chi2 = sorted(
        ((c, s) for c, s in chi_square.items() if s["p_value"] < 0.05),
        key=lambda kv: kv[1]["chi2"],
        reverse=True,
    )
    if sig_chi2:
        top = ", ".join(f"{c} (p={s['p_value']:.4f})" for c, s in sig_chi2[:3])
        bullets.append(
            f"Categorical features significantly associated with the target (chi-square): {top}."
        )

    if mutual_info:
        top_mi = sorted(mutual_info.items(), key=lambda kv: kv[1], reverse=True)[:3]
        bullets.append(
            "Top features by mutual information: "
            + ", ".join(f"{c} ({v:.3f})" for c, v in top_mi)
            + "."
        )

    return bullets or ["No statistically significant feature associations found at p<0.05."]


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {
        "numeric_columns": numeric_columns(profile),
        "categorical_columns": categorical_columns(profile),
    }


TEMPLATE = Template(
    key="classification_feature_analysis",
    title="Feature-target association (classification)",
    description="Mutual information, chi-square, and ANOVA F-test between features and the target.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
