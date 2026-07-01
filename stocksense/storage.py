"""Persistence — SQLite run history + per-run JSON output files.

SQLite schema and file naming: TECH_STACK.md §04. JSON output shape:
schema.json > output.

STATUS: stub. Build order step 6 (TECH_STACK.md).
"""

from __future__ import annotations

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


def init_db(db_path: Path = DB_PATH) -> None:
    """Create the runs table if it does not exist."""
    raise NotImplementedError("storage.init_db is not implemented yet")


def save_run(result: dict, db_path: Path = DB_PATH) -> None:
    """Insert a completed run result into SQLite (see CREATE_RUNS_TABLE)."""
    raise NotImplementedError("storage.save_run is not implemented yet")


def write_output_json(result: dict, outputs_dir: Path = OUTPUTS_DIR) -> Path:
    """Write the full result dict to ``outputs/{ticker}_{YYYYMMDD_HHMMSS}.json``."""
    raise NotImplementedError("storage.write_output_json is not implemented yet")
