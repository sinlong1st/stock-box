import json

from stocksense import storage


def _sample_result(ticker="AAPL", score=46.77, rsi_score=52.32):
    return {
        "ticker": ticker,
        "timestamp": "2026-06-30T12:34:56+00:00",
        "weights_used": {"price": 0.3, "rsi": 0.2, "news": 0.5},
        "technicals": {"current_price": 289.36, "rsi": 49.0},
        "sentiment_label": "neutral",
        "sub_scores": {"score_price": 37.68, "score_rsi": rsi_score, "score_news": 50.0},
        "final_score": score,
        "signal": "Neutral",
        "action": "No clear edge, wait",
        "flags": ["no_news_found"],
    }


def test_save_run_and_fetch_history(tmp_path):
    db = tmp_path / "test.sqlite"
    storage.save_run(_sample_result(score=40.0), db_path=db)
    storage.save_run(_sample_result(score=60.0), db_path=db)

    history = storage.fetch_history("AAPL", db_path=db)
    assert len(history) == 2
    assert {h["final_score"] for h in history} == {40.0, 60.0}
    assert history[0]["ticker"] == "AAPL"
    assert json.loads(history[0]["flags"]) == ["no_news_found"]


def test_save_run_returns_row_id(tmp_path):
    db = tmp_path / "test.sqlite"
    first = storage.save_run(_sample_result(), db_path=db)
    second = storage.save_run(_sample_result(), db_path=db)
    assert (first, second) == (1, 2)


def test_save_run_stores_null_rsi_score(tmp_path):
    db = tmp_path / "test.sqlite"
    storage.save_run(_sample_result(rsi_score=None), db_path=db)
    history = storage.fetch_history("AAPL", db_path=db)
    assert history[0]["score_rsi"] is None


def test_fetch_history_no_db_returns_empty(tmp_path):
    assert storage.fetch_history("AAPL", db_path=tmp_path / "missing.sqlite") == []


def test_fetch_history_filters_by_ticker(tmp_path):
    db = tmp_path / "test.sqlite"
    storage.save_run(_sample_result(ticker="AAPL"), db_path=db)
    storage.save_run(_sample_result(ticker="TSLA"), db_path=db)
    assert len(storage.fetch_history("TSLA", db_path=db)) == 1


def test_write_output_json_uses_run_timestamp(tmp_path):
    result = _sample_result()
    path = storage.write_output_json(result, outputs_dir=tmp_path)
    assert path.name == "AAPL_20260630_123456.json"
    assert json.loads(path.read_text(encoding="utf-8"))["final_score"] == 46.77
