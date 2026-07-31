from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import time

import pytest

from services.market_gateway import (
    Candle,
    CandleQuery,
    CandleSeries,
    InMemoryCandleCache,
    InMemoryMarketDataProvider,
    InMemoryQuoteCache,
    InstrumentSearch,
    MarketDataError,
    MarketDataGateway,
    ProviderMapping,
    QualityReport,
    QuoteQuery,
    SourceMetadata,
    default_catalog,
)


def test_xauusd_spot_resolves_to_spot_series_not_futures():
    gateway = MarketDataGateway(catalog=default_catalog())

    matches = gateway.search_instruments(
        InstrumentSearch(text="XAUUSD", asset_class="spot"),
    )

    assert len(matches) == 1
    assert matches[0].series_id == "series:spot:xau-usd:consolidated"
    assert matches[0].asset_class == "spot"
    assert matches[0].display_symbol == "XAU/USD"
    assert "GC=F" not in repr(matches[0])
    assert gateway.search_instruments(
        InstrumentSearch(text="XAUUSD", asset_class="futures"),
    ) == []


def test_gc_product_and_tradingview_alias_resolve_to_same_futures_series():
    gateway = MarketDataGateway(catalog=default_catalog())

    product_matches = gateway.search_instruments(
        InstrumentSearch(text="GC", asset_class="futures"),
    )
    provider_matches = gateway.search_instruments(
        InstrumentSearch(text="GC1!", asset_class="futures", provider="tradingview"),
    )

    assert [match.series_id for match in product_matches] == ["series:futures:gc:front"]
    assert [match.series_id for match in provider_matches] == ["series:futures:gc:front"]
    assert provider_matches[0].venue == "COMEX"
    assert provider_matches[0].futures_spec.point_value == 100.0
    assert provider_matches[0].futures_spec.tick_size == 0.1
    implicit_matches = gateway.search_instruments(
        InstrumentSearch(text="GC1!", asset_class="futures"),
    )
    assert [match.series_id for match in implicit_matches] == [
        "series:futures:gc:front",
    ]


def test_provider_alias_resolves_to_instrument_without_caller_provider_hint():
    gateway = MarketDataGateway(catalog=default_catalog())

    instrument = gateway.resolve_instrument(
        InstrumentSearch(text="GC1!", asset_class="futures"),
    )

    assert instrument is not None
    assert instrument.id == "instrument:futures:gc"


def test_btcusd_without_venue_returns_candidates_instead_of_guessing():
    gateway = MarketDataGateway(catalog=default_catalog())

    matches = gateway.search_instruments(
        InstrumentSearch(text="BTCUSD", asset_class="crypto"),
    )

    assert {match.venue for match in matches} == {None, "BINANCE", "COINBASE"}
    assert {match.series_id for match in matches} == {
        "series:crypto:btc-usd:binance",
        "series:crypto:btc-usd:coinbase",
        "series:crypto:btc-usd:consolidated",
    }


def test_catalog_search_supports_symbol_prefix_for_selector_ui():
    gateway = MarketDataGateway(catalog=default_catalog())

    matches = gateway.search_instruments(
        InstrumentSearch(text="BT", asset_class="crypto"),
    )

    assert {match.series_id for match in matches} == {
        "series:crypto:btc-usd:binance",
        "series:crypto:btc-usd:coinbase",
        "series:crypto:btc-usd:consolidated",
    }


def test_venue_context_disambiguates_btcusd():
    gateway = MarketDataGateway(catalog=default_catalog())

    matches = gateway.search_instruments(
        InstrumentSearch(text="BTCUSD", asset_class="crypto", venue="coinbase"),
    )

    assert len(matches) == 1
    assert matches[0].series_id == "series:crypto:btc-usd:coinbase"


@pytest.mark.parametrize(
    ("text", "asset_class", "expected_series"),
    [
        ("XAGUSD", "spot", "series:spot:xag-usd:consolidated"),
        ("EURUSD", "spot", "series:spot:eur-usd:consolidated"),
        ("GBPUSD", "spot", "series:spot:gbp-usd:consolidated"),
        ("USDJPY", "spot", "series:spot:usd-jpy:consolidated"),
        ("AUDUSD", "spot", "series:spot:aud-usd:consolidated"),
        ("TSLA", "equity", "series:equity:tsla:xnas"),
        ("IWM", "equity", "series:equity:iwm:arcx"),
        ("TLT", "equity", "series:equity:tlt:xnas"),
        ("USO", "equity", "series:equity:uso:arcx"),
        ("SPX500", "index", "series:index:spx500:consolidated"),
    ],
)
def test_catalog_seeds_cover_existing_supported_aliases(
    text,
    asset_class,
    expected_series,
):
    gateway = MarketDataGateway(catalog=default_catalog())

    matches = gateway.search_instruments(
        InstrumentSearch(text=text, asset_class=asset_class),
    )

    assert [match.series_id for match in matches] == [expected_series]


def test_catalog_seeds_solusd_with_consolidated_and_venue_series():
    gateway = MarketDataGateway(catalog=default_catalog())

    matches = gateway.search_instruments(
        InstrumentSearch(text="SOLUSD", asset_class="crypto"),
    )

    assert {match.series_id for match in matches} == {
        "series:crypto:sol-usd:binance",
        "series:crypto:sol-usd:coinbase",
        "series:crypto:sol-usd:consolidated",
    }


def test_ethusd_is_venue_ambiguous_like_btcusd():
    gateway = MarketDataGateway(catalog=default_catalog())

    matches = gateway.search_instruments(
        InstrumentSearch(text="ETHUSD", asset_class="crypto"),
    )

    assert {match.venue for match in matches} == {None, "BINANCE", "COINBASE"}


def test_unknown_and_unverified_provider_symbols_are_not_guessed():
    gateway = MarketDataGateway(catalog=default_catalog())

    assert gateway.search_instruments(InstrumentSearch(text="UNKNOWN")) == []
    assert gateway.search_instruments(
        InstrumentSearch(text="GC=F", asset_class="futures", provider="yahoo"),
    ) == []


def test_get_candles_uses_provider_mapping_and_returns_source_metadata():
    catalog = default_catalog()
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="memory",
            target_type="series",
            target_id="series:spot:xau-usd:consolidated",
            provider_symbol="XAU/USD",
        ),
    )
    provider = InMemoryMarketDataProvider(provider_id="memory")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    provider.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(
                open_time=open_time,
                open=2400,
                high=2410,
                low=2395,
                close=2405,
                volume=120,
                is_closed=True,
            ),
        ],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[provider])

    result = gateway.get_candles(
        CandleQuery(
            series_id="series:spot:xau-usd:consolidated",
            timeframe="1h",
            start=open_time,
            end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        ),
    )

    assert result.candles[0].close == 2405
    assert result.source.provider_id == "memory"
    assert result.source.provider_symbol == "XAU/USD"
    assert result.quality.status == "ok"
    assert result.instrument_id == "instrument:spot:xau-usd"
    assert result.listing_id is None
    assert result.requested_start == open_time
    assert result.requested_end == datetime(2026, 7, 24, 11, tzinfo=timezone.utc)
    assert result.actual_start == open_time
    assert result.actual_end == open_time


def test_get_quote_uses_the_same_canonical_target_and_mapping_boundary():
    catalog = default_catalog()
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="memory",
            target_type="series",
            target_id="series:crypto:btc-usd:coinbase",
            provider_symbol="BTC-USD",
        ),
    )
    provider = InMemoryMarketDataProvider(provider_id="memory")
    as_of = datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc)
    provider.set_quote(
        provider_symbol="BTC-USD",
        bid=118_000,
        ask=118_010,
        last=118_005,
        as_of=as_of,
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[provider])

    result = gateway.get_quote(
        QuoteQuery(
            target_type="series",
            target_id="series:crypto:btc-usd:coinbase",
        ),
    )

    assert result.last == 118_005
    assert result.as_of == as_of
    assert result.source.provider_id == "memory"
    assert result.source.provider_symbol == "BTC-USD"


def test_quote_query_can_prefer_a_mapped_provider():
    catalog = default_catalog()
    target_id = "series:equity:aapl:xnas"
    catalog.add_provider_mapping(
        ProviderMapping("primary", "series", target_id, "AAPL"),
    )
    catalog.add_provider_mapping(
        ProviderMapping("preferred", "series", target_id, "AAPL"),
    )
    primary = InMemoryMarketDataProvider(provider_id="primary")
    preferred = InMemoryMarketDataProvider(provider_id="preferred")
    as_of = datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc)
    primary.set_quote(
        provider_symbol="AAPL",
        bid=None,
        ask=None,
        last=100,
        as_of=as_of,
    )
    preferred.set_quote(
        provider_symbol="AAPL",
        bid=None,
        ask=None,
        last=101,
        as_of=as_of,
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[primary, preferred],
    )

    result = gateway.get_quote(
        QuoteQuery(
            target_type="series",
            target_id=target_id,
            preferred_providers=("preferred", "primary"),
        ),
    )

    assert result.last == 101
    assert result.source.provider_id == "preferred"


def test_repeated_quote_request_uses_short_lived_cache():
    catalog = default_catalog()
    target_id = "series:crypto:btc-usd:coinbase"
    catalog.add_provider_mapping(
        ProviderMapping("memory", "series", target_id, "BTC-USD"),
    )
    provider = InMemoryMarketDataProvider(provider_id="memory")
    as_of = datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc)
    provider.set_quote(
        provider_symbol="BTC-USD",
        bid=118_000,
        ask=118_010,
        last=118_005,
        as_of=as_of,
    )
    clock_value = [100.0]
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[provider],
        quote_cache=InMemoryQuoteCache(
            ttl_seconds=10,
            clock=lambda: clock_value[0],
        ),
    )
    query = QuoteQuery(target_type="series", target_id=target_id)

    first = gateway.get_quote(query)
    second = gateway.get_quote(query)
    clock_value[0] = 111.0
    third = gateway.get_quote(query)

    assert first.source.cache_status == "miss"
    assert second.source.cache_status == "hit"
    assert third.source.cache_status == "miss"
    assert provider.quote_fetch_count == 2


def test_quote_transient_failure_retries_then_falls_back():
    catalog = default_catalog()
    target_id = "series:crypto:btc-usd:coinbase"
    catalog.add_provider_mapping(
        ProviderMapping("primary", "series", target_id, "BTCUSD"),
    )
    catalog.add_provider_mapping(
        ProviderMapping("backup", "series", target_id, "BTC-USD"),
    )
    primary = InMemoryMarketDataProvider(provider_id="primary")
    primary.queue_quote_errors(
        provider_symbol="BTCUSD",
        error_codes=["timeout", "provider_unavailable", "rate_limited"],
    )
    backup = InMemoryMarketDataProvider(provider_id="backup")
    backup.set_quote(
        provider_symbol="BTC-USD",
        bid=118_000,
        ask=118_010,
        last=118_005,
        as_of=datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc),
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[primary, backup],
        retry_delays=(0, 0),
    )

    result = gateway.get_quote(
        QuoteQuery(target_type="series", target_id=target_id),
    )

    assert result.source.provider_id == "backup"
    assert primary.quote_fetch_count == 3


def test_quote_rejects_invalid_payload_and_falls_back():
    catalog = default_catalog()
    target_id = "series:equity:aapl:xnas"
    catalog.add_provider_mapping(
        ProviderMapping("invalid", "series", target_id, "AAPL"),
    )
    catalog.add_provider_mapping(
        ProviderMapping("backup", "series", target_id, "AAPL"),
    )
    invalid = InMemoryMarketDataProvider(provider_id="invalid")
    invalid.set_quote(
        provider_symbol="AAPL",
        bid=101,
        ask=100,
        last=float("nan"),
        as_of=datetime(2026, 7, 24),
    )
    backup = InMemoryMarketDataProvider(provider_id="backup")
    backup.set_quote(
        provider_symbol="AAPL",
        bid=100,
        ask=101,
        last=100.5,
        as_of=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[invalid, backup],
        retry_delays=(),
    )

    result = gateway.get_quote(
        QuoteQuery(target_type="series", target_id=target_id),
    )

    assert result.last == 100.5
    assert result.source.provider_id == "backup"
    assert invalid.quote_fetch_count == 1
    assert backup.quote_fetch_count == 1


def test_get_candles_falls_through_to_the_next_mapped_provider():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="primary",
            target_type="series",
            target_id=target_id,
            provider_symbol="XAUUSD",
        ),
    )
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="backup",
            target_type="series",
            target_id=target_id,
            provider_symbol="XAU/USD",
        ),
    )
    primary = InMemoryMarketDataProvider(provider_id="primary")
    backup = InMemoryMarketDataProvider(provider_id="backup")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    backup.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(
                open_time=open_time,
                open=2400,
                high=2410,
                low=2395,
                close=2405,
                volume=None,
                is_closed=True,
            ),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[primary, backup],
    )

    result = gateway.get_candles(
        CandleQuery(
            series_id=target_id,
            timeframe="1h",
            start=open_time,
            end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        ),
    )

    assert result.source.provider_id == "backup"


def test_repeated_candle_request_is_served_without_another_provider_call():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="memory",
            target_type="series",
            target_id=target_id,
            provider_symbol="XAU/USD",
        ),
    )
    provider = InMemoryMarketDataProvider(provider_id="memory")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    provider.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(
                open_time=open_time,
                open=2400,
                high=2410,
                low=2395,
                close=2405,
                volume=120,
                is_closed=True,
            ),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[provider],
        candle_cache=InMemoryCandleCache(),
    )
    query = CandleQuery(
        series_id=target_id,
        timeframe="1h",
        start=open_time,
        end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
    )

    first = gateway.get_candles(query)
    second = gateway.get_candles(query)

    assert first.source.cache_status == "miss"
    assert second.source.cache_status == "hit"
    assert provider.candle_fetch_count == 1


def test_stale_candles_are_returned_only_when_policy_allows_after_failure():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping("fixture", "series", target_id, "XAU/USD"),
    )
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    stale_series = CandleSeries(
        series_id=target_id,
        instrument_id="instrument:spot:xau-usd",
        listing_id=None,
        timeframe="1h",
        candles=(
            Candle(open_time, 2400, 2410, 2395, 2405, 10, True),
        ),
        requested_start=open_time,
        requested_end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        actual_start=open_time,
        actual_end=open_time,
        source=SourceMetadata(
            provider_id="fixture",
            provider_symbol="XAU/USD",
            provider_exchange=None,
            fetched_at=open_time,
        ),
        quality=QualityReport(status="ok"),
    )

    class StaleOnlyCache:
        def get(self, mapping, query):
            return None

        def get_stale(self, mapping, query):
            return stale_series

        def put(self, mapping, query, series):
            raise AssertionError("failed provider must not update cache")

    provider = InMemoryMarketDataProvider(provider_id="fixture")
    provider.queue_candle_errors(
        provider_symbol="XAU/USD",
        timeframe="1h",
        error_codes=["timeout", "timeout"],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[provider],
        candle_cache=StaleOnlyCache(),
        retry_delays=(),
    )
    base = {
        "series_id": target_id,
        "timeframe": "1h",
        "start": open_time,
        "end": datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
    }

    with pytest.raises(MarketDataError):
        gateway.get_candles(
            CandleQuery(**base, freshness="prefer_cache"),
        )
    result = gateway.get_candles(
        CandleQuery(**base, freshness="allow_stale"),
    )

    assert result.source.cache_status == "stale"
    assert result.quality.status == "warning"
    assert "stale_data" in result.quality.warnings


def test_require_fresh_bypasses_candle_cache():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping("memory", "series", target_id, "XAU/USD"),
    )
    provider = InMemoryMarketDataProvider(provider_id="memory")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
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
        candle_cache=InMemoryCandleCache(),
    )
    base = {
        "series_id": target_id,
        "timeframe": "1h",
        "start": open_time,
        "end": datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
    }
    gateway.get_candles(CandleQuery(**base))
    provider.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2420, 2395, 2415, 120, True),
        ],
    )

    fresh = gateway.get_candles(
        CandleQuery(**base, freshness="require_fresh"),
    )

    assert fresh.candles[0].close == 2415
    assert fresh.source.cache_status == "miss"
    assert provider.candle_fetch_count == 2


def test_transient_primary_failure_retries_then_falls_back():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    for provider_id, provider_symbol in (
        ("primary", "XAUUSD"),
        ("backup", "XAU/USD"),
    ):
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id=provider_id,
                target_type="series",
                target_id=target_id,
                provider_symbol=provider_symbol,
            ),
        )
    primary = InMemoryMarketDataProvider(provider_id="primary")
    primary.queue_candle_errors(
        provider_symbol="XAUUSD",
        timeframe="1h",
        error_codes=["timeout", "provider_unavailable", "rate_limited"],
    )
    backup = InMemoryMarketDataProvider(provider_id="backup")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    backup.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(
                open_time=open_time,
                open=2400,
                high=2410,
                low=2395,
                close=2405,
                volume=120,
                is_closed=True,
            ),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[primary, backup],
        retry_delays=(0, 0),
    )

    result = gateway.get_candles(
        CandleQuery(
            series_id=target_id,
            timeframe="1h",
            start=open_time,
            end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        ),
    )

    assert result.source.provider_id == "backup"
    assert primary.candle_fetch_count == 3
    assert backup.candle_fetch_count == 1


def test_open_circuit_skips_a_provider_that_just_failed_transiently():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    for provider_id, provider_symbol in (
        ("primary", "XAUUSD"),
        ("backup", "XAU/USD"),
    ):
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id=provider_id,
                target_type="series",
                target_id=target_id,
                provider_symbol=provider_symbol,
            ),
        )
    primary = InMemoryMarketDataProvider(provider_id="primary")
    primary.queue_candle_errors(
        provider_symbol="XAUUSD",
        timeframe="1h",
        error_codes=["timeout"] * 6,
    )
    backup = InMemoryMarketDataProvider(provider_id="backup")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    backup.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(
                open_time=open_time,
                open=2400,
                high=2410,
                low=2395,
                close=2405,
                volume=None,
                is_closed=True,
            ),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[primary, backup],
        retry_delays=(0, 0),
        circuit_failure_threshold=1,
    )
    query = CandleQuery(
        series_id=target_id,
        timeframe="1h",
        start=open_time,
        end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
    )

    gateway.get_candles(query)
    second = gateway.get_candles(query)

    assert second.source.provider_id == "backup"
    assert primary.candle_fetch_count == 3


def test_invalid_ohlc_is_rejected_before_falling_back():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    for provider_id, provider_symbol in (
        ("primary", "XAUUSD"),
        ("backup", "XAU/USD"),
    ):
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id=provider_id,
                target_type="series",
                target_id=target_id,
                provider_symbol=provider_symbol,
            ),
        )
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    primary = InMemoryMarketDataProvider(provider_id="primary")
    primary.set_candles(
        provider_symbol="XAUUSD",
        timeframe="1h",
        candles=[
            Candle(
                open_time=open_time,
                open=2400,
                high=2390,
                low=2395,
                close=2405,
                volume=10,
                is_closed=True,
            ),
        ],
    )
    backup = InMemoryMarketDataProvider(provider_id="backup")
    backup.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(
                open_time=open_time,
                open=2400,
                high=2410,
                low=2395,
                close=2405,
                volume=10,
                is_closed=True,
            ),
        ],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[primary, backup])

    result = gateway.get_candles(
        CandleQuery(
            series_id=target_id,
            timeframe="1h",
            start=open_time,
            end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        ),
    )

    assert result.source.provider_id == "backup"
    assert primary.candle_fetch_count == 1


def test_spot_gold_never_uses_yahoo_gold_futures_as_fallback():
    catalog = default_catalog()
    twelve = InMemoryMarketDataProvider(provider_id="twelve_data")
    yahoo = InMemoryMarketDataProvider(provider_id="yahoo")
    tradingview = InMemoryMarketDataProvider(provider_id="tradingview")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    yahoo.set_candles(
        provider_symbol="GC=F",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 10, True),
        ],
    )
    tradingview.set_candles(
        provider_symbol="XAUUSD",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 10, True),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[twelve, yahoo, tradingview],
        retry_delays=(),
    )

    result = gateway.get_candles(
        CandleQuery(
            series_id="series:spot:xau-usd:consolidated",
            timeframe="1h",
            start=open_time,
            end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
        ),
    )

    assert result.source.provider_id == "tradingview"
    assert result.source.provider_symbol == "XAUUSD"
    assert yahoo.candle_fetch_count == 0


def test_gold_futures_can_fall_back_from_tradingview_to_yahoo():
    catalog = default_catalog()
    tradingview = InMemoryMarketDataProvider(provider_id="tradingview")
    yahoo = InMemoryMarketDataProvider(provider_id="yahoo")
    open_time = datetime(2026, 7, 24, 4, tzinfo=timezone.utc)
    yahoo.set_candles(
        provider_symbol="GC=F",
        timeframe="D",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 10, True),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[tradingview, yahoo],
        retry_delays=(),
    )

    result = gateway.get_candles(
        CandleQuery(
            series_id="series:futures:gc:front",
            timeframe="D",
            start=open_time,
            end=datetime(2026, 7, 25, 4, tzinfo=timezone.utc),
        ),
    )

    assert result.source.provider_id == "yahoo"
    assert result.source.provider_symbol == "GC=F"


def test_backtest_rejects_incomplete_bars_before_falling_back():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping("primary", "series", target_id, "XAUUSD"),
    )
    catalog.add_provider_mapping(
        ProviderMapping("backup", "series", target_id, "XAU/USD"),
    )
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    primary = InMemoryMarketDataProvider(provider_id="primary")
    primary.set_candles(
        provider_symbol="XAUUSD",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 10, False),
        ],
    )
    backup = InMemoryMarketDataProvider(provider_id="backup")
    backup.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 10, True),
        ],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[primary, backup])

    result = gateway.get_candles(
        CandleQuery(
            series_id=target_id,
            timeframe="1h",
            start=open_time,
            end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
            purpose="backtest",
        ),
    )

    assert result.source.provider_id == "backup"


def test_concurrent_identical_cache_misses_make_one_provider_request():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping("slow", "series", target_id, "XAU/USD"),
    )

    class SlowProvider(InMemoryMarketDataProvider):
        def fetch_candles(self, mapping, query):
            time.sleep(0.05)
            return super().fetch_candles(mapping, query)

    provider = SlowProvider(provider_id="slow")
    open_time = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
    provider.set_candles(
        provider_symbol="XAU/USD",
        timeframe="1h",
        candles=[
            Candle(open_time, 2400, 2410, 2395, 2405, 10, True),
        ],
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[provider],
        candle_cache=InMemoryCandleCache(),
    )
    query = CandleQuery(
        series_id=target_id,
        timeframe="1h",
        start=open_time,
        end=datetime(2026, 7, 24, 11, tzinfo=timezone.utc),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(gateway.get_candles, (query, query)))

    assert provider.candle_fetch_count == 1
    assert {result.source.cache_status for result in results} == {"miss", "hit"}


def test_unsupported_timeframe_is_reported_explicitly():
    catalog = default_catalog()
    target_id = "series:spot:xau-usd:consolidated"
    catalog.add_provider_mapping(
        ProviderMapping("only", "series", target_id, "XAU/USD"),
    )
    provider = InMemoryMarketDataProvider(provider_id="only")
    provider.queue_candle_errors(
        provider_symbol="XAU/USD",
        timeframe="2h",
        error_codes=["unsupported_timeframe"],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[provider])

    with pytest.raises(MarketDataError) as captured:
        gateway.get_candles(
            CandleQuery(
                series_id=target_id,
                timeframe="2h",
                start=datetime(2026, 7, 24, 10, tzinfo=timezone.utc),
                end=datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
            ),
        )

    assert captured.value.code == "unsupported_timeframe"


def test_backtest_rejects_provider_with_incomplete_requested_coverage():
    catalog = default_catalog()
    target_id = "series:equity:aapl:xnas"
    catalog.add_provider_mapping(
        ProviderMapping("primary", "series", target_id, "AAPL"),
    )
    catalog.add_provider_mapping(
        ProviderMapping("backup", "series", target_id, "AAPL"),
    )
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 11, tzinfo=timezone.utc)
    primary = InMemoryMarketDataProvider(provider_id="primary")
    primary.set_candles(
        provider_symbol="AAPL",
        timeframe="D",
        candles=[
            Candle(
                datetime(2026, 7, day, tzinfo=timezone.utc),
                200,
                205,
                195,
                202,
                1000,
                True,
            )
            for day in (9, 10)
        ],
    )
    backup = InMemoryMarketDataProvider(provider_id="backup")
    backup.set_candles(
        provider_symbol="AAPL",
        timeframe="D",
        candles=[
            Candle(start, 190, 195, 185, 192, 1000, True),
            Candle(
                datetime(2026, 7, 10, tzinfo=timezone.utc),
                200,
                205,
                195,
                202,
                1000,
                True,
            ),
        ],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[primary, backup])

    result = gateway.get_candles(
        CandleQuery(
            series_id=target_id,
            timeframe="D",
            start=start,
            end=end,
            purpose="backtest",
        ),
    )

    assert result.source.provider_id == "backup"


def test_backtest_allows_intraday_boundary_gap_for_market_closure():
    catalog = default_catalog()
    target_id = "series:equity:aapl:xnas"
    catalog.add_provider_mapping(
        ProviderMapping("fixture", "series", target_id, "AAPL"),
    )
    provider = InMemoryMarketDataProvider(provider_id="fixture")
    start = datetime(2026, 7, 24, tzinfo=timezone.utc)
    provider.set_candles(
        provider_symbol="AAPL",
        timeframe="1h",
        candles=[
            Candle(
                datetime(2026, 7, 24, 14, tzinfo=timezone.utc),
                200,
                205,
                195,
                202,
                1000,
                True,
            ),
        ],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[provider])

    result = gateway.get_candles(
        CandleQuery(
            series_id=target_id,
            timeframe="1h",
            start=start,
            end=datetime(2026, 7, 24, 15, tzinfo=timezone.utc),
            purpose="backtest",
        ),
    )

    assert result.source.provider_id == "fixture"
