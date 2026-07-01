"""Technical indicators — pure pandas/numpy math, no AI.

All formulas, parameters, and fallbacks are derived from
``specs/schema.json > indicators``. Operate on the ``close`` price Series.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_RSI_PERIOD = 14
DEFAULT_N_LOCALS = 3


def calculate_rsi(prices: pd.Series, period: int = DEFAULT_RSI_PERIOD) -> pd.Series:
    """Relative Strength Index as a Series (schema.json > indicators.rsi).

    Uses a simple rolling mean of gains/losses. Values before ``period`` rows of
    data are ``NaN``. Use :func:`latest_rsi` to get the final value with the
    insufficient-data fallback applied.
    """
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    # avg_loss == 0 -> rs is inf -> rsi -> 100 (all gains, maximally overbought).
    return rsi.where(avg_loss != 0, 100.0)


def latest_rsi(prices: pd.Series, period: int = DEFAULT_RSI_PERIOD) -> float | None:
    """Most recent RSI value, or ``None`` if there is insufficient data.

    Per SPEC.md §6, with fewer than ``period`` deltas RSI cannot be computed and
    the caller should skip the RSI sub-score and redistribute its weight.
    """
    if len(prices) <= period:
        return None
    value = calculate_rsi(prices, period).iloc[-1]
    return None if pd.isna(value) else float(value)


def find_support(prices: pd.Series, n_locals: int = DEFAULT_N_LOCALS) -> float:
    """Average of the last ``n_locals`` local lows.

    Local low: ``close[i] < close[i-1] and close[i] < close[i+1]``. Falls back to
    ``min(close)`` when fewer than ``n_locals`` local lows exist
    (schema.json > indicators.support).
    """
    lows = _local_extrema(prices, kind="low")
    if len(lows) < n_locals:
        return float(prices.min())
    return float(sum(lows[-n_locals:]) / n_locals)


def find_resistance(prices: pd.Series, n_locals: int = DEFAULT_N_LOCALS) -> float:
    """Average of the last ``n_locals`` local highs.

    Local high: ``close[i] > close[i-1] and close[i] > close[i+1]``. Falls back to
    ``max(close)`` when fewer than ``n_locals`` local highs exist
    (schema.json > indicators.resistance).
    """
    highs = _local_extrema(prices, kind="high")
    if len(highs) < n_locals:
        return float(prices.max())
    return float(sum(highs[-n_locals:]) / n_locals)


def get_52w_range(prices: pd.Series) -> tuple[float, float]:
    """(low, high) over the full dataset (schema.json > indicators.range_52w)."""
    return float(prices.min()), float(prices.max())


def get_position_in_range(current: float, low: float, high: float) -> float:
    """Where ``current`` sits within [low, high], as 0.0-1.0.

    ``(current - low) / (high - low)``. Returns 0.5 (neutral) for a flat range.
    """
    span = high - low
    if span == 0:
        return 0.5
    return (current - low) / span


def _local_extrema(prices: pd.Series, kind: str) -> list[float]:
    """Interior local lows or highs, in ascending index order."""
    values = prices.to_numpy()
    out: list[float] = []
    for i in range(1, len(values) - 1):
        prev, cur, nxt = values[i - 1], values[i], values[i + 1]
        if kind == "low" and cur < prev and cur < nxt:
            out.append(float(cur))
        elif kind == "high" and cur > prev and cur > nxt:
            out.append(float(cur))
    return out
