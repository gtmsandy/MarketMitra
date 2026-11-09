"""Loader and validation rules for the extended technical-analysis fixture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path

from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord
from app.ingestion.sources.base import DataSource
from app.ingestion.sources.staging_fixture import StagingDataset, load_staging_dataset
from app.scripts.validate_provenance import validate_manifest

_DATASET_ID = "marketmitra-synthetic-technical-analysis-v1"
_GENERATOR_VERSION = "technical-fixture-generator-v1"
_BASELINE_ID = "marketmitra-synthetic-staging-v1"
_BASELINE_SHA256 = "7635e81de720d23573b571d3ccb862d5954672099509901b2da3bcb7dd9a537f"


class TechnicalFixtureError(ValueError):
    """The extended fixture failed an integrity, provenance, or compatibility check."""


@dataclass(frozen=True)
class TechnicalFixture:
    dataset: StagingDataset
    generator_version: str
    seed: int
    session_count_per_instrument: int
    baseline_fixture_sha256: str
    preserved_observation_count: int
    baseline_prices: tuple[dict, ...]
    baseline_snapshots: tuple[dict, ...]


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TechnicalFixtureError(f"unable to read fixture metadata: {exc}") from exc
    if not isinstance(value, dict):
        raise TechnicalFixtureError("technical fixture root must be an object")
    return value


def _baseline_path(manifest_path: Path, baseline_identifier: str) -> Path:
    expected = manifest_path.parent / "fixtures" / f"{baseline_identifier}.json"
    if not expected.is_file():
        raise TechnicalFixtureError("approved baseline fixture is missing")
    return expected


def _validate_preserved_baseline(fixture: dict, manifest_path: Path, entry: dict) -> None:
    baseline_path = _baseline_path(manifest_path, entry["baseline_fixture_identifier"])
    baseline_bytes = baseline_path.read_bytes()
    baseline_digest = hashlib.sha256(baseline_bytes).hexdigest()
    if baseline_digest != _BASELINE_SHA256 or baseline_digest != entry["baseline_fixture_sha256"]:
        raise TechnicalFixtureError("approved baseline fixture digest changed")
    baseline = json.loads(baseline_bytes.decode("utf-8"))
    preserved = fixture.get("preserved_baseline")
    if not isinstance(preserved, dict):
        raise TechnicalFixtureError("fixture must preserve the original baseline metadata")
    if preserved.get("identifier") != baseline["dataset_identifier"]:
        raise TechnicalFixtureError("preserved baseline identifier does not match")
    if preserved.get("sha256") != baseline_digest:
        raise TechnicalFixtureError("preserved baseline digest does not match")
    for field in ("instruments", "snapshots", "prices"):
        if preserved.get(field) != baseline.get(field):
            raise TechnicalFixtureError(f"preserved baseline {field} were altered")
    if len(preserved["prices"]) != entry["preserved_observation_count"]:
        raise TechnicalFixtureError("preserved baseline observation count does not match")


def _validate_generated_rows(dataset: StagingDataset, entry: dict, baseline: dict) -> None:
    expected_sessions = entry["session_count_per_instrument"]
    generated_keys: set[tuple[str, str]] = set()
    baseline_keys = {(row["symbol"], row["date"]) for row in baseline["prices"]}
    for symbol, rows in dataset.prices.items():
        if len(rows) != expected_sessions:
            raise TechnicalFixtureError(
                f"{symbol} has {len(rows)} generated sessions; expected {expected_sessions}"
            )
        dates = [row.date for row in rows]
        if dates != sorted(dates) or len(set(dates)) != len(dates):
            raise TechnicalFixtureError(f"{symbol} generated sessions are not chronological and unique")
        for row in rows:
            parsed = date.fromisoformat(row.date)
            if parsed.weekday() >= 5:
                raise TechnicalFixtureError(f"generated session {row.symbol} {row.date} falls on a weekend")
            key = (row.symbol, row.date)
            if key in baseline_keys:
                raise TechnicalFixtureError(f"generated session overlaps baseline {row.symbol} {row.date}")
            if key in generated_keys:
                raise TechnicalFixtureError(f"duplicate generated session {row.symbol} {row.date}")
            generated_keys.add(key)
            if any(value is None for value in (row.open, row.high, row.low, row.close, row.volume, row.turnover)):
                raise TechnicalFixtureError(f"generated session {row.symbol} {row.date} has missing OHLCV data")
            if row.high < max(row.open, row.close) or row.low > min(row.open, row.close):
                raise TechnicalFixtureError(f"generated session {row.symbol} {row.date} violates OHLC bounds")
            if min(row.open, row.high, row.low, row.close) <= 0:
                raise TechnicalFixtureError(f"generated session {row.symbol} {row.date} has a non-positive price")
            if row.volume < 0 or row.turnover < 0:
                raise TechnicalFixtureError(f"generated session {row.symbol} {row.date} has negative activity")

    if len(dataset.snapshots) != entry["snapshot_count"]:
        raise TechnicalFixtureError("generated snapshot count does not match the manifest")


def load_technical_dataset(
    manifest_path: Path, *, require_publication_approved: bool = True
) -> TechnicalFixture:
    errors = validate_manifest(manifest_path, require_publication_approved=require_publication_approved)
    if errors:
        raise TechnicalFixtureError("; ".join(errors))
    manifest = _read_json(manifest_path)
    if len(manifest["datasets"]) != 1:
        raise TechnicalFixtureError("technical-analysis manifest must describe exactly one dataset")
    entry = manifest["datasets"][0]
    if entry.get("dataset_identifier") != _DATASET_ID:
        raise TechnicalFixtureError("unexpected technical-analysis dataset identifier")
    if entry.get("generator_version") != _GENERATOR_VERSION:
        raise TechnicalFixtureError("unsupported technical fixture generator")
    if not isinstance(entry.get("generation_seed"), int):
        raise TechnicalFixtureError("generation seed must be an integer")
    if not isinstance(entry.get("session_count_per_instrument"), int) or entry["session_count_per_instrument"] < 2:
        raise TechnicalFixtureError("session_count_per_instrument must be at least two")
    fixture_path = (manifest_path.parent / entry["artifact_path"]).resolve()
    fixture = _read_json(fixture_path)
    _validate_preserved_baseline(fixture, manifest_path, entry)
    baseline = _read_json(_baseline_path(manifest_path, entry["baseline_fixture_identifier"]))
    dataset = load_staging_dataset(manifest_path, require_publication_approved=require_publication_approved)
    _validate_generated_rows(dataset, entry, baseline)
    return TechnicalFixture(
        dataset=dataset,
        generator_version=entry["generator_version"],
        seed=entry["generation_seed"],
        session_count_per_instrument=entry["session_count_per_instrument"],
        baseline_fixture_sha256=entry["baseline_fixture_sha256"],
        preserved_observation_count=entry["preserved_observation_count"],
        baseline_prices=tuple(baseline["prices"]),
        baseline_snapshots=tuple(baseline["snapshots"]),
    )


class TechnicalFixtureSource(DataSource):
    """DataSource adapter for the generated rows only; baseline rows stay untouched."""

    def __init__(self, fixture: TechnicalFixture) -> None:
        self._dataset = fixture.dataset

    @property
    def name(self) -> str:
        return self._dataset.identifier

    def fetch_instruments(self) -> list[RawInstrumentRecord]:
        return list(self._dataset.instruments)

    def fetch_snapshot(self) -> RawSnapshotRecord:
        return self._dataset.snapshots[-1]

    def fetch_snapshots(self) -> list[RawSnapshotRecord]:
        return list(self._dataset.snapshots)

    def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
        return list(self._dataset.prices.get(symbol, []))
