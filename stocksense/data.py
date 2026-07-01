"""Price data ingestion (yfinance primary, Alpaca optional).

Output shape: schema.json > data_input.price_history — a DataFrame sorted
ascending by date with columns [date, open, high, low, close, volume],
minimum 180 days.

Build order step 3 (TECH_STACK.md).
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf

MINIMUM_DAYS = 180

_OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def fetch_ohlcv(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Fetch daily OHLCV history via yfinance.

    Returns a DataFrame with columns [date, open, high, low, close, volume],
    sorted ascending by date. ``date`` is an ISO ``YYYY-MM-DD`` string
    (schema.json > data_input.price_history).

    Raises ``ValueError`` if Yahoo returns no data (delisted ticker, typo, or a
    transient API/rate-limit failure). Prefer ``period="6mo"`` over ``"180d"`` —
    more reliable per TECH_STACK.md §01.
    """
    df = yf.download(
        ticker,
        period=period,
        interval="1d",
        progress=False,
        auto_adjust=True,
    )

    if df is None or df.empty:
        raise ValueError(
            f"No price data returned for {ticker!r}. Check the symbol, or Yahoo "
            "Finance may be rate-limiting (it is an unofficial API)."
        )

    # Single-ticker downloads can come back with MultiIndex columns
    # e.g. ('Close', 'AAPL'); flatten to the price-field level.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
            "open": df["Open"].astype(float),
            "high": df["High"].astype(float),
            "low": df["Low"].astype(float),
            "close": df["Close"].astype(float),
            "volume": df["Volume"].fillna(0).astype("int64"),
        }
    )

    return out.sort_values("date").reset_index(drop=True)
