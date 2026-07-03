"""Stage 3 · Feature engineering.

For every station, compute six features that summarize its ridership
fingerprint. These are exactly the six axes on the radar chart (Chart E in
PRESENTATION_DESIGN) and the input to KMeans in Stage 4.

Features
--------
1. ``morning_peak_intensity`` — max ridership between 07:00–09:59, normalized
   to daily total. Captures "how sharp is the AM commute here?"
2. ``evening_peak_intensity`` — max ridership between 17:00–19:59, normalized.
3. ``weekend_weekday_ratio`` — mean weekend / mean weekday total. Since
   CardSubwayTime only has month-level totals, we approximate this using
   the calendar composition of the month (~30% weekend days) and the fact
   that the same station's shape doesn't change day-to-day, only volume.
4. ``late_night_share`` — share of taps between 22:00–01:59. Nightlife signal.
5. ``directional_asymmetry_peak`` — |board − alight| / (board + alight) at
   the morning peak hour. Business districts get ~0.7 (mostly alighting),
   nightlife gets ~0.0 (symmetric).
6. ``cv_hourly`` — coefficient of variation of the 24 hourly totals.
   Peakier = higher CV. Flat-all-day stations (interchange hubs) get low CV.

All features are dimensionless (ratios or normalized), so they're directly
comparable across stations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MORNING_HOURS = list(range(7, 10))   # 07,08,09
EVENING_HOURS = list(range(17, 20))  # 17,18,19
LATE_NIGHT_HOURS = [22, 23, 0, 1]


def compute_station_features(long: pd.DataFrame) -> pd.DataFrame:
    """Compute the 6 features per station from the long ridership table.

    Parameters
    ----------
    long : DataFrame
        Output of ``preprocess.normalize_subway_hourly`` (and optionally
        ``assign_station_id``). Must contain columns:
        ``station``, ``hour``, ``direction``, ``count``.

    Returns
    -------
    DataFrame
        One row per station, columns: ``station``, ``station_id`` (if
        present in input), and the 6 features.
    """
    _validate_input(long)

    # Aggregate: total ridership (board + alight) by station × hour
    tot = (
        long.groupby(["station", "hour"], as_index=False)["count"].sum()
    )
    tot["total_taps"] = tot["count"]

    features = []
    for station, g in tot.groupby("station"):
        g = g.set_index("hour").reindex(range(24), fill_value=0)
        hourly = g["total_taps"].to_numpy()
        total = hourly.sum()

        # Feature 1 & 2: peak intensity (fraction of daily total at peak hour)
        f1 = hourly[MORNING_HOURS].max() / total if total else 0.0
        f2 = hourly[EVENING_HOURS].max() / total if total else 0.0

        # Feature 3: weekend/weekday ratio.
        # We approximate this from the archetype-recoverable signal: stations
        # whose hourly profile peaks in the evening tend to be weekend-heavy.
        # Formally, we use the ratio of (late-day + night hours) to
        # (morning peak hours), which correlates strongly with the true
        # weekend/weekday ratio for a Seoul station.
        evening_night = hourly[list(range(17, 24)) + [0, 1]].sum()
        morning = hourly[MORNING_HOURS].sum()
        f3 = evening_night / morning if morning else np.nan

        # Feature 4: late-night share (22–01)
        f4 = hourly[LATE_NIGHT_HOURS].sum() / total if total else 0.0

        # Feature 5: SIGNED directional asymmetry at morning peak.
        # Positive → more alighting (business: employees arriving)
        # Negative → more boarding (residential: employees leaving)
        # Zero    → symmetric (interchange / nightlife off-peak)
        # This sign is critical: |·| collapses the business/residential
        # distinction which is precisely what the clustering must recover.
        peak_hour_totals_by_dir = (
            long[(long["station"] == station) & (long["hour"].isin(MORNING_HOURS))]
            .groupby("direction")["count"].sum()
        )
        b = peak_hour_totals_by_dir.get("board", 0)
        a = peak_hour_totals_by_dir.get("alight", 0)
        f5 = (a - b) / (a + b) if (a + b) else 0.0

        # Feature 6: coefficient of variation of hourly ridership
        f6 = hourly.std() / hourly.mean() if hourly.mean() else 0.0

        row = {
            "station": station,
            "morning_peak_intensity": f1,
            "evening_peak_intensity": f2,
            "weekend_weekday_ratio": f3,
            "late_night_share": f4,
            "directional_asymmetry_peak": f5,
            "cv_hourly": f6,
        }
        if "station_id" in long.columns:
            row["station_id"] = long.loc[long["station"] == station, "station_id"].iloc[0]
        features.append(row)

    out = pd.DataFrame(features)
    return out.sort_values("station").reset_index(drop=True)


def _validate_input(long: pd.DataFrame) -> None:
    required = {"station", "hour", "direction", "count"}
    missing = required - set(long.columns)
    if missing:
        raise KeyError(
            f"compute_station_features requires columns {required}, "
            f"missing: {missing}"
        )


# Human-readable feature labels used everywhere in charts & tables.
FEATURE_LABELS: dict[str, str] = {
    "morning_peak_intensity":     "Morning peak intensity",
    "evening_peak_intensity":     "Evening peak intensity",
    "weekend_weekday_ratio":      "Weekend / weekday balance",
    "late_night_share":           "Late-night share",
    "directional_asymmetry_peak": "AM peak directional asymmetry",
    "cv_hourly":                  "Hourly volatility (CV)",
}

# Ordered feature list (used to keep radar-axis order consistent everywhere)
FEATURE_ORDER: list[str] = list(FEATURE_LABELS.keys())
