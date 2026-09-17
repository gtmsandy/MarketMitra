import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

_VALID_SOURCES = ("mock", "postgres")


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:5176")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_market_data_source() -> Literal["mock", "postgres"]:
    """Return the configured market data source.

    Reads MARKET_DATA_SOURCE from the environment.  Defaults to 'mock'.
    Raises ValueError for any value that is not 'mock' or 'postgres'.
    """
    value = os.getenv("MARKET_DATA_SOURCE", "mock").strip().lower()
    if value not in _VALID_SOURCES:
        raise ValueError(
            f"Invalid MARKET_DATA_SOURCE={value!r}. "
            f"Must be one of: {', '.join(_VALID_SOURCES)}."
        )
    return value  # type: ignore[return-value]


def get_database_url() -> str:
    """Return DATABASE_URL from the environment.

    Raises ValueError when the variable is absent or empty, which prevents
    a misleading startup when MARKET_DATA_SOURCE=postgres is configured
    without a connection string.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise ValueError(
            "DATABASE_URL is required when MARKET_DATA_SOURCE=postgres. "
            "Set DATABASE_URL in your environment or .env file."
        )
    return url


def is_live_market_enabled() -> bool:
    return os.getenv("LIVE_MARKET_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def get_live_market_poll_interval() -> float:
    raw = os.getenv("LIVE_MARKET_POLL_INTERVAL_SECONDS", "1")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 1.0

def replay_persistence_enabled() -> bool:
    return os.getenv("REPLAY_PERSIST_LIVE_QUOTES", "false").strip().lower() in {"1", "true", "yes", "on"}
