from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.core.market_schedule import (
    KATHMANDU_TZ,
    get_market_status,
    get_most_recent_trading_day,
    is_market_open,
    to_kathmandu_time,
)


class TestIsMarketOpenWeekdays:
    def test_all_trading_weekdays_open_at_noon(self) -> None:
        # Dates in 2026:
        # Sunday: 2026-08-30 (weekday 6)
        # Monday: 2026-08-31 (weekday 0)
        # Tuesday: 2026-09-01 (weekday 1)
        # Wednesday: 2026-09-02 (weekday 2)
        # Thursday: 2026-09-03 (weekday 3)
        trading_dates = [
            (2026, 8, 30),  # Sun
            (2026, 8, 31),  # Mon
            (2026, 9, 1),   # Tue
            (2026, 9, 2),   # Wed
            (2026, 9, 3),   # Thu
        ]
        for year, month, day in trading_dates:
            dt = datetime(year, month, day, 12, 0, 0, tzinfo=KATHMANDU_TZ)
            assert is_market_open(dt) is True, f"Failed for {dt.strftime('%A %Y-%m-%d')}"
            assert get_market_status(dt) == "OPEN"

    def test_friday_closed(self) -> None:
        # Friday: 2026-09-04 (weekday 4)
        dt = datetime(2026, 9, 4, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        assert is_market_open(dt) is False
        assert get_market_status(dt) == "CLOSED"

    def test_saturday_closed(self) -> None:
        # Saturday: 2026-09-05 (weekday 5)
        dt = datetime(2026, 9, 5, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        assert is_market_open(dt) is False
        assert get_market_status(dt) == "CLOSED"


class TestIsMarketOpenTimeBoundaries:
    def test_sunday_1059_closed(self) -> None:
        dt = datetime(2026, 8, 30, 10, 59, 59, tzinfo=KATHMANDU_TZ)
        assert is_market_open(dt) is False
        assert get_market_status(dt) == "CLOSED"

    def test_sunday_1100_open(self) -> None:
        dt = datetime(2026, 8, 30, 11, 0, 0, tzinfo=KATHMANDU_TZ)
        assert is_market_open(dt) is True
        assert get_market_status(dt) == "OPEN"

    def test_thursday_1500_open(self) -> None:
        dt = datetime(2026, 9, 3, 15, 0, 0, tzinfo=KATHMANDU_TZ)
        assert is_market_open(dt) is True
        assert get_market_status(dt) == "OPEN"

    def test_thursday_1501_closed(self) -> None:
        dt = datetime(2026, 9, 3, 15, 1, 0, tzinfo=KATHMANDU_TZ)
        assert is_market_open(dt) is False
        assert get_market_status(dt) == "CLOSED"


class TestTimezoneNormalization:
    def test_naive_datetime_treated_as_kathmandu(self) -> None:
        naive_dt = datetime(2026, 9, 3, 11, 30, 0)
        normalized = to_kathmandu_time(naive_dt)
        assert normalized.tzinfo == KATHMANDU_TZ
        assert normalized.hour == 11
        assert is_market_open(naive_dt) is True

    def test_utc_datetime_converted_to_kathmandu(self) -> None:
        # 05:15 UTC on Sunday is 11:00:00 in Kathmandu (open)
        utc_dt = datetime(2026, 8, 30, 5, 15, 0, tzinfo=timezone.utc)
        assert is_market_open(utc_dt) is True

        # 05:14 UTC on Sunday is 10:59:00 in Kathmandu (closed)
        utc_early = datetime(2026, 8, 30, 5, 14, 0, tzinfo=timezone.utc)
        assert is_market_open(utc_early) is False


class TestMostRecentTradingDay:
    def test_thursday_afternoon_returns_thursday(self) -> None:
        dt = datetime(2026, 9, 3, 15, 30, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 3)

    def test_friday_returns_thursday(self) -> None:
        dt = datetime(2026, 9, 4, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 3)

    def test_saturday_returns_thursday(self) -> None:
        dt = datetime(2026, 9, 5, 12, 0, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 3)

    def test_sunday_morning_before_11_returns_thursday(self) -> None:
        dt = datetime(2026, 9, 6, 10, 30, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 3)

    def test_sunday_at_11_returns_sunday(self) -> None:
        dt = datetime(2026, 9, 6, 11, 0, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 6)

    def test_monday_morning_before_11_returns_sunday(self) -> None:
        dt = datetime(2026, 9, 7, 10, 0, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 6)

    def test_monday_at_11_returns_monday(self) -> None:
        dt = datetime(2026, 9, 7, 11, 0, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 7)

    def test_tuesday_morning_before_11_returns_monday(self) -> None:
        dt = datetime(2026, 9, 8, 9, 0, 0, tzinfo=KATHMANDU_TZ)
        assert get_most_recent_trading_day(dt) == date(2026, 9, 7)
