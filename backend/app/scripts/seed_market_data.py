"""Seed PostgreSQL with deterministic mock market data.

Delegates to IngestionService with MockDataSource so all validation,
deduplication, and audit-trail logic is exercised consistently.

The script is idempotent: re-running skips prices that already exist
and skips snapshot insertion if today's snapshot is already present.

Usage (from the backend/ directory):
    .venv\\Scripts\\python -m app.scripts.seed_market_data

Requires DATABASE_URL to be set in the environment or in a .env file.
"""
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    from app.core.config import get_database_url
    from app.db.base import Base, make_engine, make_session_factory
    from app.ingestion.service import IngestionService
    from app.ingestion.sources.mock_source import MockDataSource

    # Ensure schema exists (no-op if Alembic has already applied migrations).
    engine = make_engine(get_database_url())
    Base.metadata.create_all(engine)

    session = make_session_factory(get_database_url())()
    print("Seeding MarketMitra database from mock data…")
    try:
        service = IngestionService(
            source=MockDataSource(),
            session=session,
            on_conflict="insert",
        )
        report = service.run()
        print(report)
        if report.status == "failure":
            sys.exit(1)
    except Exception as exc:
        session.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
