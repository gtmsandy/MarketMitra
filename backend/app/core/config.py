import os
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

load_dotenv()

_VALID_SOURCES = ("mock", "postgres")
_VALID_ENVIRONMENTS = ("development", "test", "production")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_PLACEHOLDER_CREDENTIALS = {"user", "username", "password", "pass", "changeme"}


def _bounded_integer(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def get_application_environment() -> Literal["development", "test", "production"]:
    value = os.getenv("APP_ENV", "development").strip().lower()
    if value not in _VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid APP_ENV={value!r}. "
            f"Must be one of: {', '.join(_VALID_ENVIRONMENTS)}."
        )
    return value  # type: ignore[return-value]


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:5176")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_trusted_hosts() -> list[str]:
    raw = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
    return [host.strip().lower() for host in raw.split(",") if host.strip()]


def get_http_rate_limit() -> tuple[int, int, int]:
    return (
        _bounded_integer("HTTP_RATE_LIMIT_REQUESTS", 120, 1, 100_000),
        _bounded_integer("HTTP_RATE_LIMIT_WINDOW_SECONDS", 60, 1, 3600),
        _bounded_integer("HTTP_RATE_LIMIT_MAX_CLIENTS", 10_000, 1, 100_000),
    )


def get_websocket_connection_limit() -> int:
    return _bounded_integer("WEBSOCKET_MAX_CONNECTIONS", 100, 1, 10_000)


def hsts_enabled() -> bool:
    if get_application_environment() != "production":
        return False
    https_deployment = os.getenv("HTTPS_DEPLOYMENT", "false").strip().lower()
    enabled = os.getenv("HSTS_ENABLED", "false").strip().lower()
    return https_deployment in {"1", "true", "yes", "on"} and enabled in {
        "1",
        "true",
        "yes",
        "on",
    }


def _validate_production_origin(origin: str) -> None:
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname in _LOCAL_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "Production CORS_ORIGINS must contain only explicit HTTPS origins"
        )


def validate_runtime_config() -> None:
    """Fail closed for unsafe production configuration.

    Development and test retain their existing convenient defaults. Production
    requires an explicit PostgreSQL database and browser origin, and never
    permits the deterministic replay provider.
    """
    if get_application_environment() != "production":
        return

    if get_market_data_source() != "postgres":
        raise ValueError("Production requires MARKET_DATA_SOURCE=postgres")

    raw_database_url = get_database_url()
    try:
        database_url = make_url(raw_database_url)
    except ArgumentError as exc:
        raise ValueError("Production requires a valid PostgreSQL DATABASE_URL") from exc

    if not database_url.drivername.startswith("postgresql"):
        raise ValueError("Production requires a PostgreSQL DATABASE_URL")
    if database_url.host in _LOCAL_HOSTS or not database_url.host:
        raise ValueError("Production requires a remote database host")
    if not database_url.database:
        raise ValueError("Production DATABASE_URL must name a database")
    if not database_url.username or not database_url.password:
        raise ValueError("Production DATABASE_URL must include database credentials")
    if (
        database_url.username.lower() in _PLACEHOLDER_CREDENTIALS
        or database_url.password.lower() in _PLACEHOLDER_CREDENTIALS
    ):
        raise ValueError("Production rejects placeholder database credentials")
    if database_url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("Production requires an encrypted database connection")

    if "CORS_ORIGINS" not in os.environ:
        raise ValueError("Production requires explicit CORS_ORIGINS")
    origins = get_cors_origins()
    if not origins:
        raise ValueError("Production requires explicit CORS_ORIGINS")
    for origin in origins:
        _validate_production_origin(origin)

    if "TRUSTED_HOSTS" not in os.environ:
        raise ValueError("Production requires explicit TRUSTED_HOSTS")
    trusted_hosts = get_trusted_hosts()
    if not trusted_hosts:
        raise ValueError("Production requires explicit TRUSTED_HOSTS")
    for host in trusted_hosts:
        if (
            host == "*"
            or "://" in host
            or "/" in host
            or "@" in host
            or any(character.isspace() for character in host)
        ):
            raise ValueError("Production TRUSTED_HOSTS must contain explicit hostnames")

    hsts_requested = os.getenv("HSTS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if hsts_requested and not hsts_enabled():
        raise ValueError("HSTS_ENABLED requires HTTPS_DEPLOYMENT=true")

    provider = os.getenv("LIVE_MARKET_PROVIDER", "").strip().lower()
    if provider == "replay":
        raise ValueError("Production does not permit the replay live provider")
    if not is_live_market_enabled():
        return

    authorized = os.getenv("LIVE_MARKET_AUTHORIZED", "false").strip().lower()
    if authorized not in {"1", "true", "yes", "on"}:
        raise ValueError("Production live polling requires explicit authorization")
    provider_name = os.getenv("NEPSE_PROVIDER_NAME", "").strip().lower()
    if not provider_name or provider_name == "unconfigured":
        raise ValueError("Production live polling requires NEPSE_PROVIDER_NAME")
    live_url = os.getenv("NEPSE_LIVE_API_URL", "").strip()
    parsed_live_url = urlsplit(live_url)
    if parsed_live_url.scheme != "https" or not parsed_live_url.hostname:
        raise ValueError("Production live polling requires an HTTPS provider URL")


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
