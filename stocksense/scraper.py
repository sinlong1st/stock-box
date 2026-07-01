"""Playwright news scraper — recent headlines for a ticker.

Target site: Yahoo Finance news tab. Returns a list of headline strings.
Most fragile module — built last. Any failure (missing browser, blocked host,
changed markup, timeout) degrades to an empty list so the caller can flag it
and fall back to a neutral sentiment / web_search.

Build order step 7 (TECH_STACK.md).
"""

from __future__ import annotations

import asyncio

NEWS_URL = "https://finance.yahoo.com/quote/{ticker}/news/"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# Yahoo's headline markup changes often; try selectors from most to least
# specific and take the first that yields plausible headlines.
_HEADLINE_SELECTORS = ["section li h3", "h3 a", "h3"]
_MIN_HEADLINE_LEN = 20


async def scrape_headlines(ticker: str, limit: int = 10) -> list[str]:
    """Scrape recent headlines for ``ticker`` (async, headless Chromium).

    Requires ``uv run playwright install chromium`` first. Returns ``[]`` on any
    error rather than raising.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=_USER_AGENT)
                await page.goto(
                    NEWS_URL.format(ticker=ticker),
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
                await page.wait_for_timeout(2_500)  # let the news stream hydrate
                for selector in _HEADLINE_SELECTORS:
                    texts = await page.eval_on_selector_all(
                        selector,
                        "els => els.map(e => (e.textContent || '').trim())",
                    )
                    headlines = _clean(texts)
                    if headlines:
                        return headlines[:limit]
                return []
            finally:
                await browser.close()
    except Exception:
        return []


def get_headlines(ticker: str, limit: int = 10) -> list[str]:
    """Synchronous wrapper around :func:`scrape_headlines` for non-async callers."""
    try:
        return asyncio.run(scrape_headlines(ticker, limit))
    except RuntimeError:
        # An event loop is already running (rare in our sync callers); use a
        # fresh loop so we don't clash with it.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(scrape_headlines(ticker, limit))
        finally:
            loop.close()


def _clean(texts: list[str]) -> list[str]:
    """Drop blanks/boilerplate, filter to plausible headlines, dedupe in order."""
    seen: set[str] = set()
    out: list[str] = []
    for text in texts:
        text = (text or "").strip()
        if len(text) < _MIN_HEADLINE_LEN or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
