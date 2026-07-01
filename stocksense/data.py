"""Price data ingestion (yfinance primary, Alpaca optional).

Output shape: schema.json > data_input.price_history — a DataFrame sorted
ascending by date with columns [date, open, high, low, close, volume],
minimum 180 days.

STATUS: stub. Build order step 3 (TECH_STACK.md).
"""

from __future__ import annotations

import pandas as pd

MINIMUM_DAYS = 180


def fetch_ohlcv(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Fetch daily OHLCV history via yfinance.

    Reference (TECH_STACK.md §01)::

        import yfinance as yf
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        df = df[["Open", "High", "Low", "Close", "Volume"]].reset_index()
        df.columns = ["date", "open", "high", "low", "close", "volume"]

    Must check ``df.empty`` before returning. Prefer ``period="6mo"`` over
    ``"180d"`` (more reliable).
    """
    raise NotImplementedError("data.fetch_ohlcv is not implemented yet")
