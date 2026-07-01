"""Main entry point — wires every module into ``analyze(ticker, weights)``.

Output shape: schema.json > output. This assembles data -> indicators ->
sentiment -> scorer into the final result dict.

STATUS: partial. The scorer/indicator logic is real; data and sentiment are
stubs (raise NotImplementedError) until built. Build order step 5 (TECH_STACK.md).
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import data, indicators, scorer, sentiment
from .scraper import scrape_headlines  # noqa: F401  (used once scraper is built)


def analyze(ticker: str, weights: dict, headlines: list[str] | None = None) -> dict:
    """Run the full pipeline for one ticker and return the result dict.

    Validates weights up front (raises before any compute on bad weights).
    """
    scorer.validate_weights(weights)
    flags: list[str] = []

    df = data.fetch_ohlcv(ticker)
    close = df["close"]
    if len(df) < data.MINIMUM_DAYS:
        flags.append(f"insufficient_price_history_{len(df)}_days")

    current_price = float(close.iloc[-1])
    low_52w, high_52w = indicators.get_52w_range(close)
    position = indicators.get_position_in_range(current_price, low_52w, high_52w)
    rsi = indicators.latest_rsi(close, period=weights_period(weights))

    technicals = {
        "current_price": current_price,
        "rsi": rsi,
        "support": indicators.find_support(close),
        "resistance": indicators.find_resistance(close),
        "low_52w": low_52w,
        "high_52w": high_52w,
        "position_in_range": position,
    }

    if headlines is None:
        headlines = []  # scraper wiring goes here; empty -> neutral + flag
    if not headlines:
        flags.append("no_news_found")
    sentiment_label = sentiment.label_sentiment(ticker, headlines)

    scored = scorer.composite_score(technicals, sentiment_label, weights)
    interp = scorer.interpret_score(scored["final_score"])
    flags.extend(scored["flags"])

    return {
        "ticker": ticker,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "weights_used": scored["weights_used"],
        "technicals": technicals,
        "sentiment_label": sentiment_label,
        "sub_scores": scored["sub_scores"],
        "final_score": scored["final_score"],
        "signal": interp["signal"],
        "action": interp["action"],
        "flags": flags,
    }


def weights_period(weights: dict) -> int:
    """RSI period placeholder — kept configurable via config.yaml later."""
    return indicators.DEFAULT_RSI_PERIOD
