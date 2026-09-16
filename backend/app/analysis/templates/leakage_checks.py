"""Target leakage heuristics (MASTER_PROMPT.md §5.3 "Leakage heuristics (always run)"):
absurdly high single-feature correlation with the target, near-duplicates of the target,
post-event column name hints, and ID-like columns correlated with the target. Runs for
classification and regression (any confirmed target); clustering/time-series don't have the
row-level supervised-leakage concept this checks for.
"""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_NAME_HINTS = ("_after", "outcome", "status_final", "_final", "_result", "post_", "leak", "label")


def render(params: dict[str, Any]) -> str:
    target = params.get("target_column")
    name_hints = list(_NAME_HINTS)
    return f"""_target = {target!r}
_name_hints = {name_hints!r}
_leakage_summary: dict = {{"target": _target}}

if _target and _target in df.columns:
    _n = max(len(df), 1)
    _nunique = df.nunique(dropna=False)
    _id_like_cols = [
        c for c in df.columns
        if c != _target and _nunique.get(c, 0) > 1 and (_nunique.get(c, 0) / _n) > 0.98
    ]
    _name_flagged = [
        c for c in df.columns
        if c != _target and any(hint in c.lower() for hint in _name_hints)
    ]

    _target_series = df[_target]
    _target_is_numeric = pd.api.types.is_numeric_dtype(_target_series)
    _high_corr = []
    _near_dup = []
    for col in df.columns:
        if col == _target:
            continue
        series = df[col]
        if _target_is_numeric and pd.api.types.is_numeric_dtype(series):
            _aligned = pd.concat([series, _target_series], axis=1).dropna()
            if len(_aligned) > 5:
                _corr = _aligned.iloc[:, 0].corr(_aligned.iloc[:, 1])
                if pd.notna(_corr):
                    if abs(_corr) > 0.95:
                        _high_corr.append({{"column": col, "correlation": round(float(_corr), 4)}})
                    if abs(_corr) > 0.999:
                        _near_dup.append(col)
        else:
            _match_rate = (series.astype(str) == _target_series.astype(str)).mean()
            if _match_rate > 0.98:
                _near_dup.append(col)

    _high_corr_cols = [item["column"] for item in _high_corr]
    _id_corr_with_target = [c for c in _id_like_cols if c in _high_corr_cols]

    _leakage_summary.update({{
        "high_correlation_features": _high_corr,
        "near_duplicate_columns": sorted(set(_near_dup)),
        "suspicious_name_columns": _name_flagged,
        "id_like_correlated_with_target": _id_corr_with_target,
    }})

print("##DATAPILOT_SUMMARY##" + json.dumps(_leakage_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if summary.get("target") is None or "high_correlation_features" not in summary:
        return ["No confirmed target — skipping leakage checks."]

    bullets = []
    near_dup = summary.get("near_duplicate_columns") or []
    if near_dup:
        bullets.append(
            f"Possible target leakage: {', '.join(near_dup)} look like near-duplicates of the "
            "target — verify these aren't derived from it and drop them if so."
        )
    high_corr = [
        item
        for item in (summary.get("high_correlation_features") or [])
        if item["column"] not in near_dup
    ]
    if high_corr:
        desc = ", ".join(
            f"{item['column']} (r={item['correlation']:.2f})" for item in high_corr[:3]
        )
        bullets.append(
            f"Suspiciously high correlation with the target: {desc} — check for leakage."
        )
    id_corr = summary.get("id_like_correlated_with_target") or []
    if id_corr:
        bullets.append(
            f"ID-like column(s) correlated with the target: {', '.join(id_corr)} — likely an "
            "artifact of row ordering or a leak, not a real feature."
        )
    name_flagged = summary.get("suspicious_name_columns") or []
    if name_flagged:
        bullets.append(
            f"Column name(s) suggest post-outcome information: {', '.join(name_flagged)} — "
            "confirm these were known before the prediction point."
        )
    return bullets or [
        "No obvious target leakage detected by name, correlation, or duplication checks."
    ]


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="leakage_checks",
    title="Target leakage checks",
    description="Flags near-duplicate columns, suspiciously high correlations, ID-like "
    "columns, and post-event column names relative to the target.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
