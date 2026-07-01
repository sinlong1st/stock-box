"""Streamlit dashboard — weight sliders, score display, history charts.

Run: ``uv run streamlit run dashboard.py``. Consumes ``stocksense.pipeline``.
STATUS: stub. Build order step 8 (TECH_STACK.md).
"""

from __future__ import annotations

import streamlit as st

from stocksense import pipeline


def main() -> None:
    st.title("StockSense")
    ticker = st.text_input("Ticker", "AAPL")

    # Weight sliders auto-normalize to sum 1.0 (TECH_STACK.md §06).
    w_price = st.slider("Price weight", 0.0, 1.0, 0.30, 0.05)
    w_rsi = st.slider("RSI weight", 0.0, 1.0, 0.20, 0.05)
    w_news = st.slider("News weight", 0.0, 1.0, 0.50, 0.05)
    total = w_price + w_rsi + w_news or 1.0
    weights = {
        "price": round(w_price / total, 4),
        "rsi": round(w_rsi / total, 4),
        "news": round(w_news / total, 4),
    }

    if st.button("Analyze"):
        result = pipeline.analyze(ticker, weights)
        st.metric("Final score", result["final_score"], result["signal"])
        st.json(result)


if __name__ == "__main__":
    main()
