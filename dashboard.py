"""Streamlit dashboard — weight sliders, score display, run history.

Run: ``uv run streamlit run dashboard.py``. Consumes ``stocksense.pipeline``.
Build order step 8 (TECH_STACK.md).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from stocksense import pipeline, storage


def normalized_weights(w_price: float, w_rsi: float, w_news: float) -> dict:
    """Auto-normalize the three sliders to sum to 1.0 (TECH_STACK.md §06)."""
    total = w_price + w_rsi + w_news or 1.0
    return {
        "price": round(w_price / total, 4),
        "rsi": round(w_rsi / total, 4),
        "news": round(w_news / total, 4),
    }


def main() -> None:
    st.set_page_config(page_title="StockSense", page_icon="📈")
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
                result = pipeline.analyze(
                    ticker, weights, scrape_news=scrape_news, persist=persist
                )
            except Exception as exc:  # surface fetch/other errors in the UI
                st.error(f"Analysis failed: {exc}")
                return

        _render_result(result)

    _render_history(ticker)


def _render_result(result: dict) -> None:
    st.metric("Final score", result["final_score"], result["signal"])
    st.write(f"**Action:** {result['action']}")

    sub = result["sub_scores"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Price", sub["score_price"])
    c2.metric("RSI", "—" if sub["score_rsi"] is None else sub["score_rsi"])
    c3.metric("News", sub["score_news"])

    st.write(f"Sentiment: **{result['sentiment_label']}**")
    if result["flags"]:
        st.warning("Flags: " + ", ".join(result["flags"]))

    with st.expander("Technicals + raw JSON"):
        st.json(result)


def _render_history(ticker: str) -> None:
    history = storage.fetch_history(ticker)
    if not history:
        return
    st.subheader(f"History — {ticker}")
    df = pd.DataFrame(history)
    st.line_chart(df.set_index("run_at")["final_score"])
    st.dataframe(df[["run_at", "final_score", "signal", "sentiment_label"]])


if __name__ == "__main__":
    main()
