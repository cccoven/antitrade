from datetime import datetime, timezone

import httpx
import pandas as pd

from services.market_data_providers import (
    TradingViewAdapter,
    TwelveDataAdapter,
    YahooAdapter,
)
from services.market_gateway import CandleQuery, ProviderMapping, QuoteQuery


def test_twelve_data_adapter_normalizes_candles_to_utc():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "values": [
                    {
                        "datetime": "2026-07-24 11:00:00",
                        "open": "2405",
                        "high": "2412",
                        "low": "2400",
                        "close": "2410",
                        "volume": None,
                    },
                    {
                        "datetime": "2026-07-24 10:00:00",
                        "open": "2400",
                        "high": "2410",
                        "low": "2395",
                        "close": "2405",
                        "volume": "120",
                    },
                ],
            },
        )

    adapter = TwelveDataAdapter(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        now=lambda: datetime(2026, 7, 24, 12, 30, tzinfo=timezone.utc),
    )
    query = CandleQuery(
        series_id="series:spot:xau-usd:consolidated",
        timeframe="1h",
        start=datetime(2026, 7, 24, 10, tzinfo=timezone.utc),
        end=datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
    )

    result = adapter.fetch_candles(
        ProviderMapping(
            provider_id="twelve_data",
            target_type="series",
            target_id=query.series_id,
            provider_symbol="XAU/USD",
        ),
        query,
    )

    assert [candle.open_time.hour for candle in result.candles] == [10, 11]
    assert all(candle.open_time.tzinfo is timezone.utc for candle in result.candles)
    assert result.candles[0].volume == 120
    assert result.candles[1].volume is None
    assert all(candle.is_closed for candle in result.candles)
    assert requests[0].url.params["interval"] == "1h"
    assert requests[0].url.params["timezone"] == "UTC"


def test_yahoo_adapter_resamples_one_hour_bars_to_four_hours():
    calls: list[str] = []

    def history_loader(_symbol, _start, _end, interval):
        calls.append(interval)
        index = pd.date_range(
            "2026-07-24 00:00",
            periods=8,
            freq="1h",
            tz="UTC",
        )
        return pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104, 105, 106, 107],
                "High": [102, 103, 104, 105, 106, 107, 108, 109],
                "Low": [99, 100, 101, 102, 103, 104, 105, 106],
                "Close": [101, 102, 103, 104, 105, 106, 107, 108],
                "Volume": [10] * 8,
            },
            index=index,
        )

    adapter = YahooAdapter(
        history_loader=history_loader,
        now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    query = CandleQuery(
        series_id="series:equity:aapl:xnas",
        timeframe="4h",
        start=datetime(2026, 7, 24, tzinfo=timezone.utc),
        end=datetime(2026, 7, 24, 8, tzinfo=timezone.utc),
    )

    result = adapter.fetch_candles(
        ProviderMapping(
            provider_id="yahoo",
            target_type="series",
            target_id=query.series_id,
            provider_symbol="AAPL",
        ),
        query,
    )

    assert calls == ["1h"]
    assert len(result.candles) == 2
    assert result.candles[0].open == 100
    assert result.candles[0].high == 105
    assert result.candles[0].low == 99
    assert result.candles[0].close == 104
    assert result.candles[0].volume == 40


def test_yahoo_quote_reuses_loaded_rows_as_price_history():
    def history_loader(_symbol, _start, _end, _interval):
        return pd.DataFrame(
            {
                "Open": [99, 100, 101, 102],
                "High": [101, 102, 103, 104],
                "Low": [98, 99, 100, 101],
                "Close": [100, 101.5, 101, 103],
                "Volume": [10, 11, 12, 13],
            },
            index=pd.date_range("2026-07-21", periods=4, freq="1D", tz="UTC"),
        )

    adapter = YahooAdapter(
        history_loader=history_loader,
        now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    result = adapter.fetch_quote(
        ProviderMapping(
            provider_id="yahoo",
            target_type="series",
            target_id="series:equity:spy:arcx",
            provider_symbol="SPY",
        ),
        QuoteQuery(target_type="series", target_id="series:equity:spy:arcx"),
    )

    assert [price for _, price in result.recent_prices] == [100, 101.5, 101, 103]


def test_tradingview_adapter_recreates_client_and_normalizes_exchange_time():
    calls: list[tuple[str, str, int]] = []
    expected_times = [
        datetime(2026, 7, 24, hour, tzinfo=timezone.utc)
        for hour in (10, 11)
    ]
    tvdatafeed_naive_times = [
        datetime.fromtimestamp(value.timestamp())
        for value in expected_times
    ]

    class FakeTvClient:
        def get_hist(self, *, symbol, exchange, interval, n_bars):
            calls.append((symbol, exchange, n_bars))
            return pd.DataFrame(
                {
                    "open": [2400, 2405],
                    "high": [2410, 2412],
                    "low": [2395, 2400],
                    "close": [2405, 2410],
                    "volume": [100, 110],
                },
                    index=pd.DatetimeIndex(tvdatafeed_naive_times),
            )

    created: list[FakeTvClient] = []

    def client_factory():
        client = FakeTvClient()
        created.append(client)
        return client

    adapter = TradingViewAdapter(
        client_factory=client_factory,
        now=lambda: datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
    )
    query = CandleQuery(
        series_id="series:futures:gc:front",
        timeframe="1h",
        start=datetime(2026, 7, 24, 10, tzinfo=timezone.utc),
        end=datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
    )

    result = adapter.fetch_candles(
        ProviderMapping(
            provider_id="tradingview",
            target_type="series",
            target_id=query.series_id,
            provider_symbol="GC1!",
            provider_exchange="COMEX",
            provider_timezone="America/New_York",
        ),
        query,
    )

    assert len(created) == 1
    assert calls[0][:2] == ("GC1!", "COMEX")
    assert [candle.open_time for candle in result.candles] == expected_times
    assert all(candle.open_time.tzinfo is timezone.utc for candle in result.candles)


def test_tradingview_quote_reuses_intraday_candles_as_price_history():
    class FakeTvClient:
        def get_hist(self, **_kwargs):
            return pd.DataFrame(
                {
                    "open": [100, 101, 100.5, 102],
                    "high": [102, 102, 103, 104],
                    "low": [99, 100, 100, 101],
                    "close": [101, 100.5, 102, 103],
                    "volume": [10, 11, 12, 13],
                },
                index=pd.date_range(
                    "2026-07-24 11:57",
                    periods=4,
                    freq="1min",
                    tz="UTC",
                ),
            )

    adapter = TradingViewAdapter(
        client_factory=FakeTvClient,
        now=lambda: datetime(2026, 7, 24, 12, 1, tzinfo=timezone.utc),
    )
    result = adapter.fetch_quote(
        ProviderMapping(
            provider_id="tradingview",
            target_type="series",
            target_id="series:futures:nq:front",
            provider_symbol="NQ1!",
            provider_exchange="CME_MINI",
        ),
        QuoteQuery(target_type="series", target_id="series:futures:nq:front"),
    )

    assert [price for _, price in result.recent_prices] == [101, 100.5, 102, 103]


def test_twelve_data_adapter_chunks_ranges_larger_than_provider_limit():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        start = request.url.params["start_date"]
        return httpx.Response(
            200,
            json={
                "values": [
                    {
                        "datetime": start,
                        "open": "100",
                        "high": "101",
                        "low": "99",
                        "close": "100.5",
                        "volume": "1",
                    },
                ],
            },
        )

    adapter = TwelveDataAdapter(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        now=lambda: datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    query = CandleQuery(
        series_id="series:crypto:btc-usd:consolidated",
        timeframe="1min",
        start=start,
        end=start + pd.Timedelta(minutes=10_000),
    )

    result = adapter.fetch_candles(
        ProviderMapping(
            provider_id="twelve_data",
            target_type="series",
            target_id=query.series_id,
            provider_symbol="BTC/USD",
        ),
        query,
    )

    assert len(requests) == 3
    assert len(result.candles) == 3
