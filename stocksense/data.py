"""Price data ingestion (yfinance primary, Alpaca optional).

Output shape: schema.json > data_input.price_history — a DataFrame sorted
ascending by date with columns [date, open, high, low, close, volume],
minimum 180 days.

Build order step 3 (TECH_STACK.md).
"""

from __future__ import annotations

import logging

import pandas as pd
import requests
import yfinance as yf

# yfinance logs a full ConnectionError to the console when fc.yahoo.com (its
# cookie host) is blocked. We handle that by falling back, so silence the noise.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

MINIMUM_DAYS = 180

# Default to 1y: the spec requires >=180 daily rows and scores against a 52-week
# range, and "6mo" yields only ~123 trading days (below the minimum). This
# intentionally differs from the "6mo" example in TECH_STACK.md §01.
DEFAULT_PERIOD = "1y"

_OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

# Yahoo's public chart endpoint. Reachable directly and needs no auth
# cookie/crumb, so it works even when fc.yahoo.com (yfinance's cookie host)
# is blocked by a firewall/AV/DNS filter.
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_CHART_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_ohlcv(ticker: str, period: str = DEFAULT_PERIOD) -> pd.DataFrame:
    """Fetch daily OHLCV history for ``ticker``.

    Tries yfinance first, then falls back to Yahoo's chart API (which does not
    depend on the frequently-blocked fc.yahoo.com cookie host). Returns a
    DataFrame with columns [date, open, high, low, close, volume], sorted
    ascending by date; ``date`` is an ISO ``YYYY-MM-DD`` string
    (schema.json > data_input.price_history).

    Raises ``ValueError`` if both sources return nothing (bad symbol, delisting,
    or a network block affecting the query* hosts too). Defaults to ``"1y"`` to
    meet the >=180-row minimum; use named periods ("6mo", "1y", "2y") not "180d".
    """
    df = _fetch_via_yfinance(ticker, period)
    if df is None or df.empty:
        df = _fetch_via_chart_api(ticker, period)

    if df is None or df.empty:
        raise ValueError(
            f"No price data returned for {ticker!r}. Check the symbol; Yahoo may "
            "be rate-limiting, or the query*.finance.yahoo.com hosts are blocked."
        )
    return df


def _fetch_via_yfinance(ticker: str, period: str) -> pd.DataFrame | None:
    """Primary path. Returns ``None`` on any failure so the caller can fall back."""
    try:
        raw = yf.download(
            ticker, period=period, interval="1d", progress=False, auto_adjust=True
        )
    except Exception:
        return None
    if raw is None or raw.empty:
        return None

    # Single-ticker downloads can come back with MultiIndex columns
    # e.g. ('Close', 'AAPL'); flatten to the price-field level.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw = raw.reset_index()
    date_col = "Date" if "Date" in raw.columns else raw.columns[0]
    return _normalize(
        dates=raw[date_col],
        open_=raw["Open"],
        high=raw["High"],
        low=raw["Low"],
        close=raw["Close"],
        volume=raw["Volume"],
    )


def _fetch_via_chart_api(ticker: str, period: str) -> pd.DataFrame | None:
    """Fallback path via the public chart API. Returns ``None`` on any failure."""
    try:
        resp = requests.get(
            _CHART_URL.format(ticker=ticker),
            params={"range": period, "interval": "1d"},
            headers=_CHART_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()["chart"]["result"]
    except Exception:
        return None
    if not result or not result[0].get("timestamp"):
        return None

    r = result[0]
    quote = r["indicators"]["quote"][0]
    return _normalize(
        dates=pd.to_datetime(r["timestamp"], unit="s", utc=True),
        open_=quote.get("open"),
        high=quote.get("high"),
        low=quote.get("low"),
        close=quote.get("close"),
        volume=quote.get("volume"),
    )


def _normalize(dates, open_, high, low, close, volume) -> pd.DataFrame:
    """Assemble the canonical OHLCV frame, drop null-close rows, sort by date.

    Inputs may be pandas Series (yfinance) or plain lists (chart API); everything
    is coerced positionally to avoid index-alignment surprises.
    """
    date_index = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates).to_numpy()))

    def col(values):
        return pd.to_numeric(pd.Series(list(values)), errors="coerce").to_numpy()

    df = pd.DataFrame(
        {
            "date": date_index.strftime("%Y-%m-%d").tolist(),
            "open": col(open_),
            "high": col(high),
            "low": col(low),
            "close": col(close),
            "volume": col(volume),
        }
    )
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    df["volume"] = df["volume"].fillna(0).astype("int64")
    return df.sort_values("date").reset_index(drop=True)
