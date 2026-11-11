"""Deterministic, provenance, and overlap tests for the TA fixture."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import DailyPrice, Instrument, MarketSnapshot
from app.ingestion.sources.technical_fixture import load_technical_dataset
from app.scripts.generate_technical_fixture import build_fixture
from app.scripts.ingest_technical_fixture import (
    TechnicalIngestionError,
    preflight_existing_data,
    validate_database_target,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "provenance" / "technical-analysis-manifest.json"


def test_technical_fixture_is_deterministic_and_preserves_baseline() -> None:
    first, first_manifest = build_fixture()
    second, second_manifest = build_fixture()

    assert first == second
    assert first_manifest == second_manifest
    assert len(first["instruments"]) == 6
    assert len(first["prices"]) == 720
    assert len(first["snapshots"]) == 120
    assert len(first["preserved_baseline"]["prices"]) == 24


def test_technical_fixture_loader_validates_weekday_ohlcv_and_provenance() -> None:
    fixture = load_technical_dataset(MANIFEST)

    assert fixture.session_count_per_instrument == 120
    assert fixture.preserved_observation_count == 24
    assert all(
        datetime.fromisoformat(row.date).weekday() < 5
        for rows in fixture.dataset.prices.values()
        for row in rows
    )
    assert all(
        row.high >= max(row.open, row.close)
        and row.low <= min(row.open, row.close)
        and row.volume >= 0
        and row.turnover >= 0
        for rows in fixture.dataset.prices.values()
        for row in rows
    )


@pytest.mark.parametrize(
    "database_url,confirmation",
    [
        ("postgresql://user:secret@127.0.0.1:5432/marketmitra_demo", "marketmitra_demo"),
        ("postgresql://user:secret@127.0.0.1:5432/unapproved_fixture_ci", "unapproved_fixture_ci"),
        ("postgresql://user:secret@db.internal/marketmitra_ci", "marketmitra_ci"),
        ("sqlite:///marketmitra_ci", "marketmitra_ci"),
    ],
)
def test_technical_ingestion_requires_local_disposable_ci_target(database_url: str, confirmation: str) -> None:
    with pytest.raises(TechnicalIngestionError):
        validate_database_target(database_url, confirmation)


def test_technical_ingestion_accepts_confirmed_local_ci_target() -> None:
    assert validate_database_target(
        "postgresql://user:secret@127.0.0.1:5432/marketmitra_ci",
        "marketmitra_ci",
    ) == "marketmitra_ci"


def test_technical_ingestion_accepts_confirmed_local_fixture_ci_target() -> None:
    assert validate_database_target(
        "postgresql://user:secret@127.0.0.1:5432/marketmitra_fixture_ci",
        "marketmitra_fixture_ci",
    ) == "marketmitra_fixture_ci"


def _seed_baseline(session: Session, fixture) -> None:
    for record in fixture.dataset.instruments:
        session.add(
            Instrument(
                symbol=record.symbol,
                company_name=record.company_name,
                sector=record.sector,
                security_type=record.security_type,
                created_at=datetime.now(timezone.utc),
            )
        )
    for record in fixture.baseline_prices:
        session.add(DailyPrice(**record, is_ohlc_valid=True))
    for record in fixture.baseline_snapshots:
        session.add(
            MarketSnapshot(
                nepse_index=record["nepse_index"],
                index_change=record["index_change"],
                index_change_percent=record["index_change_percent"],
                turnover=record["turnover"],
                total_volume=record["total_volume"],
                total_transactions=record["total_transactions"],
                market_status=record["market_status"],
                captured_at=datetime.fromisoformat(record["captured_at"]),
            )
        )


def test_preflight_verifies_baseline_and_reports_idempotent_generated_rows() -> None:
    fixture = load_technical_dataset(MANIFEST)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            _seed_baseline(session, fixture)
            session.commit()
            report = preflight_existing_data(session, fixture)
        assert report.baseline_prices_verified == 24
        assert report.generated_prices_present == 0
        assert report.generated_prices_to_insert == 720
        assert report.generated_snapshots_present == 0
        assert report.generated_snapshots_to_insert == 120
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_preflight_rejects_altered_generated_overlap() -> None:
    fixture = load_technical_dataset(MANIFEST)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            _seed_baseline(session, fixture)
            generated = next(iter(fixture.dataset.prices.values()))[0]
            session.add(
                DailyPrice(
                    symbol=generated.symbol,
                    date=generated.date,
                    open=generated.open + 1,
                    high=generated.high + 1,
                    low=generated.low + 1,
                    close=generated.close + 1,
                    volume=generated.volume,
                    turnover=generated.turnover,
                    change=generated.change,
                    change_percent=generated.change_percent,
                    previous_close=generated.previous_close,
                    is_ohlc_valid=True,
                )
            )
            session.commit()
            with pytest.raises(TechnicalIngestionError, match="unexpected generated-price overlap"):
                preflight_existing_data(session, fixture)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
