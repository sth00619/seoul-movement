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
# Code snippets for the new "View the Code" panel
# ---------------------------------------------------------------------------
# Every snippet below is copied verbatim from the real functions in src/ —
# nothing here is invented pseudo-code. Each snippet carries a list of
# {start, end, label, note} tags marking which lines do what, so the
# interactive site can color-code preprocessing / outlier-detection /
# modeling / visualization directly over the real source.
#
# Line numbers are 1-indexed and relative to the snippet string itself
# (not the original file), since that's what the browser renders.


def get_stage_code_snippets() -> dict[str, dict]:
    """Return {stage_id: {code, language, tags, source_file}} for all 6 stages."""

    raw_code = '''def fetch_subway_hourly(months, api_key=None, save_dir=None):
    """Fetch hourly subway ridership for a list of YYYYMM months."""
    all_rows = []
    for yyyymm in months:
        start = 1
        while True:
            end = start + SEOUL_PAGE_SIZE - 1
            root = _seoul_get_page(api_key, yyyymm, start, end)
            rows = root.get("row", [])
            all_rows.extend(rows)
            total = int(root.get("list_total_count", 0))
            if end >= total or not rows:
                break
            start = end + 1
    df = pd.DataFrame(all_rows)
    df.attrs["source"] = "seoul_opendata:OA-12252:CardSubwayTime"
    return df'''
    raw_tags = [
        {"start": 3, "end": 13, "label": "preprocessing",
         "note": "Paginated ingestion — the API caps each call at 1,000 rows, so this loop keeps pulling pages until the full month is collected."},
        {"start": 14, "end": 16, "label": "preprocessing",
         "note": "Wraps the raw rows into a DataFrame, tagged with its source for the fact-check log."},
    ]

    standardize_code = '''def compute_column_distinctiveness(long: pd.DataFrame) -> pd.DataFrame:
    """Rank the 48 (hour, direction) columns by how much they
    discriminate between stations, using coefficient of variation."""
    station_hour = (
        long.groupby(["station", "hour", "direction"])["count"]
        .mean()
        .reset_index()
    )
    rows = []
    for (hour, direction), g in station_hour.groupby(["hour", "direction"]):
        vals = g["count"].to_numpy(dtype=float)
        mean = float(vals.mean())
        std = float(vals.std())
        cv = std / mean if mean > 0 else 0.0
        rows.append({
            "hour": int(hour), "direction": direction,
            "column_label": f"{hour:02d}:00 {direction}",
            "mean_riders": round(mean, 1),
            "std_riders": round(std, 1),
            "cv": round(cv, 4),
        })
    out = pd.DataFrame(rows).sort_values("cv", ascending=False)
    out["rank"] = range(1, len(out) + 1)
    out["distinctive"] = out["rank"] <= 8
    return out'''
    standardize_tags = [
        {"start": 4, "end": 8, "label": "preprocessing",
         "note": "Collapses 34,560 raw rows down to one mean value per station × hour × direction cell — the reduction that makes 48 columns comparable at all."},
        {"start": 10, "end": 19, "label": "outlier",
         "note": "Coefficient of variation, not standardized variance — z-scoring first would force every column's variance to exactly 1, hiding which columns actually differ."},
        {"start": 20, "end": 23, "label": "outlier",
         "note": "Ranks all 48 columns and flags the top 8 as statistically distinctive — this is the 'find the unusual column' step."},
    ]

    normalize_code = '''def normalize_subway_hourly(raw: pd.DataFrame) -> pd.DataFrame:
    """Convert wide CardSubwayTime dataframe to a long tidy table."""
    df = raw.copy()
    hour_cols = [c for c in df.columns if _HOUR_COL_RE.match(c)]
    id_cols = ["\\uc0ac\\uc6a9\\uc6d4", "\\ud638\\uc120\\uba85", "\\uc9c0\\ud558\\ucca0\\uc5ed"]

    long = df[id_cols + hour_cols].melt(
        id_vars=id_cols, value_vars=hour_cols,
        var_name="raw_col", value_name="count",
    )
    parsed = long["raw_col"].str.extract(_HOUR_COL_RE)
    parsed.columns = ["hour_start", "hour_end", "direction_kr"]
    long["hour"] = parsed["hour_start"].astype(int)
    long["direction"] = parsed["direction_kr"].map(_DIR_MAP)

    long = long.rename(columns={
        "\\uc0ac\\uc6a9\\uc6d4": "year_month", "\\ud638\\uc120\\uba85": "line", "\\uc9c0\\ud558\\ucca0\\uc5ed": "station",
    })
    long["year_month"] = pd.to_datetime(long["year_month"], format="%Y%m")
    long["count"] = pd.to_numeric(long["count"], errors="coerce").fillna(0).astype(int)
    long["station"] = long["station"].apply(_canonicalize_station_name)
    return long[["year_month", "line", "station", "hour", "direction", "count"]]'''
    normalize_tags = [
        {"start": 4, "end": 10, "label": "preprocessing",
         "note": "melt() pivots the 48 wide hour-columns into two tidy columns (hour, direction) — one observation per row."},
        {"start": 11, "end": 14, "label": "preprocessing",
         "note": "Regex-parses the Korean column name itself to recover the hour and direction it encodes."},
        {"start": 16, "end": 21, "label": "preprocessing",
         "note": "Renames to snake_case English, coerces types, and canonicalizes station names (strips parenthetical alternates)."},
    ]

    features_code = '''def compute_station_features(long: pd.DataFrame) -> pd.DataFrame:
    """Compute the 6 features per station from the long ridership table."""
    tot = long.groupby(["station", "hour"], as_index=False)["count"].sum()
    features = []
    for station, g in tot.groupby("station"):
        g = g.set_index("hour").reindex(range(24), fill_value=0)
        hourly = g["count"].to_numpy()
        total = hourly.sum()

        f1 = hourly[MORNING_HOURS].max() / total if total else 0.0
        f2 = hourly[EVENING_HOURS].max() / total if total else 0.0

        evening_night = hourly[list(range(17, 24)) + [0, 1]].sum()
        morning = hourly[MORNING_HOURS].sum()
        f3 = evening_night / morning if morning else np.nan

        f4 = hourly[LATE_NIGHT_HOURS].sum() / total if total else 0.0

        peak = long[(long.station == station) & (long.hour.isin(MORNING_HOURS))]
        by_dir = peak.groupby("direction")["count"].sum()
        b, a = by_dir.get("board", 0), by_dir.get("alight", 0)
        f5 = (a - b) / (a + b) if (a + b) else 0.0

        f6 = hourly.std() / hourly.mean() if hourly.mean() else 0.0
        features.append({"station": station, "morning_peak_intensity": f1,
                         "evening_peak_intensity": f2, "weekend_weekday_ratio": f3,
                         "late_night_share": f4, "directional_asymmetry_peak": f5,
                         "cv_hourly": f6})
    return pd.DataFrame(features).sort_values("station")'''
    features_tags = [
        {"start": 3, "end": 8, "label": "preprocessing",
         "note": "Reshapes per-station hourly totals into a fixed 24-length array so every station is directly comparable."},
        {"start": 10, "end": 19, "label": "preprocessing",
         "note": "Four of the six features are simple ratios of a time window to the daily total — deliberately dimensionless."},
        {"start": 21, "end": 24, "label": "outlier",
         "note": "The SIGNED directional asymmetry — this single sign flip is what separates business districts (alight-heavy, positive) from residential ones (board-heavy, negative)."},
        {"start": 26, "end": 26, "label": "outlier",
         "note": "Coefficient of variation of the full 24-hour curve — a station's own internal 'peakiness'."},
    ]

    cluster_code = '''def choose_k_and_cluster(features, k_range=(2, 8), random_state=42):
    """Standardize features, sweep k, pick the best, fit final KMeans."""
    X = features[FEATURE_ORDER].to_numpy(dtype=float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    wcss, silh, models = {}, {}, {}
    for k in range(k_range[0], k_range[1] + 1):
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        km.fit(X_scaled)
        wcss[k] = float(km.inertia_)
        silh[k] = float(silhouette_score(X_scaled, km.labels_))
        models[k] = km

    k_best = max(silh, key=silh.get)
    km_best = models[k_best]
    return ClusteringResult(labels=km_best.labels_, k_chosen=k_best,
                            silhouette_by_k=silh, kmeans=km_best, scaler=scaler)'''
    cluster_tags = [
        {"start": 3, "end": 5, "label": "preprocessing",
         "note": "StandardScaler puts all 6 features on the same scale (mean 0, std 1) — without this, cv_hourly's larger raw range would dominate the distance metric."},
        {"start": 7, "end": 12, "label": "modeling",
         "note": "Sweeps every k from 2-8, fitting a full KMeans each time and scoring it — no k is assumed in advance."},
        {"start": 14, "end": 16, "label": "modeling",
         "note": "Silhouette score picks k automatically — the k with the best-separated clusters wins, not a guessed number."},
    ]

    umap_code = '''def add_umap_embedding(result, features, n_neighbors=8, min_dist=0.15):
    """Project the 6D standardized space to 2D via UMAP."""
    X = features[FEATURE_ORDER].to_numpy(dtype=float)
    X_scaled = result.scaler.transform(X)

    reducer = umap.UMAP(
        n_neighbors=min(n_neighbors, max(len(X_scaled) - 1, 2)),
        min_dist=min_dist, n_components=2, random_state=42,
    )
    result.embedding_2d = reducer.fit_transform(X_scaled)
    return result'''
    umap_tags = [
        {"start": 3, "end": 4, "label": "preprocessing",
         "note": "Reuses the SAME fitted scaler from clustering — the 2D projection must sit in the identical standardized space the clusters were found in."},
        {"start": 6, "end": 10, "label": "modeling",
         "note": "UMAP preserves local neighborhood structure — points close in 6D stay close in 2D, unlike PCA which only preserves global variance."},
    ]

    viz_bar_code = '''fig.add_trace(go.Bar(
    x=[c["column_label"] for c in ranked[:12]],
    y=[c["cv"] for c in ranked[:12]],
    marker_color=["#C1272D" if c["distinctive"] else "#8A8580"
                  for c in ranked[:12]],
))'''
    viz_bar_tags = [
        {"start": 1, "end": 6, "label": "visualization",
         "note": "plotly.graph_objects.Bar — the top 12 columns by CV, with the top-8 'distinctive' set highlighted in stamp red against muted gray for the rest."},
    ]

    viz_raw_code = '''fig.add_trace(go.Bar(
    x=["ID columns", "Hourly columns", "Meta columns"],
    y=[n_id_cols, n_hour_cols, n_meta_cols],
    marker_color=["#4A6FA5", "#C1272D", "#8A8580"],
))'''
    viz_raw_tags = [
        {"start": 1, "end": 5, "label": "visualization",
         "note": "A single bar chart makes the 'wide table' problem visible before anything is even melted — 48 of 52 columns are one repeated pattern."},
    ]

    viz_normalized_code = '''for stn in focus_stations:
    by_hour = long[long.station == stn].groupby("hour")["count"].sum()
    fig.add_trace(go.Scatter(
        x=list(range(24)), y=(by_hour / by_hour.sum() * 100).tolist(),
        mode="lines+markers", name=STATION_EN[stn], line=dict(color=colors[stn]),
    ))'''
    viz_normalized_tags = [
        {"start": 1, "end": 6, "label": "visualization",
         "note": "Three overlaid line traces — one per focus station — sharing the same 0-24 hour x-axis, normalized to % of daily total so shape (not volume) is what's compared."},
    ]

    viz_features_code = '''for stn in focus:
    vals = normed.loc[stn, feat_cols].tolist()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=axes + [axes[0]],
        fill="none", line=dict(color=colors[stn], width=3),
    ))'''
    viz_features_tags = [
        {"start": 1, "end": 6, "label": "visualization",
         "note": "Scatterpolar with fill='none' — an earlier version used filled polygons, but nested shapes occluded each other; outlines stay visible even when one station's profile sits inside another's."},
    ]

    viz_cluster_code = '''counts = labels_df["cluster_name"].value_counts().sort_index()
fig.add_trace(go.Bar(
    x=counts.index.tolist(), y=counts.values.tolist(),
    marker_color=[cluster_colors.get(n, "#8A8580") for n in counts.index],
))'''
    viz_cluster_tags = [
        {"start": 1, "end": 5, "label": "visualization",
         "note": "Bar height = how many stations landed in each archetype — the algorithm's own vote on how many 'kinds' of neighborhood exist."},
    ]

    viz_umap_code = '''for cid, cname in sorted(names.items()):
    mask = labels == cid
    fig.add_trace(go.Scatter(
        x=embedding[mask, 0], y=embedding[mask, 1], mode="markers",
        marker=dict(color=cluster_colors[cname], size=15),
    ))
fig.update_layout(yaxis=dict(scaleanchor="x", scaleratio=1))'''
    viz_umap_tags = [
        {"start": 1, "end": 6, "label": "visualization",
         "note": "One trace per cluster so the legend and color are automatic — every station becomes one dot, colored by its KMeans label."},
        {"start": 7, "end": 7, "label": "visualization",
         "note": "scaleanchor locks the plot to a true 1:1 aspect ratio — UMAP's x/y only carry meaning as RELATIVE distances, so an unequal aspect would visually misstate how separated the clusters really are."},
    ]

    def combine(main_code, main_tags, viz_code, viz_tags):
        """Concatenate a stage's core transformation code with its
        visualization snippet, shifting the viz tags' line numbers to
        account for the offset — so both show in one code panel."""
        offset = len(main_code.split("\n")) + 2  # +2 for blank line + comment
        combined_code = main_code + "\n\n# --- visualization ---\n" + viz_code
        shifted_viz_tags = [
            {**t, "start": t["start"] + offset, "end": t["end"] + offset}
            for t in viz_tags
        ]
        return combined_code, main_tags + shifted_viz_tags

    raw_full, raw_tags = combine(raw_code, raw_tags, viz_raw_code, viz_raw_tags)
    standardize_full, standardize_tags = combine(standardize_code, standardize_tags, viz_bar_code, viz_bar_tags)
    normalize_full, normalize_tags = combine(normalize_code, normalize_tags, viz_normalized_code, viz_normalized_tags)
    features_full, features_tags = combine(features_code, features_tags, viz_features_code, viz_features_tags)
    cluster_full, cluster_tags = combine(cluster_code, cluster_tags, viz_cluster_code, viz_cluster_tags)
    umap_full, umap_tags = combine(umap_code, umap_tags, viz_umap_code, viz_umap_tags)

    return {
        "raw":          {"code": raw_full, "language": "python", "source_file": "src/ingest.py + build_interactive.py", "tags": raw_tags},
        "standardized": {"code": standardize_full, "language": "python", "source_file": "src/preprocess.py + build_interactive.py", "tags": standardize_tags},
        "normalized":   {"code": normalize_full, "language": "python", "source_file": "src/preprocess.py + build_interactive.py", "tags": normalize_tags},
        "features":     {"code": features_full, "language": "python", "source_file": "src/features.py + chart_functions.py", "tags": features_tags},
        "clustered":    {"code": cluster_full, "language": "python", "source_file": "src/cluster.py + build_interactive.py", "tags": cluster_tags},
        "projected":    {"code": umap_full, "language": "python", "source_file": "src/cluster.py + chart_functions.py", "tags": umap_tags},
    }


def _viz_column_distinctiveness(ranked_df) -> dict:
    """Bar chart payload for the new Stage 0.5 — CV ranking of all 48 columns."""
    top = ranked_df.head(16).to_dict("records")
    return {
        "type": "bar",
        "title": "Which of the 48 columns actually tells stations apart?",
        "subtitle": "Coefficient of variation across stations, top 16 columns — red bars are the top 8 most distinctive",
        "trace": {
            "x": [r["column_label"] for r in top],
            "y": [r["cv"] for r in top],
            "colors": ["#C1272D" if r["distinctive"] else "#8A8580" for r in top],
        },
    }


# ---------------------------------------------------------------------------
# Stage builders
# ---------------------------------------------------------------------------


def build_stages(mock: bool = True, seed: int = 42) -> dict:
    """Run the full pipeline and capture snapshots at every stage."""
    months = mock_data._month_range("202605", 24)
    code_snippets = get_stage_code_snippets()

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
        **code_snippets["raw"],
    }

    # ── Stage 0.5: standardize & find distinctive columns ────────────────
    long_for_ranking = preprocess.normalize_subway_hourly(raw)
    ranked_cols = preprocess.compute_column_distinctiveness(long_for_ranking)
    stage_05 = {
        "id": "standardized",
        "label": "Rank distinctive columns",
        "description": (
            f"{long_for_ranking.shape[0]:,} raw rows collapse into 48 hour×direction "
            "columns. Coefficient of variation ranks which columns actually "
            "discriminate between stations, before any feature is hand-picked."
        ),
        "preview": df_to_preview(ranked_cols),
        "viz": _viz_column_distinctiveness(ranked_cols),
        **code_snippets["standardized"],
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
        **code_snippets["normalized"],
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
        **code_snippets["features"],
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
        **code_snippets["clustered"],
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
        **code_snippets["projected"],
    }

    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source": "mock" if mock else "real",
        "n_months": len(months),
        "stages": [stage_0, stage_05, stage_1, stage_2, stage_3, stage_4],
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
