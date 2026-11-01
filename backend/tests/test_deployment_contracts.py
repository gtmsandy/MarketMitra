"""Deployment provenance and smoke-test contracts."""

from hashlib import sha256
import json
from pathlib import Path

import pytest


def _manifest(artifact: Path, *, classification: str = "synthetic_demo") -> dict:
    digest = sha256(artifact.read_bytes()).hexdigest()
    return {
        "manifest_version": 1,
        "datasets": [
            {
                "dataset_identifier": "marketmitra-demo-v1",
                "classification": classification,
                "source": "MarketMitra deterministic fixture",
                "publisher": "MarketMitra project",
                "source_reference": "backend/tests/fixtures/demo.json",
                "acquisition_timestamp": "2026-11-01T00:00:00Z",
                "observation_period": {
                    "start": "2026-09-03",
                    "end": "2026-09-03",
                    "notes": "Synthetic observations only",
                },
                "schema_version": "1",
                "artifact_path": str(artifact),
                "sha256": digest,
                "transformation_version": "none",
                "attribution_requirements": "MarketMitra synthetic demo data",
                "storage_permission": "project_generated",
                "redistribution_public_display_permission": "project_generated",
                "license_or_contract_evidence_reference": "project-generated synthetic fixture",
                "authorization_status": "approved_synthetic",
                "publication_approved": True,
                "instrument_count": 2,
                "price_observation_count": 4,
            }
        ],
    }


def test_provenance_manifest_accepts_verified_synthetic_dataset(tmp_path: Path) -> None:
    from app.scripts.validate_provenance import validate_manifest

    artifact = tmp_path / "demo.json"
    artifact.write_text('{"kind":"synthetic"}\n', encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(artifact)), encoding="utf-8")

    assert validate_manifest(manifest_path, require_publication_approved=True) == []


def test_provenance_manifest_blocks_unknown_rights_from_publication(tmp_path: Path) -> None:
    from app.scripts.validate_provenance import validate_manifest

    artifact = tmp_path / "unknown.json"
    artifact.write_text("{}\n", encoding="utf-8")
    manifest = _manifest(artifact, classification="unknown_rights")
    manifest["datasets"][0]["authorization_status"] = "unknown"
    manifest["datasets"][0]["publication_approved"] = True
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_manifest(manifest_path, require_publication_approved=True)

    assert any("unknown_rights" in error for error in errors)


def test_authorized_historical_manifest_requires_explicit_permissions(tmp_path: Path) -> None:
    from app.scripts.validate_provenance import validate_manifest

    artifact = tmp_path / "historical.json"
    artifact.write_text("{}\n", encoding="utf-8")
    manifest = _manifest(artifact, classification="authorized_historical")
    dataset = manifest["datasets"][0]
    dataset["authorization_status"] = "approved_historical"
    dataset["storage_permission"] = "unknown"
    dataset["redistribution_public_display_permission"] = "unknown"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_manifest(manifest_path, require_publication_approved=True)

    assert any("explicit granted storage and display permissions" in error for error in errors)


def test_provenance_manifest_detects_integrity_mismatch(tmp_path: Path) -> None:
    from app.scripts.validate_provenance import validate_manifest

    artifact = tmp_path / "demo.json"
    artifact.write_text("{}\n", encoding="utf-8")
    manifest = _manifest(artifact)
    manifest["datasets"][0]["sha256"] = "0" * 64
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert any("SHA-256 mismatch" in error for error in validate_manifest(manifest_path))


def test_provenance_manifest_rejects_missing_fixture(tmp_path: Path) -> None:
    from app.scripts.validate_provenance import validate_manifest

    missing = tmp_path / "missing.json"
    missing.write_text("{}\n", encoding="utf-8")
    manifest = _manifest(missing)
    missing.unlink()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert any("unreadable" in error for error in validate_manifest(manifest_path))


def test_provenance_manifest_requires_declared_dataset_counts(tmp_path: Path) -> None:
    from app.scripts.validate_provenance import validate_manifest

    artifact = tmp_path / "demo.json"
    artifact.write_text("{}\n", encoding="utf-8")
    manifest = _manifest(artifact)
    del manifest["datasets"][0]["instrument_count"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert any("instrument_count" in error for error in validate_manifest(manifest_path))


def test_committed_staging_fixture_matches_manifest_and_synthetic_policy() -> None:
    from app.ingestion.sources.staging_fixture import load_staging_dataset

    repository_root = Path(__file__).resolve().parents[2]
    dataset = load_staging_dataset(
        repository_root / "provenance" / "deployment-manifest.json",
        require_publication_approved=True,
    )

    assert dataset.identifier == "marketmitra-synthetic-staging-v1"
    assert len(dataset.instruments) == 6
    assert sum(len(prices) for prices in dataset.prices.values()) == 24
    assert {instrument.sector for instrument in dataset.instruments} == {
        "Synthetic Banking",
        "Synthetic Energy",
        "Synthetic Manufacturing",
    }
    assert all(instrument.symbol.startswith("SYN") for instrument in dataset.instruments)
    prices = [price for rows in dataset.prices.values() for price in rows]
    for price in prices:
        assert price.turnover == pytest.approx(price.close * price.volume, abs=0.01)
        assert price.change == pytest.approx(price.close - price.previous_close, abs=0.0001)
        expected_percent = round((price.change / price.previous_close) * 100, 4)
        assert price.change_percent == pytest.approx(expected_percent, abs=0.0001)
    for snapshot in dataset.snapshots:
        day = snapshot.captured_at.date().isoformat()
        daily = [price for price in prices if price.date == day]
        assert snapshot.turnover == pytest.approx(sum(price.turnover for price in daily), abs=0.01)
        assert snapshot.total_volume == sum(price.volume for price in daily)


def test_staging_fixture_rejects_unapproved_manifest(tmp_path: Path) -> None:
    from app.ingestion.sources.staging_fixture import StagingDatasetError, load_staging_dataset

    artifact = tmp_path / "fixture.json"
    artifact.write_text('{"schema_version":"1","dataset_identifier":"x","instruments":[],"snapshots":[],"prices":[]}\n', encoding="utf-8")
    manifest = _manifest(artifact)
    manifest["datasets"][0]["publication_approved"] = False
    manifest["datasets"][0]["authorization_status"] = "pending"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(StagingDatasetError, match="not approved"):
        load_staging_dataset(manifest_path, require_publication_approved=True)


def test_staging_fixture_rejects_real_data_identifier(tmp_path: Path) -> None:
    from app.ingestion.sources.staging_fixture import StagingDatasetError, load_staging_dataset

    artifact = tmp_path / "fixture.json"
    artifact.write_text(
        json.dumps({
            "schema_version": "1",
            "dataset_identifier": "marketmitra-demo-v1",
            "instruments": [{"symbol": "NABIL", "company_name": "Synthetic Company", "sector": "Synthetic Banking", "security_type": "EQUITY"}],
            "snapshots": [],
            "prices": [],
        }),
        encoding="utf-8",
    )
    manifest = _manifest(artifact)
    manifest["datasets"][0]["instrument_count"] = 1
    manifest["datasets"][0]["price_observation_count"] = 0
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(StagingDatasetError, match="synthetic symbol policy"):
        load_staging_dataset(manifest_path, require_publication_approved=True)


def test_committed_deployment_manifest_is_publication_eligible() -> None:
    from app.scripts.validate_provenance import validate_manifest

    repository_root = Path(__file__).resolve().parents[2]
    manifest = repository_root / "provenance" / "deployment-manifest.json"

    assert validate_manifest(manifest, require_publication_approved=True) == []


def test_api_container_contract_is_non_root_and_does_not_auto_migrate() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    dockerfile = (repository_root / "Dockerfile").read_text(encoding="utf-8")
    command = next(
        line for line in dockerfile.splitlines() if line.startswith("CMD ")
    )

    assert dockerfile.startswith(
        "FROM python:3.14.0-slim-bookworm@sha256:"
        "d13fa0424035d290decef3d575cea23d1b7d5952cdf429df8f5542c71e961576\n"
    )
    assert "USER marketmitra" in dockerfile
    assert '"--workers", "1"' in command
    assert "COPY provenance ./provenance" in dockerfile
    assert "alembic" not in command.lower()
    assert "seed" not in command.lower()
    assert "ingest" not in command.lower()


class _FakeResponse:
    def __init__(self, payload, content_type: str = "application/json") -> None:
        self._body = (
            json.dumps(payload).encode()
            if content_type == "application/json"
            else payload.encode()
        )
        self.headers = {"Content-Type": content_type}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_smoke_tests_cover_historical_demo_contracts() -> None:
    from app.scripts.smoke_test import run_smoke_tests

    api = "http://127.0.0.1:8000"
    responses = {
        f"{api}/api/v1/health/live": {"status": "ok", "service": "marketmitra-api"},
        f"{api}/api/v1/health/ready": {"status": "ready", "service": "marketmitra-api"},
        f"{api}/api/v1/health": {"enabled": False, "market_data_source": "postgres"},
        f"{api}/api/v1/market/overview": {
            "nepse_index": 1.0,
            "market_status": "Closed",
            "last_updated": "2026-09-03T00:00:00Z",
            "data_freshness": "HISTORICAL",
        },
        f"{api}/api/v1/stocks": [{"symbol": "SYNBANKA", "company_name": "Synthetic Horizon Bank"}],
        f"{api}/api/v1/stocks?q=SYNBANKA": [{"symbol": "SYNBANKA"}],
        f"{api}/api/v1/stocks/SYNBANKA": {"symbol": "SYNBANKA", "ltp": 105.0},
        f"{api}/api/v1/stocks/SYNBANKA/history": [
            {"date": "2026-09-08", "open": 102, "high": 103, "low": 99, "close": 100, "volume": 5100},
            {"date": "2026-09-09", "open": 100, "high": 106, "low": 99, "close": 105, "volume": 6000},
        ],
        f"{api}/api/v1/market/gainers": [{"symbol": "SYNBANKA", "change_percent": 5.0}],
        f"{api}/api/v1/market/losers": [{"symbol": "SYNBANKB", "change_percent": -4.0}],
        f"{api}/api/v1/market/most-active": [{"symbol": "SYNBANKB", "turnover": 1344000.0}],
        f"{api}/api/v1/market/sectors": [
            {"sector": "Synthetic Banking", "stock_count": 2},
            {"sector": "Synthetic Energy", "stock_count": 2},
            {"sector": "Synthetic Manufacturing", "stock_count": 2},
        ],
        f"{api}/api/v1/market/heatmap": [
            {"symbol": "SYNBANKB", "turnover": 1344000.0},
            {"symbol": "SYNENERA", "turnover": 688500.0},
            {"symbol": "SYNMAKEB", "turnover": 677710.0},
            {"symbol": "SYNBANKA", "turnover": 630000.0},
            {"symbol": "SYNENERB", "turnover": 620160.0},
            {"symbol": "SYNMAKEA", "turnover": 449820.0},
        ],
    }

    def opener(request, timeout):
        url = request.full_url
        if url == "http://127.0.0.1:4173/":
            return _FakeResponse('<div id="root"></div>', "text/html")
        return _FakeResponse(responses[url])

    checks = run_smoke_tests(
        api_base_url=api,
        frontend_url="http://127.0.0.1:4173",
        timeout=3,
        opener=opener,
    )

    assert checks == [
        "liveness",
        "readiness",
        "historical-demo-label",
        "market-overview",
        "stock-list-search",
        "stock-detail-history",
        "market-movers",
        "sector-analytics",
        "heatmap",
        "frontend",
    ]


def test_smoke_tests_refuse_remote_targets_without_explicit_permission() -> None:
    from app.scripts.smoke_test import SmokeTestError, run_smoke_tests

    with pytest.raises(SmokeTestError, match="--allow-remote"):
        run_smoke_tests(
            api_base_url="https://api.example.com",
            frontend_url="https://example.com",
            opener=lambda *_args, **_kwargs: None,
        )


def test_smoke_tests_reject_base_urls_with_embedded_credentials() -> None:
    from app.scripts.smoke_test import SmokeTestError, run_smoke_tests

    with pytest.raises(SmokeTestError, match="origin without credentials"):
        run_smoke_tests(
            api_base_url="http://user:secret@127.0.0.1:8000",
            frontend_url="http://127.0.0.1:4173",
            opener=lambda *_args, **_kwargs: None,
        )
