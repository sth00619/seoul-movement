"""Offline mock data generator.

Purpose: let the entire pipeline run *without an API key*, so that:
1. New reviewers can clone the repo and see charts in under a minute.
2. The GitHub Actions CI job for the interactive site never blocks on
   missing secrets.
3. Development iterates fast — no rate limits, no waiting.

The generated data matches the *exact column schema* of the real APIs:

- Subway hourly: columns from ``CardSubwayTime`` (사용월, 호선명, 지하철역,
  48 hourly boarding/alighting columns, 작업일자).
- MOLIT apt: columns from ``getRTMSDataSvcAptTradeDev`` (거래금액, 건축년도,
  전용면적, 년, 월, 일, 법정동, 아파트, etc.).

Realism is deliberately calibrated so the downstream analysis produces the
same *qualitative* conclusions the real data would (weekday-heavy Gangnam,
weekend-heavy Hongdae, etc.). This lets us build and validate every chart
before spending API-key hours on real ingestion.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Station catalog (~30 stations — enough to cluster meaningfully)
# ---------------------------------------------------------------------------

# Each tuple: (station_name, line, archetype, lat, lon)
# Archetypes drive the ridership curve shape.
_STATIONS: list[tuple[str, str, str, float, float]] = [
    # Business district (강남 like)
    ("강남",     "2호선", "business",    37.4979, 127.0276),
    ("삼성",     "2호선", "business",    37.5088, 127.0631),
    ("역삼",     "2호선", "business",    37.5003, 127.0364),
    ("선릉",     "2호선", "business",    37.5046, 127.0491),
    ("서초",     "2호선", "business",    37.4913, 127.0079),
    ("교대",     "2호선", "business",    37.4933, 127.0143),
    # Finance district (여의도 like)
    ("여의도",   "5호선", "finance",     37.5216, 126.9243),
    ("여의나루", "5호선", "finance",     37.5273, 126.9327),
    ("국회의사당","9호선", "finance",     37.5284, 126.9174),
    # Nightlife district (홍대 like)
    ("홍대입구", "2호선", "nightlife",   37.5573, 126.9245),
    ("합정",     "2호선", "nightlife",   37.5500, 126.9139),
    ("상수",     "6호선", "nightlife",   37.5478, 126.9226),
    ("이태원",   "6호선", "nightlife",   37.5346, 126.9946),
    ("건대입구", "2호선", "nightlife",   37.5403, 127.0699),
    # Residential commuter
    ("노원",     "4호선", "residential", 37.6543, 127.0611),
    ("창동",     "4호선", "residential", 37.6534, 127.0475),
    ("도봉산",   "1호선", "residential", 37.6899, 127.0463),
    ("수유",     "4호선", "residential", 37.6378, 127.0253),
    ("미아",     "4호선", "residential", 37.6265, 127.0257),
    ("잠실",     "2호선", "residential", 37.5133, 127.1000),  # mixed but leans residential
    ("가락시장", "3호선", "residential", 37.4926, 127.1183),
    # Mixed residential-retail
    ("건대입구", "7호선", "mixed",       37.5403, 127.0699),
    ("성신여대", "4호선", "mixed",       37.5928, 127.0165),
    ("혜화",     "4호선", "mixed",       37.5822, 127.0018),
    ("신촌",     "2호선", "mixed",       37.5551, 126.9368),
    ("이대",     "2호선", "mixed",       37.5566, 126.9464),
    # Transit interchange
    ("서울역",   "1호선", "interchange", 37.5546, 126.9707),
    ("청량리",   "1호선", "interchange", 37.5804, 127.0466),
    ("왕십리",   "2호선", "interchange", 37.5613, 127.0378),
    ("고속터미널","3호선", "interchange", 37.5049, 127.0044),
]

# Archetype → 24-hour ridership shape (relative weights, normalized later)
# Index 0 = 04:00–05:00, matching the CardSubwayTime column order.
_HOURLY_PROFILES: dict[str, np.ndarray] = {
    # Sharper AM/PM peaks for business; residential has strong 07-08 outbound
    # commute peak. These curves are calibrated so the 6 engineered features
    # separate clusters cleanly at k=4 or 5.
    "business": np.array([
        # 04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23  00  01  02  03
          0.1, 0.3, 1.0, 3.5, 9.5, 4.5, 1.5, 1.3, 2.0, 2.2, 1.7, 1.7, 1.8, 3.0, 8.0, 6.5, 2.8, 1.6, 0.9, 0.5, 0.2, 0.1, 0.05, 0.05,
    ]),
    "finance": np.array([
          0.05, 0.2, 0.7, 3.0, 11.0, 5.5, 1.2, 0.9, 1.3, 1.5, 1.0, 1.0, 1.3, 2.5, 9.5, 7.5, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.05, 0.05,
    ]),
    "nightlife": np.array([
          0.1, 0.15, 0.3, 0.8, 1.5, 1.2, 1.8, 2.5, 3.2, 3.5, 3.8, 4.0, 4.5, 5.0, 5.5, 6.5, 7.5, 8.5, 9.5, 9.0, 6.5, 3.5, 1.5, 0.4,
    ]),
    "residential": np.array([
          0.2, 0.8, 3.0, 8.5, 7.0, 2.5, 1.3, 1.0, 1.3, 1.5, 1.3, 1.3, 1.5, 2.2, 4.0, 5.0, 3.5, 2.2, 1.3, 0.7, 0.25, 0.1, 0.05, 0.05,
    ]),
    "mixed": np.array([
          0.2, 0.5, 1.5, 3.0, 4.5, 3.0, 2.5, 2.5, 3.0, 3.5, 3.5, 3.8, 4.0, 4.5, 5.0, 5.5, 5.0, 4.5, 3.5, 2.5, 1.2, 0.5, 0.2, 0.1,
    ]),
    "interchange": np.array([
          0.5, 1.2, 3.0, 5.5, 6.0, 4.5, 3.5, 3.5, 4.0, 4.5, 4.0, 4.0, 4.5, 5.0, 6.0, 6.5, 5.5, 4.0, 3.0, 1.8, 0.8, 0.3, 0.1, 0.1,
    ]),
}

# Archetype → typical monthly average boardings (used to set volume)
_ARCHETYPE_VOLUME: dict[str, int] = {
    "business":    2_800_000,
    "finance":     2_400_000,
    "nightlife":   2_600_000,
    "residential": 1_800_000,
    "mixed":       2_100_000,
    "interchange": 3_500_000,
}

# Directional asymmetry — how skewed tap-in vs tap-out is at the AM peak.
# Business/finance: employees arrive (heavy alight), so 하차 >> 승차.
# Residential: employees leave (heavy board), so 승차 >> 하차.
_MORNING_ALIGHT_SHARE: dict[str, float] = {
    "business":    0.80,   # 80% of AM peak volume is 하차
    "finance":     0.85,
    "nightlife":   0.55,
    "residential": 0.20,   # only 20% is 하차, so 80% 승차
    "mixed":       0.50,
    "interchange": 0.50,
}


# ---------------------------------------------------------------------------
# Subway hourly (OA-12252 schema)
# ---------------------------------------------------------------------------

def _hour_col_pairs() -> list[tuple[str, str]]:
    """Return the 24 (승차, 하차) column-name pairs in the API's order."""
    # CardSubwayTime columns start at 04-05 and wrap to 03-04.
    order = list(range(4, 24)) + list(range(0, 4))
    pairs = []
    for h in order:
        h_next = (h + 1) % 24
        b = f"{h:02d}시-{h_next:02d}시 승차인원"
        a = f"{h:02d}시-{h_next:02d}시 하차인원"
        pairs.append((b, a))
    return pairs


def generate_subway_hourly(
    months: list[str],
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic OA-12252 dataframe.

    Output columns match ``CardSubwayTime`` exactly, so downstream
    preprocessing needs no changes when switching to real data.
    """
    rng = np.random.default_rng(seed)
    pairs = _hour_col_pairs()
    rows = []

    for yyyymm in months:
        year, month = int(yyyymm[:4]), int(yyyymm[4:6])
        # Determine number of weekdays vs weekends in this month
        first_day = date(year, month, 1)
        next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        n_days = (next_month - first_day).days
        n_weekend = sum(
            1 for d in range(n_days) if (first_day + timedelta(days=d)).weekday() >= 5
        )
        n_weekday = n_days - n_weekend

        for name, line, archetype, _lat, _lon in _STATIONS:
            # Perturb the archetype profile slightly per station so stations
            # in the same archetype aren't clones of each other. This
            # produces a realistic silhouette curve that peaks at k=4 or 5.
            base_profile = _HOURLY_PROFILES[archetype]
            station_noise = rng.uniform(0.85, 1.15, size=24)
            profile = base_profile * station_noise
            volume = _ARCHETYPE_VOLUME[archetype] * float(rng.uniform(0.7, 1.3))
            # Weekend multiplier: nightlife amplifies, business collapses
            weekend_mult = {
                "business": 0.15, "finance": 0.10, "nightlife": 1.6,
                "residential": 0.55, "mixed": 0.85, "interchange": 0.75,
            }[archetype]

            # Split volume across the month with weekday/weekend weights
            wd_total = volume * n_weekday / (n_weekday + n_weekend * weekend_mult)
            we_total = volume - wd_total
            daily = wd_total / max(n_weekday, 1) + we_total / max(n_weekend, 1)

            # Monthly hourly totals = daily average × n_days × profile share
            hourly_totals = daily * n_days * profile / profile.sum()

            row = {
                "사용월": yyyymm,
                "호선명": line,
                "지하철역": name,
            }
            alight_share = _MORNING_ALIGHT_SHARE[archetype]
            for i, (board_col, alight_col) in enumerate(pairs):
                total = hourly_totals[i]
                # Directional asymmetry: strongest at morning-peak hours
                is_morning_peak = i in (3, 4, 5)   # 07-08, 08-09, 09-10
                is_evening_peak = i in (13, 14, 15) # 17-18, 18-19, 19-20
                if is_morning_peak:
                    share_alight = alight_share
                elif is_evening_peak:
                    share_alight = 1 - alight_share  # reversed at evening
                else:
                    share_alight = 0.5
                # Small Poisson-ish noise
                board = total * (1 - share_alight) * rng.uniform(0.9, 1.1)
                alight = total * share_alight * rng.uniform(0.9, 1.1)
                row[board_col] = int(max(board, 0))
                row[alight_col] = int(max(alight, 0))
            row["작업일자"] = f"{year}-{month:02d}-05"
            rows.append(row)

    df = pd.DataFrame(rows)
    df.attrs["source"] = "MOCK:CardSubwayTime"
    df.attrs["seed"] = seed
    return df


# ---------------------------------------------------------------------------
# Subway DAILY (OA-12914 schema) — needed for Chart A (weekday × hour heatmap)
# ---------------------------------------------------------------------------

# Weekday multiplier for daily volume by archetype
# (Mon–Fri = 1.0 baseline; Sat/Sun scaled)
_DAILY_WEEKEND_MULT: dict[str, tuple[float, float]] = {
    # (Saturday_mult, Sunday_mult) relative to weekday mean
    "business":    (0.20, 0.10),   # Gangnam nearly empty on weekends
    "finance":     (0.12, 0.06),   # Yeouido even emptier
    "nightlife":   (1.70, 1.55),   # Hongdae peaks Fri/Sat night
    "residential": (0.60, 0.50),
    "mixed":       (0.90, 0.80),
    "interchange": (0.75, 0.70),
}


def generate_subway_daily(
    months: list[str],
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic OA-12914 (CardSubwayStatsNew) dataframe.

    Schema mirrors the real API:
        사용일자 | 노선명 | 역명 | 승차총승객수 | 하차총승객수 | 등록일자

    Downstream: :func:`preprocess.build_weekday_hour_matrix` combines this
    with the hourly (OA-12252) data to produce the weekday × hour heatmap
    used in Chart A.
    """
    rng = np.random.default_rng(seed + 1)
    rows = []
    for yyyymm in months:
        year, month = int(yyyymm[:4]), int(yyyymm[4:6])
        first_day = date(year, month, 1)
        next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        n_days = (next_month - first_day).days

        for d in range(n_days):
            day = first_day + timedelta(days=d)
            weekday = day.weekday()   # 0=Mon, 6=Sun
            for name, line, archetype, _lat, _lon in _STATIONS:
                sat_m, sun_m = _DAILY_WEEKEND_MULT[archetype]
                if weekday < 5:
                    mult = 1.0
                elif weekday == 5:
                    mult = sat_m
                else:
                    mult = sun_m
                base_daily = _ARCHETYPE_VOLUME[archetype] / 30  # rough daily mean
                # Same volume perturbation seed as hourly, but shifted so it's
                # independent noise (stations still keep archetype character)
                noise = rng.uniform(0.85, 1.15)
                daily_total = base_daily * mult * noise
                # Board/alight split symmetric on a daily basis
                board = int(daily_total * rng.uniform(0.48, 0.52))
                alight = int(daily_total - board)
                rows.append({
                    "사용일자": day.strftime("%Y%m%d"),
                    "노선명": line,
                    "역명": name,
                    "승차총승객수": board,
                    "하차총승객수": alight,
                    "등록일자": (day + timedelta(days=3)).strftime("%Y%m%d"),
                })
    df = pd.DataFrame(rows)
    df.attrs["source"] = "MOCK:CardSubwayStatsNew"
    df.attrs["seed"] = seed
    return df


# ---------------------------------------------------------------------------
# MOLIT apartment trades (matches getRTMSDataSvcAptTradeDev schema)
# ---------------------------------------------------------------------------

# Baseline mean price per m² by gu (KRW, roughly calibrated to real 2024–2025 levels).
_GU_BASE_PRICE_PER_M2: dict[str, int] = {
    "11680": 32_000_000,   # 강남구
    "11440": 18_000_000,   # 마포구
    "11560": 20_000_000,   # 영등포구
}
_GU_TREND_ANNUAL: dict[str, float] = {
    "11680":  0.06,   # 강남 gently trending up
    "11440":  0.02,
    "11560":  0.04,
}


def generate_apartment_trades(
    lawd_codes: list[str],
    months: list[str],
    seed: int = 42,
    n_per_month: int = 40,
) -> pd.DataFrame:
    """Generate synthetic MOLIT apt trade rows.

    Columns emitted match the real API: 거래금액, 건축년도, 년, 월, 일, 법정동,
    아파트, 전용면적, 지번, 지역코드, 층. Downstream code depends only on 거래금액,
    전용면적, 년, 월, so extra realism was skipped for the others.
    """
    rng = np.random.default_rng(seed)
    complexes = {
        "11680": ["래미안퍼스티지", "아크로리버파크", "타워팰리스", "은마아파트"],
        "11440": ["마포래미안푸르지오", "공덕자이", "e편한세상마포"],
        "11560": ["시범아파트", "여의도자이", "여의도삼부"],
    }
    dongs = {
        "11680": ["역삼동", "삼성동", "대치동", "청담동"],
        "11440": ["공덕동", "아현동", "도화동", "상수동"],
        "11560": ["여의도동", "당산동", "영등포동"],
    }

    rows = []
    for code in lawd_codes:
        base = _GU_BASE_PRICE_PER_M2[code]
        trend = _GU_TREND_ANNUAL[code]
        for ym in months:
            year, month = int(ym[:4]), int(ym[4:6])
            months_from_start = (year - int(months[0][:4])) * 12 + (month - int(months[0][4:6]))
            price_multiplier = (1 + trend) ** (months_from_start / 12)
            for _ in range(n_per_month):
                area = float(rng.choice([59.8, 84.9, 114.9, 132.5, 152.0]))
                per_m2 = base * price_multiplier * rng.uniform(0.85, 1.15)
                deal_amount = int(per_m2 * area / 10_000)  # unit: 만원 as MOLIT returns
                rows.append({
                    "거래금액": f"{deal_amount:,}",  # MOLIT returns as string with commas
                    "건축년도": int(rng.integers(1985, 2023)),
                    "년": year,
                    "월": month,
                    "일": int(rng.integers(1, 28)),
                    "법정동": rng.choice(dongs[code]),
                    "아파트": rng.choice(complexes[code]),
                    "전용면적": area,
                    "지번": f"{rng.integers(1, 999)}",
                    "지역코드": code,
                    "층": int(rng.integers(1, 25)),
                    "법정동코드": code,
                    "조회년월": ym,
                })

    df = pd.DataFrame(rows)
    df.attrs["source"] = "MOCK:AptTradeDev"
    df.attrs["seed"] = seed
    return df


# ---------------------------------------------------------------------------
# CLI: python -m src.mock_data --out data/raw --months 24
# ---------------------------------------------------------------------------


def _month_range(end_yyyymm: str, n_months: int) -> list[str]:
    """Generate the last ``n_months`` YYYYMM strings ending at ``end_yyyymm``."""
    y, m = int(end_yyyymm[:4]), int(end_yyyymm[4:6])
    out = []
    for _ in range(n_months):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Generate mock Seoul data.")
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--end-month", default="202605",
                        help="Last month to generate, YYYYMM. Default 202605.")
    parser.add_argument("--months", type=int, default=24,
                        help="Number of months to generate. Default 24.")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    months = _month_range(args.end_month, args.months)
    print(f"Generating mock data for {len(months)} months: {months[0]} → {months[-1]}")

    subway = generate_subway_hourly(months, seed=args.seed)
    subway.to_parquet(args.out / "mock_subway_hourly.parquet", index=False)
    print(f"  subway_hourly:  {len(subway):>6} rows → {args.out / 'mock_subway_hourly.parquet'}")

    daily = generate_subway_daily(months, seed=args.seed)
    daily.to_parquet(args.out / "mock_subway_daily.parquet", index=False)
    print(f"  subway_daily:   {len(daily):>6} rows → {args.out / 'mock_subway_daily.parquet'}")

    codes = ["11680", "11440", "11560"]
    trades = generate_apartment_trades(codes, months, seed=args.seed)
    trades.to_parquet(args.out / "mock_apt_trades.parquet", index=False)
    print(f"  apt_trades:     {len(trades):>6} rows → {args.out / 'mock_apt_trades.parquet'}")


if __name__ == "__main__":
    main()
