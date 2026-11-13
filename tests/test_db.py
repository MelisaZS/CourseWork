import sqlite3

import pytest

import config
from db.database import get_connection, init_db, run_query
from db.seed import seed_database

EXPECTED_TABLES = {"customers", "products", "suppliers", "orders", "users"}


@pytest.fixture(scope="module")
def seeded_db(tmp_path_factory):
    """A temporary database filled once by seed.py and shared by the tests below."""
    path = tmp_path_factory.mktemp("db") / "company.db"
    seed_database(path)
    return path


def test_init_db_creates_all_tables(tmp_path):
    path = tmp_path / "empty.db"
    init_db(path)
    result = run_query("SELECT name FROM sqlite_master WHERE type = 'table'", db_path=path)
    tables = {row[0] for row in result["rows"]}
    assert EXPECTED_TABLES <= tables


def test_seed_record_counts(seeded_db):
    counts = {
        table: run_query(f"SELECT COUNT(*) FROM {table}", db_path=seeded_db)["rows"][0][0]
        for table in ("customers", "products", "suppliers", "orders")
    }
    assert counts == {"customers": 200, "products": 50, "suppliers": 20, "orders": 400}


def test_seed_twice_does_not_duplicate(tmp_path):
    path = tmp_path / "twice.db"
    seed_database(path)
    counts = seed_database(path)
    assert counts["customers"] == 200
    assert counts["orders"] == 400


def test_seed_is_reproducible(tmp_path):
    first, second = tmp_path / "a.db", tmp_path / "b.db"
    seed_database(first)
    seed_database(second)
    sql = "SELECT * FROM customers ORDER BY id LIMIT 5"
    assert run_query(sql, db_path=first) == run_query(sql, db_path=second)


def test_customers_have_personal_fields(seeded_db):
    result = run_query("SELECT email, phone, tc_no, iban FROM customers", db_path=seeded_db)
    for email, phone, tc_no, iban in result["rows"]:
        assert "@" in email
        assert phone.startswith("05") and len(phone.replace(" ", "")) == 11
        assert len(tc_no) == 11 and tc_no.isdigit() and tc_no[0] != "0"
        assert iban.startswith("TR") and len(iban) == 26


def test_orders_point_to_existing_rows(seeded_db):
    sql = """
        SELECT COUNT(*) FROM orders o
        LEFT JOIN customers c ON c.id = o.customer_id
        LEFT JOIN products p ON p.id = o.product_id
        WHERE c.id IS NULL OR p.id IS NULL
    """
    assert run_query(sql, db_path=seeded_db)["rows"][0][0] == 0


def test_order_totals_are_correct(seeded_db):
    sql = "SELECT COUNT(*) FROM orders WHERE ABS(total_price - quantity * unit_price) > 0.01"
    assert run_query(sql, db_path=seeded_db)["rows"][0][0] == 0


def test_run_query_format(seeded_db):
    result = run_query("SELECT id, name, price FROM products ORDER BY id LIMIT 3", db_path=seeded_db)
    assert set(result) == {"columns", "rows"}
    assert result["columns"] == ["id", "name", "price"]
    assert len(result["rows"]) == 3
    assert all(isinstance(row, list) and len(row) == 3 for row in result["rows"])


def test_run_query_with_params(seeded_db):
    result = run_query("SELECT COUNT(*) FROM products WHERE category = ?", ("Kırtasiye",), db_path=seeded_db)
    assert result["rows"][0][0] == 10


def test_run_query_uses_config_db_path(seeded_db, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", seeded_db)
    result = run_query("SELECT COUNT(*) FROM suppliers")
    assert result["rows"][0][0] == 20


def test_invalid_sql_raises_sqlite_error(seeded_db):
    with pytest.raises(sqlite3.Error):
        run_query("SELECT * FROM no_such_table", db_path=seeded_db)


def test_foreign_keys_are_enforced(seeded_db):
    conn = get_connection(seeded_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO orders (customer_id, product_id, quantity, unit_price, total_price, status, order_date)"
                " VALUES (9999, 1, 1, 10, 10, 'pending', '2026-01-01')"
            )
    finally:
        conn.close()
