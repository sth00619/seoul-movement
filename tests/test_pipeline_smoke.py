"""End-to-end pipeline smoke test.

Runs Stage 0 (mock) → Stage 1-2 (preprocess) → Stage 3 (features) →
Stage 4 (cluster) and prints a sanity summary at every step. If any stage
throws or produces an obviously-wrong shape, the test fails loudly.

Usage:
    python tests/test_pipeline_smoke.py

Run from the repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Make the repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import cluster, features, mock_data, preprocess  # noqa: E402
from src.lawd_codes import FOCUS_STATIONS  # noqa: E402


def _hr(title: str) -> None:
    print(f"\n{'=' * 4}  {title}  {'=' * (60 - len(title))}")


def main() -> None:
    _hr("Stage 0 · Mock ingestion")
    months = mock_data._month_range("202605", 24)
    raw_subway = mock_data.generate_subway_hourly(months, seed=42)
    raw_trades = mock_data.generate_apartment_trades(
        ["11680", "11440", "11560"], months, seed=42
    )
    print(f"raw subway (wide): {raw_subway.shape}  cols[:5] = {list(raw_subway.columns[:5])}")
    print(f"raw trades:        {raw_trades.shape}")
    assert raw_subway.shape[1] == 3 + 48 + 1, "Expected 3 id + 48 hour + 1 meta columns"
    assert not raw_subway.empty
    assert not raw_trades.empty

    _hr("Stage 1 · Normalize subway (wide → long)")
    long = preprocess.normalize_subway_hourly(raw_subway)
    print(f"long:  {long.shape}  cols = {list(long.columns)}")
    print(long.head(3).to_string(index=False))
    expected_rows = 30 * 24 * 24 * 2   # 30 stations × 24 months × 24 hours × 2 directions
    #                                   (there are 30 station rows in mock; both '건대입구' 2호선 and 7호선 appear)
    assert long["count"].dtype.kind == "i"
    assert long["hour"].between(0, 23).all()
    assert set(long["direction"].unique()) == {"board", "alight"}

    _hr("Stage 2 · Add station_id")
    long = preprocess.assign_station_id(long)
    n_stations = long["station"].nunique()
    print(f"unique stations: {n_stations}")
    assert n_stations >= 25, "Too few stations after canonicalization"

    _hr("Stage 1 · Normalize apt trades")
    trades = preprocess.normalize_apartment_trades(raw_trades)
    print(f"trades:  {trades.shape}  cols = {list(trades.columns)}")
    print(trades.head(3).to_string(index=False))
    assert trades["deal_krw"].min() > 100_000_000, "Deal amounts look too small"
    assert trades["price_per_m2"].between(5_000_000, 100_000_000).all(), \
        "Price/m² outside sane bounds"

    _hr("Stage 5 · Monthly price index by gu")
    price_idx = preprocess.build_monthly_price_index(trades)
    print(f"price_idx:  {price_idx.shape}")
    print(price_idx.head(6).to_string(index=False))
    assert price_idx["gu_code"].nunique() == 3

    _hr("Stage 3 · Feature engineering")
    feats = features.compute_station_features(long)
    print(f"features:  {feats.shape}")
    print(feats.round(3).to_string(index=False))
    for col in features.FEATURE_ORDER:
        assert feats[col].notna().all(), f"NaN in {col}"

    # Sanity: Gangnam should have high AM asymmetry (business archetype)
    # Hongdae should have highest late-night share
    gangnam_asym = feats.set_index("station").loc["강남", "directional_asymmetry_peak"]
    hongdae_night = feats.set_index("station").loc["홍대입구", "late_night_share"]
    print(f"\nSanity: 강남 AM asymmetry = {gangnam_asym:.3f}  (business → expect >0.5)")
    print(f"Sanity: 홍대입구 late-night = {hongdae_night:.3f}  (nightlife → expect >0.15)")
    assert gangnam_asym > 0.5, f"Gangnam asymmetry too low: {gangnam_asym}"
    assert hongdae_night > 0.15, f"Hongdae late-night too low: {hongdae_night}"

    _hr("Stage 4 · Clustering (KMeans, k chosen by silhouette)")
    result = cluster.choose_k_and_cluster(feats, k_range=(2, 8), random_state=42)
    print(f"k chosen: {result.k_chosen}")
    print(f"silhouette by k: { {k: round(v, 3) for k, v in result.silhouette_by_k.items()} }")
    print(f"WCSS by k:       { {k: round(v, 1) for k, v in result.wcss_by_k.items()} }")

    _hr("Stage 4b · Label clusters by archetype")
    result = cluster.label_clusters_by_archetype(result)
    print(f"cluster names: {result.cluster_names}")

    # Report which cluster each focus station landed in
    _hr("Focus stations → cluster assignment")
    for kr_name, meta in FOCUS_STATIONS.items():
        if kr_name in feats["station"].values:
            row_idx = feats.index[feats["station"] == kr_name][0]
            label = int(result.labels[row_idx])
            print(f"  {kr_name:10}  →  cluster {label}  ({result.cluster_names[label]})"
                  f"    hypothesis: {meta['cluster_hypothesis']}")

    print("\n✅  All pipeline stages passed.")


if __name__ == "__main__":
    main()
