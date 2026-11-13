"""SQLite connection helpers for the company database.

The database file lives at config.DB_PATH. Tables are defined in db/schema.sql
and filled with sample data by db/seed.py.

Query result format (shared by the whole project):
    {"columns": [str], "rows": [[value, ...], ...]}
"""

import sqlite3
from pathlib import Path

import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(db_path=None):
    """Open a connection to the company database with foreign keys switched on.

    The path is read from config.DB_PATH at call time, so tests can point it
    to a temporary file with monkeypatch.
    """
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Create all tables from schema.sql if they do not exist yet."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def run_query(sql, params=(), db_path=None):
    """Run one SQL statement and return {"columns", "rows"}.

    Rows are lists (not tuples) so the result can be sent as JSON directly.
    Statements that return no rows (INSERT, UPDATE ...) give empty lists.
    Invalid SQL raises sqlite3.Error; callers decide how to show the error.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(sql, params)
        if cursor.description is None:
            conn.commit()
            return {"columns": [], "rows": []}
        columns = [col[0] for col in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return {"columns": columns, "rows": rows}
    finally:
        conn.close()
