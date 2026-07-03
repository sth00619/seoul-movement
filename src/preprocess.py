"""Stages 1–2 · Schema normalization + entity resolution.

Turns raw dataframes (Korean column names, string amounts, inconsistent
station names) into analysis-ready tables with:

- snake_case English column names
- proper dtypes (integers for counts, floats for prices, datetime for dates)
- canonical ``station_id`` foreign key
- ``gu`` column resolved from station → coordinate → administrative boundary

This module is deliberately pure — no I/O, no globals. Every function
takes a dataframe and returns a new one. That makes it trivial to unit-test.
"""

from __future__ import annotations

import re
from typing import Final

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Subway ridership normalization (OA-12252 → long tidy table)
# ---------------------------------------------------------------------------

# Original CardSubwayTime hour columns look like "04시-05시 승차인원".
# We extract (hour, direction) from each.
_HOUR_COL_RE = re.compile(r"^(\d{2})시-(\d{2})시\s*(승차|하차)인원$")

# Direction map (Korean → English)
_DIR_MAP: Final = {"승차": "board", "하차": "alight"}


def normalize_subway_hourly(raw: pd.DataFrame) -> pd.DataFrame:
    """Convert wide CardSubwayTime dataframe to a long tidy table.

    Input schema (wide, 48+ columns):
        사용월 | 호선명 | 지하철역 | 04시-05시 승차인원 | 04시-05시 하차인원 | ...

    Output schema (long, one row per station-month-hour-direction):
        year_month  | line   | station     | hour | direction | count
        2024-01     | 2호선  | 강남        | 4    | board     | 12345
        2024-01     | 2호선  | 강남        | 4    | alight    | 45678
        ...

    This is the shape every downstream chart wants — heatmaps pivot on
    (hour × weekday), line charts group by hour, radar features aggregate
    over hours.
    """
    df = raw.copy()

    # Identify all hourly columns using the regex
    hour_cols = [c for c in df.columns if _HOUR_COL_RE.match(c)]
    id_cols = ["사용월", "호선명", "지하철역"]

    # Melt wide → long
    long = df[id_cols + hour_cols].melt(
        id_vars=id_cols,
        value_vars=hour_cols,
        var_name="raw_col",
        value_name="count",
    )

    # Parse hour + direction from raw column name
    parsed = long["raw_col"].str.extract(_HOUR_COL_RE)
    parsed.columns = ["hour_start", "hour_end", "direction_kr"]
    long["hour"] = parsed["hour_start"].astype(int)
    long["direction"] = parsed["direction_kr"].map(_DIR_MAP)

    # Rename + coerce dtypes
    long = long.rename(columns={
        "사용월": "year_month",
        "호선명": "line",
        "지하철역": "station",
    })
    long["year_month"] = pd.to_datetime(long["year_month"], format="%Y%m")
    long["count"] = pd.to_numeric(long["count"], errors="coerce").fillna(0).astype(int)

    # Canonicalize station names: drop parenthetical alternates, unify spacing
    long["station"] = long["station"].apply(_canonicalize_station_name)

    # Drop the intermediate raw_col (direction_kr never landed in `long`)
    long = long.drop(columns=["raw_col"])
    long = long[["year_month", "line", "station", "hour", "direction", "count"]]

    return long.reset_index(drop=True)


def _canonicalize_station_name(name: str) -> str:
    """Strip parenthetical alternates and unify whitespace.

    Examples
    --------
    >>> _canonicalize_station_name("서울역(1호선)")
    '서울역'
    >>> _canonicalize_station_name("잠실 (송파구청)")
    '잠실'
    """
    if not isinstance(name, str):
        return name
    # Drop anything in parens (Korean or Latin)
    name = re.sub(r"[\(（].*?[\)）]", "", name)
    name = re.sub(r"\s+", "", name)
    return name.strip()


# ---------------------------------------------------------------------------
# Entity resolution: station → coordinates → gu
# ---------------------------------------------------------------------------


def assign_station_id(long: pd.DataFrame) -> pd.DataFrame:
    """Add a stable integer ``station_id`` for each unique station name.

    We don't have a canonical station ID in the raw data, so we assign one
    deterministically from the sorted set of station names. This means the
    same station gets the same ID across runs, which is what any join
    depends on.
    """
    stations = sorted(long["station"].unique())
    lookup = {s: i for i, s in enumerate(stations, start=1)}
    long = long.copy()
    long["station_id"] = long["station"].map(lookup)
    return long


def attach_gu_from_coords(
    long: pd.DataFrame,
    coord_map: dict[str, tuple[float, float]],
    station_to_gu: dict[str, str],
) -> pd.DataFrame:
    """Attach latitude / longitude / gu columns.

    Parameters
    ----------
    long : DataFrame
        Output of :func:`normalize_subway_hourly` (optionally with station_id).
    coord_map : dict
        ``{station_name: (lat, lon)}``. Populated from station-coordinate
        open data.
    station_to_gu : dict
        ``{station_name: "강남구"}``. Populated from point-in-polygon check
        against the gu-level GeoJSON.

    In the mock pipeline we skip the GeoJSON step and hard-code the mapping
    (mock stations are deliberately chosen to sit unambiguously in one gu).
    In production, ``geopandas.sjoin`` handles it.
    """
    long = long.copy()
    long["lat"] = long["station"].map(lambda s: coord_map.get(s, (np.nan, np.nan))[0])
    long["lon"] = long["station"].map(lambda s: coord_map.get(s, (np.nan, np.nan))[1])
    long["gu"] = long["station"].map(station_to_gu)
    return long


# ---------------------------------------------------------------------------
# MOLIT apartment trades cleaning
# ---------------------------------------------------------------------------


def normalize_apartment_trades(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean MOLIT apt-trade dataframe.

    Key transformations:
    - ``거래금액`` comes in as ``"12,500"`` (unit: 만원 / 10,000 KRW) → int KRW.
    - Build a ``contract_date`` timestamp from (년, 월, 일).
    - Compute ``price_per_m2`` = deal_krw / 전용면적.
    """
    df = raw.copy()
    if df.empty:
        return pd.DataFrame(columns=[
            "contract_date", "gu_code", "complex", "area_m2",
            "deal_krw", "price_per_m2", "floor", "build_year",
        ])

    # Deal amount: string with commas, unit 만원, → integer KRW
    df["deal_krw"] = (
        df["거래금액"].astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
        .astype(np.int64) * 10_000
    )
    df["contract_date"] = pd.to_datetime(
        df[["년", "월", "일"]].rename(columns={"년": "year", "월": "month", "일": "day"}),
        errors="coerce",
    )
    df["area_m2"] = pd.to_numeric(df["전용면적"], errors="coerce")
    df["price_per_m2"] = df["deal_krw"] / df["area_m2"]

    out = df.rename(columns={
        "법정동코드": "gu_code",
        "아파트": "complex",
        "층": "floor",
        "건축년도": "build_year",
        "법정동": "dong",
    })
    keep = [
        "contract_date", "gu_code", "dong", "complex", "area_m2",
        "deal_krw", "price_per_m2", "floor", "build_year",
    ]
    return out[keep].sort_values("contract_date").reset_index(drop=True)


def build_monthly_price_index(trades: pd.DataFrame) -> pd.DataFrame:
    """Aggregate cleaned trades into a per-gu monthly price index.

    The index for month M in gu G is the median ``price_per_m2`` across
    all trades that closed in month M in gu G. Median is more robust than
    mean here — a single 100억원 penthouse can otherwise swing the mean by 5%.
    """
    trades = trades.copy()
    trades["year_month"] = trades["contract_date"].dt.to_period("M").dt.to_timestamp()
    idx = (
        trades.groupby(["gu_code", "year_month"], as_index=False)["price_per_m2"]
        .median()
        .rename(columns={"price_per_m2": "median_price_per_m2"})
    )
    return idx.sort_values(["gu_code", "year_month"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Daily ridership normalization (OA-12914) + weekday × hour reconstruction
# ---------------------------------------------------------------------------


def normalize_subway_daily(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize OA-12914 (CardSubwayStatsNew) into a tidy dataframe.

    Input columns: ``사용일자``, ``노선명``, ``역명``, ``승차총승객수``,
    ``하차총승객수``, ``등록일자``.

    Output columns: ``date`` (datetime), ``weekday`` (0=Mon..6=Sun),
    ``line``, ``station``, ``board_total``, ``alight_total``.
    """
    df = raw.copy()
    df = df.rename(columns={
        "사용일자": "date",
        "노선명": "line",
        "역명": "station",
        "승차총승객수": "board_total",
        "하차총승객수": "alight_total",
    })
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df["weekday"] = df["date"].dt.weekday
    df["board_total"] = pd.to_numeric(df["board_total"], errors="coerce").fillna(0).astype(int)
    df["alight_total"] = pd.to_numeric(df["alight_total"], errors="coerce").fillna(0).astype(int)
    df["station"] = df["station"].apply(_canonicalize_station_name)
    keep = ["date", "weekday", "line", "station", "board_total", "alight_total"]
    return df[keep].sort_values(["station", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Stage 0.5 · Column distinctiveness — which of the 48 hour x direction
# columns actually discriminate between stations, before we standardize
# anything or engineer features from them.
# ---------------------------------------------------------------------------


def compute_column_distinctiveness(long: pd.DataFrame) -> pd.DataFrame:
    """Rank the 48 (hour, direction) columns by how much they discriminate
    between stations, using each column's coefficient of variation (CV)
    across stations — computed on raw, pre-standardization values.

    Why coefficient of variation, and not standardized variance
    --------------------------------------------------------------
    Z-score standardizing a column sets its variance to exactly 1 by
    construction — every one of the 48 columns would tie at variance=1,
    telling us nothing about which is more informative. CV instead
    measures spread *relative to the column's own typical magnitude*:
    a column where stations wildly disagree (e.g. the 08:00 boarding
    count — packed at Gangnam, near-empty at Hongdae) scores high, while
    a column where every station behaves similarly (e.g. 03:00 boarding
    — near-zero everywhere) scores low, regardless of the two columns'
    very different absolute scales.

    This ranking is computed on the long tidy table (tens of thousands
    of rows — 34,560 in the current 24-month window), which is exactly
    the kind of row volume that makes eyeballing individual values
    hopeless and makes a systematic, code-driven ranking worthwhile.

    Parameters
    ----------
    long : DataFrame
        Output of :func:`normalize_subway_hourly`. Must contain columns
        ``station``, ``hour``, ``direction``, ``count``.

    Returns
    -------
    DataFrame
        One row per (hour, direction) column, sorted by CV descending.
        Columns: ``hour``, ``direction``, ``column_label``, ``mean_riders``,
        ``std_riders``, ``cv``, ``rank``, ``distinctive`` (top-8 flag).
    """
    # Collapse the 24-month window to one representative value per
    # station x hour x direction cell (mean daily ridership at that hour).
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
            "hour": int(hour),
            "direction": direction,
            "column_label": f"{hour:02d}:00 {direction}",
            "mean_riders": round(mean, 1),
            "std_riders": round(std, 1),
            "cv": round(cv, 4),
        })

    out = pd.DataFrame(rows).sort_values("cv", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    out["distinctive"] = out["rank"] <= 8   # top 8 of 48 columns flagged
    return out


def build_weekday_hour_matrix(
    long_hourly: pd.DataFrame,
    daily: pd.DataFrame,
    stations: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Reconstruct a weekday × hour ridership matrix per station.

    Why this exists
    ---------------
    OA-12252 gives the shape (hour-of-day profile, monthly average) but not
    per-weekday breakdown. OA-12914 gives per-day totals but not per-hour.
    Fusing them recovers the "when do people ride *and* how does that shift
    by day of week" surface — which is exactly what Chart A (the 3-panel
    heatmap) needs.

    Method
    ------
    1. From ``long_hourly``, compute each station's hourly shape:
       ``shape[h] = share of daily total spent in hour h``.
    2. From ``daily``, compute each station's weekday × board+alight total
       averaged across the window.
    3. For each (station, weekday, hour), value = weekday_daily_mean × shape[h].

    Returns
    -------
    dict[str, DataFrame]
        Maps station name → a (7, 24) dataframe with rows Mon..Sun,
        columns hour 0..23. Values are estimated mean taps.
    """
    if stations is None:
        stations = sorted(set(long_hourly["station"]) & set(daily["station"]))

    out: dict[str, pd.DataFrame] = {}
    for station in stations:
        # Step 1: hourly shape (24 values, sums to 1)
        hourly_totals = (
            long_hourly[long_hourly["station"] == station]
            .groupby("hour")["count"].sum()
            .reindex(range(24), fill_value=0)
            .to_numpy(dtype=float)
        )
        total = hourly_totals.sum()
        if total == 0:
            continue
        shape = hourly_totals / total

        # Step 2: mean daily volume by weekday
        d = daily[daily["station"] == station].copy()
        d["total"] = d["board_total"] + d["alight_total"]
        by_wd = d.groupby("weekday")["total"].mean().reindex(range(7), fill_value=0.0)

        # Step 3: outer product → (7, 24)
        mat = pd.DataFrame(
            by_wd.to_numpy().reshape(-1, 1) * shape.reshape(1, -1),
            index=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            columns=[f"{h:02d}" for h in range(24)],
        )
        out[station] = mat
    return out
