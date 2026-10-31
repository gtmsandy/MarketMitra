"""Representative-data contract for the opt-in PostgreSQL benchmark."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import DailyPrice, Instrument, LiveQuote
from tests.postgres_performance_benchmark import _seed


def test_benchmark_seed_covers_required_market_data_cases() -> None:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = Session(bind=engine, autoflush=False)
    try:
        _seed(session, 5)

        instruments = session.query(Instrument).all()
        prices = session.query(DailyPrice).all()
        assert {row.sector for row in instruments} >= {
            "Banking", "Hydropower", "Mutual Fund"
        }
        assert {row.security_type for row in instruments} >= {
            "EQUITY", "MUTUAL_FUND"
        }
        assert len({row.date for row in prices}) >= 3
        assert any(not row.is_ohlc_valid for row in prices)
        assert any(
            not any(price.symbol == instrument.symbol for price in prices)
            for instrument in instruments
        )
        assert session.query(LiveQuote).count() == 1
    finally:
        session.rollback()
        session.close()
        engine.dispose()
