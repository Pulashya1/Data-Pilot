"""Synthetic benchmark datasets for the evaluation suite (MASTER_PROMPT.md §10, §12 Phase 8).

Small, locally generated, seeded stand-ins for each named benchmark (Titanic / California
Housing / a credit-card-fraud sample / Iris / airline passengers) rather than downloads of the
real public datasets: the sandboxed kernel has no outbound network (§9) and this script
shouldn't depend on one either, and a fixed seed keeps every eval run reproducible. Each is
shaped to exercise the specific behavior §10 asks the suite to check — missing values plus a
leakage-prone column, a continuous target, heavy class imbalance, no target column at all, a
date-indexed univariate series, and deliberately messy data (mixed types, duplicates, a
target-leaking column). The builders themselves live in `app/data/samples.py`, where the
app also serves them as one-click sample datasets.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from app.data.samples import (
    airline_passengers_like,
    california_housing_like,
    credit_card_fraud_sample,
    iris_no_label,
    messy_csv,
    titanic_like,
)


@dataclass
class DatasetSpec:
    name: str
    build: Callable[[], pd.DataFrame]
    description: str
    # `ProblemType` enum value the agent's `understand` step should land on, or `None` to skip
    # that assertion (not currently used, but keeps the option open for a spec with no strong
    # expectation).
    expected_problem_type: str | None
    expects_leakage_flagged: bool = False


DATASET_SPECS: list[DatasetSpec] = [
    DatasetSpec(
        name="titanic",
        build=titanic_like,
        description="Classification, missing values, a leakage-prone column.",
        expected_problem_type="binary_classification",
        expects_leakage_flagged=True,
    ),
    DatasetSpec(
        name="california_housing",
        build=california_housing_like,
        description="Regression with a continuous target.",
        expected_problem_type="regression",
    ),
    DatasetSpec(
        name="credit_card_fraud",
        build=credit_card_fraud_sample,
        description="Heavy class imbalance (~1% positive).",
        expected_problem_type="binary_classification",
    ),
    DatasetSpec(
        name="iris_no_label",
        build=iris_no_label,
        description="No target column — clustering/exploration only.",
        expected_problem_type="clustering",
    ),
    DatasetSpec(
        name="airline_passengers",
        build=airline_passengers_like,
        description="A univariate monthly time series.",
        expected_problem_type="time_series",
    ),
    DatasetSpec(
        name="messy",
        build=messy_csv,
        description="Mixed types, duplicate rows, a column that leaks the target.",
        expected_problem_type="binary_classification",
        expects_leakage_flagged=True,
    ),
]
