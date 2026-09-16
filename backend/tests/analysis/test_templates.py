"""Renders each analysis template against a sample DataFrame and `exec`s the generated
code directly (no Docker) to check it actually runs and produces a parseable summary.
"""

import contextlib
import io
import json

import matplotlib
import numpy as np
import pandas as pd
import pytest
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.analysis.templates.base import MARKER
from app.analysis.templates.registry import TEMPLATES
from app.schemas.dataset import ColumnProfile, DataQualityScore, DatasetProfile, TopValue


def _sample_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "id": range(1, 101),
            "age": rng.normal(40, 10, 100).round(1),
            "income": np.concatenate([rng.normal(50000, 8000, 95), [500000] * 5]),
            "category": rng.choice(["a", "b", "c"], 100),
            "constant": ["x"] * 100,
            "score": [*(rng.normal(70, 15, 98).round(1)), None, None],
        }
    )


def _sample_profile(df: pd.DataFrame) -> DatasetProfile:
    columns = []
    for col in df.columns:
        series = df[col]
        is_numeric = pd.api.types.is_numeric_dtype(series)
        columns.append(
            ColumnProfile(
                name=col,
                dtype=str(series.dtype),
                missing_count=int(series.isna().sum()),
                missing_pct=0.0,
                unique_count=int(series.nunique()),
                numeric_stats={"mean": 0.0} if is_numeric else None,
                top_values=None if is_numeric else [TopValue(value="a", count=1)],
            )
        )
    return DatasetProfile(
        n_rows=len(df),
        n_columns=len(df.columns),
        memory_usage_bytes=1000,
        is_sampled=False,
        sample_size=None,
        columns=columns,
        n_duplicate_rows=0,
        duplicate_pct=0.0,
        constant_columns=["constant"],
        data_quality=DataQualityScore(overall=90.0, breakdown={}, issues=[]),
    )


def _run_code(code: str, df: pd.DataFrame) -> str:
    namespace = {
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "json": json,
        "display": lambda *a, **k: None,
        "df": df,
    }
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(compile(code, "<template>", "exec"), namespace)  # noqa: S102
    plt.close("all")
    return stdout.getvalue()


@pytest.mark.parametrize("key", list(TEMPLATES.keys()))
def test_template_renders_and_runs(key: str) -> None:
    template = TEMPLATES[key]
    df = _sample_df()
    profile = _sample_profile(df)
    params = template.default_params(profile)
    code = template.render(params)

    stdout = _run_code(code, df)

    marker_lines = [line for line in stdout.splitlines() if line.startswith(MARKER)]
    assert len(marker_lines) == 1, f"{key}: expected exactly one summary marker, got {stdout!r}"
    summary = json.loads(marker_lines[0][len(MARKER) :])

    insights = template.summarize(summary)
    assert isinstance(insights, list)
    assert all(isinstance(line, str) for line in insights)


def test_missing_values_flags_score_column() -> None:
    template = TEMPLATES["missing_values"]
    df = _sample_df()
    code = template.render(template.default_params(_sample_profile(df)))
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert summary["worst_column"] == "score"


def test_constant_and_id_columns_flags_constant_and_id() -> None:
    template = TEMPLATES["constant_and_id_columns"]
    df = _sample_df()
    code = template.render(template.default_params(_sample_profile(df)))
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert "constant" in summary["constant_columns"]
    assert "id" in summary["id_like_columns"]


def test_outliers_flags_income_outliers() -> None:
    template = TEMPLATES["outliers"]
    df = _sample_df()
    code = template.render(template.default_params(_sample_profile(df)))
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert summary["income"]["iqr_outliers"] > 0


# --- Phase 5: problem-type-specific templates (MASTER_PROMPT.md §5.3, §12) ----------------
# These render with an explicit `target_column` injected into params, the same way
# `app.notebook.seed.render_and_run_template_step` injects it centrally at runtime (so
# `Template.default_params` itself stays untouched by Phase 5 — see that module's docstring).


def test_class_balance_flags_imbalance() -> None:
    template = TEMPLATES["class_balance"]
    rng = np.random.default_rng(1)
    n = 200
    target = np.array([0] * 180 + [1] * 20)
    rng.shuffle(target)
    df = pd.DataFrame({"age": rng.normal(40, 10, n), "target": target})
    params = {**template.default_params(_sample_profile(df)), "target_column": "target"}
    code = template.render(params)
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert summary["imbalance_ratio"] >= 3
    insights = template.summarize(summary)
    assert any("imbalance" in b.lower() for b in insights)


def test_classification_feature_analysis_finds_signal() -> None:
    template = TEMPLATES["classification_feature_analysis"]
    rng = np.random.default_rng(2)
    n = 300
    target = rng.integers(0, 2, n)
    signal = target * 5 + rng.normal(0, 1, n)
    noise = rng.normal(0, 1, n)
    df = pd.DataFrame({"signal": signal, "noise": noise, "target": target})
    params = {**template.default_params(_sample_profile(df)), "target_column": "target"}
    code = template.render(params)
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert "signal" in summary["anova"]
    assert summary["anova"]["signal"]["p_value"] < 0.05


def test_regression_target_analysis_flags_skew_and_correlation() -> None:
    template = TEMPLATES["regression_target_analysis"]
    rng = np.random.default_rng(4)
    n = 300
    x1 = rng.normal(50, 10, n)
    noise = rng.normal(0, 1, n)
    target = x1 * 5 + rng.exponential(200, n)
    df = pd.DataFrame({"x1": x1, "noise": noise, "target": target})
    params = {**template.default_params(_sample_profile(df)), "target_column": "target"}
    code = template.render(params)
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert summary["skew"] > 1
    assert summary["suggested_transform"] is not None
    top_cols = [c for c, _ in summary["top_correlated_features"]]
    assert "x1" in top_cols


def test_leakage_checks_flags_near_duplicate_and_suspicious_name() -> None:
    template = TEMPLATES["leakage_checks"]
    rng = np.random.default_rng(5)
    n = 200
    target = rng.integers(0, 2, n)
    df = pd.DataFrame(
        {
            "leak_copy": target,
            "status_final": rng.normal(0, 1, n),
            "unrelated": rng.normal(0, 1, n),
            "target": target,
        }
    )
    params = {**template.default_params(_sample_profile(df)), "target_column": "target"}
    code = template.render(params)
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert "leak_copy" in summary["near_duplicate_columns"]
    assert "status_final" in summary["suspicious_name_columns"]
    insights = template.summarize(summary)
    assert any("leak" in b.lower() or "duplicate" in b.lower() for b in insights)


def test_clustering_analysis_reports_pca_and_hopkins() -> None:
    template = TEMPLATES["clustering_analysis"]
    rng = np.random.default_rng(6)
    n = 150
    cluster_a = rng.normal(0, 0.5, (n // 2, 2))
    cluster_b = rng.normal(10, 0.5, (n // 2, 2))
    df = pd.DataFrame(np.vstack([cluster_a, cluster_b]), columns=["f1", "f2"])
    params = {**template.default_params(_sample_profile(df)), "target_column": None}
    code = template.render(params)
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert summary["hopkins_statistic"] > 0.75
    assert summary["suggested_k"] == 2


def test_time_series_analysis_detects_date_and_seasonality() -> None:
    template = TEMPLATES["time_series_analysis"]
    rng = np.random.default_rng(8)
    dates = pd.date_range("2020-01-01", periods=104, freq="W")
    trend = np.linspace(0, 50, 104)
    seasonal = 10 * np.sin(np.arange(104) * 2 * np.pi / 52)
    noise = rng.normal(0, 1, 104)
    df = pd.DataFrame({"date": dates, "value": trend + seasonal + noise})
    params = {**template.default_params(_sample_profile(df)), "target_column": "value"}
    code = template.render(params)
    stdout = _run_code(code, df)
    marker_line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    summary = json.loads(marker_line[len(MARKER) :])
    assert summary["date_column"] == "date"
    assert summary["inferred_freq"] is not None
    assert summary["seasonality_period"] == 52
