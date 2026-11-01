"""Password and opaque-token primitives for MarketMitra identity."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_BYTES = 12
MAX_PASSWORD_BYTES = 128
SECRET_BYTES = 32

_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def validate_password(password: str) -> None:
    """Enforce a bounded, Unicode-friendly password policy."""
    byte_length = len(password.encode("utf-8"))
    if byte_length < MIN_PASSWORD_BYTES:
        raise ValueError("Password must be at least 12 bytes")
    if byte_length > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 128 bytes")
    if password.isspace():
        raise ValueError("Password must contain non-whitespace characters")
    if any(unicodedata.category(character).startswith("C") for character in password):
        raise ValueError("Password must not contain control characters")


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(encoded_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(encoded_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def password_needs_rehash(encoded_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.check_needs_rehash(encoded_hash)
    except InvalidHashError:
        return True


def generate_secret() -> str:
    """Return an unpadded URL-safe secret with 256 bits of entropy."""
    return secrets.token_urlsafe(SECRET_BYTES)


def digest_secret(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("ascii")).digest()


def verifier_matches(expected_verifier: bytes, candidate_secret: str) -> bool:
    return hmac.compare_digest(expected_verifier, digest_secret(candidate_secret))
