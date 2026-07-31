from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace

import httpx
import pandas as pd

from services import market_research
from services.market_gateway import (
    Candle,
    InMemoryMarketDataProvider,
    MarketDataGateway,
    default_catalog,
)


class _FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, *_args, **_kwargs):
        return next(self.responses)


def _response(payload):
    return httpx.Response(200, json=payload, request=httpx.Request("GET", "https://example.test"))


def test_market_snapshot_falls_back_through_gateway_when_twelve_is_unconfigured(
    monkeypatch,
):
    catalog = default_catalog()
    provider = InMemoryMarketDataProvider(provider_id="yahoo")
    times = pd.date_range("2026-06-01", periods=60, freq="1D", tz="UTC")
    provider.set_candles(
        provider_symbol="EURUSD=X",
        timeframe="1day",
        candles=[
            Candle(
                timestamp.to_pydatetime(),
                1.10 + index / 10_000,
                1.11 + index / 10_000,
                1.09 + index / 10_000,
                1.105 + index / 10_000,
                None,
                True,
            )
            for index, timestamp in enumerate(times)
        ],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[provider])
    monkeypatch.setattr(
        market_research,
        "get_market_data_gateway",
        lambda: gateway,
    )
    monkeypatch.setattr(
        market_research,
        "_now",
        lambda: datetime(2026, 7, 31, tzinfo=timezone.utc),
    )

    out = market_research.get_market_snapshot("forex", "EURUSD")

    assert out["provider"] == "yahoo"
    assert out["symbol"] == "EUR/USD"
    assert out["quote"]["price"] is not None
    assert out["technicals"]["sma20"] is not None


def test_futures_snapshot_uses_contract_metadata(monkeypatch):
    provider = InMemoryMarketDataProvider(provider_id="tradingview")
    times = pd.date_range("2026-07-01", periods=30, freq="h", tz="UTC")
    provider.set_candles(
        provider_symbol="MNQ1!",
        timeframe="1h",
        candles=[
            Candle(
                timestamp.to_pydatetime(),
                20000 + index,
                20002 + index,
                19998 + index,
                20001 + index,
                1000 + index,
                True,
            )
            for index, timestamp in enumerate(times)
        ],
    )
    gateway = MarketDataGateway(
        catalog=default_catalog(),
        providers=[provider],
    )
    monkeypatch.setattr(
        market_research,
        "get_market_data_gateway",
        lambda: gateway,
    )
    monkeypatch.setattr(
        market_research,
        "_now",
        lambda: datetime(2026, 7, 3, tzinfo=timezone.utc),
    )

    out = market_research.get_market_snapshot("futures", "MNQ", "1h")

    assert out["provider"] == "tradingview"
    assert out["symbol"] == "MNQ"
    assert out["quote"]["price"] == 20030
    assert out["instrument"]["point_value"] == 2
    assert out["technicals"]["atr14"] is not None


def test_macro_topic_resolves_to_fred_series(monkeypatch):
    monkeypatch.setattr("config.FRED_API_KEY", "test")
    fake = _FakeClient([
        _response({"seriess": [{"title": "Consumer Price Index", "units": "Index", "frequency": "Monthly"}]}),
        _response({"observations": [{"date": "2026-06-01", "value": "321.2"},
                                     {"date": "2026-05-01", "value": "."}]}),
    ])
    monkeypatch.setattr(market_research.httpx, "Client", lambda **_kwargs: fake)

    out = market_research.get_macro_series("inflation")

    assert out["series_id"] == "CPIAUCSL"
    assert out["observations"] == [{"date": "2026-06-01", "value": 321.2}]


def test_overview_quotes_use_gateway_and_keep_partial_fallbacks(monkeypatch):
    market_research._CACHE.clear()
    catalog = default_catalog()
    yahoo = InMemoryMarketDataProvider(provider_id="yahoo")
    tradingview = InMemoryMarketDataProvider(provider_id="tradingview")
    as_of = datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc)
    for provider_symbol in (
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "NQ=F",
        "ES=F",
        "TLT",
        "HYG",
        "USO",
        "GLD",
        "SLV",
        "GC=F",
        "EURUSD=X",
        "GBPUSD=X",
        "JPY=X",
        "AUDUSD=X",
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
    ):
        yahoo.set_quote(
            provider_symbol=provider_symbol,
            bid=None,
            ask=None,
            last=101,
            previous_close=100,
            as_of=as_of,
            open=99,
            high=102,
            low=98,
        )
    tradingview.set_quote(
        provider_symbol="XAUUSD",
        bid=None,
        ask=None,
        last=101,
        previous_close=100,
        as_of=as_of,
        open=99,
        high=102,
        low=98,
    )
    gateway = MarketDataGateway(
        catalog=catalog,
        providers=[yahoo, tradingview],
    )
    monkeypatch.setattr(
        market_research,
        "get_market_data_gateway",
        lambda: gateway,
    )

    out = market_research.get_overview_quotes()

    assert len(out["items"]) == 20
    assert [item["symbol"] for item in out["items"][:2]] == ["NQ", "ES"]
    assert out["items"][0]["price"] == 101
    assert out["items"][0]["percent_change"] == 1.0
    assert out["items"][0]["group"] == "indices"
    assert out["items"][0]["high"] == 102
    by_symbol = {item["symbol"]: item for item in out["items"]}
    assert by_symbol["EUR/USD"]["price"] == 101
    assert by_symbol["TLT"]["group"] == "rates"
    assert by_symbol["USO"]["group"] == "energy"
    assert by_symbol["SOL/USD"]["price"] == 101
    assert out["provider"] == "gateway"


def test_overview_quote_includes_provider_price_history():
    observed_at = datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc)
    quote = SimpleNamespace(
        last=103,
        previous_close=100,
        open=100,
        high=104,
        low=99,
        volume=10,
        currency="USD",
        as_of=observed_at,
        recent_prices=(
            (datetime(2026, 7, 24, 10, 28, tzinfo=timezone.utc), 101),
            (datetime(2026, 7, 24, 10, 29, tzinfo=timezone.utc), 102),
            (observed_at, 103),
        ),
        source=SimpleNamespace(provider_id="test", provider_exchange="TEST"),
    )
    gateway = SimpleNamespace(
        has_series=lambda _series_id: True,
        get_quote=lambda _query: quote,
    )

    result = market_research._get_overview_quote(
        gateway,
        ("series:test", "TEST", "Test", "indices", ("test",)),
    )

    assert result["sparkline"] == [
        {"time": "2026-07-24T10:28:00+00:00", "price": 101},
        {"time": "2026-07-24T10:29:00+00:00", "price": 102},
        {"time": "2026-07-24T10:30:00+00:00", "price": 103},
    ]


def test_market_overview_fetches_quote_and_macro_providers_concurrently(monkeypatch):
    market_research._CACHE.clear()
    quote_started = Event()
    macro_started = Event()

    def fake_quotes():
        quote_started.set()
        assert macro_started.wait(timeout=2)
        return {"provider": "gateway", "items": []}

    def fake_macro(series_id, label):
        macro_started.set()
        assert quote_started.wait(timeout=2)
        return {"series_id": series_id, "label": label}

    monkeypatch.setattr(market_research, "get_overview_quotes", fake_quotes)
    monkeypatch.setattr(market_research, "_get_macro_indicator", fake_macro)

    out = market_research.get_market_overview()

    assert out["quotes"]["provider"] == "gateway"
    assert [item["series_id"] for item in out["macro"]] == [
        series_id for series_id, _label in market_research.OVERVIEW_MACRO
    ]


def test_market_overview_caches_composed_payload(monkeypatch):
    market_research._CACHE.clear()
    calls = {"quotes": 0, "macro": 0}

    def fake_quotes():
        calls["quotes"] += 1
        return {"provider": "gateway", "items": []}

    def fake_macro(series_id, label):
        calls["macro"] += 1
        return {"series_id": series_id, "label": label}

    monkeypatch.setattr(market_research, "get_overview_quotes", fake_quotes)
    monkeypatch.setattr(market_research, "_get_macro_indicator", fake_macro)

    first = market_research.get_market_overview()
    second = market_research.get_market_overview()

    assert second is first
    assert calls == {"quotes": 1, "macro": len(market_research.OVERVIEW_MACRO)}


def test_economic_calendar_keeps_this_weeks_significant_events(monkeypatch):
    market_research._CACHE.clear()
    fake = _FakeClient([_response([
        {"title": "Low event", "country": "USD", "date": "2099-07-13T08:00:00-04:00", "impact": "Low"},
        {"title": "CPI", "country": "USD", "date": "2099-07-13T08:30:00-04:00", "impact": "High",
         "actual": "2.7%", "forecast": "2.6%", "previous": "2.5%"},
        {"title": "PMI", "country": "EUR", "date": "2099-07-13T07:00:00-04:00", "impact": "Medium",
         "actual": "", "forecast": "51.2", "previous": "50.8"},
    ])])
    monkeypatch.setattr(market_research.httpx, "Client", lambda **_kwargs: fake)

    out = market_research.get_economic_calendar()

    assert [item["title"] for item in out["items"]] == ["PMI", "CPI"]
    assert out["items"][1]["impact"] == "high"
    assert out["provider"] == "forex_factory"


def test_market_news_normalizes_finnhub_items(monkeypatch):
    monkeypatch.setattr("config.FINNHUB_API_KEY", "test")
    market_research._CACHE.clear()
    fake = _FakeClient([_response([
        {
            "datetime": 1_720_000_000,
            "headline": "Fed signals patience",
            "source": "Example Wire",
            "summary": "Policy makers kept their guidance unchanged.",
            "url": "https://example.test/fed",
            "related": "SPY,QQQ",
        },
        {"datetime": 1_720_000_001, "headline": "Missing URL"},
    ])])
    monkeypatch.setattr(market_research.httpx, "Client", lambda **_kwargs: fake)

    out = market_research.get_market_news()

    assert out["provider"] == "finnhub"
    assert len(out["items"]) == 1
    assert out["items"][0]["source"] == "Example Wire"
    assert out["items"][0]["published_at"].endswith("+00:00")


def test_market_news_without_key(monkeypatch):
    monkeypatch.setattr("config.FINNHUB_API_KEY", "")
    assert market_research.get_market_news()["error"] == "news_data_not_configured"
