from datetime import datetime, timedelta

from app.core.market_schedule import (
    get_most_recent_trading_day,
    is_market_open,
    to_kathmandu_time,
)

FRESHNESS_WINDOW = timedelta(minutes=30)


def calculate_data_freshness(
    latest_captured_at: datetime | None,
    now: datetime | None = None,
) -> str:
    """Calculate the operational freshness of market data.

    Returns:
        - "UNKNOWN": if latest_captured_at is None (no snapshot exists).
        - When market is OPEN:
            - "FRESH": if latest_captured_at was captured within the last 30 minutes of now.
            - "STALE": if older than 30 minutes.
        - When market is CLOSED:
            - "FRESH": if the snapshot's Kathmandu calendar date matches or is newer
              than the most recent regular trading day (e.g. Thursday data remains FRESH
              throughout Friday, Saturday, and Sunday before 11:00 NPT).
            - "STALE": if older than the most recent regular trading day.
    """
    if latest_captured_at is None:
        return "UNKNOWN"

    ktm_now = to_kathmandu_time(now)
    ktm_captured = to_kathmandu_time(latest_captured_at)

    if is_market_open(ktm_now):
        # Allow slight clock discrepancy (-1 minute) up to 30 minutes
        elapsed = ktm_now - ktm_captured
        if timedelta(minutes=-1) <= elapsed <= FRESHNESS_WINDOW:
            return "FRESH"
        return "STALE"

    # Market is CLOSED: freshness evaluated against most recent trading day
    most_recent_trading_day = get_most_recent_trading_day(ktm_now)
    if ktm_captured.date() >= most_recent_trading_day:
        return "FRESH"
    return "STALE"
