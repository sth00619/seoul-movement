"""Stage 4 · Standardization + clustering + 2D projection.

Pipeline
--------
1. ``StandardScaler`` — every feature has different natural units, so we
   standardize before any distance-based algorithm touches them.
2. ``KMeans`` — k chosen automatically by evaluating both the elbow (WCSS)
   and silhouette score across k = 2..8.
3. ``UMAP`` — reduce the 6D standardized feature space to 2D for scatter
   plots. UMAP is preferred over PCA here because we're visualizing
   clusters, and UMAP preserves local structure better.

Every function returns a small dataclass-like dict so the notebook can
snapshot each stage's output to JSON for the interactive site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.features import FEATURE_ORDER


@dataclass
class ClusteringResult:
    """Container for all Stage 4 outputs."""
    labels: np.ndarray                    # cluster label per station
    k_chosen: int                          # k selected
    wcss_by_k: dict[int, float]           # elbow curve data
    silhouette_by_k: dict[int, float]     # silhouette curve data
    centroids_scaled: np.ndarray          # centroids in scaled feature space
    centroids_original: pd.DataFrame      # centroids in original feature units
    scaler: StandardScaler                # fitted scaler (reusable)
    kmeans: KMeans                        # fitted model
    embedding_2d: np.ndarray | None = field(default=None)  # UMAP output
    cluster_names: dict[int, str] | None = field(default=None)


def choose_k_and_cluster(
    features: pd.DataFrame,
    k_range: tuple[int, int] = (2, 8),
    random_state: int = 42,
) -> ClusteringResult:
    """Standardize features, sweep k, pick the best, fit final KMeans.

    Selection rule: pick the k that maximizes silhouette score. Elbow curve
    is computed alongside and returned for the diagnostic plot shown in the
    notebook (spec §6.3).

    Parameters
    ----------
    features : DataFrame
        Output of :func:`features.compute_station_features`.
    k_range : (int, int)
        Inclusive range of k values to try.
    """
    X = features[FEATURE_ORDER].to_numpy(dtype=float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    wcss = {}
    silh = {}
    models = {}
    for k in range(k_range[0], k_range[1] + 1):
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        km.fit(X_scaled)
        wcss[k] = float(km.inertia_)
        silh[k] = float(silhouette_score(X_scaled, km.labels_))
        models[k] = km

    k_best = max(silh, key=silh.get)
    km_best = models[k_best]

    # Centroid in original feature units (for the radar chart)
    centroids_orig = scaler.inverse_transform(km_best.cluster_centers_)
    centroids_df = pd.DataFrame(
        centroids_orig,
        columns=FEATURE_ORDER,
        index=pd.Index([f"cluster_{i}" for i in range(k_best)], name="cluster"),
    )

    return ClusteringResult(
        labels=km_best.labels_,
        k_chosen=k_best,
        wcss_by_k=wcss,
        silhouette_by_k=silh,
        centroids_scaled=km_best.cluster_centers_,
        centroids_original=centroids_df,
        scaler=scaler,
        kmeans=km_best,
    )


def add_umap_embedding(
    result: ClusteringResult,
    features: pd.DataFrame,
    n_neighbors: int = 8,
    min_dist: float = 0.15,
    random_state: int = 42,
) -> ClusteringResult:
    """Project the 6D standardized space to 2D via UMAP.

    Split out from ``choose_k_and_cluster`` so that (a) the notebook can
    show the clustering step first without spinning up UMAP, and (b) if
    ``umap-learn`` isn't installed, the rest of the pipeline still runs.
    """
    try:
        import umap
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "umap-learn is required for the 2D projection. "
            "Install with: pip install umap-learn"
        ) from exc

    X = features[FEATURE_ORDER].to_numpy(dtype=float)
    X_scaled = result.scaler.transform(X)

    reducer = umap.UMAP(
        n_neighbors=min(n_neighbors, max(len(X_scaled) - 1, 2)),
        min_dist=min_dist,
        n_components=2,
        random_state=random_state,
    )
    result.embedding_2d = reducer.fit_transform(X_scaled)
    return result


# ---------------------------------------------------------------------------
# Cluster naming from centroid interpretation
# ---------------------------------------------------------------------------


def label_clusters_by_archetype(result: ClusteringResult) -> ClusteringResult:
    """Auto-label each cluster with a human-readable archetype name.

    Rules are ordered — the first matching rule wins per cluster. Every
    cluster is guaranteed to get a name.
    """
    c = result.centroids_original
    names: dict[int, str] = {}
    used: set[str] = set()

    # Rank clusters by each dimension for tie-breaking
    order_by_am = c["morning_peak_intensity"].rank(ascending=False)
    order_by_night = c["late_night_share"].rank(ascending=False)
    order_by_wend = c["weekend_weekday_ratio"].rank(ascending=False)
    order_by_asym = c["directional_asymmetry_peak"].rank(ascending=False)
    order_by_cv = c["cv_hourly"].rank(ascending=True)  # ascending → flat first

    # Now asymmetry is SIGNED: positive → business (alighting-heavy),
    # negative → residential (boarding-heavy).
    for i in c.index:
        idx = int(i.split("_")[1])
        asym = c.loc[i, "directional_asymmetry_peak"]
        am_intensity = c.loc[i, "morning_peak_intensity"]
        if order_by_night[i] == 1 or order_by_wend[i] == 1:
            name = "Nightlife District"
        elif asym > 0.3 and am_intensity > 0.10:
            name = "Business District"
        elif asym < -0.3 and am_intensity > 0.10:
            name = "Residential Commuter"
        elif order_by_cv[i] == 1:
            name = "Transit Interchange"
        else:
            name = "Mixed Residential-Retail"

        # De-duplicate names by suffixing
        base = name
        n = 2
        while name in used:
            name = f"{base} {n}"
            n += 1
        used.add(name)
        names[idx] = name

    result.cluster_names = names
    return result
