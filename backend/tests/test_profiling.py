import math

import pandas as pd

from app.data.profiling import build_profile, rows_to_json_safe


def test_build_profile_basic_stats() -> None:
    df = pd.DataFrame(
        {
            "id": range(1, 11),
            "category": ["a", "b", "a", "a", "b", "c", "a", "b", "a", "b"],
            "score": [1.0, 2.0, 3.0, None, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        }
    )
    profile = build_profile(df, total_rows=10, is_sampled=False, sample_size=None)

    assert profile.n_rows == 10
    assert profile.n_columns == 3
    assert not profile.is_sampled
    assert profile.sample_size is None

    score_col = next(c for c in profile.columns if c.name == "score")
    assert score_col.missing_count == 1
    assert score_col.missing_pct == 10.0
    assert score_col.numeric_stats is not None
    assert score_col.numeric_stats["min"] == 1.0
    assert score_col.numeric_stats["max"] == 10.0

    category_col = next(c for c in profile.columns if c.name == "category")
    assert category_col.top_values is not None
    assert category_col.top_values[0].value == "a"
    assert category_col.top_values[0].count == 5


def test_build_profile_duplicates_and_constant_columns() -> None:
    df = pd.DataFrame(
        {
            "id": [1, 1, 2, 3],
            "flag": ["x", "x", "x", "x"],
        }
    )
    profile = build_profile(df, total_rows=4, is_sampled=False, sample_size=None)

    assert profile.n_duplicate_rows == 1
    assert profile.duplicate_pct == 25.0
    assert profile.constant_columns == ["flag"]
    assert any("flag" in issue for issue in profile.data_quality.issues)


def test_data_quality_score_perfect_data_is_high() -> None:
    df = pd.DataFrame({"a": range(20), "b": [f"v{i}" for i in range(20)]})
    profile = build_profile(df, total_rows=20, is_sampled=False, sample_size=None)
    assert profile.data_quality.overall > 95
    assert profile.data_quality.issues == []


def test_data_quality_score_messy_data_is_low() -> None:
    df = pd.DataFrame(
        {
            "mostly_missing": [None] * 18 + [1, 2],
            "constant": ["same"] * 20,
        }
    )
    profile = build_profile(df, total_rows=20, is_sampled=False, sample_size=None)
    assert profile.data_quality.overall < 60
    assert len(profile.data_quality.issues) >= 2


def test_sampled_profile_flags_issue() -> None:
    df = pd.DataFrame({"a": range(100)})
    profile = build_profile(df, total_rows=1_000_000, is_sampled=True, sample_size=100)
    assert profile.is_sampled
    assert profile.n_rows == 1_000_000
    assert any("sample" in issue.lower() for issue in profile.data_quality.issues)


def test_rows_to_json_safe_converts_nan_to_none() -> None:
    df = pd.DataFrame({"a": [1.0, float("nan")], "b": ["x", "y"]})
    rows = rows_to_json_safe(df)
    assert rows[0] == {"a": 1.0, "b": "x"}
    assert rows[1]["a"] is None
    assert not (isinstance(rows[1]["a"], float) and math.isnan(rows[1]["a"]))  # type: ignore[arg-type]
