"""MASTER_PROMPT.md §7 / §12 Phase 5: severity buckets for the new problem-type template keys."""

from app.agent.insight_severity import classify_severity


def test_class_balance_severity_buckets() -> None:
    assert classify_severity("class_balance", {"imbalance_ratio": 1.2}) == "info"
    assert classify_severity("class_balance", {"imbalance_ratio": 5}) == "warning"
    assert classify_severity("class_balance", {"imbalance_ratio": 15}) == "critical"
    assert classify_severity("class_balance", {"imbalance_ratio": None}) == "info"


def test_leakage_checks_severity() -> None:
    assert classify_severity("leakage_checks", {}) == "info"
    assert (
        classify_severity("leakage_checks", {"suspicious_name_columns": ["status_final"]})
        == "warning"
    )
    assert (
        classify_severity(
            "leakage_checks",
            {"high_correlation_features": [{"column": "x", "correlation": 0.97}]},
        )
        == "warning"
    )
    assert (
        classify_severity("leakage_checks", {"near_duplicate_columns": ["leak_copy"]}) == "critical"
    )
    assert (
        classify_severity("leakage_checks", {"id_like_correlated_with_target": ["row_id"]})
        == "critical"
    )


def test_unhandled_template_defaults_to_info() -> None:
    assert classify_severity("classification_feature_analysis", {"anova": {}}) == "info"
    assert classify_severity("clustering_analysis", {"hopkins_statistic": 0.9}) == "info"
    assert classify_severity("time_series_analysis", {"gap_count": 5}) == "info"
