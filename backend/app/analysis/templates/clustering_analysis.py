"""No-target / clustering analysis (MASTER_PROMPT.md §5.3): per-column scale report, PCA
explained variance with a 2D projection, the Hopkins statistic for cluster tendency, and a
suggested k via the elbow method / silhouette score.
"""

from typing import Any

from app.analysis.templates.base import Template, numeric_columns
from app.schemas.dataset import DatasetProfile


def render(params: dict[str, Any]) -> str:
    numeric_cols = params.get("numeric_columns", [])
    target = params.get("target_column")
    return f"""_numeric_cols = {numeric_cols!r}
_target = {target!r}
_cluster_summary: dict = {{}}

_feature_cols = [c for c in _numeric_cols if c != _target and c in df.columns]
_X_raw = df[_feature_cols].dropna() if _feature_cols else df.iloc[:, :0]

if len(_feature_cols) >= 2 and len(_X_raw) >= 10:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    _scale_report = {{col: round(float(df[col].std()), 3) for col in _feature_cols}}

    _scaler = StandardScaler()
    _X_scaled = _scaler.fit_transform(_X_raw)

    _n_components = min(len(_feature_cols), _X_scaled.shape[0], 10)
    _pca = PCA(n_components=_n_components)
    _pca_result = _pca.fit_transform(_X_scaled)
    _explained = _pca.explained_variance_ratio_
    _cumulative = _explained.cumsum()
    _n_for_95 = int((_cumulative >= 0.95).argmax() + 1) if len(_cumulative) else 0

    plt.figure(figsize=(6, 4))
    plt.plot(range(1, len(_explained) + 1), _cumulative, marker="o")
    plt.axhline(0.95, color="red", linestyle="--", linewidth=1)
    plt.xlabel("Number of components")
    plt.ylabel("Cumulative explained variance")
    plt.title("PCA explained variance")
    plt.tight_layout()
    plt.show()

    if _pca_result.shape[1] >= 2:
        plt.figure(figsize=(6, 5))
        plt.scatter(_pca_result[:, 0], _pca_result[:, 1], alpha=0.5, s=10)
        plt.xlabel("PC1")
        plt.ylabel("PC2")
        plt.title("2D PCA projection")
        plt.tight_layout()
        plt.show()

    _rng = np.random.default_rng(42)
    _m = min(len(_X_scaled), 50)
    _sample_idx = _rng.choice(len(_X_scaled), size=_m, replace=False)
    _X_sample = _X_scaled[_sample_idx]
    _mins, _maxs = _X_scaled.min(axis=0), _X_scaled.max(axis=0)
    _Y_uniform = _rng.uniform(_mins, _maxs, size=(_m, _X_scaled.shape[1]))

    _nn_self = NearestNeighbors(n_neighbors=2).fit(_X_scaled)
    _w = _nn_self.kneighbors(_X_sample, n_neighbors=2)[0][:, 1]
    _nn_uniform = NearestNeighbors(n_neighbors=1).fit(_X_scaled)
    _u = _nn_uniform.kneighbors(_Y_uniform, n_neighbors=1)[0][:, 0]
    _denom = float(_u.sum() + _w.sum())
    _hopkins = float(_u.sum() / _denom) if _denom > 0 else 0.5

    _max_k = min(8, len(_X_scaled) - 1)
    _inertias, _silhouettes = {{}}, {{}}
    if _max_k >= 2:
        for k in range(2, _max_k + 1):
            _km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(_X_scaled)
            _inertias[k] = round(float(_km.inertia_), 3)
            _silhouettes[k] = round(float(silhouette_score(_X_scaled, _km.labels_)), 4)

        plt.figure(figsize=(6, 4))
        plt.plot(list(_inertias.keys()), list(_inertias.values()), marker="o")
        plt.xlabel("k")
        plt.ylabel("Inertia")
        plt.title("Elbow method")
        plt.tight_layout()
        plt.show()

    _suggested_k = max(_silhouettes, key=_silhouettes.get) if _silhouettes else None

    _cluster_summary = {{
        "n_rows_used": int(len(_X_raw)),
        "scale_report": _scale_report,
        "n_components_for_95pct_variance": _n_for_95,
        "hopkins_statistic": round(_hopkins, 4),
        "silhouette_scores": _silhouettes,
        "suggested_k": int(_suggested_k) if _suggested_k is not None else None,
    }}

print("##DATAPILOT_SUMMARY##" + json.dumps(_cluster_summary))
"""


def summarize(summary: dict[str, Any]) -> list[str]:
    if not summary:
        return ["Not enough numeric columns/rows to run clustering diagnostics."]

    bullets = []
    scale_report = summary.get("scale_report") or {}
    positive_stds = [v for v in scale_report.values() if v > 0]
    if positive_stds and max(positive_stds) / max(min(positive_stds), 1e-9) > 10:
        bullets.append(
            f"Feature scales vary widely (std range {min(positive_stds):.2f}-"
            f"{max(positive_stds):.2f}) — scale features (e.g. StandardScaler) before "
            "clustering or PCA."
        )
    n_for_95 = summary.get("n_components_for_95pct_variance")
    if n_for_95:
        bullets.append(f"{n_for_95} principal component(s) explain 95% of the variance.")
    hopkins = summary.get("hopkins_statistic")
    if hopkins is not None:
        if hopkins > 0.75:
            bullets.append(f"Hopkins statistic {hopkins:.2f} indicates strong cluster tendency.")
        elif hopkins < 0.5:
            bullets.append(
                f"Hopkins statistic {hopkins:.2f} is close to random — the data may not have "
                "meaningful cluster structure."
            )
        else:
            bullets.append(f"Hopkins statistic {hopkins:.2f} indicates some cluster tendency.")
    suggested_k = summary.get("suggested_k")
    if suggested_k:
        bullets.append(f"Suggested number of clusters by silhouette score: k={suggested_k}.")
    return bullets or ["Clustering diagnostics ran but produced no notable findings."]


def default_params(profile: DatasetProfile) -> dict[str, Any]:
    return {"numeric_columns": numeric_columns(profile)}


TEMPLATE = Template(
    key="clustering_analysis",
    title="Clustering diagnostics",
    description="Scaling report, PCA explained variance + 2D projection, Hopkins statistic, "
    "and a suggested k via silhouette score.",
    render=render,
    summarize=summarize,
    default_params=default_params,
)
