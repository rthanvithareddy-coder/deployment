import sqlite3
import json
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "netmotion.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                user_count INTEGER NOT NULL,
                tower_count INTEGER NOT NULL,
                scenario TEXT NOT NULL,
                conventional_results TEXT NOT NULL,
                mobility_results TEXT NOT NULL
            )
        """)


def save_experiment(record: dict) -> int:
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO experiments
            (name, created_at, duration_seconds, user_count, tower_count, scenario,
             conventional_results, mobility_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["name"], record["created_at"], record["duration_seconds"],
            record["user_count"], record["tower_count"], record["scenario"],
            json.dumps(record["conventional_results"]),
            json.dumps(record["mobility_results"]),
        ))
        return cursor.lastrowid


def list_experiments() -> list:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY id DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["conventional_results"] = json.loads(item["conventional_results"])
        item["mobility_results"] = json.loads(item["mobility_results"])
        result.append(item)
    return result
