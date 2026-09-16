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
