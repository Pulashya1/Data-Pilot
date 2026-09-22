"""Built-in sample datasets, for trying DataPilot without a file of your own.

Small, locally generated, seeded stand-ins shaped like well-known public benchmarks (Titanic,
California Housing, a credit-card-fraud sample, Iris, airline passengers) rather than downloads
of the real datasets: nothing here needs network access, and a fixed seed makes every sample
reproducible. Each one exercises a different path through the agent — missing values plus a
leakage-prone column, a continuous target, heavy class imbalance, no target at all, a
date-indexed series, and deliberately messy data. `eval/datasets.py` reuses the same builders
for the evaluation suite.
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


@dataclass(frozen=True)
class SampleDataset:
    key: str
    title: str
    description: str
    filename: str
    build: Callable[[], pd.DataFrame]


SAMPLE_DATASETS: dict[str, SampleDataset] = {
    s.key: s
    for s in (
        SampleDataset(
            key="titanic",
            title="Passenger survival",
            description="Binary classification with missing ages and a column that leaks the "
            "answer.",
            filename="passenger_survival.csv",
            build=titanic_like,
        ),
        SampleDataset(
            key="california_housing",
            title="House prices",
            description="Regression on a continuous price target.",
            filename="house_prices.csv",
            build=california_housing_like,
        ),
        SampleDataset(
            key="credit_card_fraud",
            title="Card fraud",
            description="Heavily imbalanced classification: about 1% of rows are fraud.",
            filename="card_fraud.csv",
            build=credit_card_fraud_sample,
        ),
        SampleDataset(
            key="iris_no_label",
            title="Unlabelled flowers",
            description="No target column, so the agent explores clusters instead.",
            filename="unlabelled_flowers.csv",
            build=iris_no_label,
        ),
        SampleDataset(
            key="airline_passengers",
            title="Monthly passengers",
            description="A monthly time series with trend and seasonality.",
            filename="monthly_passengers.csv",
            build=airline_passengers_like,
        ),
        SampleDataset(
            key="messy",
            title="Messy export",
            description="Mixed types, duplicate rows, and a target-leaking column.",
            filename="messy_export.csv",
            build=messy_csv,
        ),
    )
}
