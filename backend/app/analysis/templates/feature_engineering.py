"""Preprocessing pipeline builder (MASTER_PROMPT.md §5.1 step 5, §12 Phase 6).

Builds a scikit-learn `ColumnTransformer`/`Pipeline` (median/most-frequent imputation,
standard scaling, one-hot encoding of low-cardinality categoricals) from either the
deterministic defaults or a `feature_engineering_approval` decision's JSON overrides
(`app.agent.decisions.validate_answer`, `app.agent.nodes.feature_engineering_node`).
Constant and ID-like columns (recomputed at render time, same heuristic as
`constant_and_id_columns.py`) are dropped; high-cardinality categoricals are excluded from
the pipeline rather than guessed at, and reported so the user can encode them manually.

Splits are strategy-appropriate (MASTER_PROMPT.md §5.1 step 5): stratified for
classification, time-ordered (no shuffling) for time series, plain random otherwise, and
skipped entirely for clustering/no-target sessions (the pipeline is still fit on the full
`X` so it's usable). The fitted pipeline is joblib-serialized in memory and emitted as a
`##DATAPILOT_PIPELINE##<base64>` marker line (`app.analysis.templates.base`) for the notebook
export endpoint to offer as `pipeline.joblib` — no container-filesystem access needed.

Self-contained like every other template (MASTER_PROMPT.md §5.3): does not assume any other
cell has already run, since MASTER_PROMPT.md §5.1 step 3 lets the user freely reorder, skip,
or add plan steps.
"""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_TIME_SERIES = "time_series"
_CLASSIFICATION = ("binary_classification", "multiclass_classification")


def render(params: dict[str, Any]) -> str:
    target = params.get("target_column")
    problem_type = params.get("problem_type")
    numeric_impute = params.get("numeric_impute", "median")
    categorical_impute = params.get("categorical_impute", "most_frequent")
    scaling = params.get("scaling", "standard")
    high_cardinality_threshold = params.get("high_cardinality_threshold", 15)
    test_size = params.get("test_size", 0.2)
    drop_columns = params.get("drop_columns", [])
    return f"""_target = {target!r}
_problem_type = {problem_type!r}
_numeric_impute = {numeric_impute!r}
_categorical_impute = {categorical_impute!r}
_scaling = {scaling!r}
_high_card_threshold = {high_cardinality_threshold!r}
_test_size = {test_size!r}
_drop_extra = {drop_columns!r}

_nunique = df.nunique(dropna=False)
_n = max(len(df), 1)
_constant_cols = [c for c in _nunique[_nunique <= 1].index.tolist() if c != _target]
# Float-dtype columns are excluded from the ID-like check: a continuous numeric feature is
# often ~100% unique too (e.g. an unrounded `age`), and unlike a real ID (an integer sequence
# or a string/UUID column) it's a legitimate predictive feature that shouldn't be dropped.
_id_like_cols = [
    c for c in df.columns
    if c != _target
    and _nunique.get(c, 0) > 1
    and (_nunique.get(c, 0) / _n) > 0.98
    and not pd.api.types.is_float_dtype(df[c])
]
_drop_set = set(_constant_cols) | set(_id_like_cols) | set(_drop_extra)
_drop_cols = [c for c in df.columns if c in _drop_set]

_feature_df = df.drop(columns=_drop_cols)
if _target and _target in _feature_df.columns:
    _X = _feature_df.drop(columns=[_target])
    _y = _feature_df[_target]
else:
    _X = _feature_df
    _y = None

_numeric_cols = _X.select_dtypes(include="number").columns.tolist()
_all_cat_cols = _X.select_dtypes(exclude="number").columns.tolist()
_cat_nunique = _X[_all_cat_cols].nunique() if _all_cat_cols else pd.Series(dtype=int)
_categorical_cols = [c for c in _all_cat_cols if _cat_nunique.get(c, 0) <= _high_card_threshold]
_excluded_high_card = [c for c in _all_cat_cols if c not in _categorical_cols]

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

_num_steps = [("impute", SimpleImputer(strategy=_numeric_impute))]
if _scaling == "standard":
    _num_steps.append(("scale", StandardScaler()))
_numeric_pipeline = Pipeline(_num_steps)
_categorical_pipeline = Pipeline([
    ("impute", SimpleImputer(strategy=_categorical_impute)),
    ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
])

_transformers = []
if _numeric_cols:
    _transformers.append(("num", _numeric_pipeline, _numeric_cols))
if _categorical_cols:
    _transformers.append(("cat", _categorical_pipeline, _categorical_cols))

_preprocessor = ColumnTransformer(transformers=_transformers, remainder="drop")
pipeline = Pipeline([("preprocess", _preprocessor)])

_split_strategy = "none"
_n_test = 0
if _y is not None and len(_X) >= 10 and (_numeric_cols or _categorical_cols):
    from sklearn.model_selection import train_test_split

    if _problem_type == "{_TIME_SERIES}":
        _split_idx = int(len(_X) * (1 - _test_size))
        X_train, X_test = _X.iloc[:_split_idx], _X.iloc[_split_idx:]
        _split_strategy = "time_ordered"
    else:
        _stratify = (
            _y if _problem_type in {_CLASSIFICATION!r} and _y.value_counts().min() >= 2 else None
        )
        X_train, X_test = train_test_split(
            _X, test_size=_test_size, random_state=42, stratify=_stratify
        )
        _split_strategy = "stratified" if _stratify is not None else "random"
    pipeline.fit(X_train)
    _n_test = len(X_test)
elif _numeric_cols or _categorical_cols:
    X_train = _X
    pipeline.fit(X_train)
else:
    X_train = _X

_n_features_out = (
    len(_preprocessor.get_feature_names_out()) if (_numeric_cols or _categorical_cols) else 0
)

import base64
import io

import joblib

_buf = io.BytesIO()
joblib.dump(pipeline, _buf)

_fe_summary = {{
    "target": _target,
    "dropped_constant": _constant_cols,
    "dropped_id_like": _id_like_cols,
    "excluded_high_cardinality": _excluded_high_card,
    "numeric_columns": _numeric_cols,
    "categorical_columns": _categorical_cols,
    "numeric_impute": _numeric_impute,
    "categorical_impute": _categorical_impute,
    "scaling": _scaling,
    "split_strategy": _split_strategy,
    "train_rows": int(len(X_train)),
    "test_rows": int(_n_test),
    "n_features_out": _n_features_out,
}}
print("##DATAPILOT_PIPELINE##" + base64.b64encode(_buf.getvalue()).decode("ascii"))
print("##DATAPILOT_SUMMARY##" + json.dumps(_fe_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    bullets = []
    dropped = summary.get("dropped_constant") or []
    id_like = summary.get("dropped_id_like") or []
    if dropped or id_like:
        bullets.append(
            "Dropped "
            + ", ".join(f"'{c}'" for c in [*dropped, *id_like])
            + " (constant/ID-like) before building the pipeline."
        )
    excluded = summary.get("excluded_high_cardinality") or []
    if excluded:
        bullets.append(
            "Excluded high-cardinality categorical column(s) from one-hot encoding: "
            + ", ".join(excluded)
            + " — consider target/frequency encoding these manually."
        )
    n_num = len(summary.get("numeric_columns") or [])
    n_cat = len(summary.get("categorical_columns") or [])
    bullets.append(
        f"Pipeline: {summary.get('numeric_impute')} imputation + "
        f"{summary.get('scaling')} scaling for {n_num} numeric column(s), "
        f"{summary.get('categorical_impute')} imputation + one-hot encoding for {n_cat} "
        f"categorical column(s) → {summary.get('n_features_out', 0)} output feature(s)."
    )
    strategy = summary.get("split_strategy")
    if strategy and strategy != "none":
        bullets.append(
            f"Train/test split: {strategy} ({summary.get('train_rows', 0):,} train / "
            f"{summary.get('test_rows', 0):,} test rows)."
        )
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {
        "numeric_impute": "median",
        "categorical_impute": "most_frequent",
        "scaling": "standard",
        "high_cardinality_threshold": 15,
        "test_size": 0.2,
        "drop_columns": [],
    }


TEMPLATE = Template(
    key="feature_engineering",
    title="Feature engineering pipeline",
    description=(
        "Builds and fits a scikit-learn preprocessing Pipeline (impute, scale, one-hot "
        "encode) with a strategy-appropriate train/test split."
    ),
    render=render,
    summarize=summarize,
    default_params=default_params,
)
