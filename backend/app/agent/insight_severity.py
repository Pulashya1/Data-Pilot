"""Severity classification for streamed insight cards (MASTER_PROMPT.md §7, §12 Phase 3).

`Template.summarize()` (Phase 2, `app/analysis/templates/base.py`) already turns a template's
raw `##DATAPILOT_SUMMARY##` dict into grounded insight bullets; this only picks a severity
("info"/"warning"/"critical") for those bullets from the same raw dict, per template key.
Defaults to `"info"` for any template not explicitly handled below, so new templates (Phase 5)
never break this.
"""

from typing import Any, Literal

Severity = Literal["info", "warning", "critical"]


def _bucket(value: float, *, warning: float, critical: float) -> Severity:
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "info"


def classify_severity(template_key: str, summary: dict[str, Any]) -> Severity:
    if template_key == "missing_values":
        return _bucket(summary.get("worst_pct") or 0, warning=15, critical=50)

    if template_key == "duplicates":
        return _bucket(summary.get("duplicate_pct") or 0, warning=5, critical=20)

    if template_key == "constant_and_id_columns":
        count = len(summary.get("constant_columns") or []) + len(
            summary.get("id_like_columns") or []
        )
        return _bucket(count, warning=1, critical=5)

    if template_key == "outliers":
        pcts = [v.get("iqr_outlier_pct", 0) for v in summary.values() if isinstance(v, dict)]
        return _bucket(max(pcts, default=0), warning=5, critical=15)

    if template_key == "correlations":
        strongest = abs(summary.get("strongest_pearson_value") or 0)
        has_high_vif = bool(summary.get("high_vif_columns"))
        if strongest >= 0.95 or has_high_vif:
            return "warning"
        return "info"

    return "info"
