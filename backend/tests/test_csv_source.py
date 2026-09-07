"""Unit and integration tests for CsvDataSource and CSV ingestion architecture."""
import csv
from datetime import date, datetime
from pathlib import Path
import pytest

from app.core.market_schedule import KATHMANDU_TZ
from app.db.base import Base, make_engine, make_session_factory
from app.db.models import DailyPrice, IngestionRun, Instrument, MarketSnapshot
from app.ingestion.service import IngestionService
from app.ingestion.sources.csv_source import CsvDataSource, _normalize_header, _parse_float, _parse_int
from app.scripts.run_ingestion import main


class TestCsvParsingUtilities:
    def test_header_normalization(self) -> None:
        assert _normalize_header("  Published_Date ") == "published date"
        assert _normalize_header("Stock_Symbol") == "stock symbol"
        assert _normalize_header("Total_Traded_Amount") == "total traded amount"

    def test_numeric_parsing_with_commas_and_percents(self) -> None:
        assert _parse_float("1,050.00") == 1050.0
        assert _parse_float(" -0.87 % ") == -0.87
        assert _parse_float("12,500,000.50") == 12500000.5
        assert _parse_float("NULL") is None
        assert _parse_float("--") is None
        assert _parse_float("") is None

    def test_integer_parsing_from_float_strings(self) -> None:
        assert _parse_int("1111.0") == 1111
        assert _parse_int("5,000.00") == 5000
        assert _parse_int("") is None


class TestCsvDataSourceFeatures:
    def test_column_alias_mapping_and_turnover_derivation(self, tmp_path: Path) -> None:
        # Create CSV using unconventional aliases and missing turnover
        stock_file = tmp_path / "custom_stocks.csv"
        with open(stock_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Published_Date", "Ticker", "Open_Price", "High_Price", "Low_Price", "LTP", "Traded_Quantity"])
            w.writerow(["2024-01-01", "nabil", "1,000.00", "1,020.00", "990.00", "1,010.00", "500.0"])
            w.writerow(["2024-01-02", "nabil", "1,010.00", "1,030.00", "1,005.00", "1,025.00", "600.0"])

        source = CsvDataSource(stock_file=stock_file)
        instruments = source.fetch_instruments()
        assert len(instruments) == 1
        assert instruments[0].symbol == "NABIL"
        assert instruments[0].company_name == "NABIL"  # fallback
        assert instruments[0].sector is None  # missing sector defaults to None

        prices = source.fetch_prices("NABIL")
        assert len(prices) == 2
        # Turnover derived: 1010.0 * 500 = 505000.0
        assert prices[0].turnover == 505000.0
        # Previous close derivation
        assert prices[1].previous_close == 1010.0
        assert prices[1].change == 15.0
        assert round(prices[1].change_percent, 2) == 1.49

    def test_multi_symbol_csv_parsing(self, tmp_path: Path) -> None:
        multi_file = tmp_path / "multi_stocks.csv"
        with open(multi_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Open", "High", "Low", "Close", "Volume", "Turnover", "Company_Name", "Sector"])
            w.writerow(["2024-01-01", "NABIL", "500.0", "510.0", "495.0", "505.0", "1000", "505000.0", "Nabil Bank Limited", "Commercial_Banks"])
            w.writerow(["2024-01-01", "CHCL", "350.0", "360.0", "345.0", "355.0", "2000", "710000.0", "Chilime Hydropower", "Hydro_Power"])

        source = CsvDataSource(stock_file=multi_file)
        assert len(source.fetch_instruments()) == 2
        symbols = {i.symbol for i in source.fetch_instruments()}
        assert symbols == {"NABIL", "CHCL"}

        inst_map = {i.symbol: i for i in source.fetch_instruments()}
        assert inst_map["NABIL"].company_name == "Nabil Bank Limited"
        assert inst_map["NABIL"].sector == "Commercial Banks"
        assert inst_map["CHCL"].sector == "Hydro Power"

        assert len(source.fetch_prices("NABIL")) == 1
        assert len(source.fetch_prices("CHCL")) == 1

    def test_duplicate_handling_first_seen_wins(self, tmp_path: Path) -> None:
        dup_file = tmp_path / "dup_stocks.csv"
        with open(dup_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"])
            w.writerow(["2024-01-01", "NABIL", "500.0", "510.0", "495.0", "505.0", "1000"])
            # Duplicate date with different close - first-seen must win
            w.writerow(["2024-01-01", "NABIL", "500.0", "510.0", "495.0", "999.0", "2000"])

        source = CsvDataSource(stock_file=dup_file)
        prices = source.fetch_prices("NABIL")
        assert len(prices) == 1
        assert prices[0].close == 505.0

    def test_zero_prices_skipped_cleanly(self, tmp_path: Path) -> None:
        zero_file = tmp_path / "zero_stocks.csv"
        with open(zero_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"])
            w.writerow(["2024-01-01", "NABIL", "0.0", "510.0", "495.0", "505.0", "1000"])  # zero open
            w.writerow(["2024-01-02", "NABIL", "500.0", "510.0", "495.0", "505.0", "1000"])  # valid

        source = CsvDataSource(stock_file=zero_file)
        prices = source.fetch_prices("NABIL")
        assert len(prices) == 1
        assert prices[0].date == "2024-01-02"

    def test_index_metrics_nullable(self, tmp_path: Path) -> None:
        index_file = tmp_path / "index_fixture.csv"
        with open(index_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Index Value", "Absolute Change", "Percentage Change"])
            w.writerow(["2024-01-01", "2,080.50", "-15.20", "-0.72"])

        # Dummy stock file
        stock_file = tmp_path / "stock_dummy.csv"
        with open(stock_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Close"])
            w.writerow(["2024-01-01", "NABIL", "500.0"])

        source = CsvDataSource(stock_file=stock_file, index_file=index_file)
        snapshot = source.fetch_snapshot()
        assert snapshot is not None
        assert snapshot.nepse_index == 2080.50
        assert snapshot.index_change == -15.20
        assert snapshot.index_change_percent == -0.72
        assert snapshot.turnover is None
        assert snapshot.total_volume is None
        assert snapshot.total_transactions is None
        assert snapshot.market_status == "CLOSED"
        assert snapshot.captured_at.tzinfo == KATHMANDU_TZ

    def test_leaf_sector_directory_ingestion_and_normalization(self, tmp_path: Path) -> None:
        sector_dir = tmp_path / "Commercial_Banks"
        sector_dir.mkdir()
        stock_file = sector_dir / "ADBL.csv"
        with open(stock_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Close"])
            w.writerow(["2024-01-01", "300.0"])

        source = CsvDataSource(stock_file=sector_dir)
        instruments = source.fetch_instruments()
        assert len(instruments) == 1
        assert instruments[0].symbol == "ADBL"
        assert instruments[0].sector == "Commercial Banks"

    def test_nested_sector_directory_ingestion_and_normalization(self, tmp_path: Path) -> None:
        root_dir = tmp_path / "Nepse_Data"
        bank_dir = root_dir / "Commercial_Banks"
        ins_dir = root_dir / "Non-Life_Insurance"
        bank_dir.mkdir(parents=True)
        ins_dir.mkdir(parents=True)

        with open(bank_dir / "NABIL.csv", "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Close"])
            w.writerow(["2024-01-01", "500.0"])

        with open(ins_dir / "NIL.csv", "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Close"])
            w.writerow(["2024-01-01", "800.0"])

        source = CsvDataSource(stock_file=root_dir)
        instruments = {i.symbol: i for i in source.fetch_instruments()}
        assert len(instruments) == 2
        assert instruments["NABIL"].sector == "Commercial Banks"
        assert instruments["NIL"].sector == "Non-Life Insurance"

    def test_sector_normalization_from_csv_column(self, tmp_path: Path) -> None:
        stock_file = tmp_path / "hydro.csv"
        with open(stock_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Close", "Sector"])
            w.writerow(["2024-01-01", "CHCL", "400.0", "Hydro_Power"])

        source = CsvDataSource(stock_file=stock_file)
        instruments = source.fetch_instruments()
        assert len(instruments) == 1
        assert instruments[0].sector == "Hydro Power"


class TestIngestionServiceWithCsvSource:
    def test_e2e_ingestion_service_with_csv(self, tmp_path: Path) -> None:
        stock_file = tmp_path / "e2e_stocks.csv"
        with open(stock_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Open", "High", "Low", "Close", "Volume", "Turnover"])
            w.writerow(["2024-01-01", "NABIL", "500.0", "510.0", "495.0", "505.0", "1000", "505000.0"])

        index_file = tmp_path / "e2e_index.csv"
        with open(index_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Index Value", "Absolute Change", "Percentage Change"])
            w.writerow(["2024-01-01", "2080.50", "10.0", "0.5"])

        db_url = f"sqlite:///{tmp_path / 'e2e_test.db'}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        factory = make_session_factory(db_url)

        with factory() as session:
            source = CsvDataSource(stock_file=stock_file, index_file=index_file)
            service = IngestionService(
                source=source,
                session=session,
                on_conflict="insert",
                validation_mode="historical",
            )
            report = service.run()

            assert report.status == "success"
            assert report.instruments_upserted == 1
            assert report.snapshots_inserted == 1
            assert report.prices_accepted == 1
            assert report.prices_rejected == 0

            # Verify persisted DB records
            snap = session.query(MarketSnapshot).first()
            assert snap is not None
            assert snap.nepse_index == 2080.50
            assert snap.turnover is None

            price = session.query(DailyPrice).first()
            assert price is not None
            assert price.symbol == "NABIL"
            assert price.close == 505.0

    def test_cli_dry_run_csv_leaves_database_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        stock_file = tmp_path / "dry_stocks.csv"
        with open(stock_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"])
            w.writerow(["2024-01-01", "NABIL", "500.0", "510.0", "495.0", "505.0", "1000"])

        db_url = f"sqlite:///{tmp_path / 'dry_run.db'}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        monkeypatch.setenv("DATABASE_URL", db_url)

        ret = main([
            "--source", "csv",
            "--file", str(stock_file),
            "--dry-run",
            "--json",
        ])
        assert ret == 0

        factory = make_session_factory(db_url)
        with factory() as session:
            assert len(session.query(DailyPrice).all()) == 0
            assert len(session.query(IngestionRun).all()) == 0

    def test_ingestion_service_restricts_to_active_source_instruments(self, tmp_path: Path) -> None:
        from app.repositories.instrument_repository import PostgresInstrumentRepository

        db_url = f"sqlite:///{tmp_path / 'isolated_ingest.db'}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        factory = make_session_factory(db_url)

        # Pre-seed DB with an unrelated instrument
        with factory() as session:
            inst_repo = PostgresInstrumentRepository(session)
            inst_repo.upsert(symbol="OLDSYM", company_name="Old Company", sector="Old Sector")
            session.commit()

        # Ingest CSV containing ONLY NEWSYM
        stock_file = tmp_path / "new_stock.csv"
        with open(stock_file, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"])
            w.writerow(["2024-01-01", "NEWSYM", "100.0", "110.0", "95.0", "105.0", "500"])

        with factory() as session:
            source = CsvDataSource(stock_file=stock_file)
            service = IngestionService(source=source, session=session)
            report = service.run()

            assert report.status == "success"
            assert report.instruments_upserted == 1
            assert report.prices_accepted == 1

            # Only NEW_SYM prices exist in the daily_prices table
            prices = session.query(DailyPrice).all()
            assert len(prices) == 1
            assert prices[0].symbol == "NEWSYM"


class TestDataSourceContract:
    def test_fetch_snapshots_default_implementation(self) -> None:
        from app.ingestion.sources.base import DataSource
        from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord

        dummy_snap = RawSnapshotRecord(
            nepse_index=2000.0,
            index_change=10.0,
            index_change_percent=0.5,
            market_status="CLOSED",
        )

        class SingleSnapSource(DataSource):
            @property
            def name(self) -> str:
                return "single"
            def fetch_instruments(self) -> list[RawInstrumentRecord]:
                return []
            def fetch_snapshot(self) -> RawSnapshotRecord:
                return dummy_snap
            def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
                return []

        source = SingleSnapSource()
        snaps = source.fetch_snapshots()
        assert len(snaps) == 1
        assert snaps[0] == dummy_snap

    def test_fetch_snapshots_returns_empty_when_snapshot_none(self) -> None:
        from app.ingestion.sources.base import DataSource
        from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord

        class NoneSnapSource(DataSource):
            @property
            def name(self) -> str:
                return "none"
            def fetch_instruments(self) -> list[RawInstrumentRecord]:
                return []
            def fetch_snapshot(self) -> RawSnapshotRecord | None:
                return None
            def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
                return []

        source = NoneSnapSource()
        assert source.fetch_snapshots() == []

    def test_fetch_snapshots_returns_empty_on_exception(self) -> None:
        from app.ingestion.sources.base import DataSource
        from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord

        class RaisingSnapSource(DataSource):
            @property
            def name(self) -> str:
                return "raising"
            def fetch_instruments(self) -> list[RawInstrumentRecord]:
                return []
            def fetch_snapshot(self) -> RawSnapshotRecord:
                raise RuntimeError("Source unavailable")
            def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
                return []

        source = RaisingSnapSource()
        assert source.fetch_snapshots() == []
