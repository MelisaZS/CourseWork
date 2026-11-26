
"""Personal data masking and Fernet field encryption."""

import os
import re

from cryptography.fernet import Fernet
from dotenv import load_dotenv

import config

# Turkish IBAN: TR followed by 24 digits.
IBAN_PATTERN = re.compile(
    r"(?<!\w)TR(?:[\s-]?\d){24}(?!\w)",
    re.IGNORECASE,
)

# Common email addresses.
EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])([\w.+-]+)@([\w-]+(?:\.[\w-]+)+)"
)

# Turkish mobile numbers:
# 0532 123 45 67 / 5321234567 / +90 532 123 45 67
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+90[\s-]?|0)?5\d{2}(?:[\s-]?\d){7}(?!\d)"
)

# Turkish identity number: 11 digits, no leading zero.
TC_PATTERN = re.compile(
    r"(?<!\d)[1-9]\d{10}(?!\d)"
)


def _mask_digits(value, keep_first=0, keep_last=0):
    """Mask numeric characters while preserving separators."""
    positions = [
        index for index, char in enumerate(value)
        if char.isdigit()
    ]

    visible = set(positions[:keep_first])

    if keep_last:
        visible.update(positions[-keep_last:])

    return "".join(
        char if not char.isdigit() or index in visible else "*"
        for index, char in enumerate(value)
    )


def _mask_email(match):
    """Keep the first local-part character and the domain."""
    local = match.group(1)
    domain = match.group(2)

    masked_local = local[0] + "*" * max(3, len(local) - 1)

    return f"{masked_local}@{domain}"


def _mask_iban(match):
    """Mask IBAN digits except the final four."""
    value = match.group(0)

    return value[:2] + _mask_digits(
        value[2:],
        keep_last=4,
    )


def _mask_phone(match):
    """Mask phone digits, keeping limited identifying context."""
    value = match.group(0)

    if value.startswith("+90"):
        return "+90" + _mask_digits(
            value[3:],
            keep_first=1,
            keep_last=2,
        )

    return _mask_digits(
        value,
        keep_first=2,
        keep_last=2,
    )


def _mask_tc(match):
    """Keep first two and last two TC digits."""
    return _mask_digits(
        match.group(0),
        keep_first=2,
        keep_last=2,
    )


def mask_pii(text):
    """Mask Turkish identity numbers, phones, emails and IBANs.

    PII: Personally Identifiable Information.
    The original text is not modified.
    """
    if not isinstance(text, str):
        raise TypeError("mask_pii expects a string.")

    if not text:
        return text

    masked = IBAN_PATTERN.sub(_mask_iban, text)
    masked = EMAIL_PATTERN.sub(_mask_email, masked)
    masked = PHONE_PATTERN.sub(_mask_phone, masked)
    masked = TC_PATTERN.sub(_mask_tc, masked)

    return masked


def _get_fernet():
    """Load the Fernet key from the environment or local .env."""
    load_dotenv(
        dotenv_path=config.BASE_DIR / ".env",
        override=False,
    )

    key = os.getenv("FERNET_KEY")

    if not key:
        raise RuntimeError(
            "FERNET_KEY bulunamadı. "
            "Anahtarı .env dosyasında tanımlayın."
        )

    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as error:
        raise ValueError(
            "FERNET_KEY geçerli bir Fernet anahtarı değil."
        ) from error


def encrypt(value):
    """Encrypt a string using Fernet and return a string token."""
    if not isinstance(value, str):
        raise TypeError("encrypt expects a string.")

    token = _get_fernet().encrypt(
        value.encode("utf-8")
    )

    return token.decode("utf-8")


def decrypt(value):
    """Decrypt a Fernet token and return the original string."""
    if not isinstance(value, str):
        raise TypeError("decrypt expects a string.")

    plaintext = _get_fernet().decrypt(
        value.encode("utf-8")
    )

    return plaintext.decode("utf-8")

def protect_response(response, role):
    """Prepare a router response for the user's role.

    Admins see decrypted values.
    Other roles see masked personal information.
    """
    if role not in ("admin", "employee", "guest"):
        raise ValueError("Geçersiz kullanıcı rolü.")

    protected = dict(response)

    def present(value):
        if not isinstance(value, str):
            return value

        # Fernet tokens are decrypted only with the configured key.
        # An invalid token/key raises an error instead of exposing data.
        if value.startswith("gAAAA"):
            value = decrypt(value)

        if role == "admin":
            return value

        return mask_pii(value)

    if "rows" in protected:
        protected["rows"] = [
            [present(value) for value in row]
            for row in protected["rows"]
        ]

    if "answer" in protected:
        answer_text = protected["answer"]

        # SQL agent may put a scalar value directly into the answer.
        # Rebuild that answer from the protected table value.
        rows = protected.get("rows", [])
        if (
            protected.get("route") == "db"
            and isinstance(answer_text, str)
            and answer_text.startswith("Sonuç:")
            and len(rows) == 1
            and len(rows[0]) == 1
        ):
            protected["answer"] = f"Sonuç: {rows[0][0]}"
        else:
            protected["answer"] = present(answer_text)

    if "sql" in protected:
        protected["sql"] = present(protected["sql"])

    if "columns" in protected:
        protected["columns"] = [
            present(column) for column in protected["columns"]
        ]

    if "sources" in protected:
        protected["sources"] = [
            (
                {key: present(value) for key, value in source.items()}
                if isinstance(source, dict)
                else present(source)
            )
            for source in protected["sources"]
        ]

    if "matches" in protected:
        protected["matches"] = [
            {
                key: present(value)
                for key, value in match.items()
            }
            for match in protected["matches"]
        ]

    return protected
