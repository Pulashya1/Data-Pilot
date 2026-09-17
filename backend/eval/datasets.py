"""Synthetic benchmark datasets for the evaluation suite (MASTER_PROMPT.md §10, §12 Phase 8).

Small, locally generated, seeded stand-ins for each named benchmark (Titanic / California
Housing / a credit-card-fraud sample / Iris / airline passengers) rather than downloads of the
real public datasets: the sandboxed kernel has no outbound network (§9) and this script
shouldn't depend on one either, and a fixed seed keeps every eval run reproducible. Each is
shaped to exercise the specific behavior §10 asks the suite to check — missing values plus a
leakage-prone column, a continuous target, heavy class imbalance, no target column at all, a
date-indexed univariate series, and deliberately messy data (mixed types, duplicates, a
target-leaking column).
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd


def titanic_like(seed: int = 0, n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    survived = rng.integers(0, 2, n)
    df = pd.DataFrame(
        {
            "PassengerId": range(1, n + 1),
            "Pclass": rng.choice([1, 2, 3], n, p=[0.2, 0.3, 0.5]),
            "Sex": rng.choice(["male", "female"], n),
            "Age": rng.normal(30, 12, n).round(1),
            "Fare": rng.exponential(30, n).round(2),
            "Embarked": rng.choice(["S", "C", "Q"], n),
            "Survived": survived,
            # Deliberately leaky (MASTER_PROMPT.md §5.3: "post-event columns" like
            # `*_final`/`status`) — near-perfectly encodes the target.
            "survival_status_final": np.where(survived == 1, "survived", "deceased"),
        }
    )
    missing_idx = rng.choice(n, size=n // 10, replace=False)
    df.loc[missing_idx, "Age"] = np.nan
    return df


def california_housing_like(seed: int = 0, n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    median_income = rng.gamma(4, 2, n)
    house_age = rng.integers(1, 52, n)
    rooms = rng.normal(6, 1.5, n)
    value = 50_000 + median_income * 40_000 + rooms * 5_000 - house_age * 300
    value = value + rng.normal(0, 15_000, n)
    return pd.DataFrame(
        {
            "MedInc": median_income.round(2),
            "HouseAge": house_age,
            "AveRooms": rooms.round(2),
            "Population": rng.integers(200, 5000, n),
            "Latitude": rng.uniform(32, 42, n).round(2),
            "Longitude": rng.uniform(-124, -114, n).round(2),
            "MedHouseVal": value.round(0),
        }
    )


def credit_card_fraud_sample(
    seed: int = 0, n: int = 2000, fraud_rate: float = 0.01
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_fraud = max(1, int(n * fraud_rate))
    is_fraud = np.zeros(n, dtype=int)
    is_fraud[:n_fraud] = 1
    rng.shuffle(is_fraud)
    amount = np.where(is_fraud == 1, rng.exponential(200, n), rng.exponential(50, n))
    data: dict[str, object] = {f"V{i}": rng.normal(0, 1, n) for i in range(1, 6)}
    data["Amount"] = amount.round(2)
    data["Class"] = is_fraud
    return pd.DataFrame(data)


def iris_no_label(seed: int = 0, n: int = 150) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    centers = rng.normal(0, 3, size=(3, 4))
    rows = [centers[rng.integers(0, 3)] + rng.normal(0, 0.5, 4) for _ in range(n)]
    columns = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
    return pd.DataFrame(rows, columns=columns).round(2)


def airline_passengers_like(seed: int = 0, months: int = 96) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2015-01-01", periods=months, freq="MS")
    trend = np.linspace(100, 400, months)
    seasonal = 30 * np.sin(np.arange(months) * (2 * np.pi / 12))
    noise = rng.normal(0, 8, months)
    passengers = (trend + seasonal + noise).round().astype(int).clip(min=1)
    return pd.DataFrame({"Month": dates.strftime("%Y-%m"), "Passengers": passengers})


def messy_csv(seed: int = 0, n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    target = rng.integers(0, 2, n)
    raw_numeric = rng.integers(0, 100, n)
    mixed_type_col = [str(v) if i % 5 == 0 else v for i, v in enumerate(raw_numeric)]
    df = pd.DataFrame(
        {
            "id": range(1, n + 1),
            "mixed_type_col": mixed_type_col,
            "score": rng.normal(50, 10, n).round(1),
            "target": target,
            # Leaks the target almost exactly (§5.3: "features with an absurdly high
            # single-feature predictive score").
            "target_leak": target * 100 + rng.normal(0, 0.01, n),
        }
    )
    duplicated = df.sample(n=max(1, n // 20), random_state=seed)
    return pd.concat([df, duplicated], ignore_index=True)


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
