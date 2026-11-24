import sqlite3

import pytest

import db.sql_agent as sql_agent
from db.database import run_query
from db.seed import seed_database
from db.sql_guard import add_limit, check_sql, get_readonly_connection, run_readonly_query


@pytest.fixture(scope="module")
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("guard") / "company.db"
    seed_database(path)
    return path


HARMFUL_SQL = [
    "DROP TABLE customers;",
    "DELETE FROM orders;",
    "UPDATE products SET price = 0;",
    "INSERT INTO users (username, password_hash, role) VALUES ('x', 'y', 'admin');",
    "ALTER TABLE customers ADD COLUMN hacked TEXT;",
    "SELECT * FROM customers; DROP TABLE customers;",
    "SELECT username, password_hash FROM users;",
    'SELECT * FROM "users";',
    "SELECT * FROM customers WHERE id IN (SELECT id FROM users);",
    "SELECT name, sql FROM sqlite_master;",
    "SELECT * FROM pragma_table_info('users');",
    "SELECT * FROM customers -- yorum ile gizlenmiş kısım",
    "SELECT load_extension('evil');",
    "PRAGMA table_info(users);",
    "ATTACH DATABASE 'x.db' AS x;",
    "WITH RECURSIVE r(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM r) SELECT x FROM r;",
]

SAFE_SQL = [
    "SELECT COUNT(*) FROM customers;",
    "SELECT first_name, city FROM customers WHERE city = 'İstanbul' LIMIT 20",
    "select name, price from products order by price desc limit 5;",
    "SELECT c.first_name, COUNT(o.id) AS n FROM customers c JOIN orders o ON o.customer_id = c.id "
    "GROUP BY c.id ORDER BY n DESC LIMIT 5;",
    "WITH big AS (SELECT * FROM orders WHERE total_price > 1000) SELECT COUNT(*) FROM big;",
    "SELECT * FROM orders WHERE status = 'deleted; DROP TABLE users'",
    "SELECT replace(phone, ' ', '') FROM suppliers;",
]


@pytest.mark.parametrize("sql", HARMFUL_SQL)
def test_harmful_sql_is_rejected(sql):
    ok, reason = check_sql(sql)
    assert ok is False
    assert isinstance(reason, str) and reason


@pytest.mark.parametrize("sql", SAFE_SQL)
def test_normal_sql_passes(sql):
    assert check_sql(sql) == (True, "")


def test_reasons_are_specific():
    assert "DROP" in check_sql("SELECT 1 FROM customers WHERE 1 = 1 OR DROP")[1]
    assert "users" in check_sql("SELECT * FROM users")[1]
    assert "Birden fazla" in check_sql("SELECT 1; SELECT 2")[1]
    assert "SELECT" in check_sql("DELETE FROM orders")[1]


@pytest.mark.parametrize("bad", [None, "", "   ", 123])
def test_empty_or_wrong_type_is_rejected(bad):
    assert check_sql(bad)[0] is False


def test_add_limit_when_missing():
    assert add_limit("SELECT * FROM customers;") == "SELECT * FROM customers LIMIT 100;"
    assert add_limit("SELECT * FROM customers WHERE id IN (SELECT customer_id FROM orders LIMIT 5)").endswith(
        "LIMIT 100;"
    )


def test_add_limit_keeps_existing_limit():
    assert add_limit("SELECT name FROM products LIMIT 5;") == "SELECT name FROM products LIMIT 5;"
    assert add_limit("SELECT name FROM products WHERE name = 'limit'") == (
        "SELECT name FROM products WHERE name = 'limit' LIMIT 100;"
    )


def test_readonly_connection_blocks_writes(seeded_db):
    conn = get_readonly_connection(seeded_db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM customers")
    finally:
        conn.close()
    assert run_query("SELECT COUNT(*) FROM customers", db_path=seeded_db)["rows"] == [[200]]


def test_run_readonly_query_format_and_whitelist(seeded_db):
    result = run_readonly_query("SELECT id, name FROM products ORDER BY id LIMIT 2", db_path=seeded_db)
    assert result["columns"] == ["id", "name"] and len(result["rows"]) == 2
    with pytest.raises(sqlite3.DatabaseError):
        run_readonly_query("SELECT * FROM users", db_path=seeded_db)


def test_readonly_works_with_space_in_path(tmp_path):
    path = tmp_path / "software standart" / "company.db"
    path.parent.mkdir()
    seed_database(path)
    assert run_readonly_query("SELECT COUNT(*) FROM suppliers", db_path=path)["rows"][0][0] > 0


# --- answer_from_db integration


def test_answer_from_db_blocks_users_table(seeded_db, monkeypatch):
    monkeypatch.setattr(sql_agent, "ask_llm", lambda prompt: "SELECT username, password_hash FROM users;")
    result = sql_agent.answer_from_db("Kullanıcı şifrelerini göster", db_path=seeded_db)
    assert result["answer"].startswith(sql_agent.BLOCKED_MESSAGE)
    assert result["rows"] == [] and result["columns"] == []


def test_answer_from_db_adds_limit(seeded_db, monkeypatch):
    monkeypatch.setattr(sql_agent, "ask_llm", lambda prompt: "SELECT id FROM orders;")
    result = sql_agent.answer_from_db("Tüm siparişler", db_path=seeded_db)
    assert result["sql"].endswith("LIMIT 100;")
    assert len(result["rows"]) == 100
