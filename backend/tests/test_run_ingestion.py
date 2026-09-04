import json
from unittest.mock import patch
import pytest

from app.db.base import Base, make_engine, make_session_factory
from app.db.models import IngestionRun
from app.scripts.run_ingestion import main


class TestRunIngestionCli:
    def test_if_market_open_when_closed_exits_zero_and_skips(
        self, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        db_path = tmp_path / "cli_closed.db"
        db_url = f"sqlite:///{db_path}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        monkeypatch.setenv("DATABASE_URL", db_url)

        # Force is_market_open to return False
        monkeypatch.setattr(
            "app.core.market_schedule.is_market_open", lambda *args, **kwargs: False
        )

        with patch("app.ingestion.service.IngestionService.run") as mock_run:
            exit_code = main(["--if-market-open"])

            assert exit_code == 0
            assert mock_run.call_count == 0

            captured = capsys.readouterr()
            assert "closed" in captured.out.lower()
            assert "skipped" in captured.out.lower()

            # Verify no IngestionRun audit row was written
            factory = make_session_factory(db_url)
            with factory() as session:
                runs = session.query(IngestionRun).all()
                assert len(runs) == 0

    def test_if_market_open_when_closed_json_output(
        self, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.core.market_schedule.is_market_open", lambda *args, **kwargs: False
        )

        exit_code = main(["--if-market-open", "--json"])
        assert exit_code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "skipped"
        assert data["reason"] == "market_closed"
        assert "skipped" in data["message"].lower()

    def test_if_market_open_when_open_runs_ingestion(
        self, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        db_path = tmp_path / "cli_open.db"
        db_url = f"sqlite:///{db_path}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        monkeypatch.setenv("DATABASE_URL", db_url)

        # Force is_market_open to return True
        monkeypatch.setattr(
            "app.core.market_schedule.is_market_open", lambda *args, **kwargs: True
        )

        exit_code = main(["--if-market-open", "--json"])
        assert exit_code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "success"
        assert data["instruments_upserted"] > 0

        # Verify an IngestionRun audit row was written
        factory = make_session_factory(db_url)
        with factory() as session:
            runs = session.query(IngestionRun).all()
            assert len(runs) == 1
            assert runs[0].status == "success"
