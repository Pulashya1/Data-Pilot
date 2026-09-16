"""Pydantic schemas for dataset profiling (deterministic, no LLM)."""

from typing import Any

from pydantic import BaseModel


class TopValue(BaseModel):
    value: Any
    count: int


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    missing_count: int
    missing_pct: float
    unique_count: int
    numeric_stats: dict[str, float] | None = None
    top_values: list[TopValue] | None = None


class DataQualityScore(BaseModel):
    overall: float
    breakdown: dict[str, float]
    issues: list[str]


class DatasetProfile(BaseModel):
    n_rows: int
    n_columns: int
    memory_usage_bytes: int
    is_sampled: bool
    sample_size: int | None
    columns: list[ColumnProfile]
    n_duplicate_rows: int
    duplicate_pct: float
    constant_columns: list[str]
    data_quality: DataQualityScore
