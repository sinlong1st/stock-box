"""Streamlit dashboard — price chart, score, explanation, and run history.

Run: ``uv run streamlit run dashboard.py``. Consumes ``stocksense.pipeline``.
Build order step 8 (TECH_STACK.md).
"""

from __future__ import annotations

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from stocksense import data, pipeline, storage


def normalized_weights(w_price: float, w_rsi: float, w_news: float) -> dict:
    """Auto-normalize the three sliders to sum to 1.0 (TECH_STACK.md §06)."""
    total = w_price + w_rsi + w_news or 1.0
    return {
        "price": round(w_price / total, 4),
        "rsi": round(w_rsi / total, 4),
        "news": round(w_news / total, 4),
    }


def main() -> None:
    st.set_page_config(page_title="StockSense", page_icon="📈", layout="wide")
    st.title("📈 StockSense")
    st.caption("Technical indicators + AI news sentiment + your weights → one score.")

    ticker = st.text_input("Ticker", "AAPL").strip().upper()

    st.sidebar.header("Weights")
    weights = normalized_weights(
        st.sidebar.slider("Price weight", 0.0, 1.0, 0.30, 0.05),
        st.sidebar.slider("RSI weight", 0.0, 1.0, 0.20, 0.05),
        st.sidebar.slider("News weight", 0.0, 1.0, 0.50, 0.05),
    )
    st.sidebar.write("Normalized:", weights)
    scrape_news = st.sidebar.checkbox("Scrape live news (Playwright)", value=False)
    persist = st.sidebar.checkbox("Save run (SQLite + JSON)", value=True)

    if st.button("Analyze", type="primary") and ticker:
        with st.spinner(f"Analyzing {ticker}…"):
            try:
                df = data.fetch_ohlcv(ticker)
                result = pipeline.analyze(
                    ticker, weights, scrape_news=scrape_news,
                    persist=persist, prices=df,
                )
            except Exception as exc:  # surface fetch/other errors in the UI
                st.error(f"Analysis failed: {exc}")
                return

        _render_price_header(df, result)
        _render_price_chart(df, result["technicals"])
        _render_score(result)
        _render_explanation(result)

    _render_history(ticker)


def _render_price_header(df: pd.DataFrame, result: dict) -> None:
    close = df["close"]
    current = float(close.iloc[-1])
    as_of = df["date"].iloc[-1]

    delta_txt = None
    if len(close) >= 2:
        change = current - float(close.iloc[-2])
        pct = change / float(close.iloc[-2]) * 100 if close.iloc[-2] else 0.0
        delta_txt = f"{change:+.2f} ({pct:+.2f}%) vs prev close"

    col1, col2 = st.columns([1, 2])
    col1.metric(f"{result['ticker']} — current price", f"${current:,.2f}", delta_txt)
    col2.caption(
        f"📅 Price as of **{as_of}** (most recent daily close). "
        f"Analysis run at **{_fmt_ts(result['timestamp'])}**. "
        f"Data source: Yahoo Finance ({len(df)} trading days)."
    )


def _render_price_chart(df: pd.DataFrame, technicals: dict) -> None:
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])

    price_line = (
        alt.Chart(d)
        .mark_line(color="#4c78a8")
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("close:Q", title="Close price", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("date:T"), alt.Tooltip("close:Q", format="$.2f")],
        )
    )

    levels = pd.DataFrame(
        {
            "label": ["Support", "Resistance", "52w low", "52w high"],
            "value": [
                technicals["support"],
                technicals["resistance"],
                technicals["low_52w"],
                technicals["high_52w"],
            ],
        }
    )
    rules = (
        alt.Chart(levels)
        .mark_rule(strokeDash=[4, 4], opacity=0.7)
        .encode(
            y="value:Q",
            color=alt.Color("label:N", title="Levels"),
            tooltip=[alt.Tooltip("label:N"), alt.Tooltip("value:Q", format="$.2f")],
        )
    )

    st.altair_chart(
        (price_line + rules).properties(height=380).interactive(),
        width="stretch",
    )


def _render_score(result: dict) -> None:
    st.subheader("Score")
    st.metric("Final score (0–100)", result["final_score"], result["signal"])
    st.write(f"**Suggested action:** {result['action']}")

    sub = result["sub_scores"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Price sub-score", sub["score_price"])
    c2.metric("RSI sub-score", "—" if sub["score_rsi"] is None else sub["score_rsi"])
    c3.metric("News sub-score", sub["score_news"])
    st.progress(min(int(result["final_score"]), 100))

    if result["flags"]:
        st.warning("Flags: " + ", ".join(result["flags"]))


def _render_explanation(result: dict) -> None:
    tech = result["technicals"]
    pos_pct = tech["position_in_range"] * 100
    rsi = tech["rsi"]
    rsi_txt = (
        "not enough data to compute" if rsi is None
        else f"{rsi:.1f} — {'oversold (bullish)' if rsi <= 30 else 'overbought (bearish)' if rsi >= 70 else 'neutral'}"
    )

    st.subheader("What this means")
    st.markdown(
        f"""
- **Price:** trading **{pos_pct:.0f}%** of the way up its 52-week range
  (${tech['low_52w']:,.2f} → ${tech['high_52w']:,.2f}). StockSense scores *higher*
  when a stock is nearer its **low** (cheaper), so this contributes
  **{result['sub_scores']['score_price']}**/100.
- **RSI (momentum):** {rsi_txt}. Lower RSI = more oversold = higher score.
- **News sentiment:** labeled **{result['sentiment_label']}** →
  **{result['sub_scores']['score_news']}**/100.
- **Final = weighted average** using your weights
  ({', '.join(f'{k} {v}' for k, v in result['weights_used'].items())})
  = **{result['final_score']}** → *{result['signal']}*.
"""
    )

    with st.expander("ℹ️ How the scoring works (methodology)"):
        st.markdown(
            """
Each sub-score is 0–100, then blended by **your weights** (which must sum to 1.0):

| Sub-score | Higher when… | Formula |
|---|---|---|
| **Price** | price is near its 52-week **low** | `(1 − position_in_range) × 100` |
| **RSI** | stock is **oversold** | 100 if RSI ≤ 30, 0 if RSI ≥ 70, else scaled |
| **News** | headlines are **positive** | Claude label → score (very_positive=100 … very_negative=0) |

**This is a heuristic, not a prediction.** A high score means "cheap + oversold +
positive news" by these rules — always seek your own confirmation. StockSense never
places trades and never guarantees direction.
"""
        )


def _render_history(ticker: str) -> None:
    history = storage.fetch_history(ticker)
    if not history:
        return
    st.subheader(f"Run history — {ticker}")
    df = pd.DataFrame(history)
    st.line_chart(df.set_index("run_at")["final_score"])
    st.dataframe(
        df[["run_at", "final_score", "signal", "sentiment_label", "flags"]],
        width="stretch",
    )


def _fmt_ts(iso_ts: str) -> str:
    """Render an ISO timestamp as a readable UTC string."""
    try:
        return datetime.fromisoformat(iso_ts).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return iso_ts


if __name__ == "__main__":
    main()
