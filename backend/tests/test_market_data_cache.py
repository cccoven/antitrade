from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from services.market_data_cache import SqlAlchemyCandleCache
from services.market_gateway import (
    Candle,
    CandleQuery,
    InMemoryMarketDataProvider,
    MarketDataGateway,
    ProviderMapping,
    default_catalog,
)


def test_postgres_cache_survives_gateway_and_provider_recreation(_pg_engine):
    session_factory = sessionmaker(bind=_pg_engine, expire_on_commit=False)
    cache = SqlAlchemyCandleCache(session_factory)
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping("memory", "series", target_id, "XAU/USD"),
    )
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    provider = InMemoryMarketDataProvider(provider_id="memory")
    provider.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 120, True),
        ],
    )
    query = CandleQuery(
        series_id=target_id,
        timeframe="1h",
        start=open_time,
        end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        purpose="backtest",
    )

    first_gateway = MarketDataGateway(
        catalog=catalog,
        providers=[provider],
        candle_cache=cache,
    )
    first_gateway.get_candles(query)

    empty_provider = InMemoryMarketDataProvider(provider_id="memory")
    second_gateway = MarketDataGateway(
        catalog=catalog,
        providers=[empty_provider],
        candle_cache=SqlAlchemyCandleCache(session_factory),
    )
    cached = second_gateway.get_candles(query)

    assert cached.source.cache_status == "hit"
    assert cached.candles[0].close == 2405
    assert empty_provider.candle_fetch_count == 0


def test_database_cache_outage_does_not_block_provider_fallback():
    def unavailable_session():
        raise SQLAlchemyError("database unavailable")

    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping("memory", "series", target_id, "XAU/USD"),
    )
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    provider = InMemoryMarketDataProvider(provider_id="memory")
    provider.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 120, True),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[provider],
        candle_cache=SqlAlchemyCandleCache(unavailable_session),
    )

    result = gateway.get_candles(
        CandleQuery(
            series_id=target_id,
            timeframe="1h",
            start=open_time,
            end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        ),
    )

    assert result.source.provider_id == "memory"
