"""Production adapters for the internal market-data provider seam."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Callable

import httpx
import pandas as pd

from services.market_gateway import (
    Candle,
    CandleQuery,
    MarketDataError,
    ProviderCandleResponse,
    ProviderMapping,
    ProviderQuoteResponse,
    QuoteQuery,
)


TWELVE_DATA_URL = "https://api.twelvedata.com"

TWELVE_INTERVALS = {
    "1": "1min",
    "1min": "1min",
    "5": "5min",
    "5min": "5min",
    "15": "15min",
    "15min": "15min",
    "60": "1h",
    "1h": "1h",
    "240": "4h",
    "4h": "4h",
    "D": "1day",
    "1day": "1day",
    "W": "1week",
    "1week": "1week",
    "M": "1month",
    "1month": "1month",
}

TIMEFRAME_DURATION = {
    "1min": timedelta(minutes=1),
    "5min": timedelta(minutes=5),
    "15min": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1day": timedelta(days=1),
    "1week": timedelta(weeks=1),
    "1month": timedelta(days=31),
}

YAHOO_INTERVALS = {
    "1": "1m",
    "1min": "1m",
    "5": "5m",
    "5min": "5m",
    "15": "15m",
    "15min": "15m",
    "60": "1h",
    "1h": "1h",
    "D": "1d",
    "1day": "1d",
    "W": "1wk",
    "1week": "1wk",
    "M": "1mo",
    "1month": "1mo",
}


def _tradingview_intervals() -> dict[str, object]:
    from tvDatafeed import Interval

    return {
        "1": Interval.in_1_minute,
        "1min": Interval.in_1_minute,
        "5": Interval.in_5_minute,
        "5min": Interval.in_5_minute,
        "15": Interval.in_15_minute,
        "15min": Interval.in_15_minute,
        "60": Interval.in_1_hour,
        "1h": Interval.in_1_hour,
        "240": Interval.in_4_hour,
        "4h": Interval.in_4_hour,
        "D": Interval.in_daily,
        "1day": Interval.in_daily,
        "W": Interval.in_weekly,
        "1week": Interval.in_weekly,
        "M": Interval.in_monthly,
        "1month": Interval.in_monthly,
    }


def _number(value: object, *, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataError(
            "invalid_payload",
            f"invalid numeric field {field}",
        ) from exc


def _optional_number(value: object) -> float | None:
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataError("invalid_payload", "invalid optional numeric field") from exc


def _utc_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise MarketDataError("invalid_payload", "missing candle datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketDataError("invalid_payload", "invalid candle datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class TwelveDataAdapter:
    provider_id = "twelve_data"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 10,
        transport: httpx.BaseTransport | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._now = now

    def fetch_candles(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> ProviderCandleResponse:
        interval = TWELVE_INTERVALS.get(query.timeframe)
        if interval is None:
            raise MarketDataError(
                "unsupported_timeframe",
                f"Twelve Data does not support {query.timeframe}",
            )
        if not self._api_key:
            raise MarketDataError(
                "authentication_failed",
                "Twelve Data API key is not configured",
            )

        duration = TIMEFRAME_DURATION[interval]
        cursor = query.start.astimezone(timezone.utc)
        requested_end = query.end.astimezone(timezone.utc)
        chunk_span = duration * 4500
        values: list[object] = []
        while cursor < requested_end:
            chunk_end = min(cursor + chunk_span, requested_end)
            params: dict[str, object] = {
                "symbol": mapping.provider_symbol,
                "interval": interval,
                "start_date": cursor.strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": chunk_end.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": "UTC",
                "order": "asc",
                "outputsize": 5000,
                "apikey": self._api_key,
            }
            if mapping.provider_exchange:
                params["exchange"] = mapping.provider_exchange
            payload = self._get("/time_series", params=params)
            chunk_values = payload.get("values")
            if not isinstance(chunk_values, list):
                raise MarketDataError(
                    "invalid_payload",
                    "Twelve Data response has no values",
                )
            values.extend(chunk_values)
            cursor = chunk_end

        now = self._now().astimezone(timezone.utc)
        parsed_candles: list[Candle] = []
        for row in values:
            if not isinstance(row, dict):
                continue
            open_time = _utc_datetime(row.get("datetime"))
            parsed_candles.append(
                Candle(
                    open_time=open_time,
                    open=_number(row.get("open"), field="open"),
                    high=_number(row.get("high"), field="high"),
                    low=_number(row.get("low"), field="low"),
                    close=_number(row.get("close"), field="close"),
                    volume=_optional_number(row.get("volume")),
                    is_closed=open_time + duration <= now,
                ),
            )
        candles = tuple(sorted(parsed_candles, key=lambda candle: candle.open_time))
        if not candles:
            raise MarketDataError("coverage_unavailable", "Twelve Data returned no candles")
        return ProviderCandleResponse(candles=candles, fetched_at=now)

    def fetch_quote(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> ProviderQuoteResponse:
        del query
        if not self._api_key:
            raise MarketDataError(
                "authentication_failed",
                "Twelve Data API key is not configured",
            )
        params: dict[str, object] = {
            "symbol": mapping.provider_symbol,
            "apikey": self._api_key,
        }
        if mapping.provider_exchange:
            params["exchange"] = mapping.provider_exchange
        payload = self._get(
            "/quote",
            params=params,
        )
        now = self._now().astimezone(timezone.utc)
        observed = payload.get("datetime")
        as_of = _utc_datetime(observed) if observed else now
        return ProviderQuoteResponse(
            bid=_optional_number(payload.get("bid")),
            ask=_optional_number(payload.get("ask")),
            last=_number(payload.get("close"), field="close"),
            as_of=as_of,
            fetched_at=now,
            open=_optional_number(payload.get("open")),
            high=_optional_number(payload.get("high")),
            low=_optional_number(payload.get("low")),
            previous_close=_optional_number(payload.get("previous_close")),
            volume=_optional_number(payload.get("volume")),
            currency=payload.get("currency")
            if isinstance(payload.get("currency"), str)
            else None,
        )

    def _get(self, path: str, *, params: dict[str, object]) -> dict:
        try:
            with httpx.Client(
                base_url=TWELVE_DATA_URL,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise MarketDataError("timeout", "Twelve Data request timed out") from exc
        except httpx.HTTPError as exc:
            raise MarketDataError(
                "provider_unavailable",
                "Twelve Data request failed",
            ) from exc

        if response.status_code == 429:
            raise MarketDataError("rate_limited", "Twelve Data rate limit reached")
        if response.status_code in {401, 403}:
            raise MarketDataError("authentication_failed", "Twelve Data rejected API key")
        if response.status_code == 404:
            raise MarketDataError("symbol_not_found", "Twelve Data symbol not found")
        if response.status_code >= 500:
            raise MarketDataError("provider_unavailable", "Twelve Data is unavailable")
        try:
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise MarketDataError("invalid_payload", "Twelve Data rejected request") from exc
        except ValueError as exc:
            raise MarketDataError("invalid_payload", "Twelve Data returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise MarketDataError("invalid_payload", "Twelve Data payload is not an object")
        if payload.get("status") == "error":
            code = payload.get("code")
            if code == 429:
                raise MarketDataError("rate_limited", "Twelve Data rate limit reached")
            if code in {401, 403}:
                raise MarketDataError("authentication_failed", "Twelve Data rejected API key")
            raise MarketDataError(
                "symbol_not_found",
                str(payload.get("message") or "Twelve Data rejected symbol"),
            )
        return payload


class YahooAdapter:
    provider_id = "yahoo"

    def __init__(
        self,
        *,
        history_loader: Callable[[str, datetime, datetime, str], pd.DataFrame] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._history_loader = history_loader or self._load_history
        self._now = now

    def fetch_candles(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> ProviderCandleResponse:
        resample_four_hours = query.timeframe in {"240", "4h"}
        interval = "1h" if resample_four_hours else YAHOO_INTERVALS.get(query.timeframe)
        if interval is None:
            raise MarketDataError(
                "unsupported_timeframe",
                f"Yahoo does not support {query.timeframe}",
            )
        try:
            frame = self._history_loader(
                mapping.provider_symbol,
                query.start,
                query.end,
                interval,
            )
        except TimeoutError as exc:
            raise MarketDataError("timeout", "Yahoo request timed out") from exc
        except Exception as exc:
            error_name = type(exc).__name__.lower()
            if "ratelimit" in error_name or "too many requests" in str(exc).lower():
                raise MarketDataError("rate_limited", "Yahoo rate limit reached") from exc
            raise MarketDataError("provider_unavailable", "Yahoo request failed") from exc
        if frame is None or frame.empty:
            raise MarketDataError("coverage_unavailable", "Yahoo returned no candles")

        normalized = frame.copy()
        normalized.columns = [str(column).lower() for column in normalized.columns]
        required = {"open", "high", "low", "close"}
        if not required.issubset(normalized.columns):
            raise MarketDataError("invalid_payload", "Yahoo response is missing OHLC fields")
        if not isinstance(normalized.index, pd.DatetimeIndex):
            normalized.index = pd.to_datetime(normalized.index, errors="coerce", utc=True)
        elif normalized.index.tz is None:
            normalized.index = normalized.index.tz_localize("UTC")
        normalized.index = normalized.index.tz_convert("UTC")
        normalized = normalized.loc[~normalized.index.isna()].sort_index()

        if resample_four_hours:
            grouped = normalized.resample("4h", label="left", closed="left")
            normalized = pd.DataFrame(
                {
                    "open": grouped["open"].first(),
                    "high": grouped["high"].max(),
                    "low": grouped["low"].min(),
                    "close": grouped["close"].last(),
                    "volume": grouped["volume"].sum(min_count=1)
                    if "volume" in normalized.columns
                    else None,
                },
            ).dropna(subset=["open", "high", "low", "close"])

        duration_key = "4h" if resample_four_hours else _canonical_yahoo_timeframe(interval)
        duration = TIMEFRAME_DURATION[duration_key]
        now = self._now().astimezone(timezone.utc)
        candles: list[Candle] = []
        for index, row in normalized.iterrows():
            open_time = index.to_pydatetime().astimezone(timezone.utc)
            volume = row.get("volume")
            candles.append(
                Candle(
                    open_time=open_time,
                    open=_number(row.get("open"), field="open"),
                    high=_number(row.get("high"), field="high"),
                    low=_number(row.get("low"), field="low"),
                    close=_number(row.get("close"), field="close"),
                    volume=None if pd.isna(volume) else _optional_number(volume),
                    is_closed=open_time + duration <= now,
                ),
            )
        if not candles:
            raise MarketDataError("coverage_unavailable", "Yahoo returned no usable candles")
        return ProviderCandleResponse(candles=tuple(candles), fetched_at=now)

    def fetch_quote(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> ProviderQuoteResponse:
        del query
        now = self._now().astimezone(timezone.utc)
        try:
            frame = self._history_loader(
                mapping.provider_symbol,
                now - timedelta(days=7),
                now + timedelta(days=1),
                "1d",
            )
        except Exception as exc:
            raise MarketDataError("provider_unavailable", "Yahoo quote request failed") from exc
        if frame is None or frame.empty:
            raise MarketDataError("coverage_unavailable", "Yahoo returned no quote")
        frame = frame.copy()
        frame.columns = [str(column).lower() for column in frame.columns]
        last_row = frame.iloc[-1]
        previous_row = frame.iloc[-2] if len(frame) > 1 else last_row
        index = frame.index[-1]
        as_of = pd.Timestamp(index)
        if as_of.tzinfo is None:
            as_of = as_of.tz_localize("UTC")
        recent_prices: list[tuple[datetime, float]] = []
        for observed_index, row in frame.tail(32).iterrows():
            observed_at = pd.Timestamp(observed_index)
            if observed_at.tzinfo is None:
                observed_at = observed_at.tz_localize("UTC")
            close = _optional_number(row.get("close"))
            if close is not None:
                recent_prices.append(
                    (observed_at.tz_convert("UTC").to_pydatetime(), close),
                )
        return ProviderQuoteResponse(
            bid=None,
            ask=None,
            last=_number(last_row.get("close"), field="close"),
            as_of=as_of.tz_convert("UTC").to_pydatetime(),
            fetched_at=now,
            open=_optional_number(last_row.get("open")),
            high=_optional_number(last_row.get("high")),
            low=_optional_number(last_row.get("low")),
            previous_close=_optional_number(previous_row.get("close")),
            volume=_optional_number(last_row.get("volume")),
            recent_prices=tuple(recent_prices),
        )

    @staticmethod
    def _load_history(
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance is not installed") from exc
        return yf.Ticker(symbol).history(
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            actions=False,
            repair=False,
            timeout=10,
            raise_errors=True,
        )


def _canonical_yahoo_timeframe(interval: str) -> str:
    return {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "1h": "1h",
        "1d": "1day",
        "1wk": "1week",
        "1mo": "1month",
    }[interval]


class TradingViewAdapter:
    provider_id = "tradingview"

    def __init__(
        self,
        *,
        client_factory: Callable[[], object] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._client_factory = client_factory or self._new_client
        self._now = now

    def fetch_candles(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> ProviderCandleResponse:
        interval = _tradingview_intervals().get(query.timeframe)
        duration = _duration_for(query.timeframe)
        if interval is None or duration is None:
            raise MarketDataError(
                "unsupported_timeframe",
                f"TradingView does not support {query.timeframe}",
            )
        if not mapping.provider_exchange:
            raise MarketDataError(
                "invalid_payload",
                "TradingView mapping requires provider_exchange",
            )

        now = self._now().astimezone(timezone.utc)
        requested_bars = math.ceil(
            max((now - query.start).total_seconds(), duration.total_seconds())
            / duration.total_seconds(),
        )
        n_bars = min(5000, max(200, requested_bars + 10))
        try:
            client = self._client_factory()
            frame = client.get_hist(
                symbol=mapping.provider_symbol,
                exchange=mapping.provider_exchange,
                interval=interval,
                n_bars=n_bars,
            )
        except Exception as exc:
            message = str(exc).lower()
            code = "timeout" if "timed out" in message or "timeout" in message else "provider_unavailable"
            raise MarketDataError(code, "TradingView request failed") from exc
        if frame is None or frame.empty:
            raise MarketDataError("symbol_not_found", "TradingView returned no candles")

        normalized = frame.copy()
        normalized.columns = [str(column).lower() for column in normalized.columns]
        required = {"open", "high", "low", "close"}
        if not required.issubset(normalized.columns):
            raise MarketDataError(
                "invalid_payload",
                "TradingView response is missing OHLC fields",
            )
        if not isinstance(normalized.index, pd.DatetimeIndex):
            normalized.index = pd.to_datetime(normalized.index, errors="coerce")
        if normalized.index.tz is None:
            # tvdatafeed uses datetime.fromtimestamp(epoch), which produces
            # a naive timestamp in the server's local timezone. datetime.timestamp()
            # is the matching inverse and remains correct when the server timezone
            # differs from the exchange timezone.
            normalized.index = pd.DatetimeIndex(
                [
                    datetime.fromtimestamp(
                        value.to_pydatetime().timestamp(),
                        timezone.utc,
                    )
                    for value in normalized.index
                ],
            )
        else:
            normalized.index = normalized.index.tz_convert("UTC")
        normalized = normalized.loc[~normalized.index.isna()].sort_index()

        candles: list[Candle] = []
        for index, row in normalized.iterrows():
            open_time = index.to_pydatetime().astimezone(timezone.utc)
            volume = row.get("volume")
            candles.append(
                Candle(
                    open_time=open_time,
                    open=_number(row.get("open"), field="open"),
                    high=_number(row.get("high"), field="high"),
                    low=_number(row.get("low"), field="low"),
                    close=_number(row.get("close"), field="close"),
                    volume=None if pd.isna(volume) else _optional_number(volume),
                    is_closed=open_time + duration <= now,
                ),
            )
        if not candles:
            raise MarketDataError(
                "coverage_unavailable",
                "TradingView returned no usable candles",
            )
        return ProviderCandleResponse(candles=tuple(candles), fetched_at=now)

    def fetch_quote(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> ProviderQuoteResponse:
        now = self._now().astimezone(timezone.utc)
        result = self.fetch_candles(
            mapping,
            CandleQuery(
                series_id=query.target_id,
                timeframe="1min",
                start=now - timedelta(minutes=10),
                end=now + timedelta(minutes=1),
            ),
        )
        latest = result.candles[-1]
        previous = result.candles[-2] if len(result.candles) > 1 else latest
        return ProviderQuoteResponse(
            bid=None,
            ask=None,
            last=latest.close,
            as_of=latest.open_time,
            fetched_at=result.fetched_at,
            open=latest.open,
            high=latest.high,
            low=latest.low,
            previous_close=previous.close,
            volume=latest.volume,
            recent_prices=tuple(
                (candle.open_time, candle.close)
                for candle in result.candles[-32:]
            ),
        )

    @staticmethod
    def _new_client() -> object:
        from tvDatafeed import TvDatafeed

        return TvDatafeed()


def _duration_for(timeframe: str) -> timedelta | None:
    canonical = {
        "1": "1min",
        "5": "5min",
        "15": "15min",
        "60": "1h",
        "240": "4h",
        "D": "1day",
        "W": "1week",
        "M": "1month",
    }.get(timeframe, timeframe)
    return TIMEFRAME_DURATION.get(canonical)
