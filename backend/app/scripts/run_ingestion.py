"""CLI entry point for the market data ingestion pipeline.

Usage (from the backend/ directory):

    .venv\\Scripts\\python -m app.scripts.run_ingestion --source mock
    .venv\\Scripts\\python -m app.scripts.run_ingestion --source mock --mode replace

Arguments:
    --source  Data source identifier.  Currently supported: mock
    --mode    Conflict resolution for existing daily prices.
              insert (default) — skip rows already present
              replace          — overwrite rows already present

Requires DATABASE_URL to be set in the environment or .env file.
"""
import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

_SUPPORTED_SOURCES = ("mock",)
_SUPPORTED_MODES = ("insert", "replace")


def _build_source(name: str):
    if name == "mock":
        from app.ingestion.sources.mock_source import MockDataSource
        return MockDataSource()
    print(f"Unknown source: {name!r}. Supported: {', '.join(_SUPPORTED_SOURCES)}", file=sys.stderr)
    sys.exit(1)


def _build_session():
    from app.core.config import get_database_url
    from app.db.base import make_session_factory
    return make_session_factory(get_database_url())()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MarketMitra ingestion pipeline.")
    parser.add_argument(
        "--source",
        choices=_SUPPORTED_SOURCES,
        default="mock",
        help="Data source to ingest from (default: mock).",
    )
    parser.add_argument(
        "--mode",
        choices=_SUPPORTED_MODES,
        default="insert",
        help="Conflict mode for existing daily prices (default: insert).",
    )
    args = parser.parse_args()

    from app.ingestion.service import IngestionService

    source = _build_source(args.source)
    session = _build_session()

    try:
        service = IngestionService(source=source, session=session, on_conflict=args.mode)
        report = service.run()
        print(report)
        if report.status == "failure":
            sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
