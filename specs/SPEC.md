# StockSense — Product Specification

> AI READING INSTRUCTIONS: This file provides narrative context and intent.
> For exact formulas, thresholds, and data shapes, always refer to `schema.json`.
> When generating code, derive logic from `schema.json` first, use this file to resolve ambiguity.

---

## 1. What Is StockSense

StockSense is a configurable stock analysis pipeline. It combines:
- Deterministic technical indicators (computed from price history)
- AI-assisted news sentiment labeling (Claude reads headlines)
- A user-configurable weighted scoring system

The output is a single score (0-100) with full sub-score breakdown, plus a human-readable signal label.

**Key design constraint:** The user always controls the weights. StockSense never hardcodes a "correct" weighting — the user adjusts based on their current market thesis.

---

## 2. Architecture

```
[Data Source] → [Technical Analysis] → [News Ingestion] → [AI Sentiment] → [Scorer] → [Output]
```

### 2.1 Data Source (pluggable)
- Primary: Robinhood MCP (if available)
- Fallback: yfinance / Yahoo Finance API
- Custom: Playwright scraper for any broker or data site

Input required: minimum 180 days of daily OHLCV (Open, High, Low, Close, Volume).

### 2.2 Technical Analysis
Pure math, no AI. Computed from price history only.
- RSI (14-day default, configurable)
- 52-week high/low and current position in that range
- Support level (average of recent local lows)
- Resistance level (average of recent local highs)

See `schema.json > indicators` for exact formulas and parameters.

### 2.3 News Ingestion
- Primary: Playwright scraper pulling headlines from financial news sites
- Fallback: Claude web_search tool
- Input to AI: list of recent headlines (last 7 days) for the target ticker

### 2.4 AI Sentiment Labeling
Claude reads the headlines and assigns exactly one label from a fixed enum.
See `schema.json > sentiment.labels` for the enum and score mapping.

Claude should NOT explain its reasoning in this step — output label only (for JSON parsing).

### 2.5 Scorer
Computes weighted composite score from sub-scores.
See `schema.json > scoring` for formulas and weight validation rules.

### 2.6 Output
JSON by default. Optional: plain text report for human reading.
See `schema.json > output` for the exact output shape.

---

## 3. Configurable Weights — Design Intent

The weights system exists because different market conditions require different priorities.

**Example scenarios:**
- Normal market: balanced weights (price 0.3, rsi 0.2, news 0.5)
- War / macro shock: prioritize news heavily (news 0.7, price 0.2, rsi 0.1)
- Quiet macro, earnings season: reduce news weight, increase rsi (rsi 0.4, news 0.3, price 0.3)

The user passes a weight config object at runtime. The system validates that weights sum to 1.0 before computing.

---

## 4. What StockSense Does NOT Do

- Place trades autonomously — never
- Guarantee price direction — scores are heuristics, not predictions
- Support portfolios — single ticker per run in v1.0
- Stream real-time prices — polling per request only
- Handle options or derivatives

---

## 5. Sentiment Labeling Prompt (for AI)

When Claude labels news sentiment, use this prompt pattern:

```
You are a financial news sentiment classifier.
Given the following headlines for ticker [TICKER], assign exactly one label from:
very_positive, positive, neutral, negative, very_negative

Headlines:
[LIST OF HEADLINES]

Respond with JSON only: {"sentiment": "<label>"}
```

---

## 6. Error Handling Expectations

- Weight validation failure: raise error before computing, do not proceed
- Missing price data (< 180 days): warn user, compute with available data but flag result
- No news found: default sentiment to "neutral", flag in output
- RSI cannot be computed (< 14 data points): skip RSI score, redistribute its weight to price
