"""Application composition root for the shared MarketDataGateway."""

from __future__ import annotations

from functools import lru_cache

from config import TWELVE_DATA_API_KEY
from db import SessionLocal
from services.market_data_cache import SqlAlchemyCandleCache
from services.market_data_providers import (
    TradingViewAdapter,
    TwelveDataAdapter,
    YahooAdapter,
)
from services.market_gateway import InMemoryQuoteCache, MarketDataGateway, default_catalog


@lru_cache(maxsize=1)
def get_market_data_gateway() -> MarketDataGateway:
    providers = []
    if TWELVE_DATA_API_KEY:
        providers.append(TwelveDataAdapter(api_key=TWELVE_DATA_API_KEY))
    providers.extend((YahooAdapter(), TradingViewAdapter()))
    return MarketDataGateway(
        catalog=default_catalog(),
        providers=providers,
        candle_cache=SqlAlchemyCandleCache(SessionLocal),
        quote_cache=InMemoryQuoteCache(ttl_seconds=15),
    )
