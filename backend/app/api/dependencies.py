from app.providers.mock_market import MockMarketProvider
from app.services.market_service import MarketService

# Single shared service instance. The provider is constructed once so all
# routes share the same data source. Swapping to a real provider in Phase 2
# requires changing only this module.
_market_service = MarketService(MockMarketProvider())


def get_market_service() -> MarketService:
    """FastAPI dependency that supplies the shared MarketService."""
    return _market_service
