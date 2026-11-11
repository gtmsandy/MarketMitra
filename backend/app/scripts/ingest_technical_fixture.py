"""Safely preflight or ingest the extended fixture into an allowlisted disposable database."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
from math import isclose

from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.db.base import make_engine, make_session_factory
from app.db.models import DailyPrice, Instrument, MarketSnapshot
from app.ingestion.service import IngestionService
from app.ingestion.sources.technical_fixture import TechnicalFixture, TechnicalFixtureSource, load_technical_dataset
from app.scripts.seed_staging_data import verify_migrated_schema

_DISPOSABLE_DATABASES = frozenset({"marketmitra_ci", "marketmitra_fixture_ci"})
_PROTECTED_DATABASES = {"marketmitra", "marketmitra_auth_ci", "marketmitra_demo", "postgres", "vinay_clinic"}


class TechnicalIngestionError(RuntimeError):
    """The target or fixture failed a safe-ingestion prerequisite."""


@dataclass(frozen=True)
class TechnicalPreflight:
    database: str
    user: str
    baseline_prices_verified: int
    generated_prices_present: int
    generated_prices_to_insert: int
    generated_snapshots_present: int
    generated_snapshots_to_insert: int


def validate_database_target(database_url: str, confirmation: str | None) -> str:
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise TechnicalIngestionError("DATABASE_URL must be a valid PostgreSQL URL") from exc
    database = (url.database or "").lower()
    if (
        not url.drivername.startswith("postgresql")
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or database not in _DISPOSABLE_DATABASES
        or database in _PROTECTED_DATABASES
    ):
        raise TechnicalIngestionError(
            "technical fixture ingestion requires a runner-local allowlisted disposable database"
        )
    if confirmation != database:
        raise TechnicalIngestionError("MARKETMITRA_CONFIRM_DISPOSABLE must exactly match the database name")
    return database


def verify_database_identity(engine: Engine, expected_database: str) -> str:
    with engine.connect() as connection:
        actual_database, actual_user = connection.execute(
            text("SELECT current_database(), current_user")
        ).one()
    if actual_database != expected_database:
        raise TechnicalIngestionError("connected database identity does not match DATABASE_URL")
    if not actual_user:
        raise TechnicalIngestionError("connected database user identity is empty")
    return str(actual_user)


def _same_price(row: DailyPrice, expected: dict) -> bool:
    numeric_fields = ("open", "high", "low", "close", "turnover", "change", "change_percent", "previous_close")
    return (
        row.symbol == expected["symbol"]
        and row.date == expected["date"]
        and row.volume == expected["volume"]
        and all(isclose(float(getattr(row, field)), float(expected[field]), abs_tol=0.0001) for field in numeric_fields)
    )


def _same_snapshot(row: MarketSnapshot, expected: dict) -> bool:
    return (
        row.captured_at.date().isoformat() == expected["captured_at"][:10]
        and isclose(float(row.nepse_index), float(expected["nepse_index"]), abs_tol=0.0001)
        and isclose(float(row.index_change), float(expected["index_change"]), abs_tol=0.0001)
        and isclose(float(row.index_change_percent), float(expected["index_change_percent"]), abs_tol=0.0001)
        and row.total_volume == expected["total_volume"]
        and isclose(float(row.turnover), float(expected["turnover"]), abs_tol=0.01)
    )


def preflight_existing_data(session: Session, fixture: TechnicalFixture) -> TechnicalPreflight:
    expected_instruments = {record.symbol: record for record in fixture.dataset.instruments}
    existing_instruments = {
        row.symbol: row for row in session.query(Instrument).filter(Instrument.symbol.in_(expected_instruments)).all()
    }
    missing_instruments = set(expected_instruments) - set(existing_instruments)
    if missing_instruments:
        raise TechnicalIngestionError(f"baseline instruments are missing: {sorted(missing_instruments)}")
    for symbol, expected in expected_instruments.items():
        actual = existing_instruments[symbol]
        if (actual.company_name, actual.sector, actual.security_type) != (expected.company_name, expected.sector, expected.security_type):
            raise TechnicalIngestionError(f"baseline instrument {symbol} does not match the approved fixture")

    existing_prices = {
        (row.symbol, row.date): row
        for row in session.query(DailyPrice).filter(DailyPrice.symbol.in_(expected_instruments)).all()
    }
    for expected in fixture.baseline_prices:
        row = existing_prices.get((expected["symbol"], expected["date"]))
        if row is None or not _same_price(row, expected):
            raise TechnicalIngestionError(f"baseline price {expected['symbol']} {expected['date']} is missing or altered")

    generated_prices = [row for rows in fixture.dataset.prices.values() for row in rows]
    generated_present = 0
    generated_to_insert = 0
    for expected in generated_prices:
        row = existing_prices.get((expected.symbol, expected.date))
        if row is None:
            generated_to_insert += 1
        elif _same_price(row, expected.__dict__):
            generated_present += 1
        else:
            raise TechnicalIngestionError(f"unexpected generated-price overlap at {expected.symbol} {expected.date}")

    existing_snapshots = {
        row.captured_at.date().isoformat(): row for row in session.query(MarketSnapshot).all()
    }
    for expected in fixture.baseline_snapshots:
        row = existing_snapshots.get(expected["captured_at"][:10])
        if row is None or not _same_snapshot(row, expected):
            raise TechnicalIngestionError(f"baseline snapshot {expected['captured_at'][:10]} is missing or altered")
    generated_snapshots_present = 0
    generated_snapshots_to_insert = 0
    for expected in fixture.dataset.snapshots:
        expected_dict = {
            "captured_at": expected.captured_at.isoformat(),
            "nepse_index": expected.nepse_index,
            "index_change": expected.index_change,
            "index_change_percent": expected.index_change_percent,
            "turnover": expected.turnover,
            "total_volume": expected.total_volume,
        }
        row = existing_snapshots.get(expected_dict["captured_at"][:10])
        if row is None:
            generated_snapshots_to_insert += 1
        elif _same_snapshot(row, expected_dict):
            generated_snapshots_present += 1
        else:
            raise TechnicalIngestionError(f"unexpected generated-snapshot overlap on {expected_dict['captured_at'][:10]}")

    return TechnicalPreflight(
        database="",
        user="",
        baseline_prices_verified=len(fixture.baseline_prices),
        generated_prices_present=generated_present,
        generated_prices_to_insert=generated_to_insert,
        generated_snapshots_present=generated_snapshots_present,
        generated_snapshots_to_insert=generated_snapshots_to_insert,
    )


def ingest_technical_database(*, manifest_path: Path, database_url: str, confirmation: str, apply: bool = False):
    expected_database = validate_database_target(database_url, confirmation)
    fixture = load_technical_dataset(manifest_path, require_publication_approved=True)
    engine = make_engine(database_url)
    try:
        current_user = verify_database_identity(engine, expected_database)
        verify_migrated_schema(engine)
        with make_session_factory(database_url)() as session:
            preflight = preflight_existing_data(session, fixture)
            preflight = TechnicalPreflight(
                database=expected_database,
                user=current_user,
                baseline_prices_verified=preflight.baseline_prices_verified,
                generated_prices_present=preflight.generated_prices_present,
                generated_prices_to_insert=preflight.generated_prices_to_insert,
                generated_snapshots_present=preflight.generated_snapshots_present,
                generated_snapshots_to_insert=preflight.generated_snapshots_to_insert,
            )
            dry_run = IngestionService(
                TechnicalFixtureSource(fixture), session, validation_mode="historical", dry_run=True
            ).run()
            if dry_run.status != "dry_run" or dry_run.prices_rejected or dry_run.snapshots_inserted != preflight.generated_snapshots_to_insert:
                raise TechnicalIngestionError(f"technical fixture dry-run did not validate cleanly: {dry_run}")
        if not apply:
            return preflight, dry_run
        with make_session_factory(database_url)() as session:
            report = IngestionService(
                TechnicalFixtureSource(fixture), session, validation_mode="historical"
            ).run()
        if report.status != "success" or report.prices_rejected:
            raise TechnicalIngestionError(f"technical fixture ingestion failed: {report}")
        return preflight, report
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("provenance/technical-analysis-manifest.json"))
    parser.add_argument("--apply", action="store_true", help="commit after the dry-run preflight")
    args = parser.parse_args()
    try:
        report = ingest_technical_database(
            manifest_path=args.manifest,
            database_url=os.getenv("DATABASE_URL", "").strip(),
            confirmation=os.getenv("MARKETMITRA_CONFIRM_DISPOSABLE", ""),
            apply=args.apply,
        )
    except Exception as exc:
        print(f"TECHNICAL FIXTURE INGESTION FAILED: {exc}")
        return 2
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
