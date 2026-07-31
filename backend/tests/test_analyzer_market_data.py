from datetime import datetime, timezone

from services import analyzer
from services.market_gateway import (
    Candle,
    InMemoryMarketDataProvider,
    MarketDataGateway,
    default_catalog,
)


def test_analyzer_fetches_through_shared_gateway(monkeypatch):
    provider = InMemoryMarketDataProvider(provider_id="twelve_data")
    provider.set_candles(
        provider_symbol="XAU/USD",
        timeframe="60",
        candles=[
            Candle(
                datetime(2026, 7, 24, hour, tzinfo=timezone.utc),
                2400 + hour,
                2410 + hour,
                2395 + hour,
                2405 + hour,
                100,
                True,
            )
            for hour in (10, 11)
        ],
    )
    gateway = MarketDataGateway(
        catalog=default_catalog(),
        providers=[provider],
    )
    monkeypatch.setattr(
        analyzer,
        "get_market_data_gateway",
        lambda: gateway,
    )
    monkeypatch.setattr(
        analyzer,
        "_now",
        lambda: datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
    )

    frame = analyzer.fetch_ohlcv(
        symbol="XAUUSD",
        exchange="COMEX",
        interval="60",
        n_bars=2,
    )

    assert list(frame["close"]) == [2415, 2416]
    assert provider.candle_fetch_count == 1
