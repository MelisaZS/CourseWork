"""Text-to-SQL: answers natural language questions from the company database.

Flow: question -> prompt (schema + examples) -> LLM -> SQL -> check_sql -> read-only query -> answer.

Result format (shared by the whole project):
    {"answer": str, "sql": str, "columns": [str], "rows": [[value, ...], ...]}

Try it from the terminal:
    python -m db.sql_agent "En çok sipariş veren 5 müşteri kim?"
"""

import re
import sqlite3
import sys
from pathlib import Path

import config
from agent.llm import OLLAMA_ERROR, ask_llm
from db.database import get_connection
from db.sql_guard import ALLOWED_TABLES, add_limit, check_sql, run_readonly_query

FEW_SHOT_EXAMPLES = [
    ("Kaç müşterimiz var?",
     "SELECT COUNT(*) AS customer_count FROM customers;"),
    ("İstanbul'daki müşterileri listele",
     "SELECT first_name, last_name, city FROM customers WHERE city = 'İstanbul' LIMIT 20;"),
    ("En pahalı 5 ürün hangisi?",
     "SELECT name, category, price FROM products ORDER BY price DESC LIMIT 5;"),
    ("En çok sipariş veren 5 müşteri kim?",
     "SELECT c.first_name, c.last_name, COUNT(o.id) AS order_count FROM customers c "
     "JOIN orders o ON o.customer_id = c.id GROUP BY c.id ORDER BY order_count DESC LIMIT 5;"),
    ("Kategorilere göre toplam satış tutarı nedir?",
     "SELECT p.category, ROUND(SUM(o.total_price), 2) AS total_sales FROM orders o "
     "JOIN products p ON p.id = o.product_id WHERE o.status != 'cancelled' "
     "GROUP BY p.category ORDER BY total_sales DESC;"),
]

NO_DB_MESSAGE = "Veritabanı bulunamadı. Önce 'python db/seed.py' komutunu çalıştırın."
NOT_SELECT_MESSAGE = "Sadece veri okuyan (SELECT) sorgular çalıştırılabilir."
BLOCKED_MESSAGE = "Sorgu güvenlik kontrolünden geçmedi:"
NO_SQL_MESSAGE = "Bu soru için bir SQL sorgusu üretilemedi. Soruyu farklı şekilde sormayı deneyin."


def get_schema_text(db_path=None):
    """Return the allowed tables and their columns as plain text for the prompt."""
    conn = get_connection(db_path)
    try:
        lines = []
        for table in ALLOWED_TABLES:
            columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
            if columns:
                cols = ", ".join(f"{c[1]} {c[2]}" for c in columns)
                lines.append(f"{table}({cols})")
        return "\n".join(lines)
    finally:
        conn.close()


def build_sql_prompt(question, schema_text):
    examples = "\n\n".join(f"Soru: {q}\nSQL: {sql}" for q, sql in FEW_SHOT_EXAMPLES)
    return (
        "Sen bir SQLite uzmanısın. Aşağıdaki veritabanı şemasına göre soruyu cevaplayan "
        "TEK bir SQLite SELECT sorgusu yaz.\n"
        "Kurallar:\n"
        "- Sadece SELECT kullan, veriyi değiştiren komut yazma.\n"
        "- Sadece şemadaki tablo ve kolonları kullan.\n"
        "- Liste döndüren sorgularda LIMIT kullan (en fazla 50).\n"
        "- order status değerleri: pending, shipped, delivered, cancelled.\n"
        "- Tarihler YYYY-MM-DD formatında metin olarak tutulur.\n"
        "- Açıklama yazma, sadece SQL döndür.\n\n"
        f"Şema:\n{schema_text}\n\n"
        f"Örnekler:\n{examples}\n\n"
        f"Soru: {question}\nSQL:"
    )


def extract_sql(llm_output):
    """Pull a single SQL statement out of the LLM answer.

    Handles ```sql code blocks, a leading "SQL:" label and extra text after the query.
    Returns "" when no SELECT/WITH statement is found.
    """
    text = llm_output.strip()
    block = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if block:
        text = block.group(1).strip()
    start = re.search(r"\b(SELECT|WITH)\b", text, flags=re.IGNORECASE)
    if not start:
        return ""
    text = text[start.start():]
    sql = text.split(";")[0].strip()
    return sql + ";" if sql else ""


def is_select(sql):
    return bool(re.match(r"^\s*(SELECT|WITH)\b", sql, flags=re.IGNORECASE))


def format_answer(columns, rows):
    """Short Turkish summary of the query result."""
    if not rows:
        return "Sorgu çalıştı ama sonuç bulunamadı."
    if len(rows) == 1 and len(columns) == 1:
        return f"Sonuç: {rows[0][0]}"
    return f"{len(rows)} kayıt bulundu."


def _result(answer, sql="", columns=None, rows=None):
    return {"answer": answer, "sql": sql, "columns": columns or [], "rows": rows or []}


def answer_from_db(question, db_path=None):
    """Answer a question from the company database. Never raises."""
    if not Path(db_path or config.DB_PATH).exists():
        return _result(NO_DB_MESSAGE)

    prompt = build_sql_prompt(question, get_schema_text(db_path))
    llm_output = ask_llm(prompt)
    if llm_output == OLLAMA_ERROR:
        return _result(OLLAMA_ERROR)

    sql = extract_sql(llm_output)
    if not sql:
        return _result(NO_SQL_MESSAGE)
    if not is_select(sql):
        return _result(NOT_SELECT_MESSAGE, sql=sql)

    safe, reason = check_sql(sql)
    if not safe:
        return _result(f"{BLOCKED_MESSAGE} {reason}", sql=sql)
    sql = add_limit(sql)

    try:
        result = run_readonly_query(sql, db_path=db_path)
    except sqlite3.Error as error:
        return _result(f"Sorgu çalıştırılamadı: {error}", sql=sql)

    return _result(format_answer(result["columns"], result["rows"]), sql, result["columns"], result["rows"])


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Kaç müşterimiz var?"
    output = answer_from_db(question)
    print("SQL:", output["sql"])
    print(output["answer"])
    for row in output["rows"][:10]:
        print(row)
