"""Disposable PostgreSQL verification for the extended technical fixture."""

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.scripts.ingest_technical_fixture import ingest_technical_database
from tests.postgres_ci import require_disposable_ci_database


def test_extended_fixture_ingests_and_is_idempotent_in_disposable_postgres() -> None:
    database_url = require_disposable_ci_database()
    manifest = Path(__file__).resolve().parents[2] / "provenance" / "technical-analysis-manifest.json"

    first_preflight, first_report = ingest_technical_database(
        manifest_path=manifest,
        database_url=database_url,
        confirmation=make_url(database_url).database,
        apply=True,
    )
    assert first_preflight.baseline_prices_verified == 24
    assert first_preflight.generated_prices_to_insert == 720
    assert first_preflight.generated_snapshots_to_insert == 120
    assert first_report.status == "success"
    assert first_report.prices_accepted == 720
    assert first_report.snapshots_inserted == 120
    assert first_report.prices_rejected == 0

    second_preflight, second_report = ingest_technical_database(
        manifest_path=manifest,
        database_url=database_url,
        confirmation=make_url(database_url).database,
        apply=True,
    )
    assert second_preflight.generated_prices_present == 720
    assert second_preflight.generated_prices_to_insert == 0
    assert second_preflight.generated_snapshots_present == 120
    assert second_preflight.generated_snapshots_to_insert == 0
    assert second_report.status == "success"
    assert second_report.prices_accepted == 0
    assert second_report.prices_skipped == 720
    assert second_report.snapshots_skipped == 120

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            prices, snapshots = connection.execute(
                text("SELECT (SELECT count(*) FROM daily_prices), (SELECT count(*) FROM market_snapshots)")
            ).one()
        assert prices == 744
        assert snapshots == 124
    finally:
        engine.dispose()
