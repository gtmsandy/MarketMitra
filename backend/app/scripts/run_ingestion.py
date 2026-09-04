"""CLI entry point for the market data ingestion pipeline.

Usage (from the backend/ directory):

    .venv\\Scripts\\python -m app.scripts.run_ingestion --source mock
    .venv\\Scripts\\python -m app.scripts.run_ingestion --source mock --mode replace
    .venv\\Scripts\\python -m app.scripts.run_ingestion --if-market-open
    .venv\\Scripts\\python -m app.scripts.run_ingestion --json

Arguments:
    --source          Data source identifier. Currently supported: mock
    --mode            Conflict mode for existing daily prices:
                      insert (default) — skip rows already present
                      replace          — overwrite rows already present
    --if-market-open  Only run ingestion if the NEPSE market is currently open.
                      If closed, exit 0 without running ingestion.
    --json            Output structured execution report as JSON on stdout.

Requires DATABASE_URL to be set in the environment or .env file.
"""
import argparse
import json
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


def main(argv: list[str] | None = None) -> int:
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
    parser.add_argument(
        "--if-market-open",
        action="store_true",
        help="Only run ingestion if the NEPSE market is currently open. If closed, exit 0.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output execution report as JSON on stdout.",
    )
    args = parser.parse_args(argv)

    if args.if_market_open:
        from app.core.market_schedule import is_market_open
        if not is_market_open():
            if args.json:
                payload = {
                    "status": "skipped",
                    "reason": "market_closed",
                    "message": "NEPSE market is currently closed; ingestion skipped.",
                }
                print(json.dumps(payload, indent=2))
            else:
                print("NEPSE market is currently closed; ingestion skipped.")
            return 0

    from app.ingestion.service import IngestionService

    source = _build_source(args.source)
    session = _build_session()

    try:
        service = IngestionService(source=source, session=session, on_conflict=args.mode)
        report = service.run()

        if args.json:
            payload = {
                "source": report.source,
                "status": report.status,
                "started_at": report.started_at.isoformat() if report.started_at else None,
                "finished_at": report.finished_at.isoformat() if report.finished_at else None,
                "instruments_upserted": report.instruments_upserted,
                "snapshots_inserted": report.snapshots_inserted,
                "snapshots_skipped": report.snapshots_skipped,
                "prices_accepted": report.prices_accepted,
                "prices_skipped": report.prices_skipped,
                "prices_replaced": report.prices_replaced,
                "prices_rejected": report.prices_rejected,
                "error_detail": report.error_detail,
                "rejection_summary": report.rejection_summary,
            }
            print(json.dumps(payload, indent=2))
        else:
            print(report)

        if report.status == "failure":
            return 1
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
