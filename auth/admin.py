"""Data for the admin security panel (/admin).

Reads the audit_log table written by auth.audit.log_event and the users table.
Audit timestamps are stored in UTC; the panel shows them in the computer's
local time (Turkey time on the team's machines).

Nothing returned here is secret: no password hashes, and no question texts
(the audit log never stores them).
"""

import json
from datetime import date, datetime, time, timedelta, timezone

from auth.audit import CREATE_AUDIT_TABLE
from auth.users import ROLES, list_users
from db.database import get_connection

RECENT_LIMIT = 50  # last 50 audit records / rejected requests
DAILY_DAYS = 7  # daily question counts for the last 7 days

ACTION_LABELS = {
    "login_success": "Giriş",
    "login_failed": "Hatalı giriş",
    "logout": "Çıkış",
    "question": "Soru",
    "prompt_rejected": "Engellenen soru",
    "upload_success": "PDF yükleme",
    "upload_failed": "Başarısız yükleme",
}
RESULT_LABELS = {"success": "Başarılı", "denied": "Reddedildi", "error": "Hata"}
REASON_LABELS = {
    "prompt_injection": "Prompt injection şüphesi",
    "no_file_selected": "Dosya seçilmedi",
    "invalid_file_type": "PDF olmayan dosya",
    "index_failed": "PDF index'i güncellenemedi",
}
ROUTE_LABELS = {"db": "Veritabanı", "doc": "Doküman", "web": "Web"}
QUESTION_ACTIONS = ("question", "prompt_rejected")

MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
WEEKDAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

# Fixed SQL texts (values always go in as ? parameters)
RECENT_EVENTS_SQL = "SELECT id, timestamp, username, action, detail FROM audit_log ORDER BY id DESC LIMIT ?"
# LIKE narrows the rows in SQL; parse_detail then checks that the result really is "denied"
DENIED_EVENTS_SQL = (
    "SELECT id, timestamp, username, action, detail FROM audit_log "
    "WHERE detail LIKE '%denied%' AND timestamp >= ? ORDER BY id DESC"
)
QUESTION_EVENTS_SQL = "SELECT timestamp, action, detail FROM audit_log WHERE action IN (?, ?) AND timestamp >= ?"
LAST_LOGIN_SQL = "SELECT username, MAX(timestamp) FROM audit_log WHERE action = 'login_success' GROUP BY username"
AUDIT_COUNT_SQL = "SELECT COUNT(*) FROM audit_log"


def _query(sql, params=(), db_path=None):
    """Run a read query on the audit/users database. The audit table is created if missing,
    so the panel also works before the first event is logged."""
    conn = get_connection(db_path)
    try:
        conn.execute(CREATE_AUDIT_TABLE)
        conn.commit()
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def parse_detail(text):
    """Audit details are JSON like {"result": "denied", "reason": ...}; plain text is kept as {"text": ...}."""
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return {"text": text or ""}
    return value if isinstance(value, dict) else {"text": str(value)}


def to_local(timestamp, tz=None):
    """UTC ISO timestamp -> datetime in the given time zone (default: this computer's). None if unreadable."""
    try:
        moment = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz)


def detail_summary(action, detail):
    """Short Turkish explanation for the "Ayrıntı" column."""
    parts = []
    if detail.get("route"):
        parts.append(f"Kaynak: {ROUTE_LABELS.get(detail['route'], detail['route'])}")
    if action == "question" and detail.get("result") == "denied":
        parts.append("Rolün bu kaynağa yetkisi yok")
    if detail.get("reason"):
        parts.append(REASON_LABELS.get(detail["reason"], detail["reason"]))
    if detail.get("file_count"):
        parts.append(f"{detail['file_count']} dosya")
    if detail.get("text"):
        parts.append(detail["text"])
    return " · ".join(str(p) for p in parts)


def describe(row, tz=None):
    """Turn an audit_log row into what the panel shows."""
    record_id, timestamp, username, action, detail_text = row
    detail = parse_detail(detail_text)
    result = detail.get("result", "")
    moment = to_local(timestamp, tz)
    return {
        "id": record_id,
        "time": moment.strftime("%d.%m.%Y %H:%M:%S") if moment else str(timestamp),
        "username": username,
        "action": action,
        "action_label": ACTION_LABELS.get(action, action),
        "result": result,
        "result_label": RESULT_LABELS.get(result, result or "-"),
        "info": detail_summary(action, detail),
    }


def recent_events(limit=RECENT_LIMIT, db_path=None, tz=None):
    """The newest audit records, newest first."""
    rows = _query(RECENT_EVENTS_SQL, (limit,), db_path)
    return [describe(row, tz) for row in rows]


def _denied_rows(db_path=None, since=None):
    # "" is smaller than every timestamp, so since=None means "all time"
    since_text = since.astimezone(timezone.utc).isoformat() if since else ""
    rows = _query(DENIED_EVENTS_SQL, (since_text,), db_path)
    return [row for row in rows if parse_detail(row[4]).get("result") == "denied"]


def denied_requests(limit=RECENT_LIMIT, db_path=None, tz=None):
    """Requests the security layer turned down: wrong passwords, prompt injection,
    questions outside the user's role, rejected uploads. Newest first."""
    return [describe(row, tz) for row in _denied_rows(db_path)[:limit]]


def daily_question_counts(days=DAILY_DAYS, db_path=None, tz=None, now=None):
    """Questions asked per day for the last `days` days, newest first; days without questions are included.

    Counts "question" and "prompt_rejected" events. "denied" is how many of them were refused
    (prompt injection or a source the role may not use). "percent" is the bar length.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    first_day = now.date() - timedelta(days=days - 1)
    start = datetime.combine(first_day, time.min, tzinfo=now.tzinfo)
    # one extra day of margin in SQL; the exact local day is decided below
    since = (start - timedelta(days=1)).astimezone(timezone.utc).isoformat()
    rows = _query(QUESTION_EVENTS_SQL, (*QUESTION_ACTIONS, since), db_path)

    counts = {first_day + timedelta(days=i): {"total": 0, "denied": 0} for i in range(days)}
    for timestamp, action, detail in rows:
        moment = to_local(timestamp, tz)
        day = counts.get(moment.date()) if moment else None
        if day is None:
            continue
        day["total"] += 1
        if action == "prompt_rejected" or parse_detail(detail).get("result") == "denied":
            day["denied"] += 1

    peak = max(c["total"] for c in counts.values()) or 1
    return [
        {
            "date": day.isoformat(),
            "label": f"{day.day} {MONTHS[day.month - 1]} {WEEKDAYS[day.weekday()]}",
            "total": c["total"],
            "denied": c["denied"],
            "percent": round(100 * c["total"] / peak),
        }
        for day, c in sorted(counts.items(), reverse=True)
    ]


def users_with_last_login(db_path=None, tz=None):
    """All users with their role and last successful login (no password hashes)."""
    rows = _query(LAST_LOGIN_SQL, db_path=db_path)
    last_login = {username: to_local(ts, tz) for username, ts in rows}
    users = []
    for user in list_users(db_path):
        moment = last_login.get(user["username"])
        users.append({
            **user,
            "created": _format_date(user["created_at"]),
            "last_login": moment.strftime("%d.%m.%Y %H:%M") if moment else "-",
        })
    return users


def _format_date(value):
    """'2026-11-27' -> '27.11.2026' (left as it is if it is not a plain date)."""
    try:
        return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except ValueError:
        return value or "-"


def admin_dashboard(db_path=None, tz=None, now=None):
    """Everything templates/admin.html needs, in one dict."""
    now = now or datetime.now(timezone.utc)
    users = users_with_last_login(db_path, tz)
    daily = daily_question_counts(db_path=db_path, tz=tz, now=now)
    audit_total = _query(AUDIT_COUNT_SQL, db_path=db_path)[0][0]
    return {
        "events": recent_events(db_path=db_path, tz=tz),
        "denied": denied_requests(db_path=db_path, tz=tz),
        "users": users,
        "daily": daily,
        "stats": {
            "questions_today": daily[0]["total"],
            "denied_24h": len(_denied_rows(db_path, since=now - timedelta(hours=24))),
            "user_count": len(users),
            "role_counts": {role: sum(u["role"] == role for u in users) for role in ROLES},
            "audit_total": audit_total,
        },
        "recent_limit": RECENT_LIMIT,
        "daily_days": DAILY_DAYS,
    }
