import hashlib
import random
from datetime import date, datetime, timedelta, timezone

from app.models.market import (
    MarketMover,
    MarketOverview,
    MostActiveStock,
    StockQuote,
)
from app.models.stock import PriceHistoryPoint, StockDetail
from app.providers.base import MarketDataProvider


NEPAL_TIMEZONE = timezone(timedelta(hours=5, minutes=45))
MOCK_LAST_UPDATED = datetime(2026, 9, 3, 11, 30, tzinfo=NEPAL_TIMEZONE)
MOCK_END_DATE = date(2026, 9, 3)
HISTORY_TRADING_DAYS = 180


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
        self._stock_by_symbol: dict[str, StockQuote] = {
            stock.symbol: stock for stock in self._stocks
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

    def search_stocks(self, query: str) -> list[StockQuote]:
        if not query or not query.strip():
            return list(self._stocks)
        term = query.strip().lower()
        return [
            stock for stock in self._stocks
            if term in stock.symbol.lower() or term in stock.company_name.lower()
        ]

    def get_stock_detail(self, symbol: str) -> StockDetail | None:
        stock = self._stock_by_symbol.get(symbol.upper())
        if stock is None:
            return None
        history = self._generate_price_history(stock.symbol, stock.ltp, stock.volume)
        high_52w = max(p.high for p in history)
        low_52w = min(p.low for p in history)
        # Ensure the current day's high/low are included in the range.
        high_52w = max(high_52w, stock.high)
        low_52w = min(low_52w, stock.low)
        return StockDetail(
            symbol=stock.symbol,
            company_name=stock.company_name,
            ltp=stock.ltp,
            change=stock.change,
            change_percent=stock.change_percent,
            open=stock.open,
            high=stock.high,
            low=stock.low,
            previous_close=stock.previous_close,
            volume=stock.volume,
            last_updated=stock.last_updated,
            fifty_two_week_high=round(high_52w, 2),
            fifty_two_week_low=round(low_52w, 2),
        )

    def get_stock_history(self, symbol: str) -> list[PriceHistoryPoint] | None:
        stock = self._stock_by_symbol.get(symbol.upper())
        if stock is None:
            return None
        return self._generate_price_history(stock.symbol, stock.ltp, stock.volume)

    @staticmethod
    def _stable_seed(symbol: str) -> int:
        """Derive a stable integer seed from a symbol using SHA-256."""
        digest = hashlib.sha256(symbol.encode("utf-8")).hexdigest()
        return int(digest, 16) % (2**31)

    @staticmethod
    def _trading_days(end: date, count: int) -> list[date]:
        """Return `count` NEPSE trading days ending on or before `end`.

        NEPSE trades Sunday–Thursday; Friday (weekday 4) and
        Saturday (weekday 5) are holidays.
        """
        days: list[date] = []
        current = end
        while len(days) < count:
            if current.weekday() not in (4, 5):
                days.append(current)
            current -= timedelta(days=1)
        days.reverse()
        return days

    @staticmethod
    def _generate_price_history(
        symbol: str,
        current_ltp: float,
        base_volume: int,
    ) -> list[PriceHistoryPoint]:
        """Generate deterministic OHLCV history for a stock.

        Uses SHA-256 of the symbol as seed so output is identical across
        process restarts regardless of Python hash randomisation.
        """
        seed = MockMarketProvider._stable_seed(symbol)
        rng = random.Random(seed)
        days = MockMarketProvider._trading_days(MOCK_END_DATE, HISTORY_TRADING_DAYS)

        # Walk forward from a starting price below the current LTP.
        price = current_ltp * rng.uniform(0.72, 0.88)
        points: list[PriceHistoryPoint] = []

        for d in days:
            daily_return = rng.gauss(0.001, 0.018)
            close = max(price * (1 + daily_return), 1.0)

            intraday_spread = rng.uniform(0.005, 0.025)
            high = close * (1 + intraday_spread * rng.uniform(0.3, 1.0))
            low = close * (1 - intraday_spread * rng.uniform(0.3, 1.0))
            open_price = price * (1 + rng.uniform(-0.008, 0.008))

            # Ensure OHLC consistency.
            high = max(high, open_price, close)
            low = min(low, open_price, close)

            vol = max(1_000, int(rng.gauss(base_volume, base_volume * 0.35)))

            points.append(PriceHistoryPoint(
                date=d.isoformat(),
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=vol,
            ))
            price = close

        return points

    @staticmethod
    def _to_market_mover(stock: StockQuote) -> MarketMover:
        return MarketMover(
            symbol=stock.symbol,
            company_name=stock.company_name,
            ltp=stock.ltp,
            change_percent=stock.change_percent,
            volume=stock.volume,
        )

