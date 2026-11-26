
"""Audit logging for security-relevant application events."""

import json
from datetime import datetime, timezone

from db.database import get_connection

CREATE_AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL
)
"""

# Allowed event names.
AUDIT_ACTIONS = {
    "login_success",
    "login_failed",
    "logout",
    "question",
    "prompt_rejected",
    "upload_success",
    "upload_failed",
}


def log_event(user, action, detail="", db_path=None):
    """Store an audit event in the SQLite database.

    Args:
        user: A user dictionary, username string, or None.
        action: Event type.
        detail: Event result or non-sensitive metadata.
        db_path: Optional database path for tests.

    Returns:
        ID of the created audit record.
    """
    if action not in AUDIT_ACTIONS:
        raise ValueError(f"Geçersiz audit işlemi: {action}")

    if isinstance(user, dict):
        username = user.get("username") or "anonymous"
    elif isinstance(user, str):
        username = user or "anonymous"
    else:
        username = "anonymous"

    if isinstance(detail, dict):
        detail_text = json.dumps(
            detail,
            ensure_ascii=False,
            sort_keys=True,
        )
    else:
        detail_text = str(detail)

    timestamp = datetime.now(timezone.utc).isoformat()

    conn = get_connection(db_path)
    try:
        conn.execute(CREATE_AUDIT_TABLE)

        cursor = conn.execute(
            """
            INSERT INTO audit_log (
                timestamp,
                username,
                action,
                detail
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                timestamp,
                username,
                action,
                detail_text,
            ),
        )

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_audit_logs(limit=100, db_path=None):
    """Read recent audit records, primarily for tests and inspection."""
    if not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Limit 1 ile 1000 arasında olmalı.")

    conn = get_connection(db_path)
    try:
        conn.execute(CREATE_AUDIT_TABLE)
        conn.commit()

        rows = conn.execute(
            """
            SELECT id, timestamp, username, action, detail
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "username": row[2],
                "action": row[3],
                "detail": row[4],
            }
            for row in rows
        ]
    finally:
        conn.close()
