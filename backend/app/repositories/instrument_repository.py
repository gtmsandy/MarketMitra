from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Instrument


class InstrumentRepository(ABC):
    @abstractmethod
    def upsert(
        self,
        symbol: str,
        company_name: str,
        sector: str | None = None,
        security_type: str = "EQUITY",
    ) -> Instrument:
        """Insert or update an instrument record."""

    @abstractmethod
    def get_by_symbol(self, symbol: str) -> Instrument | None:
        """Return the instrument for the given symbol, or None."""

    @abstractmethod
    def get_all(self) -> list[Instrument]:
        """Return all instruments."""


class PostgresInstrumentRepository(InstrumentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        symbol: str,
        company_name: str,
        sector: str | None = None,
        security_type: str = "EQUITY",
    ) -> Instrument:
        existing = self._session.get(Instrument, symbol)
        if existing is not None:
            existing.company_name = company_name
            existing.sector = sector
            existing.security_type = security_type
            return existing

        instrument = Instrument(
            symbol=symbol,
            company_name=company_name,
            sector=sector,
            security_type=security_type,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(instrument)
        return instrument

    def get_by_symbol(self, symbol: str) -> Instrument | None:
        return self._session.get(Instrument, symbol)

    def get_all(self) -> list[Instrument]:
        return self._session.query(Instrument).order_by(Instrument.symbol).all()
