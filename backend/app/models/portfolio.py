from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PortfolioCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_currency: Literal["NPR"] = "NPR"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Portfolio name is required")
        return value


class PortfolioRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Portfolio name is required")
        return value


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    base_currency: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TransactionCreateRequest(BaseModel):
    idempotency_key: UUID
    symbol: str = Field(min_length=1, max_length=32)
    side: Literal["BUY", "SELL"]
    trade_date: date
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    unit_price: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    fees: Decimal = Field(default=Decimal("0"), ge=0, max_digits=24, decimal_places=8)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    symbol: str
    side: Literal["BUY", "SELL"]
    trade_date: date
    trade_sequence: int
    quantity: Decimal
    unit_price: Decimal
    fees: Decimal
    idempotency_key: UUID
    notes: str | None
    created_at: datetime


class HoldingResponse(BaseModel):
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    invested_cost: Decimal
    realized_pnl: Decimal


class ValuationResponse(BaseModel):
    as_of: date
    source: str
    freshness: str
    observed_on_by_symbol: dict[str, date]
    complete: bool
    missing_symbols: list[str]
    stale_symbols: list[str]


class PortfolioSummaryResponse(BaseModel):
    holdings: list[HoldingResponse]
    cash_flow_cost: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    total_pnl: Decimal | None
    return_percent: Decimal | None
    valuation: ValuationResponse


class SectorAllocationResponse(BaseModel):
    sector: str
    market_value: Decimal
    percentage: Decimal
