
"""Integration tests for privacy and database encryption."""

from cryptography.fernet import Fernet

from auth.privacy import decrypt, encrypt, protect_response
from db.database import get_connection
from db.privacy_migration import encrypt_customer_fields
from db.seed import seed_database


def test_migration_encrypts_existing_records(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FERNET_KEY",
        Fernet.generate_key().decode(),
    )

    db_path = tmp_path / "company.db"
    seed_database(db_path)

    conn = get_connection(db_path)
    try:
        original = conn.execute(
            "SELECT phone, tc_no FROM customers WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()

    count = encrypt_customer_fields(db_path)

    assert count == 200

    conn = get_connection(db_path)
    try:
        encrypted = conn.execute(
            "SELECT phone, tc_no FROM customers WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()

    assert encrypted[0] != original[0]
    assert encrypted[1] != original[1]

    assert decrypt(encrypted[0]) == original[0]
    assert decrypt(encrypted[1]) == original[1]


def test_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FERNET_KEY",
        Fernet.generate_key().decode(),
    )

    db_path = tmp_path / "company.db"
    seed_database(db_path)

    first_count = encrypt_customer_fields(db_path)
    second_count = encrypt_customer_fields(db_path)

    assert first_count == 200
    assert second_count == 0


def test_employee_gets_masked_database_results(monkeypatch):
    monkeypatch.setenv(
        "FERNET_KEY",
        Fernet.generate_key().decode(),
    )

    encrypted_phone = encrypt("0532 123 45 67")
    encrypted_tc = encrypt("12345678901")

    response = {
        "route": "db",
        "answer": "2 kayıt bulundu.",
        "columns": ["phone", "tc_no"],
        "rows": [[encrypted_phone, encrypted_tc]],
        "sources": [],
    }

    result = protect_response(response, "employee")

    assert result["rows"][0][0] == "05** *** ** 67"
    assert result["rows"][0][1] == "12*******01"

    assert encrypted_phone not in str(result)
    assert "0532 123 45 67" not in str(result)
    assert "12345678901" not in str(result)


def test_admin_gets_decrypted_database_results(monkeypatch):
    monkeypatch.setenv(
        "FERNET_KEY",
        Fernet.generate_key().decode(),
    )

    encrypted_phone = encrypt("0532 123 45 67")

    response = {
        "route": "db",
        "answer": "Sonuç: " + encrypted_phone,
        "columns": ["phone"],
        "rows": [[encrypted_phone]],
        "sources": [],
    }

    result = protect_response(response, "admin")

    assert result["rows"] == [["0532 123 45 67"]]
    assert result["answer"] == "Sonuç: 0532 123 45 67"


def test_employee_scalar_answer_is_masked(monkeypatch):
    monkeypatch.setenv(
        "FERNET_KEY",
        Fernet.generate_key().decode(),
    )

    token = encrypt("0532 123 45 67")

    response = {
        "route": "db",
        "answer": f"Sonuç: {token}",
        "columns": ["phone"],
        "rows": [[token]],
    }

    result = protect_response(response, "employee")

    assert result["answer"] == "Sonuç: 05** *** ** 67"


def test_employee_pdf_answer_is_masked():
    response = {
        "route": "doc",
        "answer": "İletişim: ahmet@example.com",
        "sources": [{"source": "example.pdf", "page": 3}],
        "matches": [
            {
                "text": "Telefon: 0532 123 45 67",
                "source": "example.pdf",
                "page": 3,
                "score": 0.95,
            }
        ],
    }

    result = protect_response(response, "employee")

    assert "ahmet@example.com" not in result["answer"]
    assert result["matches"][0]["text"] == (
        "Telefon: 05** *** ** 67"
    )


def test_invalid_role_is_rejected():
    response = {"route": "db", "answer": "Gizli bilgi"}

    try:
        protect_response(response, "unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown role should be rejected")
