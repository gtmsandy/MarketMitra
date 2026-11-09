from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_watchlist_name(value: str) -> str:
    normalized = " ".join(value.split()).strip().lower()
    if not normalized:
        raise ValueError("Watchlist name is required")
    return normalized


def normalize_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized or len(normalized) > 32 or any(not (char.isalnum() or char in ".-&") for char in normalized):
        raise ValueError("Enter a valid instrument symbol")
    return normalized


class WatchlistCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_watchlist_name(value)


class WatchlistRenameRequest(WatchlistCreateRequest):
    pass


class WatchlistItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class WatchlistItemResponse(BaseModel):
    symbol: str
    company_name: str
    observation_date: str | None = None
    latest_price: float | None = None
    change_percent: float | None = None
    created_at: datetime


class WatchlistResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    items: list[WatchlistItemResponse]
