# StockSense

A configurable, single-ticker stock analysis pipeline. It blends **deterministic
technical indicators**, **AI-assisted news sentiment** (Claude), and a
**user-controlled weighted scoring system** into one 0–100 score with a full
sub-score breakdown and a human-readable signal.

> StockSense never hardcodes a "correct" weighting. The user always controls the
> weights and tunes them to their current market thesis. See [specs/SPEC.md](specs/SPEC.md).

## How the score works

| Sub-score | Source | Logic |
|---|---|---|
| Price | pure math | Higher near the 52-week low: `(1 - position_in_range) * 100` |
| RSI | pure math | Higher when oversold: `100` if RSI≤30, `0` if RSI≥70, else `(70-rsi)/40*100` |
| News | Claude sentiment | Label → score (`very_positive`=100 … `very_negative`=0) |

Final score = weighted average of the three, where `price + rsi + news` weights
must sum to `1.0` (tolerance 0.01). Formulas and thresholds live in
[specs/schema.json](specs/schema.json) — the source of truth for all code.

## Setup

```bash
# Install dependencies (uv creates the .venv automatically)
uv sync

# Chromium for the news scraper
uv run playwright install chromium

# Secrets
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

## Run the tests

```bash
uv run pytest
```

## Project layout

```
stocksense/
├── indicators.py   # RSI, support, resistance, 52w range      [implemented]
├── scorer.py       # weighted composite scoring + interpretation [implemented]
├── data.py         # yfinance / Alpaca OHLCV ingestion         [stub]
├── sentiment.py    # Claude sentiment labeling                 [stub]
├── scraper.py      # Playwright news scraper                   [stub]
├── storage.py      # SQLite history + JSON output files        [stub]
└── pipeline.py     # analyze(ticker, weights) — main entry     [stub]
dashboard.py        # Streamlit UI                              [stub]
```

Build order (each layer depends on the one above): `scorer → indicators → data →
sentiment → pipeline → storage → scraper → dashboard`. See
[specs/TECH_STACK.md](specs/TECH_STACK.md).

## Status

Scaffolded with the pure-math core (`scorer.py`, `indicators.py`) implemented and
unit-tested. The remaining modules are stubbed with signatures matching the spec
and raise `NotImplementedError`.
