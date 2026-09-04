from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_database_url, get_market_data_source
from app.core.freshness import calculate_data_freshness
from app.core.market_schedule import get_market_status

router = APIRouter(tags=["health"])


class IngestionSummary(BaseModel):
    source: str
    status: str
    finished_at: datetime
    prices_accepted: int = 0
    prices_rejected: int = 0


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["marketmitra-api"]
    market_data_source: str
    database_status: Literal["connected", "disconnected", "not_configured"]
    market_status: Literal["OPEN", "CLOSED"]
    data_freshness: Literal["FRESH", "STALE", "UNKNOWN"]
    last_ingestion: IngestionSummary | None = None


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    source = get_market_data_source()
    market_status: Literal["OPEN", "CLOSED"] = (
        "OPEN" if get_market_status() == "OPEN" else "CLOSED"
    )

    if source == "mock":
        from app.providers.mock_market import MockMarketProvider

        mock_provider = MockMarketProvider()
        overview = mock_provider.get_market_overview()
        freshness: Literal["FRESH", "STALE", "UNKNOWN"] = (
            calculate_data_freshness(overview.last_updated)  # type: ignore[assignment]
        )

        return HealthResponse(
            status="ok",
            service="marketmitra-api",
            market_data_source="mock",
            database_status="not_configured",
            market_status=market_status,
            data_freshness=freshness,
            last_ingestion=None,
        )

    # MARKET_DATA_SOURCE is postgres: guarded connection check
    database_status: Literal["connected", "disconnected", "not_configured"]
    status: Literal["ok", "degraded"]
    data_freshness: Literal["FRESH", "STALE", "UNKNOWN"] = "UNKNOWN"
    last_ingestion: IngestionSummary | None = None

    try:
        from app.db.base import make_session_factory
        from app.repositories.ingestion_run_repository import PostgresIngestionRunRepository
        from app.repositories.market_repository import PostgresMarketSnapshotRepository

        db_url = get_database_url()
        factory = make_session_factory(db_url)
        with factory() as session:
            session.execute(text("SELECT 1"))
            database_status = "connected"
            status = "ok"

            snapshot_repo = PostgresMarketSnapshotRepository(session)
            latest_snapshot = snapshot_repo.get_latest()
            latest_captured_at = (
                latest_snapshot.captured_at if latest_snapshot is not None else None
            )
            data_freshness = calculate_data_freshness(latest_captured_at)  # type: ignore[assignment]

            runs_repo = PostgresIngestionRunRepository(session)
            latest_run = runs_repo.get_latest()
            if latest_run is not None:
                last_ingestion = IngestionSummary(
                    source=latest_run.source,
                    status=latest_run.status,
                    finished_at=latest_run.finished_at,
                    prices_accepted=latest_run.prices_accepted,
                    prices_rejected=latest_run.prices_rejected,
                )
    except Exception:
        status = "degraded"
        database_status = "disconnected"
        data_freshness = "UNKNOWN"
        last_ingestion = None

    return HealthResponse(
        status=status,
        service="marketmitra-api",
        market_data_source="postgres",
        database_status=database_status,
        market_status=market_status,
        data_freshness=data_freshness,
        last_ingestion=last_ingestion,
    )
