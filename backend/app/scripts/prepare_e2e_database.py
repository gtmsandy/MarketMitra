"""Prepare the explicitly authorized disposable database for authenticated E2E tests.

This script is intentionally narrower than the staging and technical-fixture
importers.  It accepts only the local E2E database and loads the approved
four-session synthetic baseline after migrations have been applied separately.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

from app.db.models import IngestionRun
from app.ingestion.service import IngestionService
from app.ingestion.sources.staging_fixture import (
    StagingFixtureSource,
    load_staging_dataset,
)
from app.scripts.seed_staging_data import _verify_report

E2E_DATABASE = "marketmitra_e2e_ci"
E2E_ROLE = "marketmitra_e2e_ci_user"
E2E_CONFIRMATION = f"{E2E_DATABASE}/{E2E_ROLE}"
EXPECTED_ALEMBIC_HEAD = "0010"
EXPECTED_COUNTS = {"instruments": 6, "market_snapshots": 4, "daily_prices": 24}


class E2EPreparationError(RuntimeError):
    """The E2E target or baseline did not satisfy the safety contract."""


def _database_url() -> tuple[str, str]:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise E2EPreparationError("DATABASE_URL is required")
    try:
        parsed = make_url(raw)
    except Exception as exc:
        raise E2EPreparationError("DATABASE_URL is invalid") from exc
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host != "127.0.0.1"
        or parsed.database != E2E_DATABASE
        or parsed.username != E2E_ROLE
    ):
        raise E2EPreparationError("DATABASE_URL is not the authorized E2E target")
    if os.getenv("MARKETMITRA_E2E_CONFIRMATION") != E2E_CONFIRMATION:
        raise E2EPreparationError("E2E confirmation must match database/role")
    return raw, parsed.database


def expected_head() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    scripts = ScriptDirectory.from_config(Config(str(backend_root / "alembic.ini")))
    heads = scripts.get_heads()
    if heads != [EXPECTED_ALEMBIC_HEAD]:
        raise E2EPreparationError("repository Alembic head is not 0010")
    return EXPECTED_ALEMBIC_HEAD


def verify_target(engine: Engine, expected_database: str) -> None:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT current_database(), current_user,
                       r.rolsuper, r.rolcreatedb, r.rolcreaterole,
                       r.rolreplication, r.rolbypassrls, r.rolcanlogin
                FROM pg_roles AS r
                WHERE r.rolname = current_user
                """
            )
        ).one()
    database, role, attributes = row[0], row[1], row[2:]
    if database != expected_database or role != E2E_ROLE:
        raise E2EPreparationError("connected database identity is not the authorized target")
    if any(attributes[:5]) or not attributes[5]:
        raise E2EPreparationError("E2E role must be a non-privileged login role")


def verify_schema(engine: Engine) -> None:
    from app.db.base import Base
    import app.db.models  # noqa: F401

    required = set(Base.metadata.tables)
    actual = set(inspect(engine).get_table_names())
    if not required <= actual or "alembic_version" not in actual:
        raise E2EPreparationError("Alembic migrations have not created the complete schema")
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    if revision != EXPECTED_ALEMBIC_HEAD:
        raise E2EPreparationError("database Alembic revision is not 0010")


def _counts(session) -> dict[str, int]:
    from app.db.base import Base
    import app.db.models  # noqa: F401

    return {
        name: session.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one()
        for name in Base.metadata.tables
    }


def require_empty_database(session) -> None:
    counts = _counts(session)
    if any(counts.values()):
        raise E2EPreparationError("E2E database is not empty; refusing to reset or reuse it")


def prepare(*, manifest_path: Path, apply: bool) -> dict[str, int | str]:
    database_url, database = _database_url()
    expected_head()
    from app.db.base import make_engine

    engine = make_engine(database_url)
    try:
        verify_target(engine, database)
        verify_schema(engine)
        dataset = load_staging_dataset(manifest_path, require_publication_approved=True)
        if (
            len(dataset.instruments) != EXPECTED_COUNTS["instruments"]
            or len(dataset.snapshots) != EXPECTED_COUNTS["market_snapshots"]
            or sum(len(rows) for rows in dataset.prices.values()) != EXPECTED_COUNTS["daily_prices"]
        ):
            raise E2EPreparationError("baseline fixture counts do not match the approved contract")

        factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        with factory() as session:
            require_empty_database(session)
            dry_run = IngestionService(
                StagingFixtureSource(dataset), session, dry_run=True
            ).run()
        _verify_report(dry_run, dataset, expected_status="dry_run")
        if not apply:
            return {"database": database, "status": "dry_run", **EXPECTED_COUNTS}

        # Re-check identity immediately before the only mutating operation.
        verify_target(engine, database)
        with factory() as session:
            require_empty_database(session)
            report = IngestionService(StagingFixtureSource(dataset), session).run()
        _verify_report(report, dataset, expected_status="success")
        with factory() as session:
            counts = _counts(session)
            if any(counts.get(name) != value for name, value in EXPECTED_COUNTS.items()):
                raise E2EPreparationError("post-ingestion baseline counts are incorrect")
            runs = session.query(IngestionRun).filter(IngestionRun.status == "success").count()
            if runs != 1:
                raise E2EPreparationError("expected exactly one successful E2E ingestion run")
        return {"database": database, "status": "applied", **EXPECTED_COUNTS}
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("provenance/deployment-manifest.json"))
    parser.add_argument("--apply", action="store_true", help="persist the approved baseline")
    args = parser.parse_args(argv)
    try:
        result = prepare(manifest_path=args.manifest, apply=args.apply)
    except Exception as exc:
        print(f"E2E DATABASE PREPARATION FAILED: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(
        "E2E DATABASE PREPARATION OK: "
        + ", ".join(f"{key}={value}" for key, value in result.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
