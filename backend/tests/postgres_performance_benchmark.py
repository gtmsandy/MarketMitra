"""Opt-in PostgreSQL benchmark runner for an empty disposable database.

This module is not collected by pytest. It refuses ordinary database names,
remote hosts, populated MarketMitra tables, and missing explicit confirmation.
All synthetic rows are written inside one transaction and rolled back.
"""

import json
import os
from datetime import datetime, timezone
from math import ceil
from statistics import median
from time import perf_counter

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.models import DailyPrice, Instrument, LiveQuote, MarketSnapshot
from app.providers.postgres_market import PostgresMarketProvider
from tests.sql_measurement import measure_sql


TABLES = (
    "instruments",
    "daily_prices",
    "market_snapshots",
    "live_quotes",
    "ingestion_runs",
)
SIZES = (5, 20, 100)
RUNS = 10


def _validated_database_url() -> str:
    raw = os.getenv("MARKETMITRA_BENCHMARK_DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("MARKETMITRA_BENCHMARK_DATABASE_URL is required")
    url = make_url(raw)
    database = url.database or ""
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Benchmark URL must use PostgreSQL")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Benchmark database must be local")
    if not database.endswith(("_benchmark", "_test")):
        raise RuntimeError("Database name must end in _benchmark or _test")
    if os.getenv("MARKETMITRA_CONFIRM_DISPOSABLE") != database:
        raise RuntimeError(
            "MARKETMITRA_CONFIRM_DISPOSABLE must exactly match the database name"
        )
    return raw


def _verify_empty_schema(engine) -> dict[str, str]:
    inspector = inspect(engine)
    missing = [table for table in TABLES if not inspector.has_table(table)]
    if missing:
        raise RuntimeError(
            f"Apply migrations to the disposable database first; missing: {missing}"
        )
    with engine.connect() as connection:
        identity = connection.execute(
            text("select current_database(), current_user")
        ).one()
        missing_permissions = [
            table
            for table in TABLES
            if not connection.execute(
                text(
                    "select has_table_privilege("
                    "current_user, :table, 'SELECT,INSERT,UPDATE,DELETE')"
                ),
                {"table": table},
            ).scalar_one()
        ]
        populated = {
            table: connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
            for table in TABLES
        }
    if missing_permissions:
        raise RuntimeError(
            f"Benchmark user lacks required table permissions: {missing_permissions}"
        )
    if any(populated.values()):
        raise RuntimeError(f"Benchmark database is not empty: {populated}")
    return {"database": identity[0], "user": identity[1]}


def _seed(session: Session, instrument_count: int) -> None:
    instruments = [
        Instrument(
            symbol=f"BENCH{index:04d}",
            company_name=f"Benchmark Company {index:04d}",
            sector="Banking" if index % 2 == 0 else "Hydropower",
            security_type="EQUITY",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        for index in range(instrument_count)
    ]
    session.add_all(instruments)
    session.flush()
    session.add_all(
        DailyPrice(
            symbol=instrument.symbol,
            date="2026-09-03",
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=1_000 + index,
            turnover=101_000.0 + index,
            change=1.0,
            change_percent=1.0,
            previous_close=100.0,
            is_ohlc_valid=True,
        )
        for index, instrument in enumerate(instruments)
    )
    session.add_all(
        DailyPrice(
            symbol=instrument.symbol,
            date="2026-09-02",
            open=99.0,
            high=101.0,
            low=98.0,
            close=100.0,
            volume=900 + index,
            turnover=90_000.0 + index,
            change=1.0,
            change_percent=1.01,
            previous_close=99.0,
            is_ohlc_valid=True,
        )
        for index, instrument in enumerate(instruments)
    )
    session.add_all(
        [
            Instrument(
                symbol="BENCHMISSING",
                company_name="Missing Benchmark Observation",
                sector="Banking",
                security_type="EQUITY",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            Instrument(
                symbol="BENCHFUND",
                company_name="Benchmark Mutual Fund",
                sector="Mutual Fund",
                security_type="MUTUAL_FUND",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            DailyPrice(
                symbol=instruments[0].symbol,
                date="2026-09-04",
                open=100.0,
                high=90.0,
                low=99.0,
                close=101.0,
                volume=1_000,
                turnover=101_000.0,
                change=1.0,
                change_percent=1.0,
                previous_close=100.0,
                is_ohlc_valid=False,
                validation_reason="ohlc_ordering",
            ),
            DailyPrice(
                symbol="BENCHFUND",
                date="2026-09-05",
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1_000,
                turnover=101_000.0,
                change=1.0,
                change_percent=1.0,
                previous_close=100.0,
                is_ohlc_valid=True,
            ),
            LiveQuote(
                symbol=instruments[0].symbol,
                timestamp=datetime(2026, 9, 3, 11, 0, tzinfo=timezone.utc),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1_000,
                turnover=101_000.0,
                provider="BENCHMARK",
                ingested_at=datetime(2026, 9, 3, 11, 0, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    session.add(
        MarketSnapshot(
            nepse_index=2_800.0,
            index_change=10.0,
            index_change_percent=0.36,
            turnover=1_000_000.0,
            total_volume=10_000,
            total_transactions=500,
            market_status="CLOSED",
            captured_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
        )
    )
    session.flush()


def _p95(values: list[float]) -> float:
    return sorted(values)[ceil(len(values) * 0.95) - 1]


def _measure(engine, session: Session, operation) -> dict[str, float | int]:
    session.expunge_all()
    operation(PostgresMarketProvider(session))
    elapsed: list[float] = []
    database: list[float] = []
    counts: list[int] = []
    response_bytes: list[int] = []
    for _ in range(RUNS):
        session.expunge_all()
        started = perf_counter()
        with measure_sql(engine) as measurement:
            rows = operation(PostgresMarketProvider(session))
        elapsed.append((perf_counter() - started) * 1_000)
        database.append(measurement.database_time_ms)
        counts.append(measurement.statement_count)
        payload = json.dumps(
            [row.model_dump(mode="json") for row in rows], default=str
        ).encode("utf-8")
        response_bytes.append(len(payload))
    return {
        "runs": RUNS,
        "query_count": counts[0],
        "query_count_stable": len(set(counts)) == 1,
        "elapsed_median_ms": round(median(elapsed), 3),
        "elapsed_p95_ms": round(_p95(elapsed), 3),
        "database_median_ms": round(median(database), 3),
        "database_p95_ms": round(_p95(database), 3),
        "response_bytes": response_bytes[0],
    }


def main() -> None:
    engine = create_engine(_validated_database_url(), pool_pre_ping=True)
    identity = _verify_empty_schema(engine)
    report = {"environment": identity, "measurements": {}}
    operations = {
        "stocks": lambda provider: provider.get_stocks(),
        "search": lambda provider: provider.search_stocks("Benchmark Company"),
        "gainers": lambda provider: provider.get_top_gainers(),
        "losers": lambda provider: provider.get_top_losers(),
        "most_active": lambda provider: provider.get_most_active(),
    }
    try:
        for size in SIZES:
            with engine.connect() as connection:
                transaction = connection.begin()
                session = Session(bind=connection, autoflush=False)
                try:
                    _seed(session, size)
                    report["measurements"][str(size)] = {
                        name: _measure(engine, session, operation)
                        for name, operation in operations.items()
                    }
                finally:
                    session.close()
                    transaction.rollback()
    finally:
        engine.dispose()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
