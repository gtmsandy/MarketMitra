from datetime import datetime
import os
from pathlib import Path
from typing import Annotated, Callable, Literal

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import (
    get_database_url,
    get_market_data_source,
    validate_runtime_config,
)
from app.core.freshness import calculate_data_freshness
from app.core.market_schedule import get_market_status

router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["marketmitra-api"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    service: Literal["marketmitra-api"]


def check_runtime_readiness() -> None:
    """Validate required configuration, connectivity, and migration revision."""
    validate_runtime_config()
    if get_market_data_source() != "postgres":
        return

    from app.db.base import make_engine

    engine = make_engine(get_database_url())
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current_heads = set(
                MigrationContext.configure(connection).get_current_heads()
            )

        alembic_config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
        expected_heads = set(ScriptDirectory.from_config(alembic_config).get_heads())
        if current_heads != expected_heads:
            raise RuntimeError("Database migration revision is not current")
    finally:
        engine.dispose()


def get_readiness_checker() -> Callable[[], None]:
    return check_runtime_readiness


@router.get("/health/live", response_model=LivenessResponse)
def get_liveness() -> LivenessResponse:
    return LivenessResponse(status="ok", service="marketmitra-api")


@router.get("/health/ready", response_model=ReadinessResponse)
def get_readiness(
    checker: Annotated[Callable[[], None], Depends(get_readiness_checker)],
) -> ReadinessResponse:
    try:
        checker()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "service": "marketmitra-api"},
        ) from exc
    return ReadinessResponse(status="ready", service="marketmitra-api")


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
    market_status: Literal["OPEN", "CLOSED", "HALTED", "DATA_UNAVAILABLE", "STALE"]
    data_freshness: Literal["FRESH", "STALE", "UNKNOWN", "LIVE", "DELAYED", "HISTORICAL", "DATA_UNAVAILABLE"]
    market_snapshot_date: datetime | None = None
    last_ingestion: IngestionSummary | None = None
    provider: str = "unconfigured"
    enabled: bool = False
    configured: bool = False
    connection_status: str = "DISCONNECTED"
    failure_count: int = 0
    circuit_state: str = "CLOSED"
    market_snapshot_date = None


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    source = get_market_data_source()
    live_enabled = os.getenv("LIVE_MARKET_ENABLED", "false").lower() in {"1", "true", "yes"}
    provider_name = os.getenv("LIVE_MARKET_PROVIDER", "unconfigured")
    configured = bool(os.getenv("NEPSE_LIVE_API_URL")) or provider_name.lower() == "replay"
    market_status = get_market_status()

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
            market_snapshot_date=overview.last_updated,
            last_ingestion=None,
            provider=provider_name, enabled=live_enabled, configured=configured,
            connection_status="CONNECTED" if configured and live_enabled else "DISCONNECTED",
        )

    # MARKET_DATA_SOURCE is postgres: guarded connection check
    database_status: Literal["connected", "disconnected", "not_configured"]
    status: Literal["ok", "degraded"]
    data_freshness: Literal["FRESH", "STALE", "UNKNOWN"] = "UNKNOWN"
    last_ingestion: IngestionSummary | None = None
    market_snapshot_date = None

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
            market_snapshot_date = latest_captured_at
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
        market_snapshot_date=market_snapshot_date,
        provider=provider_name, enabled=live_enabled, configured=configured,
        connection_status="CONNECTED" if configured and live_enabled else "DISCONNECTED",
    )
