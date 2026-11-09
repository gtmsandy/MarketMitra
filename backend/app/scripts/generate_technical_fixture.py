"""Generate the deterministic synthetic history used by technical-analysis tests."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random

BASELINE_SHA256 = "7635e81de720d23573b571d3ccb862d5954672099509901b2da3bcb7dd9a537f"
DATASET_IDENTIFIER = "marketmitra-synthetic-technical-analysis-v1"
GENERATOR_VERSION = "technical-fixture-generator-v1"
SEED = 20261109
SESSION_COUNT = 120
END_DATE = date(2026, 9, 4)
OFFSET = timezone(timedelta(hours=5, minutes=45))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _baseline_path() -> Path:
    return _repo_root() / "provenance" / "fixtures" / "marketmitra-synthetic-staging-v1.json"


def _artifact_path() -> Path:
    return _repo_root() / "provenance" / "fixtures" / "marketmitra-synthetic-technical-analysis-v1.json"


def _manifest_path() -> Path:
    return _repo_root() / "provenance" / "technical-analysis-manifest.json"


def _canonical_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _load_baseline() -> dict:
    path = _baseline_path()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASELINE_SHA256:
        raise RuntimeError("the approved baseline fixture digest changed")
    return json.loads(raw.decode("utf-8"))


def trading_dates() -> list[date]:
    dates: list[date] = []
    current = END_DATE
    while len(dates) < SESSION_COUNT:
        if current.weekday() < 5:
            dates.append(current)
        current -= timedelta(days=1)
    return list(reversed(dates))


def _price_rows(instrument: dict, baseline_rows: list[dict], symbol_index: int) -> list[dict]:
    target = float(baseline_rows[0]["previous_close"])
    initial = round(target * (1.08 + symbol_index * 0.012), 2)
    rng = random.Random(SEED + symbol_index * 1009)
    rows: list[dict] = []
    previous_close = initial
    dates = trading_dates()
    for index, session_date in enumerate(dates):
        drift = (target / initial) ** (1 / (len(dates) - 1)) - 1
        close = previous_close * (1 + drift + rng.uniform(-0.0035, 0.0035))
        if index == len(dates) - 1:
            close = target
        close = round(max(close, 1.0), 2)
        opening = round(max(previous_close * (1 + rng.uniform(-0.003, 0.003)), 1.0), 2)
        high = round(max(opening, close) * (1 + rng.uniform(0.001, 0.006)), 2)
        low = round(min(opening, close) * (1 - rng.uniform(0.001, 0.006)), 2)
        high = max(high, opening, close)
        low = min(low, opening, close)
        volume = int(3500 + symbol_index * 450 + (index % 17) * 120 + rng.randint(0, 220))
        change = round(close - previous_close, 2)
        change_percent = round((change / previous_close) * 100, 4)
        rows.append(
            {
                "symbol": instrument["symbol"],
                "date": session_date.isoformat(),
                "open": opening,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "turnover": round(close * volume, 2),
                "previous_close": previous_close,
                "change": change,
                "change_percent": change_percent,
            }
        )
        previous_close = close
    return rows


def _snapshots(prices: list[dict]) -> list[dict]:
    by_date: dict[str, list[dict]] = {}
    for row in prices:
        by_date.setdefault(row["date"], []).append(row)
    previous_index = 1000.0
    snapshots: list[dict] = []
    for session_date in sorted(by_date):
        rows = by_date[session_date]
        average_change = sum(row["change_percent"] for row in rows) / len(rows)
        nepse_index = round(previous_index * (1 + (average_change * 0.35) / 100), 2)
        index_change = round(nepse_index - previous_index, 2)
        snapshots.append(
            {
                "nepse_index": nepse_index,
                "index_change": index_change,
                "index_change_percent": round((index_change / previous_index) * 100, 4),
                "turnover": round(sum(row["turnover"] for row in rows), 2),
                "total_volume": sum(row["volume"] for row in rows),
                "total_transactions": 600 + len(snapshots) * 7,
                "market_status": "Closed",
                "captured_at": datetime.combine(
                    date.fromisoformat(session_date), time(15, 0), tzinfo=OFFSET
                ).isoformat(),
            }
        )
        previous_index = nepse_index
    return snapshots


def build_fixture() -> tuple[dict, dict]:
    baseline = _load_baseline()
    baseline_by_symbol: dict[str, list[dict]] = {item["symbol"]: [] for item in baseline["instruments"]}
    for row in baseline["prices"]:
        baseline_by_symbol[row["symbol"]].append(row)

    prices: list[dict] = []
    for symbol_index, instrument in enumerate(baseline["instruments"]):
        prices.extend(_price_rows(instrument, baseline_by_symbol[instrument["symbol"]], symbol_index))

    fixture = {
        "schema_version": "1",
        "dataset_identifier": DATASET_IDENTIFIER,
        "description": "Deterministic synthetic weekday history for technical-analysis demonstrations; not NEPSE market data.",
        "attribution": "MarketMitra synthetic technical-analysis fixture",
        "generator_version": GENERATOR_VERSION,
        "generation_seed": SEED,
        "calendar_assumption": "Monday-Friday calendar only; no official NEPSE holiday calendar is modeled.",
        "instruments": baseline["instruments"],
        "snapshots": _snapshots(prices),
        "prices": prices,
        "preserved_baseline": {
            "identifier": baseline["dataset_identifier"],
            "sha256": BASELINE_SHA256,
            "instruments": baseline["instruments"],
            "snapshots": baseline["snapshots"],
            "prices": baseline["prices"],
        },
    }
    manifest = {
        "manifest_version": 1,
        "datasets": [
            {
                "dataset_identifier": DATASET_IDENTIFIER,
                "classification": "synthetic_demo",
                "source": "MarketMitra project-generated deterministic technical-analysis fixture",
                "publisher": "MarketMitra project",
                "source_reference": "provenance/fixtures/marketmitra-synthetic-technical-analysis-v1.json",
                "acquisition_timestamp": "2026-11-09T00:00:00Z",
                "observation_period": {
                    "start": trading_dates()[0].isoformat(),
                    "end": trading_dates()[-1].isoformat(),
                    "notes": "120 generated weekday sessions per symbol; the original v1 fixture is preserved separately and is not rewritten.",
                },
                "schema_version": "1",
                "artifact_path": "fixtures/marketmitra-synthetic-technical-analysis-v1.json",
                "sha256": "",
                "instrument_count": len(fixture["instruments"]),
                "price_observation_count": len(fixture["prices"]),
                "transformation_version": GENERATOR_VERSION,
                "attribution_requirements": "Label as MarketMitra synthetic technical-analysis data; never represent as NEPSE data",
                "storage_permission": "project_generated",
                "redistribution_public_display_permission": "project_generated",
                "license_or_contract_evidence_reference": "Project-generated fixture committed with the MarketMitra source repository",
                "authorization_status": "approved_synthetic",
                "publication_approved": True,
                "generator_version": GENERATOR_VERSION,
                "generation_seed": SEED,
                "session_count_per_instrument": SESSION_COUNT,
                "snapshot_count": len(fixture["snapshots"]),
                "baseline_fixture_identifier": baseline["dataset_identifier"],
                "baseline_fixture_sha256": BASELINE_SHA256,
                "preserved_observation_count": len(baseline["prices"]),
                "data_limitations": "Synthetic prices are for engineering demonstrations only; weekday generation does not model official NEPSE holidays or live market behavior.",
            }
        ],
    }
    artifact_bytes = _canonical_bytes(fixture)
    manifest["datasets"][0]["sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    return fixture, manifest


def write_fixture() -> tuple[Path, Path]:
    fixture, manifest = build_fixture()
    artifact_path = _artifact_path()
    manifest_path = _manifest_path()
    artifact_path.write_bytes(_canonical_bytes(fixture))
    manifest_path.write_bytes(_canonical_bytes(manifest))
    return artifact_path, manifest_path


if __name__ == "__main__":
    artifact, manifest = write_fixture()
    print(f"Wrote {artifact}")
    print(f"Wrote {manifest}")
