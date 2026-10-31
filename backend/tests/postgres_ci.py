"""Safety guard for tests that mutate an explicitly disposable PostgreSQL DB."""

import os

from sqlalchemy.engine import make_url


def require_disposable_ci_database() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL integration tests")

    url = make_url(raw)
    database = url.database or ""
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("PostgreSQL integration tests require a PostgreSQL URL")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("PostgreSQL integration tests require a runner-local host")
    if not database.endswith("_ci"):
        raise RuntimeError("PostgreSQL integration database name must end in _ci")
    if os.getenv("MARKETMITRA_CONFIRM_DISPOSABLE") != database:
        raise RuntimeError(
            "MARKETMITRA_CONFIRM_DISPOSABLE must exactly match the database name"
        )
    return raw
