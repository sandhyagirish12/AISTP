import os
import sqlite3
from datetime import datetime
from typing import Dict, List

DB_PATH = os.path.join(os.path.dirname(__file__), "safety_history.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scored_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    toxicity REAL NOT NULL,
    bias REAL NOT NULL,
    disallowed REAL NOT NULL,
    overall_score REAL NOT NULL,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    conn.close()


def save_result(record: Dict) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scored_outputs (text, toxicity, bias, disallowed, overall_score, label, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            record["text"],
            record["toxicity"],
            record["bias"],
            record["disallowed"],
            record["overall_score"],
            record["label"],
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 50) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, text, toxicity, bias, disallowed, overall_score, label, created_at FROM scored_outputs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
