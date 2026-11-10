"""Start the local interview demo only after verifying its database target."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

EXPECTED_DATABASE = "marketmitra_demo"
EXPECTED_ROLE = "marketmitra_demo_user"
EXPECTED_ALEMBIC_HEAD = "0010"


@dataclass(frozen=True)
class DemoDatabaseIdentity:
    database: str
    user: str
    revision: str


def validate_demo_configuration(
    *, database_url: str, market_data_source: str
) -> URL:
    """Validate non-secret demo configuration before opening a connection."""
    if market_data_source.strip().lower() != "postgres":
        raise ValueError("Demo startup requires MARKET_DATA_SOURCE=postgres")
    try:
        parsed = make_url(database_url)
    except Exception as exc:  # SQLAlchemy exposes multiple URL parse exceptions.
        raise ValueError("Demo startup requires a valid PostgreSQL DATABASE_URL") from exc
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("Demo startup requires a PostgreSQL DATABASE_URL")
    if parsed.database != EXPECTED_DATABASE:
        raise ValueError(f"Demo startup requires database {EXPECTED_DATABASE}")
    if parsed.username != EXPECTED_ROLE:
        raise ValueError(f"Demo startup requires role {EXPECTED_ROLE}")
    return parsed


def verify_demo_database(database_url: str) -> DemoDatabaseIdentity:
    """Perform read-only identity and migration checks against the demo DB."""
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            database, user = connection.execute(
                text("select current_database(), current_user")
            ).one()
            revision = connection.execute(
                text("select version_num from alembic_version")
            ).scalar_one_or_none()
    finally:
        engine.dispose()

    if database != EXPECTED_DATABASE or user != EXPECTED_ROLE:
        raise RuntimeError("Demo database identity does not match the approved target")
    if revision != EXPECTED_ALEMBIC_HEAD:
        raise RuntimeError(
            f"Demo database must be at Alembic head {EXPECTED_ALEMBIC_HEAD}"
        )
    return DemoDatabaseIdentity(database=database, user=user, revision=revision)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env.demo.local"),
        help="Demo environment file, relative to the backend working directory",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.env_file.is_file():
        raise SystemExit(f"Demo environment file not found: {args.env_file}")
    load_dotenv(args.env_file, override=True)
    database_url = os.getenv("DATABASE_URL", "").strip()
    validate_demo_configuration(
        database_url=database_url,
        market_data_source=os.getenv("MARKET_DATA_SOURCE", ""),
    )
    identity = verify_demo_database(database_url)
    print(
        f"Verified demo database: {identity.database}; "
        f"role: {identity.user}; Alembic: {identity.revision}"
    )

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
