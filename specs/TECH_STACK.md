# StockSense — Tech Stack Reference

> AI READING INSTRUCTIONS: This file describes every tool, library, and pattern
> used in StockSense. When generating code, use ONLY the libraries listed here.
> Do not introduce new dependencies without flagging it. For data shapes and
> formulas, defer to schema.json. For architecture decisions, defer to SPEC.md.

---

## Stack Overview

| Layer | Tool | Free? | Notes |
|---|---|---|---|
| Price data | yfinance | Yes | Primary. No signup required. |
| Price data (alt) | Alpaca API | Yes (free tier) | Use when paper trading or real-time needed |
| News scraping | Playwright (Python) | Yes | Custom scraper for headlines |
| News fallback | Claude web_search | API cost only | Fallback when scraper not running |
| Technical analysis | pandas + numpy | Yes | All indicator math |
| Sentiment labeling | Claude API (claude-sonnet-4-6) | API cost only | JSON-only output, one label per run |
| Scoring | Python (custom module) | Yes | Weighted composite, see schema.json |
| Config | config.yaml + PyYAML | Yes | Per-ticker weight config |
| Storage | SQLite + json files | Yes | SQLite for history, JSON for per-run output |
| API layer | FastAPI | Yes | Optional, add when scaling |
| Scheduler | APScheduler or cron | Yes | Optional, for scheduled runs |
| Dashboard | Streamlit | Yes | Weight sliders, score display, charts |
| Package manager | uv | Yes | Faster than pip |
| Testing | pytest | Yes | Unit tests for scoring module |
| Secrets | python-dotenv + .env | Yes | API keys, never hardcode |

---

## 01 — Data Layer

### yfinance (primary)
```python
pip install yfinance
```
- Use for: historical OHLCV data, minimum 180 days
- Call pattern:
```python
import yfinance as yf
df = yf.download("AAPL", period="6mo", interval="1d", progress=False)
df = df[["Open", "High", "Low", "Close", "Volume"]].reset_index()
df.columns = ["date", "open", "high", "low", "close", "volume"]
```
- Output: pandas DataFrame, sorted ascending by date
- Gotchas:
  - Yahoo Finance is an unofficial API, can rate-limit or break without warning
  - Always check `df.empty` before proceeding
  - Use `period="6mo"` not `period="180d"` — more reliable

### Alpaca API (alternative / paper trading)
```python
pip install alpaca-py
```
- Use for: paper trading simulation, real-time bars, live execution (future)
- Free tier gives IEX-sourced data (real-time but ~5-10% of volume)
- Paid tier ($9/mo) gives SIP consolidated data — needed for volume-sensitive strategies
- Call pattern:
```python
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

client = StockHistoricalDataClient(api_key, secret_key)
request = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame.Day,
    start=datetime.now() - timedelta(days=180)
)
bars = client.get_stock_bars(request).df
```
- Paper trading base URL: `https://paper-api.alpaca.markets`
- Env vars needed: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`

### Playwright (news scraper)
```python
pip install playwright
playwright install chromium
```
- Use for: scraping recent headlines from financial news sites
- Target sites: Yahoo Finance news tab, MarketWatch, Seeking Alpha
- Output: list of strings (headlines), last 7 days for the target ticker
- Call pattern (async):
```python
from playwright.async_api import async_playwright

async def scrape_headlines(ticker: str) -> list[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"https://finance.yahoo.com/quote/{ticker}/news/")
        await page.wait_for_timeout(2000)
        headlines = await page.eval_on_selector_all(
            "h3.Mb\\(5px\\)", "els => els.map(e => e.textContent)"
        )
        await browser.close()
        return headlines[:10]
```
- Fallback: if scraper returns empty list, flag in output and use Claude web_search

---

## 02 — Analysis Layer

### pandas + numpy
```python
pip install pandas numpy
```
- All technical indicator math runs here — no AI involved
- Key functions to implement (see schema.json > indicators for formulas):
  - `calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series`
  - `find_support(prices: pd.Series, n_locals: int = 3) -> float`
  - `find_resistance(prices: pd.Series, n_locals: int = 3) -> float`
  - `get_52w_range(prices: pd.Series) -> tuple[float, float]`
  - `get_position_in_range(current: float, low: float, high: float) -> float`
- Always operate on `df["close"]` as a pandas Series
- Always use the last value after rolling calculations: `rsi_series.iloc[-1]`

### Claude API — sentiment labeling
```python
pip install anthropic
```
- Model: `claude-sonnet-4-6` — always use this, do not swap
- Use for: reading news headlines and returning one sentiment label
- Output must be JSON only: `{"sentiment": "<label>"}`
- Call pattern:
```python
import anthropic
import json

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def label_sentiment(ticker: str, headlines: list[str]) -> str:
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    prompt = f"""You are a financial news sentiment classifier.
Given the following headlines for ticker {ticker}, assign exactly one label from:
very_positive, positive, neutral, negative, very_negative

Headlines:
{headlines_text}

Respond with JSON only: {{"sentiment": "<label>"}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}]
    )
    result = json.loads(message.content[0].text)
    return result["sentiment"]
```
- If headlines list is empty: skip API call, return `"neutral"`, add flag to output
- max_tokens: 50 is enough — the output is a tiny JSON object
- Error handling: wrap json.loads in try/except, fall back to `"neutral"` on parse failure

---

## 03 — Scoring Layer

### Python scoring module (custom)
- No external library needed — pure Python math
- File: `stocksense/scorer.py`
- Functions to implement:
  - `score_price(position_in_range: float) -> float`
  - `score_rsi(rsi: float) -> float`
  - `score_news(sentiment_label: str) -> float`
  - `validate_weights(weights: dict) -> None` — raises ValueError if sum != 1.0
  - `composite_score(technicals: dict, sentiment_label: str, weights: dict) -> dict`
  - `interpret_score(score: float) -> dict` — returns label + action
- See schema.json > scoring for all formulas and thresholds

### config.yaml (per-ticker weight config)
```python
pip install pyyaml
```
- One file per ticker or strategy
- Format:
```yaml
ticker: AAPL
weights:
  price: 0.30
  rsi: 0.20
  news: 0.50
rsi_period: 14
news_lookback_days: 7
```
- Load pattern:
```python
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)
```
- Never hardcode weights in Python — always read from config

---

## 04 — Storage Layer

### SQLite
```python
# built into Python stdlib — no install needed
import sqlite3
```
- Use for: storing every run result for historical analysis
- Schema (create on first run):
```sql
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    weights_price REAL,
    weights_rsi REAL,
    weights_news REAL,
    score_price REAL,
    score_rsi REAL,
    score_news REAL,
    final_score REAL,
    sentiment_label TEXT,
    signal TEXT,
    flags TEXT
);
```
- Insert pattern: save every call to `composite_score()` here
- Query pattern: `SELECT * FROM runs WHERE ticker = ? ORDER BY run_at DESC` for dashboard

### JSON output files
- Save the full output dict from each run as a `.json` file
- Naming: `outputs/{ticker}_{YYYYMMDD_HHMMSS}.json`
- Shape: see schema.json > output for the exact structure

---

## 05 — API Layer (optional)

### FastAPI
```python
pip install fastapi uvicorn
```
- Add this layer when you want to call StockSense from Streamlit remotely
  or expose it as a service
- Single endpoint to implement:
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AnalyzeRequest(BaseModel):
    ticker: str
    weights: dict[str, float]

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    # call the pipeline here
    return result
```
- Run: `uvicorn main:app --reload`
- Skip this in v1 — call the Python functions directly from Streamlit instead

### APScheduler (optional)
```python
pip install apscheduler
```
- Use for: running analysis on a schedule (e.g. every morning at 9am before market open)
- Pattern:
```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

@scheduler.scheduled_job("cron", hour=9, minute=0, day_of_week="mon-fri")
def morning_run():
    run_pipeline("AAPL", config["weights"])

scheduler.start()
```

---

## 06 — Dashboard Layer

### Streamlit
```python
pip install streamlit
```
- Run: `streamlit run dashboard.py`
- Key widgets to use:
  - `st.slider()` — weight config (price / rsi / news, auto-sum to 1.0)
  - `st.text_input()` — ticker input
  - `st.metric()` — display final score and sub-scores
  - `st.line_chart()` or `st.plotly_chart()` — score history from SQLite
  - `st.json()` — raw output display
- Pattern for weight sliders (auto-normalize to sum 1.0):
```python
w_price = st.slider("Price weight", 0.0, 1.0, 0.3, 0.05)
w_rsi   = st.slider("RSI weight",   0.0, 1.0, 0.2, 0.05)
w_news  = st.slider("News weight",  0.0, 1.0, 0.5, 0.05)
total = w_price + w_rsi + w_news
weights = {
    "price": round(w_price / total, 4),
    "rsi":   round(w_rsi   / total, 4),
    "news":  round(w_news  / total, 4),
}
```

---

## Dev Tooling

### uv (package manager)
```bash
curl -Ls https://astral.sh/uv/install.sh | sh
uv init stocksense
uv add yfinance pandas numpy anthropic playwright pyyaml streamlit
```
- Replaces pip + venv in one tool — faster and cleaner

### pytest
```python
uv add --dev pytest
```
- Write tests for: score_price, score_rsi, score_news, composite_score, validate_weights
- These are pure math functions — 100% testable with no mocks
- Run: `pytest tests/`

### python-dotenv
```python
uv add python-dotenv
```
- `.env` file (never commit to git):
```
ANTHROPIC_API_KEY=sk-ant-...
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
```
- Load at entry point:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Project Structure

```
stocksense/
├── .env                    # secrets — never commit
├── config.yaml             # default weight config
├── SPEC.md                 # architecture + intent
├── TECH_STACK.md           # this file
├── schema.json             # formulas + data shapes
├── pyproject.toml          # uv-managed dependencies
├── stocksense/
│   ├── __init__.py
│   ├── data.py             # yfinance + Alpaca ingestion
│   ├── scraper.py          # Playwright news scraper
│   ├── indicators.py       # RSI, support, resistance, 52w range
│   ├── sentiment.py        # Claude API sentiment call
│   ├── scorer.py           # composite scoring logic
│   ├── storage.py          # SQLite + JSON file output
│   └── pipeline.py         # analyze(ticker, weights) — main entry point
├── dashboard.py            # Streamlit UI
├── tests/
│   ├── test_indicators.py
│   └── test_scorer.py
└── outputs/                # per-run JSON files
```

---

## Build Order

Build in this exact sequence — each layer depends on the one above:

1. `scorer.py` + `tests/test_scorer.py` — pure math, no external deps, verify formulas
2. `indicators.py` + `tests/test_indicators.py` — pandas math, testable with sample data
3. `data.py` — yfinance ingestion, check output shape matches schema.json > data_input
4. `sentiment.py` — Claude API call, test with a hardcoded headline list first
5. `pipeline.py` — wire all modules into `analyze(ticker, weights) -> dict`
6. `storage.py` — SQLite schema + JSON file write
7. `scraper.py` — Playwright news scraper (most fragile, build last)
8. `dashboard.py` — Streamlit UI consuming pipeline.py
9. FastAPI layer — only when ready to expose as a service

---

## Environment Variables Reference

| Variable | Used by | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | sentiment.py | Yes |
| `ALPACA_API_KEY` | data.py (Alpaca only) | No (yfinance doesn't need it) |
| `ALPACA_SECRET_KEY` | data.py (Alpaca only) | No |

---

## Companion Files

| File | Purpose |
|---|---|
| `SPEC.md` | Architecture, design decisions, edge cases |
| `schema.json` | Formulas, data shapes, enums — source of truth for code generation |
| `TECH_STACK.md` | This file — tools, patterns, project structure |
