
"""Tests for SQLite audit logging."""

import json
from datetime import datetime

import pytest

from auth.audit import get_audit_logs, log_event
from db.database import get_connection


@pytest.fixture
def audit_db(tmp_path):
    """Use an isolated database for each test."""
    return tmp_path / "audit_test.db"


def test_log_event_creates_record(audit_db):
    record_id = log_event(
        "celal",
        "login_success",
        "Giris basarili",
        db_path=audit_db,
    )

    assert record_id == 1

    logs = get_audit_logs(db_path=audit_db)
    assert len(logs) == 1
    assert logs[0]["username"] == "celal"
    assert logs[0]["action"] == "login_success"
    assert logs[0]["detail"] == "Giris basarili"


def test_user_dictionary(audit_db):
    user = {"id": 1, "username": "celal", "role": "admin"}

    log_event(
        user,
        "question",
        {"route": "doc", "result": "success"},
        db_path=audit_db,
    )

    record = get_audit_logs(db_path=audit_db)[0]

    assert record["username"] == "celal"
    assert json.loads(record["detail"]) == {
        "route": "doc",
        "result": "success",
    }


def test_anonymous_user(audit_db):
    log_event(None, "login_failed", "Invalid credentials", db_path=audit_db)

    logs = get_audit_logs(db_path=audit_db)

    assert logs[0]["username"] == "anonymous"


def test_prompt_rejection(audit_db):
    log_event(
        "guest",
        "prompt_rejected",
        {"reason": "prompt_injection"},
        db_path=audit_db,
    )

    logs = get_audit_logs(db_path=audit_db)

    assert logs[0]["action"] == "prompt_rejected"
    assert "prompt_injection" in logs[0]["detail"]


def test_multiple_events_order(audit_db):
    log_event("celal", "login_success", db_path=audit_db)
    log_event("celal", "question", db_path=audit_db)
    log_event("celal", "logout", db_path=audit_db)

    logs = get_audit_logs(db_path=audit_db)

    assert [log["action"] for log in logs] == [
        "logout",
        "question",
        "login_success",
    ]


def test_utc_timestamp(audit_db):
    log_event("celal", "question", db_path=audit_db)

    timestamp = get_audit_logs(db_path=audit_db)[0]["timestamp"]
    parsed = datetime.fromisoformat(timestamp)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    "action",
    [
        "login_success",
        "login_failed",
        "logout",
        "question",
        "prompt_rejected",
        "upload_success",
        "upload_failed",
    ],
)
def test_supported_actions(audit_db, action):
    log_event("celal", action, db_path=audit_db)

    assert get_audit_logs(db_path=audit_db)[0]["action"] == action


def test_invalid_action(audit_db):
    with pytest.raises(ValueError, match="Geçersiz audit işlemi"):
        log_event("celal", "unknown_action", db_path=audit_db)


def test_invalid_limit(audit_db):
    with pytest.raises(ValueError, match="Limit"):
        get_audit_logs(limit=0, db_path=audit_db)


def test_audit_table_exists(audit_db):
    log_event("celal", "question", db_path=audit_db)

    conn = get_connection(audit_db)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'audit_log'"
        ).fetchone()

        assert row == ("audit_log",)
    finally:
        conn.close()
