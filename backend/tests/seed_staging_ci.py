"""Load the approved staging fixture only into the confirmed disposable CI DB."""

from pathlib import Path

from app.db.base import make_session_factory
from app.ingestion.service import IngestionService
from app.ingestion.sources.staging_fixture import StagingFixtureSource, load_staging_dataset
from app.scripts.seed_staging_data import _verify_report
from tests.postgres_ci import require_disposable_ci_database


def main() -> None:
    database_url = require_disposable_ci_database()
    manifest = Path(__file__).resolve().parents[2] / "provenance" / "deployment-manifest.json"
    dataset = load_staging_dataset(manifest, require_publication_approved=True)
    with make_session_factory(database_url)() as session:
        report = IngestionService(StagingFixtureSource(dataset), session).run()
    _verify_report(report, dataset, expected_status="success")
    print(report)


if __name__ == "__main__":
    main()
