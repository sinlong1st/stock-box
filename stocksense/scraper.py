"""Playwright news scraper — recent headlines for a ticker.

Target sites: Yahoo Finance news tab, MarketWatch, Seeking Alpha. Returns a list
of headline strings from the last 7 days. Most fragile module — built last.
If it returns an empty list, the caller flags it and falls back to web_search.

STATUS: stub. Build order step 7 (TECH_STACK.md).
"""

from __future__ import annotations


async def scrape_headlines(ticker: str, limit: int = 10) -> list[str]:
    """Scrape recent headlines for ``ticker`` (async, headless Chromium).

    Reference call pattern in TECH_STACK.md §01. Requires
    ``uv run playwright install chromium`` first.
    """
    raise NotImplementedError("scraper.scrape_headlines is not implemented yet")
