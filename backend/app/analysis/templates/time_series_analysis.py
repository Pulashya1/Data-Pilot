"""Time series analysis (MASTER_PROMPT.md §5.3 Time series): date-column detection, ordering/
frequency/gaps, trend/seasonality decomposition, ACF/PACF, and lag/rolling-feature + time-aware
split suggestions. The date column is detected heuristically (first datetime-typed or
reliably-parseable column other than the target) since only the value column is a normal
"target" selection here.
"""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_FREQ_PERIOD = {
    "D": 7,
    "B": 5,
    "W": 52,
    "M": 12,
    "MS": 12,
    "Q": 4,
    "QS": 4,
    "A": 1,
    "Y": 1,
    "H": 24,
    "T": 60,
}


def render(params: dict[str, Any]) -> str:
    target = params.get("target_column")
    freq_period = dict(_FREQ_PERIOD)
    return f"""_target = {target!r}
_freq_period = {freq_period!r}
_ts_summary: dict = {{"target": _target}}

_date_col = None
if _target and _target in df.columns:
    _best_rate = 0.0
    for col in df.columns:
        if col == _target:
            continue
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            _date_col = col
            break
        if series.dtype == object:
            _parsed = pd.to_datetime(series, errors="coerce")
            _rate = float(_parsed.notna().mean()) if len(series) else 0.0
            if _rate > 0.95 and _rate > _best_rate:
                _date_col = col
                _best_rate = _rate

_ts_summary["date_column"] = _date_col

if _date_col is not None and _target in df.columns:
    _ts = df[[_date_col, _target]].copy()
    _ts[_date_col] = pd.to_datetime(_ts[_date_col], errors="coerce")
    _ts = _ts.dropna(subset=[_date_col]).sort_values(_date_col)
    _freq = pd.infer_freq(_ts[_date_col])
    _diffs = _ts[_date_col].diff().dropna()
    _median_gap = _diffs.median() if len(_diffs) else pd.Timedelta(0)
    _has_gaps = len(_diffs) and _median_gap > pd.Timedelta(0)
    _gap_count = int((_diffs > _median_gap * 1.5).sum()) if _has_gaps else 0

    _ts_summary.update({{
        "inferred_freq": _freq,
        "n_points": int(len(_ts)),
        "date_range": [str(_ts[_date_col].min()), str(_ts[_date_col].max())],
        "gap_count": _gap_count,
    }})

    plt.figure(figsize=(10, 4))
    plt.plot(_ts[_date_col], _ts[_target])
    plt.xlabel(_date_col)
    plt.ylabel(_target)
    plt.title(f"{{_target}} over time")
    plt.tight_layout()
    plt.show()

    _series = _ts.set_index(_date_col)[_target]
    if _freq:
        _series = _series.asfreq(_freq)
    _series = _series.interpolate().dropna()

    _period = _freq_period.get((_freq or "").split("-")[0]) if _freq else None
    if _period and len(_series) >= 2 * _period:
        from statsmodels.tsa.seasonal import seasonal_decompose

        _decomp = seasonal_decompose(
            _series, period=_period, model="additive", extrapolate_trend="period"
        )
        _fig = _decomp.plot()
        _fig.set_size_inches(10, 8)
        plt.tight_layout()
        plt.show()

        _detrended_var = float((_decomp.trend + _decomp.resid).dropna().var())
        _trend_strength = (
            round(max(0.0, 1 - float(_decomp.resid.dropna().var()) / _detrended_var), 3)
            if _detrended_var > 0
            else None
        )
        _deseasoned_var = float((_decomp.seasonal + _decomp.resid).dropna().var())
        _seasonal_strength = (
            round(max(0.0, 1 - float(_decomp.resid.dropna().var()) / _deseasoned_var), 3)
            if _deseasoned_var > 0
            else None
        )
        _ts_summary.update({{
            "seasonality_period": _period,
            "trend_strength": _trend_strength,
            "seasonal_strength": _seasonal_strength,
        }})

    if len(_series) >= 10:
        from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

        _max_lags = max(1, min(24, len(_series) // 2 - 1))
        _fig, _axes = plt.subplots(1, 2, figsize=(12, 4))
        plot_acf(_series, ax=_axes[0], lags=_max_lags)
        plot_pacf(_series, ax=_axes[1], lags=_max_lags, method="ywm")
        plt.tight_layout()
        plt.show()

print("##DATAPILOT_SUMMARY##" + json.dumps(_ts_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if not summary.get("date_column"):
        return [
            "Couldn't reliably detect a date/time column, or no target is set — skipping "
            "time-series diagnostics."
        ]

    bullets = [
        f"Detected date column '{summary['date_column']}' "
        f"(inferred freq: {summary.get('inferred_freq') or 'irregular'}), "
        f"{summary.get('n_points', 0):,} points."
    ]
    if summary.get("gap_count"):
        bullets.append(
            f"{summary['gap_count']} gap(s) larger than 1.5x the typical interval — check for "
            "missing periods before modeling."
        )
    period = summary.get("seasonality_period")
    if period:
        trend = summary.get("trend_strength")
        seasonal = summary.get("seasonal_strength")
        bullets.append(
            f"Seasonal decomposition (period={period}): trend strength "
            f"{trend if trend is not None else 'n/a'}, seasonal strength "
            f"{seasonal if seasonal is not None else 'n/a'}."
        )
        bullets.append(
            f"Consider lag features at lag 1 and lag {period} (seasonal), plus a rolling "
            f"mean/std over a window of {period}."
        )
    bullets.append("Use a time-ordered train/test split (no shuffling) for this problem type.")
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="time_series_analysis",
    title="Time series diagnostics",
    description="Date-column detection, frequency/gaps, trend/seasonality decomposition, "
    "ACF/PACF, and lag/split suggestions.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
