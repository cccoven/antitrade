"""Free-tier market research data for the AI assistant."""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

import httpx

from services.market_data import resolve_legacy_series_id
from services.market_data_runtime import get_market_data_gateway
from services.market_gateway import (
    CandleQuery,
    InstrumentSearch,
    MarketDataError,
    QuoteQuery,
)


FRED_URL = "https://api.stlouisfed.org/fred"
FINNHUB_URL = "https://finnhub.io/api/v1"
ECONOMIC_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FUTURES_INTERVAL_MAP = {
    "1min": "1", "5min": "5", "15min": "15", "1h": "60",
    "4h": "240", "1day": "D", "1week": "W", "1month": "M",
}

FRED_TOPICS = {
    "cpi": "CPIAUCSL",
    "inflation": "CPIAUCSL",
    "通胀": "CPIAUCSL",
    "pce": "PCEPI",
    "unemployment": "UNRATE",
    "失业率": "UNRATE",
    "payroll": "PAYEMS",
    "nonfarm": "PAYEMS",
    "非农": "PAYEMS",
    "gdp": "GDP",
    "fed funds": "FEDFUNDS",
    "利率": "FEDFUNDS",
    "10y": "DGS10",
    "十年期美债": "DGS10",
    "2y": "DGS2",
    "两年期美债": "DGS2",
    "dollar": "DTWEXBGS",
    "美元": "DTWEXBGS",
    "m2": "M2SL",
    "liquidity": "M2SL",
    "流动性": "M2SL",
    "financial conditions": "NFCI",
    "金融条件": "NFCI",
}

YAHOO_FIRST = ("yahoo", "tradingview", "twelve_data")
TRADINGVIEW_FIRST = ("tradingview", "yahoo", "twelve_data")

OVERVIEW_MARKETS = (
    ("series:futures:nq:front", "NQ", "Nasdaq Futures", "indices", TRADINGVIEW_FIRST),
    ("series:futures:es:front", "ES", "S&P Futures", "indices", TRADINGVIEW_FIRST),
    ("series:equity:spy:arcx", "SPY", "S&P 500", "indices", YAHOO_FIRST),
    ("series:equity:qqq:xnas", "QQQ", "Nasdaq 100", "indices", YAHOO_FIRST),
    ("series:equity:iwm:arcx", "IWM", "Russell 2000", "indices", YAHOO_FIRST),
    ("series:equity:dia:arcx", "DIA", "Dow Jones", "indices", YAHOO_FIRST),
    ("series:equity:tlt:xnas", "TLT", "US 20Y Treasury", "rates", YAHOO_FIRST),
    ("series:equity:hyg:arcx", "HYG", "High Yield Bonds", "rates", YAHOO_FIRST),
    ("series:equity:uso:arcx", "USO", "WTI Oil ETF", "energy", YAHOO_FIRST),
    ("series:equity:gld:arcx", "GLD", "Gold ETF", "metals", YAHOO_FIRST),
    ("series:equity:slv:arcx", "SLV", "Silver ETF", "metals", YAHOO_FIRST),
    ("series:futures:gc:front", "GC", "Gold Futures", "metals", TRADINGVIEW_FIRST),
    ("series:spot:xau-usd:consolidated", "XAU/USD", "Gold Spot", "metals", TRADINGVIEW_FIRST),
    ("series:spot:eur-usd:consolidated", "EUR/USD", "EUR/USD", "forex", YAHOO_FIRST),
    ("series:spot:gbp-usd:consolidated", "GBP/USD", "GBP/USD", "forex", YAHOO_FIRST),
    ("series:spot:usd-jpy:consolidated", "USD/JPY", "USD/JPY", "forex", YAHOO_FIRST),
    ("series:spot:aud-usd:consolidated", "AUD/USD", "AUD/USD", "forex", YAHOO_FIRST),
    ("series:crypto:btc-usd:consolidated", "BTC/USD", "Bitcoin", "crypto", YAHOO_FIRST),
    ("series:crypto:eth-usd:consolidated", "ETH/USD", "Ethereum", "crypto", YAHOO_FIRST),
    ("series:crypto:sol-usd:consolidated", "SOL/USD", "Solana", "crypto", YAHOO_FIRST),
)

OVERVIEW_MACRO = (
    ("CPIAUCSL", "CPI"),
    ("UNRATE", "Unemployment"),
    ("FEDFUNDS", "Fed Funds"),
    ("DGS2", "US 2Y"),
    ("DGS10", "US 10Y"),
    ("M2SL", "M2"),
)

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_OVERVIEW_LOCK = Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cached(key: str) -> dict[str, Any] | None:
    item = _CACHE.get(key)
    if item is None or item[0] <= time.monotonic():
        _CACHE.pop(key, None)
        return None
    return item[1]


def _store(key: str, value: dict[str, Any], ttl: int) -> dict[str, Any]:
    _CACHE[key] = (time.monotonic() + ttl, value)
    return value


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", ".") else None
    except (TypeError, ValueError):
        return None


def _normalize_symbol(symbol: str, asset_class: str) -> str:
    if asset_class == "futures":
        from services.instruments import normalize_instrument_symbol

        return normalize_instrument_symbol(asset_class, symbol)
    value = symbol.strip().upper().replace(" ", "")
    if asset_class == "stock" or "/" in value:
        return value
    value = value.replace("-", "").replace("_", "")
    quote_currencies = ("USDT", "USDC", "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD")
    for quote in quote_currencies:
        if value.endswith(quote) and len(value) > len(quote):
            return f"{value[:-len(quote)]}/{quote}"
    return value


def _technical_summary(values: list[dict[str, Any]]) -> dict[str, Any]:
    chronological = list(reversed(values))
    closes = [_number(row.get("close")) for row in chronological]
    highs = [_number(row.get("high")) for row in values[:20]]
    lows = [_number(row.get("low")) for row in values[:20]]
    closes = [v for v in closes if v is not None]
    highs = [v for v in highs if v is not None]
    lows = [v for v in lows if v is not None]

    def sma(period: int) -> float | None:
        return sum(closes[-period:]) / period if len(closes) >= period else None

    rsi14 = None
    if len(closes) >= 15:
        changes = [closes[i] - closes[i - 1] for i in range(len(closes) - 14, len(closes))]
        gains = sum(max(change, 0) for change in changes) / 14
        losses = sum(max(-change, 0) for change in changes) / 14
        rsi14 = 100.0 if losses == 0 else 100 - (100 / (1 + gains / losses))

    true_ranges: list[float] = []
    previous_close = None
    for row in chronological:
        high = _number(row.get("high"))
        low = _number(row.get("low"))
        close = _number(row.get("close"))
        if high is not None and low is not None:
            candidates = [high - low]
            if previous_close is not None:
                candidates.extend([abs(high - previous_close), abs(low - previous_close)])
            true_ranges.append(max(candidates))
        if close is not None:
            previous_close = close
    atr14 = sum(true_ranges[-14:]) / 14 if len(true_ranges) >= 14 else None

    return {
        "sma20": sma(20),
        "sma50": sma(50),
        "rsi14": rsi14,
        "atr14": atr14,
        "high20": max(highs) if highs else None,
        "low20": min(lows) if lows else None,
    }


def _futures_market_snapshot(symbol: str, interval: str) -> dict[str, Any]:
    return _gateway_market_snapshot("futures", symbol, interval)


def get_market_snapshot(asset_class: str, symbol: str, interval: str = "1day") -> dict[str, Any]:
    """Return a normalized snapshot through the shared market-data gateway."""
    if asset_class not in {"stock", "forex", "crypto", "futures"}:
        return {"error": "unsupported_asset_class"}
    return _gateway_market_snapshot(asset_class, symbol, interval)


def _gateway_market_snapshot(
    asset_class: str,
    symbol: str,
    interval: str,
) -> dict[str, Any]:
    gateway = get_market_data_gateway()
    canonical_asset_class = {
        "stock": "equity",
        "forex": "spot",
    }.get(asset_class, asset_class)
    series_id = resolve_legacy_series_id(gateway, symbol)
    if not series_id:
        return {
            "error": "unsupported_or_ambiguous_symbol",
            "symbol": _normalize_symbol(symbol, asset_class),
        }

    duration = {
        "1min": timedelta(minutes=1),
        "5min": timedelta(minutes=5),
        "15min": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1day": timedelta(days=1),
        "1week": timedelta(weeks=1),
        "1month": timedelta(days=31),
    }.get(interval)
    if duration is None:
        return {"error": "unsupported_interval", "symbol": symbol}
    end = _now()
    start = end - duration * 150
    try:
        candle_series = gateway.get_candles(
            CandleQuery(
                series_id=series_id,
                timeframe=interval,
                start=start,
                end=end + duration,
                purpose="interactive",
            ),
        )
    except MarketDataError as exc:
        return {
            "error": exc.code,
            "symbol": _normalize_symbol(symbol, asset_class),
        }

    matches = gateway.search_instruments(
        InstrumentSearch(text=symbol, asset_class=canonical_asset_class),
    )
    match = next(
        (candidate for candidate in matches if candidate.series_id == series_id),
        None,
    )
    values = [
        {
            "datetime": candle.open_time.isoformat(),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in reversed(candle_series.candles[-100:])
    ]
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    price = latest["close"]
    previous_close = previous["close"]
    change = price - previous_close
    percent_change = (
        change / previous_close * 100 if previous_close not in (None, 0) else None
    )
    warnings = list(candle_series.quality.warnings)
    if candle_series.source.provider_id == "tradingview":
        warnings.append("anonymous_provider")
    futures_spec = match.futures_spec if match else None
    result = {
        "provider": candle_series.source.provider_id,
        "asset_class": asset_class,
        "series_id": series_id,
        "symbol": match.display_symbol if match else _normalize_symbol(symbol, asset_class),
        "exchange": (
            candle_series.source.provider_exchange
            or (match.venue if match else None)
        ),
        "currency": futures_spec.currency if futures_spec else None,
        "interval": interval,
        "as_of": latest["datetime"],
        "fetched_at": candle_series.source.fetched_at.isoformat(),
        "quote": {
            "price": price,
            "open": latest["open"],
            "high": latest["high"],
            "low": latest["low"],
            "previous_close": previous_close,
            "change": change,
            "percent_change": percent_change,
            "volume": latest["volume"],
        },
        "technicals": _technical_summary(values),
        "recent_candles": values[:30],
        "warnings": list(dict.fromkeys(warnings)),
    }
    if futures_spec is not None:
        result["instrument"] = {
            "tick_size": futures_spec.tick_size,
            "tick_value": futures_spec.tick_value,
            "point_value": futures_spec.point_value,
            "timezone": futures_spec.timezone,
        }
    return result


def get_macro_series(topic: str, series_id: str | None = None) -> dict[str, Any]:
    """Return recent observations for one FRED macro series."""
    from config import FRED_API_KEY

    if not FRED_API_KEY:
        return {"error": "macro_data_not_configured", "provider": "fred"}

    resolved = series_id.strip().upper() if series_id else FRED_TOPICS.get(topic.strip().lower())
    if not resolved:
        return {"error": "unknown_macro_topic", "supported_topics": sorted(FRED_TOPICS)}
    if not re.fullmatch(r"[A-Z0-9_-]{1,50}", resolved):
        return {"error": "invalid_series_id"}

    cache_key = f"fred:{resolved}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    common = {"api_key": FRED_API_KEY, "file_type": "json"}
    try:
        with httpx.Client(timeout=12) as client:
            info_response = client.get(f"{FRED_URL}/series", params={**common, "series_id": resolved})
            data_response = client.get(
                f"{FRED_URL}/series/observations",
                params={**common, "series_id": resolved, "sort_order": "desc", "limit": 12},
            )
            info_response.raise_for_status()
            data_response.raise_for_status()
            info_payload = info_response.json()
            data_payload = data_response.json()
    except (httpx.HTTPError, ValueError):
        return {"error": "macro_data_unavailable", "provider": "fred"}

    series = (info_payload.get("seriess") or [{}])[0]
    observations = [
        {"date": item.get("date"), "value": _number(item.get("value"))}
        for item in data_payload.get("observations", [])
        if _number(item.get("value")) is not None
    ]
    result = {
        "provider": "fred",
        "series_id": resolved,
        "title": series.get("title"),
        "units": series.get("units"),
        "frequency": series.get("frequency"),
        "last_updated": series.get("last_updated"),
        "observations": observations,
    }
    return _store(cache_key, result, 3600)


def _get_overview_quote(gateway, market) -> dict[str, Any]:
    series_id, symbol, label, group, preferred_providers = market
    if not gateway.has_series(series_id):
        return {
            "symbol": symbol,
            "label": label,
            "group": group,
            "error": "unsupported_or_ambiguous_symbol",
        }
    try:
        quote = gateway.get_quote(
            QuoteQuery(
                target_type="series",
                target_id=series_id,
                preferred_providers=preferred_providers,
            ),
        )
    except MarketDataError as exc:
        return {
            "symbol": symbol,
            "label": label,
            "group": group,
            "error": exc.code,
        }
    change = (
        quote.last - quote.previous_close
        if quote.previous_close is not None
        else None
    )
    percent_change = (
        change / quote.previous_close * 100
        if change is not None and quote.previous_close not in (None, 0)
        else None
    )
    return {
        "symbol": symbol,
        "label": label,
        "group": group,
        "price": quote.last,
        "change": change,
        "percent_change": percent_change,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "volume": quote.volume,
        "currency": quote.currency,
        "exchange": quote.source.provider_exchange,
        "as_of": quote.as_of.isoformat(),
        "provider": quote.source.provider_id,
        "sparkline": [
            {"time": observed_at.isoformat(), "price": price}
            for observed_at, price in quote.recent_prices
        ],
    }


def get_overview_quotes(force_refresh: bool = False) -> dict[str, Any]:
    """Fetch dashboard quotes through the shared gateway with per-symbol fallback."""
    if not force_refresh:
        cached = _cached("overview:quotes")
        if cached is not None:
            return cached

    gateway = get_market_data_gateway()
    with ThreadPoolExecutor(max_workers=4) as executor:
        items = list(executor.map(
            lambda market: _get_overview_quote(gateway, market),
            OVERVIEW_MARKETS,
        ))
    result: dict[str, Any] = {"provider": "gateway", "items": items}
    if not any("price" in item for item in items):
        result["error"] = "market_data_unavailable"
    return _store("overview:quotes", result, 60)


def _get_macro_indicator(series_id: str, label: str) -> dict[str, Any]:
    from config import FRED_API_KEY

    if not FRED_API_KEY:
        return {"series_id": series_id, "label": label, "error": "macro_data_not_configured"}
    cache_key = f"overview:fred:{series_id}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=12) as client:
            response = client.get(
                f"{FRED_URL}/series/observations",
                params={
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "series_id": series_id,
                    "sort_order": "desc",
                    "limit": 12,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"series_id": series_id, "label": label, "error": "macro_data_unavailable"}

    observations = [
        {"date": item.get("date"), "value": _number(item.get("value"))}
        for item in payload.get("observations", [])
        if _number(item.get("value")) is not None
    ]
    result = {
        "series_id": series_id,
        "label": label,
        "latest": observations[0] if observations else None,
        "previous": observations[1] if len(observations) > 1 else None,
    }
    return _store(cache_key, result, 3600)


def _event_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def get_economic_calendar() -> dict[str, Any]:
    """Return this week's medium- and high-impact events from the public export."""
    cached = _cached("overview:economic-calendar")
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=12) as client:
            response = client.get(ECONOMIC_CALENDAR_URL)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"error": "calendar_unavailable", "provider": "forex_factory", "items": []}

    if not isinstance(payload, list):
        return {"error": "calendar_unavailable", "provider": "forex_factory", "items": []}

    events = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        event_time = _event_datetime(row.get("date"))
        impact = str(row.get("impact") or "").lower()
        if event_time is None or impact not in {"medium", "high"}:
            continue
        events.append({
            "title": row.get("title"),
            "currency": row.get("country"),
            "date": event_time.isoformat(),
            "impact": impact,
            "actual": row.get("actual"),
            "forecast": row.get("forecast"),
            "previous": row.get("previous"),
        })

    events.sort(key=lambda item: item["date"])
    result = {
        "provider": "forex_factory",
        "source_url": "https://www.forexfactory.com/calendar",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": events,
    }
    return _store("overview:economic-calendar", result, 900)


def get_market_news() -> dict[str, Any]:
    """Return recent general-market headlines from Finnhub when configured."""
    from config import FINNHUB_API_KEY

    if not FINNHUB_API_KEY:
        return {"error": "news_data_not_configured", "provider": "finnhub", "items": []}
    cached = _cached("overview:market-news")
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=12) as client:
            response = client.get(
                f"{FINNHUB_URL}/news",
                params={"category": "general", "minId": 0, "token": FINNHUB_API_KEY},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"error": "news_data_unavailable", "provider": "finnhub", "items": []}

    if not isinstance(payload, list):
        return {"error": "news_data_unavailable", "provider": "finnhub", "items": []}

    items = []
    for row in payload[:20]:
        if not isinstance(row, dict) or not row.get("headline") or not row.get("url"):
            continue
        published_at = None
        timestamp = _number(row.get("datetime"))
        if timestamp is not None:
            published_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        items.append({
            "title": str(row["headline"]),
            "summary": str(row.get("summary") or ""),
            "source": str(row.get("source") or "Finnhub"),
            "url": str(row["url"]),
            "published_at": published_at,
            "related": str(row.get("related") or ""),
        })

    result = {
        "provider": "finnhub",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    return _store("overview:market-news", result, 300)


def get_market_overview(force_refresh: bool = False) -> dict[str, Any]:
    """Compose the public dashboard payload without invoking an LLM."""
    if not force_refresh:
        cached = _cached("overview:composed")
        if cached is not None:
            return cached

    with _OVERVIEW_LOCK:
        if not force_refresh:
            cached = _cached("overview:composed")
            if cached is not None:
                return cached

        with ThreadPoolExecutor(max_workers=2) as executor:
            quotes_future = (
                executor.submit(get_overview_quotes, True)
                if force_refresh
                else executor.submit(get_overview_quotes)
            )
            macro = [
                _get_macro_indicator(series_id, label)
                for series_id, label in OVERVIEW_MACRO
            ]
            quotes = quotes_future.result()

        changes = {
            item["symbol"]: item["percent_change"]
            for item in quotes.get("items", [])
            if item.get("percent_change") is not None
        }
        risk_values = [
            changes[symbol]
            for symbol in ("SPY", "QQQ", "BTC/USD")
            if symbol in changes
        ]
        risk_score = sum(risk_values) / len(risk_values) if risk_values else None
        result = {
            "quotes": quotes,
            "macro": macro,
            "states": {
                "risk": None if risk_score is None else ("risk_on" if risk_score >= 0 else "risk_off"),
                "equities": None if "SPY" not in changes else ("up" if changes["SPY"] >= 0 else "down"),
                "crypto": None if "BTC/USD" not in changes else ("up" if changes["BTC/USD"] >= 0 else "down"),
                "dollar": None if "EUR/USD" not in changes else ("weaker" if changes["EUR/USD"] >= 0 else "stronger"),
                "gold": None if "GLD" not in changes else ("up" if changes["GLD"] >= 0 else "down"),
            },
        }
        return _store("overview:composed", result, 5)
