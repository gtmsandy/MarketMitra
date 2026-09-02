from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.db.models import IngestionRun
from app.ingestion.models import IngestionReport


class IngestionRunRepository(ABC):
    @abstractmethod
    def record(self, report: IngestionReport) -> IngestionRun:
        """Persist an IngestionReport as an IngestionRun audit row."""

    @abstractmethod
    def get_latest(self) -> IngestionRun | None:
        """Return the most recent ingestion run, or None."""


class PostgresIngestionRunRepository(IngestionRunRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, report: IngestionReport) -> IngestionRun:
        run = IngestionRun(
            source=report.source,
            started_at=report.started_at,
            finished_at=report.finished_at,
            status=report.status,
            instruments_upserted=report.instruments_upserted,
            snapshots_inserted=report.snapshots_inserted,
            snapshots_skipped=report.snapshots_skipped,
            prices_accepted=report.prices_accepted,
            prices_skipped=report.prices_skipped,
            prices_replaced=report.prices_replaced,
            prices_rejected=report.prices_rejected,
            error_detail=report.error_detail,
        )
        self._session.add(run)
        self._session.flush()
        return run

    def get_latest(self) -> IngestionRun | None:
        return (
            self._session.query(IngestionRun)
            .order_by(IngestionRun.started_at.desc())
            .first()
        )
