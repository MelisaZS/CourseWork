
"""Encrypt existing customer phone and identity fields."""

from pathlib import Path

import config
from auth.privacy import decrypt, encrypt
from db.database import get_connection


def _encrypt_if_needed(value):
    """Encrypt plaintext, preserving existing valid Fernet tokens."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError("Customer PII must be a string.")

    if value.startswith("gAAAA"):
        # Verify the existing token with the current key.
        # Wrong keys or corrupted values must stop migration.
        decrypt(value)
        return value

    return encrypt(value)


def encrypt_customer_fields(db_path=None):
    """Encrypt phone and tc_no in the customers table.

    Safe to run repeatedly with the same Fernet key.
    Returns the number of updated customer records.
    """
    path = Path(db_path or config.DB_PATH)

    if not path.is_file():
        raise FileNotFoundError(
            f"Veritabanı bulunamadı: {path}"
        )

    conn = get_connection(path)

    try:
        customers = conn.execute(
            "SELECT id, phone, tc_no FROM customers"
        ).fetchall()

        updates = []

        for customer_id, phone, tc_no in customers:
            encrypted_phone = _encrypt_if_needed(phone)
            encrypted_tc = _encrypt_if_needed(tc_no)

            if encrypted_phone != phone or encrypted_tc != tc_no:
                updates.append(
                    (encrypted_phone, encrypted_tc, customer_id)
                )

        # Apply all updates in one transaction.
        with conn:
            conn.executemany(
                """
                UPDATE customers
                SET phone = ?, tc_no = ?
                WHERE id = ?
                """,
                updates,
            )

        return len(updates)

    finally:
        conn.close()


if __name__ == "__main__":
    count = encrypt_customer_fields()
    print(f"Şifrelenen müşteri kaydı: {count}")
