"""Main entry point — wires every module into ``analyze(ticker, weights)``.

Output shape: schema.json > output. Assembles data -> indicators -> news ->
sentiment -> scorer, and optionally persists the run. Build order step 5.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import data, indicators, scorer, sentiment, storage
from .scraper import get_headlines


def analyze(
    ticker: str,
    weights: dict,
    headlines: list[str] | None = None,
    *,
    scrape_news: bool = False,
    rsi_period: int = indicators.DEFAULT_RSI_PERIOD,
    persist: bool = False,
    prices=None,
) -> dict:
    """Run the full pipeline for one ticker and return the result dict.

    - ``headlines``: pass a pre-fetched list to label sentiment on. If ``None``
      and ``scrape_news`` is True, headlines are scraped via Playwright.
    - ``scrape_news``: enable the (fragile) Playwright scraper. Off by default so
      the pipeline stays deterministic/offline unless explicitly asked.
    - ``persist``: when True, save the run to SQLite and write an outputs/*.json.
    - ``prices``: optional pre-fetched OHLCV DataFrame (schema.json shape) to reuse
      instead of fetching again — lets a caller chart the same data it scored on.

    Validates weights up front (raises before any compute on bad weights).
    """
    scorer.validate_weights(weights)
    flags: list[str] = []

    df = data.fetch_ohlcv(ticker) if prices is None else prices
    close = df["close"]
    if len(df) < data.MINIMUM_DAYS:
        flags.append(f"insufficient_price_history_{len(df)}_days")

    current_price = float(close.iloc[-1])
    low_52w, high_52w = indicators.get_52w_range(close)
    technicals = {
        "current_price": current_price,
        "rsi": indicators.latest_rsi(close, period=rsi_period),
        "support": indicators.find_support(close),
        "resistance": indicators.find_resistance(close),
        "low_52w": low_52w,
        "high_52w": high_52w,
        "position_in_range": indicators.get_position_in_range(
            current_price, low_52w, high_52w
        ),
    }

    if headlines is None and scrape_news:
        headlines = get_headlines(ticker)
    if not headlines:
        flags.append("no_news_found")
        headlines = []
    sentiment_label = sentiment.label_sentiment(ticker, headlines)

    scored = scorer.composite_score(technicals, sentiment_label, weights)
    interp = scorer.interpret_score(scored["final_score"])
    flags.extend(scored["flags"])

    result = {
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

    if persist:
        storage.save_run(result)
        storage.write_output_json(result)

    return result
