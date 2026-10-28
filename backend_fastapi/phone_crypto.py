"""Authenticated encryption helpers for phone numbers stored in the database."""

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    key = os.getenv("PHONE_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PHONE_ENCRYPTION_KEY is required. Generate a Fernet key and keep it stable; "
            "the database cannot decrypt phone numbers without it."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("PHONE_ENCRYPTION_KEY must be a valid Fernet key") from exc


def validate_phone_encryption_key() -> None:
    """Fail at startup rather than accidentally accepting plaintext writes."""
    _fernet()


def is_encrypted_phone(value: Optional[str]) -> bool:
    return bool(value and value.startswith(_PREFIX))


def encrypt_phone(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return value
    if is_encrypted_phone(value):
        # Validate that an existing ciphertext belongs to the configured key.
        decrypt_phone(value)
        return value
    ciphertext = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{ciphertext}"


def decrypt_phone(value: Optional[str]) -> Optional[str]:
    if value is None or value == "" or not is_encrypted_phone(value):
        # Untagged values are legacy plaintext and are encrypted during DB startup.
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            "Unable to decrypt a stored phone number. Check PHONE_ENCRYPTION_KEY."
        ) from exc
