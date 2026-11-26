
"""Tests for PII masking and Fernet encryption."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from auth.privacy import decrypt, encrypt, mask_pii


def test_mask_turkish_identity_number():
    text = "Müşteri TC: 12345678901"

    result = mask_pii(text)

    assert result == "Müşteri TC: 12*******01"
    assert "12345678901" not in result


def test_mask_phone_number():
    text = "Telefon: 0532 123 45 67"

    result = mask_pii(text)

    assert result == "Telefon: 05** *** ** 67"
    assert "0532 123 45 67" not in result


def test_mask_phone_without_spaces():
    text = "Telefon: 05321234567"

    result = mask_pii(text)

    assert result == "Telefon: 05*******67"


def test_mask_email():
    text = "E-posta: ahmet@example.com"

    result = mask_pii(text)

    assert result == "E-posta: a****@example.com"
    assert "ahmet@example.com" not in result


def test_mask_iban():
    text = "IBAN: TR33 0006 1005 1978 6457 8413 26"

    result = mask_pii(text)

    assert "TR33 0006" not in result
    assert result.endswith("13 26")
    assert "*" in result


def test_mask_multiple_pii():
    text = (
        "TC: 12345678901, "
        "Telefon: 0532 123 45 67, "
        "E-posta: ahmet@example.com"
    )

    result = mask_pii(text)

    assert "12345678901" not in result
    assert "0532 123 45 67" not in result
    assert "ahmet@example.com" not in result

    assert "12*******01" in result
    assert "05** *** ** 67" in result
    assert "a****@example.com" in result


def test_normal_text_unchanged():
    text = "Toplam 200 müşterimiz bulunmaktadır."

    assert mask_pii(text) == text


def test_empty_text():
    assert mask_pii("") == ""


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)

    original = "0532 123 45 67"

    encrypted = encrypt(original)
    decrypted = decrypt(encrypted)

    assert encrypted != original
    assert decrypted == original


def test_encrypt_tc_number(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)

    original = "12345678901"

    encrypted = encrypt(original)

    assert original not in encrypted
    assert decrypt(encrypted) == original


def test_same_value_generates_different_tokens(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)

    first = encrypt("test-value")
    second = encrypt("test-value")

    assert first != second
    assert decrypt(first) == decrypt(second)


def test_wrong_key_cannot_decrypt(monkeypatch):
    first_key = Fernet.generate_key().decode()
    second_key = Fernet.generate_key().decode()

    monkeypatch.setenv("FERNET_KEY", first_key)
    encrypted = encrypt("Gizli müşteri verisi")

    monkeypatch.setenv("FERNET_KEY", second_key)

    with pytest.raises(InvalidToken):
        decrypt(encrypted)


def test_invalid_input_types():
    with pytest.raises(TypeError):
        mask_pii(123)

    with pytest.raises(TypeError):
        encrypt(123)

    with pytest.raises(TypeError):
        decrypt(123)
