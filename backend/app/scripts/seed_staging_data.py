"""Safely load the provenance-approved synthetic fixture into staging PostgreSQL."""

import argparse
import os
from pathlib import Path
import re
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

from app.db.models import DailyPrice, IngestionRun, Instrument, MarketSnapshot
from app.ingestion.models import IngestionReport
from app.ingestion.service import IngestionService
from app.ingestion.sources.staging_fixture import (
    StagingDataset,
    StagingFixtureSource,
    load_staging_dataset,
)

_STAGING_DATABASE = re.compile(r"^[a-z0-9][a-z0-9_]*_staging$")
_FORBIDDEN_NAME_PARTS = {"prod", "production", "shared", "dev", "development"}


class StagingSeedError(RuntimeError):
    pass


def validate_database_target(database_url: str, confirmation: str | None) -> str:
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise StagingSeedError("DATABASE_URL must be a valid PostgreSQL URL") from exc
    database = url.database or ""
    parts = set(database.lower().split("_"))
    if (
        not url.drivername.startswith("postgresql")
        or not url.host
        or url.host in {"localhost", "127.0.0.1", "::1"}
        or not _STAGING_DATABASE.fullmatch(database.lower())
        or parts & _FORBIDDEN_NAME_PARTS
    ):
        raise StagingSeedError("target must be a remote dedicated staging database")
    if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise StagingSeedError("staging database connection must require TLS")
    if confirmation != database:
        raise StagingSeedError("staging confirmation token must exactly match database name")
    return database


def expected_alembic_head() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    scripts = ScriptDirectory.from_config(Config(str(backend_root / "alembic.ini")))
    heads = scripts.get_heads()
    if len(heads) != 1:
        raise StagingSeedError("staging ingestion requires exactly one Alembic head")
    return heads[0]


def verify_migrated_schema(engine: Engine) -> None:
    from app.db.base import Base
    import app.db.models  # noqa: F401

    inspector = inspect(engine)
    required_tables = set(Base.metadata.tables)
    actual_tables = set(inspector.get_table_names())
    if not required_tables <= actual_tables or "alembic_version" not in actual_tables:
        raise StagingSeedError("Alembic migrations must create the complete schema before seeding")
    with engine.connect() as connection:
        revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    if revisions != [expected_alembic_head()]:
        raise StagingSeedError("database Alembic revision does not match the application head")


def verify_database_identity(engine: Engine, expected_database: str) -> None:
    with engine.connect() as connection:
        actual = connection.execute(text("SELECT current_database()" )).scalar_one()
    if actual != expected_database:
        raise StagingSeedError("connected database identity does not match DATABASE_URL")


def _require_empty_database(session) -> None:
    counts = {
        "instruments": session.scalar(select(text("count(*)")).select_from(Instrument)),
        "daily_prices": session.scalar(select(text("count(*)")).select_from(DailyPrice)),
        "market_snapshots": session.scalar(select(text("count(*)")).select_from(MarketSnapshot)),
        "ingestion_runs": session.scalar(select(text("count(*)")).select_from(IngestionRun)),
    }
    if any(counts.values()):
        raise StagingSeedError(f"staging database is not empty: {counts}")


def _verify_report(
    report: IngestionReport, dataset: StagingDataset, *, expected_status: str
) -> None:
    expected_prices = sum(len(rows) for rows in dataset.prices.values())
    if (
        report.status != expected_status
        or report.instruments_upserted != len(dataset.instruments)
        or report.snapshots_inserted != len(dataset.snapshots)
        or report.snapshots_skipped != 0
        or report.prices_accepted != expected_prices
        or report.prices_skipped != 0
        or report.prices_replaced != 0
        or report.prices_rejected != 0
    ):
        raise StagingSeedError(f"staging ingestion counts do not match fixture: {report}")


def seed_staging_database(*, manifest_path: Path, database_url: str, confirmation: str):
    from app.db.base import make_engine

    dataset = load_staging_dataset(manifest_path, require_publication_approved=True)
    source = StagingFixtureSource(dataset)
    engine = make_engine(database_url)
    try:
        expected_database = validate_database_target(database_url, confirmation)
        verify_database_identity(engine, expected_database)
        verify_migrated_schema(engine)
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        with session_factory() as session:
            _require_empty_database(session)
            dry_run = IngestionService(source, session, dry_run=True).run()
        _verify_report(dry_run, dataset, expected_status="dry_run")
        with session_factory() as session:
            _require_empty_database(session)
            report = IngestionService(source, session).run()
        _verify_report(report, dataset, expected_status="success")
        return report
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("/app/provenance/deployment-manifest.json"),
    )
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL", "").strip()
    confirmation = os.getenv("MARKETMITRA_CONFIRM_STAGING", "")
    try:
        if os.getenv("APP_ENV") != "production":
            raise StagingSeedError("APP_ENV must be production for staging seeding")
        report = seed_staging_database(
            manifest_path=args.manifest,
            database_url=database_url,
            confirmation=confirmation,
        )
    except Exception as exc:
        print(f"STAGING SEED FAILED: {exc}", file=sys.stderr)
        return 2
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
