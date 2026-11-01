"""Safety contracts for provenance-bound staging ingestion."""

from pathlib import Path
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session


def test_staging_target_requires_exact_confirmation_token() -> None:
    from app.scripts.seed_staging_data import StagingSeedError, validate_database_target

    with pytest.raises(StagingSeedError, match="confirmation token"):
        validate_database_target(
            "postgresql://user:secret@db.internal/marketmitra_staging?sslmode=require",
            "wrong_database",
        )


@pytest.mark.parametrize(
    "database_name",
    ["marketmitra", "marketmitra_production", "marketmitra_shared", "marketmitra_development"],
)
def test_staging_target_rejects_non_staging_database_names(database_name: str) -> None:
    from app.scripts.seed_staging_data import StagingSeedError, validate_database_target

    with pytest.raises(StagingSeedError, match="dedicated staging database"):
        validate_database_target(
            f"postgresql://user:secret@db.internal/{database_name}?sslmode=require",
            database_name,
        )


def test_staging_target_accepts_explicit_remote_encrypted_database() -> None:
    from app.scripts.seed_staging_data import validate_database_target

    assert validate_database_target(
        "postgresql://user:secret@db.internal/marketmitra_staging?sslmode=require",
        "marketmitra_staging",
    ) == "marketmitra_staging"


def test_schema_prerequisite_rejects_unmigrated_database() -> None:
    from app.scripts.seed_staging_data import StagingSeedError, verify_migrated_schema

    engine = create_engine("sqlite://")
    with pytest.raises(StagingSeedError, match="Alembic migrations"):
        verify_migrated_schema(engine)


def test_schema_prerequisite_accepts_current_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db.base import Base
    import app.db.models  # noqa: F401
    from app.scripts import seed_staging_data

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('expected-head')"))
    monkeypatch.setattr(seed_staging_data, "expected_alembic_head", lambda: "expected-head")

    seed_staging_data.verify_migrated_schema(engine)


def test_database_identity_rejects_a_different_connected_database() -> None:
    from app.scripts.seed_staging_data import StagingSeedError, verify_database_identity

    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def register_current_database(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_function("current_database", 0, lambda: "other_staging")

    with pytest.raises(StagingSeedError, match="identity"):
        verify_database_identity(engine, "marketmitra_staging")


def test_committed_fixture_source_preserves_expected_ingestion_counts() -> None:
    from app.ingestion.models import IngestionReport
    from app.ingestion.sources.staging_fixture import StagingFixtureSource, load_staging_dataset
    from app.scripts.seed_staging_data import _verify_report

    manifest = Path(__file__).resolve().parents[2] / "provenance" / "deployment-manifest.json"
    dataset = load_staging_dataset(manifest)
    source = StagingFixtureSource(dataset)

    assert len(source.fetch_instruments()) == 6
    assert len(source.fetch_snapshots()) == 4
    assert sum(len(source.fetch_prices(item.symbol)) for item in source.fetch_instruments()) == 24
    now = datetime.now(timezone.utc)
    _verify_report(
        IngestionReport(
            source=dataset.identifier,
            started_at=now,
            finished_at=now,
            status="success",
            instruments_upserted=6,
            snapshots_inserted=4,
            prices_accepted=24,
        ),
        dataset,
        expected_status="success",
    )


def test_staging_ingestion_rejects_inaccurate_snapshot_count() -> None:
    from app.ingestion.models import IngestionReport
    from app.ingestion.sources.staging_fixture import load_staging_dataset
    from app.scripts.seed_staging_data import StagingSeedError, _verify_report

    manifest = Path(__file__).resolve().parents[2] / "provenance" / "deployment-manifest.json"
    dataset = load_staging_dataset(manifest)
    now = datetime.now(timezone.utc)
    report = IngestionReport(
        source=dataset.identifier,
        started_at=now,
        finished_at=now,
        status="success",
        instruments_upserted=6,
        snapshots_inserted=3,
        prices_accepted=24,
    )

    with pytest.raises(StagingSeedError, match="counts do not match"):
        _verify_report(report, dataset, expected_status="success")


def test_repeated_staging_ingestion_fails_closed_for_nonempty_database() -> None:
    from app.db.base import Base
    from app.db.models import Instrument
    import app.db.models  # noqa: F401
    from app.scripts.seed_staging_data import StagingSeedError, _require_empty_database

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        session.add(Instrument(
            symbol="SYNEXISTS",
            company_name="Synthetic Existing Company",
            sector="Synthetic Test",
            security_type="EQUITY",
            created_at=datetime.now(timezone.utc),
        ))
        session.commit()
        with pytest.raises(StagingSeedError, match="not empty"):
            _require_empty_database(session)
    finally:
        session.close()
