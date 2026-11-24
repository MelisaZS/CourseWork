"""SQL safety guard for queries written by the LLM (Text-to-SQL).

Rules:
    - Only one read-only SELECT (or WITH ... SELECT) statement.
    - DROP/DELETE/UPDATE/INSERT/ALTER ... and several statements joined with ";" are rejected.
    - Only whitelisted tables can be read. The users table (password hashes) is never allowed.
    - A query without LIMIT gets "LIMIT 100".
    - Queries run on a read-only connection.

check_sql(sql) returns (bool, reason): (True, "") when the query is safe,
(False, "<Turkish reason>") when it is rejected.

Try it from the terminal:
    python -m db.sql_guard "SELECT * FROM users"
"""

import re
import sqlite3
import sys
from pathlib import Path

import config
from db.database import SCHEMA_PATH

# Tables the Text-to-SQL agent may read. "users" (passwords, roles) is never allowed.
ALLOWED_TABLES = ("customers", "suppliers", "products", "orders")

DEFAULT_LIMIT = 100

FORBIDDEN_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
)
FORBIDDEN_FUNCTIONS = ("load_extension",)

STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")
SQLITE_RECURSIVE = getattr(sqlite3, "SQLITE_RECURSIVE", 33)  # constant is missing in older Python


def _strip_strings(sql):
    """Replace '...' literals with '' so keywords inside text values are ignored."""
    return STRING_LITERAL.sub("''", sql)


def _authorizer(blocked):
    """SQLite calls this for every table, column and function a statement uses.

    Anything that is not a plain read from a whitelisted table is denied and the
    reason is appended to `blocked`.
    """

    def check(action, arg1, arg2, db_name, source):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            if arg1 in ALLOWED_TABLES:
                return sqlite3.SQLITE_OK
            blocked.append(f"İzin verilmeyen tablo: {arg1}")
        elif action == sqlite3.SQLITE_FUNCTION:
            if (arg2 or "").lower() not in FORBIDDEN_FUNCTIONS:
                return sqlite3.SQLITE_OK
            blocked.append(f"İzin verilmeyen fonksiyon: {arg2}")
        elif action == SQLITE_RECURSIVE:
            blocked.append("Özyinelemeli (WITH RECURSIVE) sorgulara izin verilmiyor.")
        else:
            blocked.append("Sadece veri okuyan sorgulara izin veriliyor.")
        return sqlite3.SQLITE_DENY

    return check


def _check_tables(sql):
    """Compile the query on an empty in-memory copy of the schema (nothing is run on real data)."""
    blocked = []
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.set_authorizer(_authorizer(blocked))
        conn.execute(f"EXPLAIN {sql}")
    except sqlite3.Error as error:
        return False, blocked[0] if blocked else f"Geçersiz SQL: {error}"
    finally:
        conn.close()
    return True, ""


def check_sql(sql):
    """Return (True, "") for a safe single SELECT, otherwise (False, reason). Never raises."""
    if not isinstance(sql, str) or not sql.strip():
        return False, "Boş sorgu."

    text = _strip_strings(sql).strip()
    if "--" in text or "/*" in text:
        return False, "Yorum satırı (-- veya /* */) içeren sorgulara izin verilmiyor."
    if ";" in text.rstrip(";").rstrip() or text.count(";") > 1:
        return False, "Birden fazla sorgu (;) çalıştırılamaz."
    if not re.match(r"(SELECT|WITH)\b", text, flags=re.IGNORECASE):
        return False, "Sadece SELECT sorgularına izin veriliyor."

    pattern = r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b"
    keyword = re.search(pattern, text, flags=re.IGNORECASE)
    if keyword:
        return False, f"Yasaklı komut: {keyword.group(1).upper()}"

    return _check_tables(sql.strip().rstrip(";"))


def _has_top_level_limit(text):
    """True when LIMIT appears outside parentheses (a LIMIT inside a subquery does not count)."""
    depth = 0
    for match in re.finditer(r"\(|\)|\bLIMIT\b", text, flags=re.IGNORECASE):
        token = match.group(0)
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0:
            return True
    return False


def add_limit(sql, limit=DEFAULT_LIMIT):
    """Append LIMIT to a query that has none. Call after check_sql."""
    query = sql.strip().rstrip(";").rstrip()
    if _has_top_level_limit(_strip_strings(query)):
        return query + ";"
    return f"{query} LIMIT {limit};"


def get_readonly_connection(db_path=None):
    """Open the company database in read-only mode (writes fail with an error)."""
    path = Path(db_path or config.DB_PATH).resolve()
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


def run_readonly_query(sql, db_path=None):
    """Run one query on a read-only connection and return {"columns", "rows"}.

    The table whitelist is enforced again here as a second layer.
    Invalid or blocked SQL raises sqlite3.Error; callers decide how to show the error.
    """
    blocked = []
    conn = get_readonly_connection(db_path)
    try:
        conn.set_authorizer(_authorizer(blocked))
        cursor = conn.execute(sql)
        columns = [col[0] for col in cursor.description or []]
        rows = [list(row) for row in cursor.fetchall()]
        return {"columns": columns, "rows": rows}
    finally:
        conn.close()


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "SELECT * FROM customers"
    ok, reason = check_sql(query)
    print("GÜVENLİ" if ok else "REDDEDİLDİ", "|", reason or add_limit(query))
