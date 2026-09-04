from datetime import datetime

from app.core.freshness import calculate_data_freshness
from app.core.market_schedule import KATHMANDU_TZ


class TestCalculateDataFreshness:
    def test_unknown_with_no_snapshot(self) -> None:
        assert calculate_data_freshness(None) == "UNKNOWN"

    def test_open_market_fresh_within_30_minutes(self) -> None:
        # Thursday at 12:00: market open. Snapshot at 11:45 (15 mins ago).
        now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        snapshot = datetime(2026, 9, 3, 11, 45, 0, tzinfo=KATHMANDU_TZ)
        assert calculate_data_freshness(snapshot, now) == "FRESH"

    def test_open_market_stale_beyond_30_minutes(self) -> None:
        # Thursday at 12:00: market open. Snapshot at 11:20 (40 mins ago).
        now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        snapshot = datetime(2026, 9, 3, 11, 20, 0, tzinfo=KATHMANDU_TZ)
        assert calculate_data_freshness(snapshot, now) == "STALE"

    def test_thursday_data_fresh_friday(self) -> None:
        # Thursday end-of-day snapshot viewed on Friday (non-trading day)
        snapshot = datetime(2026, 9, 3, 14, 55, 0, tzinfo=KATHMANDU_TZ)
        friday_now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        assert calculate_data_freshness(snapshot, friday_now) == "FRESH"

    def test_thursday_data_fresh_saturday(self) -> None:
        # Thursday end-of-day snapshot viewed on Saturday (non-trading day)
        snapshot = datetime(2026, 9, 3, 14, 55, 0, tzinfo=KATHMANDU_TZ)
        saturday_now = datetime(2026, 9, 5, 14, 0, 0, tzinfo=KATHMANDU_TZ)
        assert calculate_data_freshness(snapshot, saturday_now) == "FRESH"

    def test_thursday_data_fresh_sunday_before_11(self) -> None:
        # Thursday end-of-day snapshot viewed on Sunday morning before 11:00 NPT
        snapshot = datetime(2026, 9, 3, 14, 55, 0, tzinfo=KATHMANDU_TZ)
        sunday_early = datetime(2026, 9, 6, 10, 30, 0, tzinfo=KATHMANDU_TZ)
        assert calculate_data_freshness(snapshot, sunday_early) == "FRESH"

    def test_stale_snapshot_older_than_most_recent_trading_day(self) -> None:
        # Wednesday snapshot viewed on Friday (most recent trading day is Thursday)
        wednesday_snapshot = datetime(2026, 9, 2, 14, 55, 0, tzinfo=KATHMANDU_TZ)
        friday_now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        assert calculate_data_freshness(wednesday_snapshot, friday_now) == "STALE"

    def test_sunday_after_open_thursday_data_is_stale(self) -> None:
        # Thursday data viewed after Sunday 11:00 AM (market has opened, data is days old)
        thursday_snapshot = datetime(2026, 9, 3, 14, 55, 0, tzinfo=KATHMANDU_TZ)
        sunday_open = datetime(2026, 9, 6, 11, 35, 0, tzinfo=KATHMANDU_TZ)
        assert calculate_data_freshness(thursday_snapshot, sunday_open) == "STALE"
