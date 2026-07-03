"""Smoke test for Section 4 charts (A and B).

Regenerates mock data, runs Stages 1-2, then builds both charts and
verifies the PNG artifacts land in ``data/exports/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import chart_functions, mock_data, preprocess


def main() -> None:
    months = mock_data._month_range("202605", 24)

    print("Generating mock ridership …")
    raw_hourly = mock_data.generate_subway_hourly(months, seed=42)
    raw_daily = mock_data.generate_subway_daily(months, seed=42)

    print("Normalizing …")
    long_hourly = preprocess.normalize_subway_hourly(raw_hourly)
    daily = preprocess.normalize_subway_daily(raw_daily)

    print(f"  long_hourly: {long_hourly.shape}")
    print(f"  daily:       {daily.shape}")

    export_dir = Path(__file__).resolve().parent.parent / "data/exports"

    print("\nRendering Section 4 charts …")
    figs = chart_functions.render_section_4(
        long_hourly, daily,
        focus_stations=["강남", "홍대입구", "여의도"],
        export_dir=export_dir,
    )

    # Verify files land on disk
    expected = [
        export_dir / "chart_A_weekday_hour_heatmap.png",
        export_dir / "chart_B_hourly_curves.png",
    ]
    for p in expected:
        assert p.exists() and p.stat().st_size > 5_000, f"Missing or tiny: {p}"
        print(f"  ✅  {p.name}  ({p.stat().st_size / 1024:.1f} KB)")

    # Sanity: heatmap max should be at Fri or Sat night for Hongdae, and
    # weekday morning hour for Gangnam / Yeouido
    matrices = preprocess.build_weekday_hour_matrix(long_hourly, daily,
                                                    ["강남", "홍대입구", "여의도"])
    gangnam_argmax = matrices["강남"].to_numpy().argmax()
    hongdae_argmax = matrices["홍대입구"].to_numpy().argmax()

    gangnam_wd, gangnam_h = divmod(gangnam_argmax, 24)
    hongdae_wd, hongdae_h = divmod(hongdae_argmax, 24)

    print(f"\nSanity check on heatmap peaks:")
    print(f"  Gangnam  brightest cell: {chart_functions.DAYS_EN[gangnam_wd]} {gangnam_h:02d}:00")
    print(f"  Hongdae  brightest cell: {chart_functions.DAYS_EN[hongdae_wd]} {hongdae_h:02d}:00")
    assert gangnam_wd < 5, "Gangnam heatmap peak should be a weekday"
    assert hongdae_wd >= 4 or hongdae_h >= 18, "Hongdae peak should be late Fri or weekend"

    print("\n✅  Section 4 charts render correctly.")


if __name__ == "__main__":
    main()
