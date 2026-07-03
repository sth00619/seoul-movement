"""Build per-stage snapshots for the interactive GitHub Pages demo.

For each pipeline stage, this script serializes:
1. A `preview` of the data at that stage (first ~20 rows, for the left pane)
2. A `viz` payload describing what the right pane should render at that stage

The output is a single ``interactive/data/pipeline.json`` file that the
browser fetches once at page load. All state transitions happen client-side
by swapping which stage's viz+preview is currently displayed.

This makes the whole demo work as **pure static** files — no server, no
runtime Python, no live database. GitHub Actions calls this script on every
push and commits the resulting JSON alongside the site.

Usage
-----
    python -m src.build_interactive --source mock
    python -m src.build_interactive --source processed
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src import cluster, features, mock_data, preprocess

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def df_to_preview(df: pd.DataFrame, n: int = 15) -> dict:
    """Serialize the first n rows of a dataframe for the left-pane table."""
    head = df.head(n).copy()
    for col in head.columns:
        if pd.api.types.is_datetime64_any_dtype(head[col]):
            head[col] = head[col].dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_numeric_dtype(head[col]):
            head[col] = head[col].round(3)
    return {
        "columns": list(head.columns),
        "rows": head.astype(str).values.tolist(),
        "total_rows": int(len(df)),
        "total_cols": int(len(df.columns)),
    }


# ---------------------------------------------------------------------------
# Stage builders
# ---------------------------------------------------------------------------


def build_stages(mock: bool = True, seed: int = 42) -> dict:
    """Run the full pipeline and capture snapshots at every stage."""
    months = mock_data._month_range("202605", 24)

    # ── Stage 0: raw hourly ──────────────────────────────────────────────
    raw = mock_data.generate_subway_hourly(months, seed=seed)
    stage_0 = {
        "id": "raw",
        "label": "Raw API data",
        "description": (
            "48 hour × direction columns per row. Korean column names. "
            "Strings for counts. This is what the Seoul Open Data API returns."
        ),
        "preview": df_to_preview(raw.head(15)),
        "viz": _viz_raw_shape(raw),
    }

    # ── Stage 1: normalized long ─────────────────────────────────────────
    long = preprocess.normalize_subway_hourly(raw)
    long = preprocess.assign_station_id(long)
    stage_1 = {
        "id": "normalized",
        "label": "Normalized (wide → long)",
        "description": (
            "melt() pivots the 48 hourly columns into two: hour + direction. "
            "Column names are snake_case English. Types are proper integers."
        ),
        "preview": df_to_preview(long),
        "viz": _viz_normalized_flow(long),
    }

    # ── Stage 2: features ────────────────────────────────────────────────
    feats = features.compute_station_features(long)
    stage_2 = {
        "id": "features",
        "label": "Feature engineering",
        "description": (
            "Six features per station summarize its ridership fingerprint. "
            "Dimensionless — every feature is a ratio or normalized share."
        ),
        "preview": df_to_preview(feats),
        "viz": _viz_features_radar(feats),
    }

    # ── Stage 3: standardized + clustered ────────────────────────────────
    result = cluster.choose_k_and_cluster(feats, random_state=seed)
    result = cluster.label_clusters_by_archetype(result)
    labels_df = pd.DataFrame({
        "station": feats["station"],
        "cluster": result.labels,
        "cluster_name": [result.cluster_names[c] for c in result.labels],
    })
    stage_3 = {
        "id": "clustered",
        "label": "Standardized + KMeans clustered",
        "description": (
            f"StandardScaler standardizes each feature, then KMeans finds "
            f"k={result.k_chosen} natural groupings (silhouette-selected)."
        ),
        "preview": df_to_preview(labels_df),
        "viz": _viz_cluster_bars(labels_df, result),
    }

    # ── Stage 4: UMAP projected ──────────────────────────────────────────
    result = cluster.add_umap_embedding(result, feats, random_state=seed)
    embed_df = pd.DataFrame({
        "station": feats["station"],
        "umap_x": result.embedding_2d[:, 0].round(3),
        "umap_y": result.embedding_2d[:, 1].round(3),
        "cluster": result.labels,
        "cluster_name": [result.cluster_names[c] for c in result.labels],
    })
    stage_4 = {
        "id": "projected",
        "label": "UMAP → 2D projection",
        "description": (
            "6D feature space reduced to 2D. UMAP preserves local structure — "
            "stations of the same archetype land near each other."
        ),
        "preview": df_to_preview(embed_df),
        "viz": _viz_umap_scatter(embed_df, result),
    }

    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source": "mock" if mock else "real",
        "n_months": len(months),
        "stages": [stage_0, stage_1, stage_2, stage_3, stage_4],
    }


# ---------------------------------------------------------------------------
# Viz payload builders (one per stage)
# ---------------------------------------------------------------------------


def _viz_raw_shape(raw: pd.DataFrame) -> dict:
    """Bar chart of column count grouped by type — makes the 'wide' problem visible."""
    n_id_cols   = 3
    n_hour_cols = 48
    n_meta_cols = 1
    return {
        "type": "bar",
        "title": "The raw table is inconveniently wide",
        "subtitle": f"{raw.shape[1]} columns — 48 hour columns × direction, hard to filter",
        "trace": {
            "x": ["ID columns", "Hourly columns", "Meta columns"],
            "y": [n_id_cols, n_hour_cols, n_meta_cols],
            "colors": ["#4A6FA5", "#C1272D", "#8A8580"],
        },
    }


def _viz_normalized_flow(long: pd.DataFrame) -> dict:
    """Line chart of 3 focus stations' hourly ridership — first useful viz."""
    focus = ["강남", "홍대입구", "여의도"]
    en    = {"강남": "Gangnam", "홍대입구": "Hongdae", "여의도": "Yeouido"}
    colors = {"강남": "#D4A017", "홍대입구": "#C1272D", "여의도": "#4A6FA5"}
    traces = []
    for stn in focus:
        by_hour = (
            long[long["station"] == stn]
            .groupby("hour")["count"].sum()
            .reindex(range(24), fill_value=0)
        )
        total = by_hour.sum()
        traces.append({
            "name": en[stn],
            "x": list(range(24)),
            "y": (by_hour / total * 100).round(2).tolist() if total else [0]*24,
            "color": colors[stn],
        })
    return {
        "type": "lines",
        "title": "Now you can plot: hourly ridership shape by station",
        "subtitle": "Same data, structured — each station's daily rhythm reveals itself",
        "traces": traces,
        "xaxis": "Hour of day", "yaxis": "Share of daily ridership (%)",
    }


def _viz_features_radar(feats: pd.DataFrame) -> dict:
    """Radar chart of the 6 engineered features for the 3 focus stations."""
    focus = ["강남", "홍대입구", "여의도"]
    en    = {"강남": "Gangnam", "홍대입구": "Hongdae", "여의도": "Yeouido"}
    colors = {"강남": "#D4A017", "홍대입구": "#C1272D", "여의도": "#4A6FA5"}
    feat_cols = features.FEATURE_ORDER
    axes = ["AM peak", "PM peak", "Weekend bal.", "Late-night",
            "AM asymmetry", "Volatility"]

    sub = feats[feats["station"].isin(focus)].set_index("station")
    normed = sub[feat_cols].copy()
    for c in feat_cols:
        lo, hi = normed[c].min(), normed[c].max()
        normed[c] = (normed[c] - lo) / (hi - lo) if hi > lo else 0

    traces = []
    for stn in focus:
        vals = normed.loc[stn, feat_cols].round(3).tolist()
        traces.append({
            "name": en[stn],
            "r": vals + [vals[0]],
            "theta": axes + [axes[0]],
            "color": colors[stn],
        })
    return {
        "type": "radar",
        "title": "Six-feature profile — three completely different shapes",
        "subtitle": "Each polygon is one station's fingerprint",
        "traces": traces,
    }


def _viz_cluster_bars(labels_df: pd.DataFrame, result) -> dict:
    """Bar chart of cluster sizes with archetype names."""
    counts = labels_df["cluster_name"].value_counts().sort_index()
    cluster_colors = {
        "Business District":    "#D4A017",
        "Business District 2":  "#B87333",
        "Nightlife District":   "#C1272D",
        "Residential Commuter": "#4A6FA5",
        "Transit Interchange":  "#5A9E6F",
    }
    return {
        "type": "bar",
        "title": f"KMeans finds k={result.k_chosen} natural archetypes",
        "subtitle": "The algorithm never saw the word 'neighborhood' — it discovered them from ridership shape alone",
        "trace": {
            "x": counts.index.tolist(),
            "y": counts.values.tolist(),
            "colors": [cluster_colors.get(n, "#8A8580") for n in counts.index],
        },
    }


def _viz_umap_scatter(embed_df: pd.DataFrame, result) -> dict:
    """2D scatter of UMAP embedding coloured by cluster — the interactive punchline."""
    cluster_colors = {
        "Business District":    "#D4A017",
        "Business District 2":  "#B87333",
        "Nightlife District":   "#C1272D",
        "Residential Commuter": "#4A6FA5",
        "Transit Interchange":  "#5A9E6F",
    }
    en = {"강남": "Gangnam", "홍대입구": "Hongdae", "여의도": "Yeouido"}
    traces = []
    for name, sub in embed_df.groupby("cluster_name"):
        traces.append({
            "name": name,
            "x": sub["umap_x"].tolist(),
            "y": sub["umap_y"].tolist(),
            "text": [en.get(s, s) for s in sub["station"]],
            "color": cluster_colors.get(name, "#8A8580"),
            "focus_flags": [s in en for s in sub["station"]],
        })
    return {
        "type": "scatter2d",
        "title": "Every station as a dot — clusters emerge visually",
        "subtitle": "Hover any dot for the station name. Focus stations are enlarged.",
        "traces": traces,
        "xaxis": "UMAP 1", "yaxis": "UMAP 2",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["mock", "processed"], default="mock")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("interactive/data/pipeline.json"))
    args = parser.parse_args()

    print(f"Building interactive snapshots from source={args.source} ...")
    payload = build_stages(mock=(args.source == "mock"), seed=args.seed)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"Wrote {args.out}  ({args.out.stat().st_size / 1024:.1f} KB)")
    print(f"Stages: {[s['id'] for s in payload['stages']]}")


if __name__ == "__main__":
    main()
