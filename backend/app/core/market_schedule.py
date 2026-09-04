from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KATHMANDU_TZ = ZoneInfo("Asia/Kathmandu")

# Python weekday(): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
TRADING_WEEKDAYS = {6, 0, 1, 2, 3}  # Sunday through Thursday
NON_TRADING_WEEKDAYS = {4, 5}  # Friday and Saturday

MARKET_OPEN_TIME = time(11, 0, 0)
MARKET_CLOSE_TIME = time(15, 0, 0)


def to_kathmandu_time(dt: datetime | None = None) -> datetime:
    """Normalize any datetime to Asia/Kathmandu timezone.

    If dt is None, returns current time in Asia/Kathmandu.
    If dt is naive, it is assumed to be in Asia/Kathmandu local time.
    If dt is timezone-aware, it is converted to Asia/Kathmandu.
    """
    if dt is None:
        return datetime.now(KATHMANDU_TZ)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KATHMANDU_TZ)
    return dt.astimezone(KATHMANDU_TZ)


def is_market_open(now: datetime | None = None) -> bool:
    """Return True if the NEPSE market is currently in its regular trading session.

    Trading session is Sunday through Thursday, 11:00:00 through 15:00:00 inclusive,
    in Asia/Kathmandu time.
    """
    ktm_now = to_kathmandu_time(now)
    if ktm_now.weekday() not in TRADING_WEEKDAYS:
        return False
    return MARKET_OPEN_TIME <= ktm_now.time() <= MARKET_CLOSE_TIME


def get_market_status(now: datetime | None = None) -> str:
    """Return 'OPEN' if market is in active trading session, else 'CLOSED'."""
    return "OPEN" if is_market_open(now) else "CLOSED"


def get_most_recent_trading_day(now: datetime | None = None) -> date:
    """Return the calendar date of the most recent active regular trading day.

    - During an open trading session or after close on a trading day: returns today's date.
    - On a trading day before the 11:00 opening: returns the previous trading day's date
      (e.g., Sunday before 11:00 returns Thursday).
    - On non-trading days (Friday and Saturday): returns Thursday's date.
    """
    ktm_now = to_kathmandu_time(now)
    current_date = ktm_now.date()
    weekday = ktm_now.weekday()

    if weekday in TRADING_WEEKDAYS and ktm_now.time() >= MARKET_OPEN_TIME:
        return current_date

    candidate = current_date - timedelta(days=1)
    while candidate.weekday() not in TRADING_WEEKDAYS:
        candidate -= timedelta(days=1)
    return candidate
