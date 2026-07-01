"""Persistence — SQLite run history + per-run JSON output files.

SQLite schema and file naming: TECH_STACK.md §04. JSON output shape:
schema.json > output.

Build order step 6 (TECH_STACK.md).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("stocksense.sqlite")
OUTPUTS_DIR = Path("outputs")

CREATE_RUNS_TABLE = """
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
"""

_INSERT_RUN = """
INSERT INTO runs (
    ticker, run_at, weights_price, weights_rsi, weights_news,
    score_price, score_rsi, score_news, final_score,
    sentiment_label, signal, flags
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    """Create the runs table if it does not exist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_RUNS_TABLE)


def save_run(result: dict, db_path: Path = DB_PATH) -> int:
    """Insert a completed run result into SQLite. Returns the new row id.

    ``result`` is the dict produced by ``pipeline.analyze`` (schema.json > output).
    Idempotently ensures the table exists first. ``flags`` is stored as a JSON
    string. ``score_rsi`` may be ``None`` (RSI skipped) and is stored as NULL.
    """
    weights = result["weights_used"]
    sub = result["sub_scores"]
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_RUNS_TABLE)
        cursor = conn.execute(
            _INSERT_RUN,
            (
                result["ticker"],
                result["timestamp"],
                weights["price"],
                weights["rsi"],
                weights["news"],
                sub["score_price"],
                sub["score_rsi"],
                sub["score_news"],
                result["final_score"],
                result["sentiment_label"],
                result["signal"],
                json.dumps(result["flags"]),
            ),
        )
        return int(cursor.lastrowid)


def fetch_history(ticker: str, db_path: Path = DB_PATH) -> list[dict]:
    """Return all runs for ``ticker``, most recent first (for the dashboard)."""
    if not Path(db_path).exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM runs WHERE ticker = ? ORDER BY run_at DESC",
            (ticker,),
        ).fetchall()
    return [dict(row) for row in rows]


def write_output_json(result: dict, outputs_dir: Path = OUTPUTS_DIR) -> Path:
    """Write the full result dict to ``outputs/{ticker}_{YYYYMMDD_HHMMSS}.json``.

    Returns the path written. The timestamp is derived from the run's own
    ``timestamp`` (falling back to now) so the filename matches the record.
    """
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    stamp = _filename_stamp(result.get("timestamp"))
    path = outputs_dir / f"{result['ticker']}_{stamp}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path


def _filename_stamp(iso_timestamp: str | None) -> str:
    """Turn an ISO timestamp into a ``YYYYMMDD_HHMMSS`` filename stamp."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
    except (TypeError, ValueError):
        dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")
