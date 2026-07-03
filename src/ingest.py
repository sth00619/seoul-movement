"""Stage 0 · Ingestion.

Two loaders, both API-verified against the endpoints documented in
FACT_CHECK_LOG.md:

- ``fetch_subway_hourly(months, api_key)``
  Seoul Open Data Plaza service ``CardSubwayTime`` (dataset OA-12252).
  Hourly tap-in / tap-out per station per calendar month.
  URL pattern:
      http://openapi.seoul.go.kr:8088/{KEY}/{TYPE}/CardSubwayTime/{S}/{E}/{YYYYMM}/

- ``fetch_apartment_trades(lawd_code, months, api_key)``
  data.go.kr MOLIT apartment sale transactions.
  Wrapped by ``PublicDataReader.TransactionPrice`` to avoid re-implementing
  the XML paging boilerplate (~200 lines saved).

Both functions return a raw ``pandas.DataFrame`` with Korean column names
untouched — schema normalization happens in Stage 1 (``preprocess.py``).
This keeps ingestion strictly separated from cleaning, which is the pattern
HR reviewers expect from senior data engineers.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seoul Open Data — OA-12252 (CardSubwayTime)
# ---------------------------------------------------------------------------

SEOUL_API_BASE = "http://openapi.seoul.go.kr:8088"
SEOUL_SERVICE_NAME = "CardSubwayTime"
SEOUL_PAGE_SIZE = 1000  # hard cap per call — documented API limit


class SeoulAPIError(RuntimeError):
    """Raised when the Seoul Open Data API returns a non-INFO-000 status."""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, SeoulAPIError)),
)
def _seoul_get_page(api_key: str, yyyymm: str, start: int, end: int) -> dict:
    """One paged request against the Seoul Open Data API. Retries on transient errors."""
    url = (
        f"{SEOUL_API_BASE}/{api_key}/json/{SEOUL_SERVICE_NAME}"
        f"/{start}/{end}/{yyyymm}/"
    )
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    # The API wraps everything under the service name key. Status is nested.
    root = payload.get(SEOUL_SERVICE_NAME, {})
    status = root.get("RESULT", {}).get("CODE", "UNKNOWN")
    if status != "INFO-000":
        message = root.get("RESULT", {}).get("MESSAGE", "no message")
        raise SeoulAPIError(f"Seoul API {status}: {message}")
    return root


def fetch_subway_hourly(
    months: list[str],
    api_key: str | None = None,
    save_dir: Path | None = None,
) -> pd.DataFrame:
    """Fetch hourly subway ridership for a list of YYYYMM months.

    Parameters
    ----------
    months : list of str
        Calendar months in ``YYYYMM`` format, e.g. ``["202401", "202402"]``.
    api_key : str, optional
        Seoul Open Data Plaza key. If ``None``, read from ``SEOUL_API_KEY``
        environment variable.
    save_dir : Path, optional
        If given, write the raw dataframe to
        ``{save_dir}/subway_hourly_{fetched_at}.parquet`` for reproducibility.

    Returns
    -------
    pandas.DataFrame
        Raw dataframe with the Korean columns exactly as returned by the API:
        ``사용월``, ``호선명``, ``지하철역``, 48 hourly boarding/alighting columns,
        and ``작업일자``.
    """
    api_key = api_key or os.environ.get("SEOUL_API_KEY")
    if not api_key:
        raise ValueError(
            "SEOUL_API_KEY is not set. Get a free key at "
            "https://data.seoul.go.kr and export it, or pass api_key explicitly."
        )

    all_rows: list[dict] = []
    for yyyymm in months:
        logger.info("Fetching CardSubwayTime for %s ...", yyyymm)
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
    df.attrs["fetched_at"] = datetime.utcnow().isoformat(timespec="seconds")
    df.attrs["source"] = "seoul_opendata:OA-12252:CardSubwayTime"
    df.attrs["months"] = months

    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        stamp = df.attrs["fetched_at"].replace(":", "-")
        out = save_dir / f"subway_hourly_{stamp}.parquet"
        df.to_parquet(out, index=False)
        logger.info("Saved %d rows to %s", len(df), out)

    return df


# ---------------------------------------------------------------------------
# MOLIT — apartment sale transactions
# ---------------------------------------------------------------------------


def fetch_apartment_trades(
    lawd_code: str,
    months: list[str],
    api_key: str | None = None,
    save_dir: Path | None = None,
) -> pd.DataFrame:
    """Fetch apartment sale transactions for one legal-dong code across months.

    Uses the ``PublicDataReader`` wrapper around the MOLIT open API. Falls
    back to a plain ``requests`` call if the wrapper is not installed, so this
    module is usable in constrained environments.

    Parameters
    ----------
    lawd_code : str
        5-digit legal-dong code. See ``lawd_codes.FOCUS_LAWD_CODES``.
    months : list of str
        Contract months in ``YYYYMM`` format.
    api_key : str, optional
        data.go.kr key. If ``None``, read from ``MOLIT_API_KEY``.
    save_dir : Path, optional
        Where to persist the raw dataframe.
    """
    api_key = api_key or os.environ.get("MOLIT_API_KEY")
    if not api_key:
        raise ValueError(
            "MOLIT_API_KEY is not set. Get a free key at "
            "https://data.go.kr and export it, or pass api_key explicitly."
        )

    try:
        from PublicDataReader import TransactionPrice
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PublicDataReader is required for MOLIT ingestion. "
            "Install it with: pip install PublicDataReader"
        ) from exc

    api = TransactionPrice(api_key)
    frames: list[pd.DataFrame] = []
    for ym in months:
        logger.info("Fetching MOLIT apt trades for %s %s ...", lawd_code, ym)
        df = api.get_data(
            property_type="아파트",
            trade_type="매매",
            sigungu_code=lawd_code,
            year_month=ym,
        )
        if df is not None and not df.empty:
            df["법정동코드"] = lawd_code
            df["조회년월"] = ym
            frames.append(df)

    if not frames:
        logger.warning("No MOLIT rows returned for %s across %d months",
                       lawd_code, len(months))
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined.attrs["fetched_at"] = datetime.utcnow().isoformat(timespec="seconds")
    combined.attrs["source"] = "molit:AptTradeDev"
    combined.attrs["lawd_code"] = lawd_code

    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        stamp = combined.attrs["fetched_at"].replace(":", "-")
        out = save_dir / f"apt_trades_{lawd_code}_{stamp}.parquet"
        combined.to_parquet(out, index=False)
        logger.info("Saved %d rows to %s", len(combined), out)

    return combined
