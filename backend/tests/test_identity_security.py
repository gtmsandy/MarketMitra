import base64

import pytest

from app.identity.security import (
    digest_secret,
    generate_secret,
    hash_password,
    validate_password,
    verifier_matches,
    verify_password,
)


def test_password_hash_uses_reviewed_argon2id_parameters() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert verify_password(encoded, "correct horse battery staple") is True
    assert verify_password(encoded, "incorrect horse battery staple") is False


@pytest.mark.parametrize(
    "password, message",
    [
        ("short", "at least 12 bytes"),
        ("x" * 129, "at most 128 bytes"),
        (" " * 12, "non-whitespace"),
        ("valid-password\n", "control characters"),
    ],
)
def test_password_validation_rejects_unsafe_inputs(
    password: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_password(password)


def test_password_validation_measures_utf8_bytes() -> None:
    with pytest.raises(ValueError, match="at most 128 bytes"):
        validate_password("न" * 43)


def test_opaque_secret_contains_256_bits_without_padding() -> None:
    first = generate_secret()
    second = generate_secret()

    assert first != second
    assert "=" not in first
    assert len(base64.urlsafe_b64decode(first + "=")) == 32


def test_secret_verifier_is_fixed_length_and_constant_time_comparable() -> None:
    secret = generate_secret()
    verifier = digest_secret(secret)

    assert len(verifier) == 32
    assert verifier_matches(verifier, secret) is True
    assert verifier_matches(verifier, generate_secret()) is False
    assert verifier_matches(verifier, "न") is False
