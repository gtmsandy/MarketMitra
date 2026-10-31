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
        f"{api}/api/v1/stocks": [{"symbol": "TEST", "company_name": "Synthetic"}],
        f"{api}/api/v1/stocks?q=TEST": [{"symbol": "TEST"}],
        f"{api}/api/v1/stocks/TEST": {"symbol": "TEST", "ltp": 1.0},
        f"{api}/api/v1/stocks/TEST/history": [
            {"date": "2026-09-03", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
        ],
        f"{api}/api/v1/market/sectors": [],
        f"{api}/api/v1/market/heatmap": [],
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
        "sector-heatmap",
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
