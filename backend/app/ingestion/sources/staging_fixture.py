"""Provenance-bound deterministic data source for isolated staging only."""

from dataclasses import dataclass
from datetime import datetime
import json
from math import isclose
from pathlib import Path
import re

from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord
from app.ingestion.sources.base import DataSource
from app.scripts.validate_provenance import validate_manifest

_SUPPORTED_SCHEMA_VERSION = "1"
_SYNTHETIC_SYMBOL = re.compile(r"^SYN[A-Z0-9]{2,17}$")


class StagingDatasetError(ValueError):
    """The staging artifact failed provenance or synthetic-data validation."""


@dataclass(frozen=True)
class StagingDataset:
    identifier: str
    instruments: list[RawInstrumentRecord]
    snapshots: list[RawSnapshotRecord]
    prices: dict[str, list[RawPriceRecord]]


def _require_synthetic_instrument(record: dict) -> RawInstrumentRecord:
    symbol = record.get("symbol")
    company = record.get("company_name")
    sector = record.get("sector")
    if not isinstance(symbol, str) or not _SYNTHETIC_SYMBOL.fullmatch(symbol):
        raise StagingDatasetError("fixture violates the synthetic symbol policy")
    if not isinstance(company, str) or not company.startswith("Synthetic "):
        raise StagingDatasetError(f"{symbol} must use an explicitly synthetic company name")
    if not isinstance(sector, str) or not sector.startswith("Synthetic "):
        raise StagingDatasetError(f"{symbol} must use an explicitly synthetic sector")
    if record.get("security_type") != "EQUITY":
        raise StagingDatasetError(f"{symbol} must be an EQUITY fixture instrument")
    return RawInstrumentRecord(symbol, company, sector, "EQUITY")


def _load_fixture(path: Path, manifest_entry: dict) -> StagingDataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StagingDatasetError(f"unable to read staging fixture: {exc}") from exc
    if not isinstance(payload, dict):
        raise StagingDatasetError("staging fixture root must be an object")
    if payload.get("schema_version") != _SUPPORTED_SCHEMA_VERSION:
        raise StagingDatasetError("unsupported staging fixture schema version")
    if payload.get("schema_version") != manifest_entry["schema_version"]:
        raise StagingDatasetError("fixture schema version does not match manifest")
    if payload.get("dataset_identifier") != manifest_entry["dataset_identifier"]:
        raise StagingDatasetError("fixture dataset identifier does not match manifest")

    raw_instruments = payload.get("instruments")
    raw_snapshots = payload.get("snapshots")
    raw_prices = payload.get("prices")
    if not all(isinstance(value, list) for value in (raw_instruments, raw_snapshots, raw_prices)):
        raise StagingDatasetError("fixture instruments, snapshots, and prices must be lists")

    instruments = [_require_synthetic_instrument(record) for record in raw_instruments]
    symbols = {record.symbol for record in instruments}
    if len(symbols) != len(instruments):
        raise StagingDatasetError("fixture instrument symbols must be unique")
    if len(instruments) != manifest_entry["instrument_count"]:
        raise StagingDatasetError("fixture instrument count does not match manifest")

    prices: dict[str, list[RawPriceRecord]] = {symbol: [] for symbol in symbols}
    seen_price_keys: set[tuple[str, str]] = set()
    for record in raw_prices:
        try:
            symbol = record["symbol"]
            date = record["date"]
            price = RawPriceRecord(
                symbol=symbol,
                date=date,
                open=record["open"], high=record["high"], low=record["low"],
                close=record["close"], volume=record["volume"], turnover=record["turnover"],
                change=record["change"], change_percent=record["change_percent"],
                previous_close=record["previous_close"],
            )
        except (KeyError, TypeError) as exc:
            raise StagingDatasetError(f"invalid fixture price record: {exc}") from exc
        if symbol not in symbols:
            raise StagingDatasetError(f"price references unknown synthetic symbol {symbol!r}")
        key = (symbol, date)
        if key in seen_price_keys:
            raise StagingDatasetError(f"duplicate fixture price for {symbol} on {date}")
        try:
            if not isclose(price.turnover, price.close * price.volume, abs_tol=0.01):
                raise StagingDatasetError(f"inconsistent turnover for {symbol} on {date}")
            if not isclose(price.change, price.close - price.previous_close, abs_tol=0.0001):
                raise StagingDatasetError(f"inconsistent change for {symbol} on {date}")
            if price.previous_close <= 0:
                raise StagingDatasetError(f"invalid previous close for {symbol} on {date}")
            expected_percent = round((price.change / price.previous_close) * 100, 4)
            if not isclose(price.change_percent, expected_percent, abs_tol=0.0001):
                raise StagingDatasetError(
                    f"inconsistent change percentage for {symbol} on {date}"
                )
        except (TypeError, ValueError) as exc:
            raise StagingDatasetError(f"invalid numeric data for {symbol} on {date}") from exc
        seen_price_keys.add(key)
        prices[symbol].append(price)
    if len(raw_prices) != manifest_entry["price_observation_count"]:
        raise StagingDatasetError("fixture price-observation count does not match manifest")

    snapshots: list[RawSnapshotRecord] = []
    for record in raw_snapshots:
        try:
            snapshots.append(RawSnapshotRecord(
                nepse_index=record["nepse_index"],
                index_change=record["index_change"],
                index_change_percent=record["index_change_percent"],
                turnover=record["turnover"], total_volume=record["total_volume"],
                total_transactions=record["total_transactions"],
                market_status=record["market_status"],
                captured_at=datetime.fromisoformat(record["captured_at"]),
            ))
        except (KeyError, TypeError, ValueError) as exc:
            raise StagingDatasetError(f"invalid fixture snapshot: {exc}") from exc
    if not snapshots:
        raise StagingDatasetError("fixture must contain at least one market snapshot")
    all_prices = [price for rows in prices.values() for price in rows]
    for snapshot in snapshots:
        snapshot_date = snapshot.captured_at.date().isoformat()
        daily = [price for price in all_prices if price.date == snapshot_date]
        if len(daily) != len(instruments):
            raise StagingDatasetError(f"incomplete common session for {snapshot_date}")
        if not isclose(snapshot.turnover, sum(price.turnover for price in daily), abs_tol=0.01):
            raise StagingDatasetError(f"inconsistent snapshot turnover for {snapshot_date}")
        if snapshot.total_volume != sum(price.volume for price in daily):
            raise StagingDatasetError(f"inconsistent snapshot volume for {snapshot_date}")

    return StagingDataset(manifest_entry["dataset_identifier"], instruments, snapshots, prices)


def load_staging_dataset(
    manifest_path: Path, *, require_publication_approved: bool = True
) -> StagingDataset:
    errors = validate_manifest(
        manifest_path, require_publication_approved=require_publication_approved
    )
    if errors:
        message = "; ".join(errors)
        if "not approved for publication" in message:
            raise StagingDatasetError(f"staging dataset is not approved: {message}")
        raise StagingDatasetError(message)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest["datasets"]) != 1:
        raise StagingDatasetError("staging manifest must describe exactly one dataset")
    entry = manifest["datasets"][0]
    fixture_path = (manifest_path.parent / entry["artifact_path"]).resolve()
    return _load_fixture(fixture_path, entry)


class StagingFixtureSource(DataSource):
    def __init__(self, dataset: StagingDataset) -> None:
        self._dataset = dataset

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
