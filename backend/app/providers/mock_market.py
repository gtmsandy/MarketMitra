from datetime import datetime, timedelta, timezone

from app.models.market import (
    MarketMover,
    MarketOverview,
    MostActiveStock,
    StockQuote,
)
from app.providers.base import MarketDataProvider


NEPAL_TIMEZONE = timezone(timedelta(hours=5, minutes=45))
MOCK_LAST_UPDATED = datetime(2026, 9, 3, 11, 30, tzinfo=NEPAL_TIMEZONE)


class MockMarketProvider(MarketDataProvider):
    """Deterministic sample data for development; it is not live NEPSE data."""

    def __init__(self) -> None:
        self._stocks = [
            StockQuote(
                symbol="NABIL",
                company_name="Nabil Bank Limited",
                ltp=515.0,
                change=13.0,
                change_percent=2.59,
                open=504.0,
                high=520.0,
                low=502.0,
                previous_close=502.0,
                volume=182_450,
                last_updated=MOCK_LAST_UPDATED,
            ),
            StockQuote(
                symbol="NICA",
                company_name="NIC Asia Bank Limited",
                ltp=674.5,
                change=-11.5,
                change_percent=-1.68,
                open=687.0,
                high=690.0,
                low=672.0,
                previous_close=686.0,
                volume=147_820,
                last_updated=MOCK_LAST_UPDATED,
            ),
            StockQuote(
                symbol="GBIME",
                company_name="Global IME Bank Limited",
                ltp=241.8,
                change=5.8,
                change_percent=2.46,
                open=238.0,
                high=244.0,
                low=236.5,
                previous_close=236.0,
                volume=221_600,
                last_updated=MOCK_LAST_UPDATED,
            ),
            StockQuote(
                symbol="SCB",
                company_name="Standard Chartered Bank Nepal",
                ltp=576.0,
                change=-4.0,
                change_percent=-0.69,
                open=582.0,
                high=583.0,
                low=574.0,
                previous_close=580.0,
                volume=38_400,
                last_updated=MOCK_LAST_UPDATED,
            ),
            StockQuote(
                symbol="NTC",
                company_name="Nepal Telecom",
                ltp=935.0,
                change=18.0,
                change_percent=1.96,
                open=920.0,
                high=941.0,
                low=918.0,
                previous_close=917.0,
                volume=96_750,
                last_updated=MOCK_LAST_UPDATED,
            ),
            StockQuote(
                symbol="UPPER",
                company_name="Upper Tamakoshi Hydropower",
                ltp=216.4,
                change=-6.6,
                change_percent=-2.96,
                open=224.0,
                high=225.0,
                low=215.5,
                previous_close=223.0,
                volume=304_920,
                last_updated=MOCK_LAST_UPDATED,
            ),
            StockQuote(
                symbol="CHCL",
                company_name="Chilime Hydropower Company",
                ltp=552.0,
                change=15.0,
                change_percent=2.79,
                open=540.0,
                high=558.0,
                low=538.0,
                previous_close=537.0,
                volume=84_600,
                last_updated=MOCK_LAST_UPDATED,
            ),
            StockQuote(
                symbol="SHIVM",
                company_name="Shivam Cements",
                ltp=486.2,
                change=-9.8,
                change_percent=-1.98,
                open=498.0,
                high=500.0,
                low=484.0,
                previous_close=496.0,
                volume=165_350,
                last_updated=MOCK_LAST_UPDATED,
            ),
        ]
        self._turnovers = {
            "NABIL": 93_961_750.0,
            "NICA": 99_703_590.0,
            "GBIME": 53_586_888.0,
            "SCB": 22_118_400.0,
            "NTC": 90_461_250.0,
            "UPPER": 65_984_688.0,
            "CHCL": 46_699_200.0,
            "SHIVM": 80_392_167.0,
        }

    def get_market_overview(self) -> MarketOverview:
        return MarketOverview(
            nepse_index=2_786.42,
            index_change=21.35,
            index_change_percent=0.77,
            turnover=sum(self._turnovers.values()),
            total_volume=sum(stock.volume for stock in self._stocks),
            total_transactions=38_640,
            market_status="Open",
            last_updated=MOCK_LAST_UPDATED,
        )

    def get_top_gainers(self) -> list[MarketMover]:
        gainers = [self._to_market_mover(stock) for stock in self._stocks if stock.change_percent > 0]
        return sorted(gainers, key=lambda stock: stock.change_percent, reverse=True)

    def get_top_losers(self) -> list[MarketMover]:
        losers = [self._to_market_mover(stock) for stock in self._stocks if stock.change_percent < 0]
        return sorted(losers, key=lambda stock: stock.change_percent)

    def get_most_active(self) -> list[MostActiveStock]:
        active_stocks = [
            MostActiveStock(
                symbol=stock.symbol,
                company_name=stock.company_name,
                ltp=stock.ltp,
                volume=stock.volume,
                turnover=self._turnovers[stock.symbol],
            )
            for stock in self._stocks
        ]
        return sorted(active_stocks, key=lambda stock: stock.turnover, reverse=True)

    def get_stocks(self) -> list[StockQuote]:
        return list(self._stocks)

    @staticmethod
    def _to_market_mover(stock: StockQuote) -> MarketMover:
        return MarketMover(
            symbol=stock.symbol,
            company_name=stock.company_name,
            ltp=stock.ltp,
            change_percent=stock.change_percent,
            volume=stock.volume,
        )
