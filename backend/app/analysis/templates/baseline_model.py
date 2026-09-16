"""Quick baseline model (MASTER_PROMPT.md §5.1 step 6, §12 Phase 6).

Trains a `RandomForestClassifier`/`RandomForestRegressor` on a light inline preprocessing
(median/most-frequent impute, one-hot encode low-cardinality categoricals — deliberately not
sharing kernel state with the `feature_engineering` template, since MASTER_PROMPT.md §5.1
step 3 lets the user freely reorder/skip/add plan steps, so this cell must never assume
another cell ran first) and reports metrics, feature importance, and a SHAP summary plot.
Random forests are used specifically so `shap.TreeExplainer` (exact, fast) applies — no
sampling-based `KernelExplainer`, which would be far too slow for an interactive baseline.

Only meaningful for classification/regression with a confirmed target (MASTER_PROMPT.md §5.1
step 6 wording: "appropriate metrics" implies a supervised target); no-ops for clustering,
time series, or no-target sessions — same no-target-degrades-gracefully convention as every
other problem-type template (`app.analysis.templates.class_balance`, etc.).
"""

from typing import Any

from app.analysis.templates.base import Template
from app.schemas.dataset import DatasetProfile

_CLASSIFICATION = ("binary_classification", "multiclass_classification")
_SUPERVISED = (*_CLASSIFICATION, "regression")


def render(params: dict[str, Any]) -> str:
    target = params.get("target_column")
    problem_type = params.get("problem_type")
    return f"""_target = {target!r}
_problem_type = {problem_type!r}
_baseline_summary: dict = {{"target": _target, "problem_type": _problem_type}}

if _target and _target in df.columns and _problem_type in {_SUPERVISED!r}:
    _X = df.drop(columns=[_target])
    _y = df[_target]

    _numeric_cols = _X.select_dtypes(include="number").columns.tolist()
    _categorical_cols = [c for c in _X.columns if c not in _numeric_cols and _X[c].nunique() <= 15]
    _use_cols = _numeric_cols + _categorical_cols

    if _use_cols and len(_X) >= 20:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder

        _is_classification = _problem_type in {_CLASSIFICATION!r}
        _preprocessor = ColumnTransformer(
            transformers=[
                ("num", SimpleImputer(strategy="median"), _numeric_cols),
                (
                    "cat",
                    Pipeline([
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]),
                    _categorical_cols,
                ),
            ],
            remainder="drop",
        )
        _model = (
            RandomForestClassifier(
                n_estimators=200, max_depth=8, random_state=42, class_weight="balanced"
            )
            if _is_classification
            else RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
        )

        _stratify = _y if _is_classification and _y.value_counts().min() >= 2 else None
        X_train, X_test, y_train, y_test = train_test_split(
            _X[_use_cols], _y, test_size=0.2, random_state=42, stratify=_stratify
        )

        _pipeline = Pipeline([("preprocess", _preprocessor), ("model", _model)])
        _pipeline.fit(X_train, y_train)
        _preds = _pipeline.predict(X_test)

        _metrics: dict = {{}}
        if _is_classification:
            from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

            _average = "binary" if _y.nunique() == 2 else "macro"
            _precision = precision_score(y_test, _preds, average=_average, zero_division=0)
            _recall = recall_score(y_test, _preds, average=_average, zero_division=0)
            _f1 = f1_score(y_test, _preds, average=_average, zero_division=0)
            _metrics = {{
                "accuracy": round(float(accuracy_score(y_test, _preds)), 4),
                "precision": round(float(_precision), 4),
                "recall": round(float(_recall), 4),
                "f1": round(float(_f1), 4),
            }}
            if _y.nunique() == 2:
                from sklearn.metrics import roc_auc_score

                _proba = _pipeline.predict_proba(X_test)[:, 1]
                _metrics["roc_auc"] = round(float(roc_auc_score(y_test, _proba)), 4)
        else:
            from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

            _metrics = {{
                "rmse": round(float(root_mean_squared_error(y_test, _preds)), 4),
                "mae": round(float(mean_absolute_error(y_test, _preds)), 4),
                "r2": round(float(r2_score(y_test, _preds)), 4),
            }}

        _feature_names = list(_preprocessor.get_feature_names_out())
        _importances = dict(zip(_feature_names, _model.feature_importances_.round(4), strict=True))
        _top_importances = dict(
            sorted(_importances.items(), key=lambda kv: kv[1], reverse=True)[:10]
        )

        import shap

        _X_test_transformed = _preprocessor.transform(X_test)
        _sample_n = min(100, _X_test_transformed.shape[0])
        _X_sample = _X_test_transformed[:_sample_n]
        _explainer = shap.TreeExplainer(_model)
        _shap_values = _explainer.shap_values(_X_sample)
        # shap's return shape for a classifier varies by version: a list of per-class arrays,
        # or a single (n_samples, n_features, n_classes) array — normalize to one 2D array
        # (the positive/first class) either way; regressors already return a plain 2D array.
        if isinstance(_shap_values, list):
            _shap_for_plot = _shap_values[1] if len(_shap_values) > 1 else _shap_values[0]
        elif getattr(_shap_values, "ndim", 2) == 3:
            _class_idx = 1 if _shap_values.shape[2] > 1 else 0
            _shap_for_plot = _shap_values[:, :, _class_idx]
        else:
            _shap_for_plot = _shap_values
        shap.summary_plot(
            _shap_for_plot, _X_sample, feature_names=_feature_names, show=False, plot_size=(10, 5)
        )
        plt.tight_layout()
        plt.show()

        _metrics_json = {{
            k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in _metrics.items()
        }}
        _baseline_summary.update({{
            "model": type(_model).__name__,
            "metrics": _metrics_json,
            "top_feature_importances": {{k: float(v) for k, v in _top_importances.items()}},
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
        }})
    else:
        _baseline_summary["skipped_reason"] = "not enough usable rows/columns for a baseline model"
else:
    _baseline_summary["skipped_reason"] = "no confirmed classification/regression target"

print("##DATAPILOT_SUMMARY##" + json.dumps(_baseline_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if summary.get("skipped_reason"):
        return [f"Baseline model skipped: {summary['skipped_reason']}."]

    metrics = summary.get("metrics") or {}
    metrics_text = ", ".join(f"{k}={v}" for k, v in metrics.items())
    bullets = [
        f"Baseline {summary.get('model')} ({summary.get('train_rows', 0):,} train / "
        f"{summary.get('test_rows', 0):,} test rows): {metrics_text}."
    ]
    top = summary.get("top_feature_importances") or {}
    if top:
        top3 = list(top.items())[:3]
        bullets.append(
            "Most important features (Gini importance): "
            + ", ".join(f"{name} ({value:.3f})" for name, value in top3)
            + "."
        )
    bullets.append(
        "This is a quick, untuned baseline for a reference point — see the SHAP summary plot "
        "above for per-feature direction of impact, not just magnitude."
    )
    return bullets


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {}


TEMPLATE = Template(
    key="baseline_model",
    title="Baseline model",
    description=(
        "Trains a quick baseline RandomForest and reports metrics, feature importance, "
        "and a SHAP summary."
    ),
    render=render,
    summarize=summarize,
    default_params=default_params,
)
