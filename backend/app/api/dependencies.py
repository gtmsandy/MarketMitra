from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_url, get_market_data_source
from app.providers.base import MarketDataProvider
from app.providers.mock_market import MockMarketProvider
from app.services.market_service import MarketService


# ---------------------------------------------------------------------------
# Provider-selection helpers (evaluated once at first call, then cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_source() -> str:
    """Read and validate MARKET_DATA_SOURCE once; cache the result."""
    return get_market_data_source()


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    """Build the SQLAlchemy session factory once.

    Only called when MARKET_DATA_SOURCE=postgres.  Raises ValueError if
    DATABASE_URL is absent, which surfaces clearly at startup.
    """
    from app.db.base import make_session_factory
    return make_session_factory(get_database_url())


# ---------------------------------------------------------------------------
# Request-scoped session dependency
#
# Yields None for the mock source so DATABASE_URL is never read.
# Yields a real Session for the postgres source.
# ---------------------------------------------------------------------------

def _get_db_session() -> Generator[Session | None, None, None]:
    """Yield a per-request database session for the postgres source,
    or None for the mock source.  Guarantees session cleanup.
    """
    if _get_source() != "postgres":
        yield None
        return

    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session | None, Depends(_get_db_session)]


# ---------------------------------------------------------------------------
# Provider + service dependency
# ---------------------------------------------------------------------------

def get_market_service(session: DbSession) -> MarketService:
    """FastAPI dependency that returns a MarketService wired to the
    configured provider.

    - MARKET_DATA_SOURCE=mock      → MockMarketProvider (session is None)
    - MARKET_DATA_SOURCE=postgres  → PostgresMarketProvider (session injected)
    """
    source = _get_source()

    if source == "mock":
        provider: MarketDataProvider = MockMarketProvider()
    else:
        from app.providers.postgres_market import PostgresMarketProvider
        provider = PostgresMarketProvider(session)  # type: ignore[arg-type]

    return MarketService(provider)
