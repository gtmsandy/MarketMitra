"""CsvDataSource — generic, reusable CSV ingestion adapter.

Implements the DataSource abstraction to ingest authentic multi-symbol NEPSE
historical stock datasets and optional NEPSE index datasets without modifying
source files.
"""
import csv
import os
from datetime import date, datetime, time
from pathlib import Path

from app.core.market_schedule import KATHMANDU_TZ
from app.ingestion.models import (
    RawInstrumentRecord,
    RawPriceRecord,
    RawSnapshotRecord,
)
from app.ingestion.sources.base import DataSource


def _normalize_header(col: str) -> str:
    """Normalize header by trimming, lowercasing, and replacing underscores with spaces."""
    return col.strip().lower().replace("_", " ")


def _parse_float(val: str | None) -> float | None:
    """Parse float from string, handling commas, percent signs, and null placeholders."""
    if val is None:
        return None
    clean = val.replace(",", "").replace("%", "").strip()
    if not clean or clean.lower() in ("null", "none", "nan", "na", "-", "--"):
        return None
    try:
        return float(clean)
    except ValueError:
        return None


def _parse_int(val: str | None) -> int | None:
    """Parse integer from string or float string (e.g. '1111.0' -> 1111)."""
    f = _parse_float(val)
    return int(f) if f is not None else None


class CsvDataSource(DataSource):
    """Generic CSV data source for stock price history and market snapshots."""

    def __init__(
        self,
        stock_file: str | Path,
        index_file: str | Path | None = None,
    ) -> None:
        self._stock_path = Path(stock_file)
        self._index_path = Path(index_file) if index_file else None

        self._instruments: dict[str, RawInstrumentRecord] = {}
        self._prices_by_symbol: dict[str, list[RawPriceRecord]] = {}
        self._snapshots: list[RawSnapshotRecord] = []

        self._load_stocks()
        if self._index_path and self._index_path.exists():
            self._load_index()

    @property
    def name(self) -> str:
        return "csv"

    def fetch_instruments(self) -> list[RawInstrumentRecord]:
        return list(self._instruments.values())

    def fetch_snapshot(self) -> RawSnapshotRecord | None:
        if self._snapshots:
            return self._snapshots[-1]
        return None

    def fetch_snapshots(self) -> list[RawSnapshotRecord]:
        return list(self._snapshots)

    def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
        return list(self._prices_by_symbol.get(symbol.upper().strip(), []))

    # ------------------------------------------------------------------
    # Stock Dataset Parsing
    # ------------------------------------------------------------------

    def _load_stocks(self) -> None:
        if not self._stock_path.exists():
            raise FileNotFoundError(f"Stock file or directory not found: {self._stock_path}")

        files_to_process: list[Path] = []
        if self._stock_path.is_file():
            files_to_process = [self._stock_path]
        elif self._stock_path.is_dir():
            for root, _, files in os.walk(self._stock_path):
                for f in files:
                    if f.lower().endswith(".csv"):
                        files_to_process.append(Path(root) / f)
        files_to_process.sort()

        seen_keys: set[tuple[str, str]] = set()
        has_subdirs = self._stock_path.is_dir() and any(
            p.is_dir() for p in self._stock_path.iterdir()
        )

        for file_path in files_to_process:
            rel_parent = file_path.parent
            if self._stock_path.is_dir():
                if rel_parent != self._stock_path:
                    raw_folder_sector = rel_parent.name
                elif not has_subdirs:
                    raw_folder_sector = self._stock_path.name
                else:
                    raw_folder_sector = None
            else:
                raw_folder_sector = None

            if raw_folder_sector == "Promoter_Share":
                security_type_from_folder = "PROMOTER_SHARE"
                sector_from_folder = None
            elif raw_folder_sector == "Corporate_Debentures":
                security_type_from_folder = "DEBENTURE"
                sector_from_folder = None
            elif raw_folder_sector == "Mutual_Fund":
                security_type_from_folder = "MUTUAL_FUND"
                sector_from_folder = None
            elif raw_folder_sector == "Government_Bonds":
                security_type_from_folder = "GOVERNMENT_BOND"
                sector_from_folder = None
            elif raw_folder_sector == "Preference_Share":
                security_type_from_folder = "PREFERENCE_SHARE"
                sector_from_folder = None
            else:
                security_type_from_folder = "EQUITY"
                sector_from_folder = (
                    raw_folder_sector.replace("_", " ").strip()
                    if raw_folder_sector
                    else None
                )
            sym_from_filename = file_path.stem.upper().strip()
            with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                rdr = csv.reader(fp)
                header = next(rdr, None)
                if not header:
                    continue

                normalized_header = [_normalize_header(c) for c in header]

                def find_idx(*aliases: str) -> int | None:
                    for a in aliases:
                        norm_alias = _normalize_header(a)
                        if norm_alias in normalized_header:
                            return normalized_header.index(norm_alias)
                    return None

                date_idx = find_idx("date", "published_date", "trade_date", "businessdate", "transactiondate")
                sym_idx = find_idx("symbol", "ticker", "stocksymbol", "securityid", "security")
                open_idx = find_idx("open", "open_price", "openingprice")
                high_idx = find_idx("high", "high_price", "maxprice")
                low_idx = find_idx("low", "low_price", "minprice")
                close_idx = find_idx("close", "close_price", "ltp", "lasttradedprice")
                vol_idx = find_idx("volume", "traded_quantity", "tradedshares", "totaltradedquantity", "sharevolume", "qty")
                turnover_idx = find_idx("turnover", "traded_amount", "totaltradedamount", "totalamount", "totalturnover")
                pct_idx = find_idx("% change", "change_percent", "percent change", "pct_change", "perchange", "percentage change")
                comp_idx = find_idx("company_name", "company", "security_name", "name", "stockname")
                sector_idx = find_idx("sector", "sector_name", "industry", "category")

                if date_idx is None or close_idx is None:
                    continue

                for row in rdr:
                    if not row or not any(row):
                        continue

                    date_val = row[date_idx].strip() if date_idx < len(row) else ""
                    if not date_val:
                        continue

                    # Resolve symbol: prefer column value if present, fallback to filename stem
                    if sym_idx is not None and sym_idx < len(row) and row[sym_idx].strip():
                        symbol = row[sym_idx].upper().strip()
                    else:
                        symbol = sym_from_filename

                    if not symbol:
                        continue

                    # First-seen deduplication on (symbol, date)
                    key = (symbol, date_val)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    # Parse prices
                    c = _parse_float(row[close_idx]) if close_idx < len(row) else None
                    if c is None:
                        continue

                    o = _parse_float(row[open_idx]) if open_idx is not None and open_idx < len(row) else None
                    h = _parse_float(row[high_idx]) if high_idx is not None and high_idx < len(row) else None
                    l = _parse_float(row[low_idx]) if low_idx is not None and low_idx < len(row) else None
                    # Preserve missing values for the validator; never substitute.
                    # Persisted rows with required fields missing are rejected there.
                    if any(value is not None and value <= 0 for value in (o, h, l, c)):
                        continue
                    v = _parse_int(row[vol_idx]) if vol_idx is not None and vol_idx < len(row) else None
                    t = _parse_float(row[turnover_idx]) if turnover_idx is not None and turnover_idx < len(row) else None
                    if c is not None and c <= 0:
                        continue

                    # Company name and sector
                    company_name = (
                        row[comp_idx].strip()
                        if comp_idx is not None and comp_idx < len(row) and row[comp_idx].strip()
                        else symbol
                    )
                    raw_sector = (
                        row[sector_idx].strip()
                        if sector_idx is not None and sector_idx < len(row) and row[sector_idx].strip()
                        else sector_from_folder
                    )
                    sector = (
                        raw_sector.replace("_", " ").strip()
                        if raw_sector
                        else None
                    )

                    # Ensure instrument record
                    if symbol not in self._instruments:
                        self._instruments[symbol] = RawInstrumentRecord(
                            symbol=symbol,
                            company_name=company_name,
                            sector=sector,
                            security_type=security_type_from_folder,
                        )

                    if symbol not in self._prices_by_symbol:
                        self._prices_by_symbol[symbol] = []

                    # Store parsed price point
                    pct_val = _parse_float(row[pct_idx]) if pct_idx is not None and pct_idx < len(row) else None
                    self._prices_by_symbol[symbol].append(
                        RawPriceRecord(
                            symbol=symbol,
                            date=date_val,
                            open=o,
                            high=h,
                            low=l,
                            close=c,
                            volume=v,
                            turnover=t,
                            change=0.0,
                            change_percent=pct_val if pct_val is not None else 0.0,
                            previous_close=c,
                        )
                    )

        # Post-process chronological order and sequential change / previous_close per symbol
        for sym, price_records in self._prices_by_symbol.items():
            price_records.sort(key=lambda p: p.date)
            for i, p in enumerate(price_records):
                if i > 0:
                    prev = price_records[i - 1].close
                    if prev is None or p.close is None:
                        continue
                    p.previous_close = prev
                    p.change = round(p.close - prev, 4)
                    if p.change_percent == 0.0 and prev > 0:
                        p.change_percent = round((p.change / prev) * 100, 4)
                else:
                    if p.open is None or p.close is None:
                        continue
                    p.previous_close = p.open
                    p.change = round(p.close - p.open, 4)
                    if p.change_percent == 0.0 and p.open > 0:
                        p.change_percent = round((p.change / p.open) * 100, 4)

    # ------------------------------------------------------------------
    # Index Dataset Parsing
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        if not self._index_path or not self._index_path.exists():
            return

        with open(self._index_path, "r", encoding="utf-8", errors="replace") as fp:
            rdr = csv.reader(fp)
            header = next(rdr, None)
            if not header:
                return

            normalized_header = [_normalize_header(c) for c in header]

            def find_idx(*aliases: str) -> int | None:
                for a in aliases:
                    norm_alias = _normalize_header(a)
                    if norm_alias in normalized_header:
                        return normalized_header.index(norm_alias)
                return None

            date_idx = find_idx("date", "published_date", "trade_date", "businessdate")
            index_idx = find_idx("index value", "nepse_index", "index", "close", "nepse index")
            change_idx = find_idx("absolute change", "index_change", "change", "pointchange", "net_change")
            pct_idx = find_idx("percentage change", "index_change_percent", "change_percent", "pct_change", "change(%)", "perchange")
            turnover_idx = find_idx("turnover", "market_turnover", "total_turnover", "traded_amount")
            vol_idx = find_idx("volume", "total_volume", "total_shares", "traded_quantity")
            tx_idx = find_idx("transactions", "total_transactions", "trades", "total_trades")

            if date_idx is None or index_idx is None:
                return

            seen_dates: set[str] = set()

            for row in rdr:
                if not row or not any(row):
                    continue

                date_val = row[date_idx].strip() if date_idx < len(row) else ""
                if not date_val or date_val in seen_dates:
                    continue

                index_val = _parse_float(row[index_idx]) if index_idx < len(row) else None
                if index_val is None or index_val <= 0:
                    continue

                seen_dates.add(date_val)

                chg = _parse_float(row[change_idx]) if change_idx is not None and change_idx < len(row) else 0.0
                pct = _parse_float(row[pct_idx]) if pct_idx is not None and pct_idx < len(row) else 0.0
                to = _parse_float(row[turnover_idx]) if turnover_idx is not None and turnover_idx < len(row) else None
                vol = _parse_int(row[vol_idx]) if vol_idx is not None and vol_idx < len(row) else None
                tx = _parse_int(row[tx_idx]) if tx_idx is not None and tx_idx < len(row) else None

                try:
                    d_parsed = date.fromisoformat(date_val)
                    captured_at = datetime.combine(d_parsed, time(15, 0, 0), tzinfo=KATHMANDU_TZ)
                except ValueError:
                    continue

                self._snapshots.append(
                    RawSnapshotRecord(
                        nepse_index=index_val,
                        index_change=chg if chg is not None else 0.0,
                        index_change_percent=pct if pct is not None else 0.0,
                        turnover=to,
                        total_volume=vol,
                        total_transactions=tx,
                        market_status="CLOSED",
                        captured_at=captured_at,
                    )
                )

        self._snapshots.sort(key=lambda s: s.captured_at if s.captured_at else datetime.min)
