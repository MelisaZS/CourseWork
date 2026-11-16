import pytest

import db.sql_agent as sql_agent
from agent.llm import OLLAMA_ERROR
from db.seed import seed_database
from db.sql_agent import answer_from_db, build_sql_prompt, extract_sql, get_schema_text


@pytest.fixture(scope="module")
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("sql") / "company.db"
    seed_database(path)
    return path


def fake_llm(output):
    """Replace the LLM with a function that always returns the given text."""
    return lambda prompt: output


# --- extract_sql

def test_extract_sql_from_code_block():
    text = "İşte sorgu:\n```sql\nSELECT COUNT(*) FROM customers;\n```\nBu sorgu müşterileri sayar."
    assert extract_sql(text) == "SELECT COUNT(*) FROM customers;"


def test_extract_sql_with_label_and_extra_text():
    assert extract_sql("SQL: SELECT name FROM products LIMIT 5; -- en pahalılar") == \
        "SELECT name FROM products LIMIT 5;"


def test_extract_sql_keeps_only_first_statement():
    assert extract_sql("SELECT 1; DROP TABLE customers;") == "SELECT 1;"


def test_extract_sql_returns_empty_when_no_query():
    assert extract_sql("Bu soruyu cevaplayamıyorum.") == ""


# --- schema and prompt

def test_schema_hides_users_table(seeded_db):
    schema = get_schema_text(seeded_db)
    assert "customers(" in schema and "orders(" in schema
    assert "users" not in schema
    assert "password_hash" not in schema


def test_prompt_contains_schema_examples_and_question(seeded_db):
    prompt = build_sql_prompt("Kaç ürün var?", get_schema_text(seeded_db))
    assert "products(" in prompt
    assert "En çok sipariş veren 5 müşteri kim?" in prompt
    assert prompt.rstrip().endswith("Soru: Kaç ürün var?\nSQL:")


# --- answer_from_db

def test_answer_single_value(seeded_db, monkeypatch):
    monkeypatch.setattr(sql_agent, "ask_llm", fake_llm("SELECT COUNT(*) AS n FROM customers;"))
    result = answer_from_db("Kaç müşterimiz var?", db_path=seeded_db)
    assert set(result) == {"answer", "sql", "columns", "rows"}
    assert result["rows"] == [[200]]
    assert result["answer"] == "Sonuç: 200"


def test_answer_top_customers(seeded_db, monkeypatch):
    sql = sql_agent.FEW_SHOT_EXAMPLES[3][1]
    monkeypatch.setattr(sql_agent, "ask_llm", fake_llm(f"```sql\n{sql}\n```"))
    result = answer_from_db("En çok sipariş veren 5 müşteri kim?", db_path=seeded_db)
    assert result["columns"] == ["first_name", "last_name", "order_count"]
    assert len(result["rows"]) == 5
    counts = [row[2] for row in result["rows"]]
    assert counts == sorted(counts, reverse=True)


def test_invalid_sql_does_not_crash(seeded_db, monkeypatch):
    monkeypatch.setattr(sql_agent, "ask_llm", fake_llm("SELECT * FROM olmayan_tablo;"))
    result = answer_from_db("Bir şey sor", db_path=seeded_db)
    assert result["answer"].startswith("Sorgu çalıştırılamadı")
    assert result["rows"] == []


def test_non_select_is_rejected(seeded_db, monkeypatch):
    monkeypatch.setattr(sql_agent, "ask_llm", fake_llm("DELETE FROM customers;"))
    result = answer_from_db("Müşterileri sil", db_path=seeded_db)
    assert result["answer"] in (sql_agent.NO_SQL_MESSAGE, sql_agent.NOT_SELECT_MESSAGE)
    count = sql_agent.run_query("SELECT COUNT(*) FROM customers", db_path=seeded_db)["rows"][0][0]
    assert count == 200


def test_ollama_error_is_passed_through(seeded_db, monkeypatch):
    monkeypatch.setattr(sql_agent, "ask_llm", fake_llm(OLLAMA_ERROR))
    result = answer_from_db("Kaç müşterimiz var?", db_path=seeded_db)
    assert result["answer"] == OLLAMA_ERROR
    assert result["sql"] == ""


def test_missing_database(tmp_path):
    result = answer_from_db("Kaç müşterimiz var?", db_path=tmp_path / "yok.db")
    assert result["answer"] == sql_agent.NO_DB_MESSAGE
