"""Validated HTTP contracts for MarketMitra identity endpoints."""

from datetime import datetime
import re
import unicodedata
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.identity.security import validate_password

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) > 254 or not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid email address")
    return normalized


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    display_name: str = Field(min_length=1, max_length=80)
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Display name is required")
        if any(unicodedata.category(character).startswith("C") for character in normalized):
            raise ValueError("Display name contains unsupported characters")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password(value)
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 128:
            raise ValueError("Password must be at most 128 bytes")
        return value


class IdentityUserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    created_at: datetime


class AuthSessionResponse(BaseModel):
    user: IdentityUserResponse
    csrf_token: str
    expires_at: datetime


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
