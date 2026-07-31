"""Provider-neutral market identity and data access boundary.

Provider symbols deliberately live outside the instrument models.  A symbol such as
``XAUUSD`` identifies a user intent only after asset-class/venue context is applied;
it is not safe to pass directly to a data vendor.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import math
import time
from threading import Lock
from typing import Callable, Literal, Protocol, Sequence


AssetClass = Literal["equity", "spot", "crypto", "futures", "index", "commodity"]
TargetType = Literal["instrument", "listing", "series"]
SeriesKind = Literal["listing", "consolidated", "continuous_future"]
DataPurpose = Literal["backtest", "replay", "interactive", "overview"]
FreshnessPolicy = Literal["prefer_cache", "require_fresh", "allow_stale"]


@dataclass(frozen=True, slots=True)
class FuturesSpecification:
    currency: str
    tick_size: float
    tick_value: float
    point_value: float
    timezone: str


FUTURES_CONTRACT_SPECS: dict[str, FuturesSpecification] = {
    "NQ": FuturesSpecification("USD", 0.25, 5.0, 20.0, "America/Chicago"),
    "MNQ": FuturesSpecification("USD", 0.25, 0.5, 2.0, "America/Chicago"),
    "ES": FuturesSpecification("USD", 0.25, 12.5, 50.0, "America/Chicago"),
    "MES": FuturesSpecification("USD", 0.25, 1.25, 5.0, "America/Chicago"),
    "GC": FuturesSpecification("USD", 0.1, 10.0, 100.0, "America/New_York"),
    "MGC": FuturesSpecification("USD", 0.1, 1.0, 10.0, "America/New_York"),
}


@dataclass(frozen=True, slots=True)
class Instrument:
    id: str
    asset_class: AssetClass
    display_symbol: str
    display_name: str
    futures_spec: FuturesSpecification | None = None


@dataclass(frozen=True, slots=True)
class Listing:
    id: str
    instrument_id: str
    venue: str
    listing_symbol: str
    timezone: str


@dataclass(frozen=True, slots=True)
class MarketSeries:
    id: str
    instrument_id: str
    kind: SeriesKind
    display_symbol: str
    display_name: str
    listing_id: str | None = None


@dataclass(frozen=True, slots=True)
class Alias:
    value: str
    target_type: TargetType
    target_id: str
    asset_class: AssetClass
    venue: str | None = None
    provider: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class InstrumentSearch:
    text: str
    asset_class: AssetClass | None = None
    venue: str | None = None
    provider: str | None = None
    limit: int = 20


@dataclass(frozen=True, slots=True)
class InstrumentMatch:
    target_type: TargetType
    target_id: str
    instrument_id: str
    display_symbol: str
    display_name: str
    asset_class: AssetClass
    listing_id: str | None = None
    series_id: str | None = None
    venue: str | None = None
    series_kind: SeriesKind | None = None
    futures_spec: FuturesSpecification | None = None
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class ProviderMapping:
    provider_id: str
    target_type: TargetType
    target_id: str
    provider_symbol: str
    provider_exchange: str | None = None
    provider_timezone: str = "UTC"


@dataclass(frozen=True, slots=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    is_closed: bool


@dataclass(frozen=True, slots=True)
class CandleQuery:
    series_id: str
    timeframe: str
    start: datetime
    end: datetime
    purpose: DataPurpose = "interactive"
    freshness: FreshnessPolicy = "prefer_cache"


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    provider_id: str
    provider_symbol: str
    provider_exchange: str | None
    fetched_at: datetime
    cache_status: Literal["miss", "hit", "stale"] = "miss"


@dataclass(frozen=True, slots=True)
class QualityReport:
    status: Literal["ok", "warning"]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandleSeries:
    series_id: str
    instrument_id: str
    listing_id: str | None
    timeframe: str
    candles: tuple[Candle, ...]
    requested_start: datetime
    requested_end: datetime
    actual_start: datetime
    actual_end: datetime
    source: SourceMetadata
    quality: QualityReport


@dataclass(frozen=True, slots=True)
class QuoteQuery:
    target_type: TargetType
    target_id: str
    preferred_providers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    target_type: TargetType
    target_id: str
    bid: float | None
    ask: float | None
    last: float
    as_of: datetime
    source: SourceMetadata
    quality: QualityReport
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    currency: str | None = None
    recent_prices: tuple[tuple[datetime, float], ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderCandleResponse:
    candles: tuple[Candle, ...]
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderQuoteResponse:
    bid: float | None
    ask: float | None
    last: float
    as_of: datetime
    fetched_at: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    currency: str | None = None
    recent_prices: tuple[tuple[datetime, float], ...] = ()


class MarketDataError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


TRANSIENT_PROVIDER_ERRORS = {
    "timeout",
    "connection_reset",
    "rate_limited",
    "provider_unavailable",
}


class MarketDataProvider(Protocol):
    provider_id: str

    def fetch_candles(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> ProviderCandleResponse: ...

    def fetch_quote(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> ProviderQuoteResponse: ...


class CandleCache(Protocol):
    def get(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> CandleSeries | None: ...

    def put(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
        series: CandleSeries,
    ) -> None: ...

    def get_stale(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> CandleSeries | None: ...


class QuoteCache(Protocol):
    def get(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> QuoteSnapshot | None: ...

    def put(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
        quote: QuoteSnapshot,
    ) -> None: ...


class InMemoryQuoteCache:
    def __init__(
        self,
        *,
        ttl_seconds: float = 15,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._items: dict[
            tuple[str, TargetType, str],
            tuple[float, QuoteSnapshot],
        ] = {}

    @staticmethod
    def _key(
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> tuple[str, TargetType, str]:
        return mapping.provider_id, query.target_type, query.target_id

    def get(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> QuoteSnapshot | None:
        key = self._key(mapping, query)
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, quote = item
        if self._clock() >= expires_at:
            self._items.pop(key, None)
            return None
        return replace(
            quote,
            source=replace(quote.source, cache_status="hit"),
        )

    def put(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
        quote: QuoteSnapshot,
    ) -> None:
        self._items[self._key(mapping, query)] = (
            self._clock() + self._ttl_seconds,
            quote,
        )


class InMemoryCandleCache:
    def __init__(self) -> None:
        self._items: dict[
            tuple[str, str, str, datetime, datetime, DataPurpose],
            CandleSeries,
        ] = {}

    @staticmethod
    def _key(
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> tuple[str, str, str, datetime, datetime, DataPurpose]:
        return (
            mapping.provider_id,
            query.series_id,
            query.timeframe,
            query.start,
            query.end,
            query.purpose,
        )

    def get(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> CandleSeries | None:
        item = self._items.get(self._key(mapping, query))
        if item is None:
            return None
        return replace(
            item,
            source=replace(item.source, cache_status="hit"),
        )

    def put(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
        series: CandleSeries,
    ) -> None:
        self._items[self._key(mapping, query)] = series

    def get_stale(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> CandleSeries | None:
        del mapping, query
        return None


class InMemoryMarketDataProvider:
    """Deterministic provider for gateway contract tests and local development."""

    def __init__(self, *, provider_id: str) -> None:
        self.provider_id = provider_id.lower()
        self._candles: dict[tuple[str, str], tuple[Candle, ...]] = {}
        self._quotes: dict[str, ProviderQuoteResponse] = {}
        self._candle_errors: dict[tuple[str, str], list[str]] = {}
        self._quote_errors: dict[str, list[str]] = {}
        self.candle_fetch_count = 0
        self.quote_fetch_count = 0

    def set_candles(
        self,
        *,
        provider_symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
    ) -> None:
        self._candles[(provider_symbol, timeframe)] = tuple(candles)

    def queue_candle_errors(
        self,
        *,
        provider_symbol: str,
        timeframe: str,
        error_codes: Sequence[str],
    ) -> None:
        self._candle_errors[(provider_symbol, timeframe)] = list(error_codes)

    def fetch_candles(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> ProviderCandleResponse:
        self.candle_fetch_count += 1
        error_queue = self._candle_errors.get((mapping.provider_symbol, query.timeframe))
        if error_queue:
            code = error_queue.pop(0)
            raise MarketDataError(code, f"queued provider failure: {code}")
        candles = self._candles.get((mapping.provider_symbol, query.timeframe))
        if candles is None:
            raise MarketDataError(
                "provider_data_missing",
                f"no candle fixture for {mapping.provider_symbol} {query.timeframe}",
            )
        selected = tuple(
            candle
            for candle in candles
            if query.start <= candle.open_time < query.end
        )
        if not selected:
            raise MarketDataError(
                "provider_data_empty",
                f"no candles in requested range for {mapping.provider_symbol}",
            )
        return ProviderCandleResponse(
            candles=selected,
            fetched_at=datetime.now(timezone.utc),
        )

    def set_quote(
        self,
        *,
        provider_symbol: str,
        bid: float | None,
        ask: float | None,
        last: float,
        as_of: datetime,
        open: float | None = None,
        high: float | None = None,
        low: float | None = None,
        previous_close: float | None = None,
        volume: float | None = None,
        currency: str | None = None,
        recent_prices: Sequence[tuple[datetime, float]] = (),
    ) -> None:
        self._quotes[provider_symbol] = ProviderQuoteResponse(
            bid=bid,
            ask=ask,
            last=last,
            as_of=as_of,
            fetched_at=datetime.now(timezone.utc),
            open=open,
            high=high,
            low=low,
            previous_close=previous_close,
            volume=volume,
            currency=currency,
            recent_prices=tuple(recent_prices),
        )

    def queue_quote_errors(
        self,
        *,
        provider_symbol: str,
        error_codes: Sequence[str],
    ) -> None:
        self._quote_errors[provider_symbol] = list(error_codes)

    def fetch_quote(
        self,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> ProviderQuoteResponse:
        del query
        self.quote_fetch_count += 1
        error_queue = self._quote_errors.get(mapping.provider_symbol)
        if error_queue:
            code = error_queue.pop(0)
            raise MarketDataError(code, f"queued provider failure: {code}")
        quote = self._quotes.get(mapping.provider_symbol)
        if quote is None:
            raise MarketDataError(
                "provider_data_missing",
                f"no quote fixture for {mapping.provider_symbol}",
            )
        return quote


def _alias_key(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum() or character == "!")


def _timeframe_duration(timeframe: str) -> timedelta | None:
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
    return {
        "1min": timedelta(minutes=1),
        "5min": timedelta(minutes=5),
        "15min": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1day": timedelta(days=1),
        "1week": timedelta(weeks=1),
        "1month": timedelta(days=31),
    }.get(canonical)


class InstrumentCatalog:
    """In-memory canonical catalog; persistence can be added behind this interface."""

    def __init__(self) -> None:
        self._instruments: dict[str, Instrument] = {}
        self._listings: dict[str, Listing] = {}
        self._series: dict[str, MarketSeries] = {}
        self._aliases: list[Alias] = []
        self._provider_mappings: list[ProviderMapping] = []

    def add_instrument(self, instrument: Instrument) -> None:
        self._instruments[instrument.id] = instrument

    def add_listing(self, listing: Listing) -> None:
        if listing.instrument_id not in self._instruments:
            raise ValueError(f"unknown instrument: {listing.instrument_id}")
        self._listings[listing.id] = listing

    def add_series(self, series: MarketSeries) -> None:
        if series.instrument_id not in self._instruments:
            raise ValueError(f"unknown instrument: {series.instrument_id}")
        if series.listing_id is not None and series.listing_id not in self._listings:
            raise ValueError(f"unknown listing: {series.listing_id}")
        self._series[series.id] = series

    def add_alias(self, alias: Alias) -> None:
        targets = {
            "instrument": self._instruments,
            "listing": self._listings,
            "series": self._series,
        }
        if alias.target_id not in targets[alias.target_type]:
            raise ValueError(f"unknown alias target: {alias.target_id}")
        self._aliases.append(alias)

    def add_provider_mapping(self, mapping: ProviderMapping) -> None:
        targets = {
            "instrument": self._instruments,
            "listing": self._listings,
            "series": self._series,
        }
        if mapping.target_id not in targets[mapping.target_type]:
            raise ValueError(f"unknown provider mapping target: {mapping.target_id}")
        self._provider_mappings.append(
            ProviderMapping(
                provider_id=mapping.provider_id.lower(),
                target_type=mapping.target_type,
                target_id=mapping.target_id,
                provider_symbol=mapping.provider_symbol,
                provider_exchange=mapping.provider_exchange,
                provider_timezone=mapping.provider_timezone,
            ),
        )

    def has_series(self, series_id: str) -> bool:
        return series_id in self._series

    def resolve_instrument(self, query: InstrumentSearch) -> Instrument | None:
        direct = self._instruments.get(query.text.strip().lower())
        if direct is not None:
            if query.asset_class is not None and direct.asset_class != query.asset_class:
                return None
            return direct

        instrument_ids = {
            match.instrument_id
            for match in self.search(query)
        }
        if len(instrument_ids) != 1:
            return None
        return self._instruments[next(iter(instrument_ids))]

    def series_identity(self, series_id: str) -> tuple[str, str | None]:
        series = self._series[series_id]
        return series.instrument_id, series.listing_id

    def has_target(self, target_type: TargetType, target_id: str) -> bool:
        targets = {
            "instrument": self._instruments,
            "listing": self._listings,
            "series": self._series,
        }
        return target_id in targets[target_type]

    def provider_mappings(
        self,
        *,
        target_type: TargetType,
        target_id: str,
    ) -> tuple[ProviderMapping, ...]:
        return tuple(
            mapping
            for mapping in self._provider_mappings
            if mapping.target_type == target_type and mapping.target_id == target_id
        )

    def search(self, query: InstrumentSearch) -> list[InstrumentMatch]:
        if query.limit < 1:
            return []

        search_key = _alias_key(query.text)
        if not search_key:
            return []
        candidates: dict[tuple[TargetType, str], InstrumentMatch] = {}
        for alias in self._aliases:
            alias_key = _alias_key(alias.value)
            if not alias_key.startswith(search_key):
                continue
            if query.asset_class is not None and alias.asset_class != query.asset_class:
                continue
            if query.venue is not None and alias.venue != query.venue.upper():
                continue
            if query.provider is not None and alias.provider not in {None, query.provider.lower()}:
                continue

            match = self._match_for(alias)
            if alias_key != search_key:
                match = replace(
                    match,
                    confidence=match.confidence * 0.8,
                )
            key = (match.target_type, match.target_id)
            previous = candidates.get(key)
            if previous is None or match.confidence > previous.confidence:
                candidates[key] = match

        return sorted(
            candidates.values(),
            key=lambda match: (-match.confidence, match.display_symbol, match.target_id),
        )[: query.limit]

    def _match_for(self, alias: Alias) -> InstrumentMatch:
        listing: Listing | None = None
        series: MarketSeries | None = None

        if alias.target_type == "instrument":
            instrument = self._instruments[alias.target_id]
        elif alias.target_type == "listing":
            listing = self._listings[alias.target_id]
            instrument = self._instruments[listing.instrument_id]
        else:
            series = self._series[alias.target_id]
            instrument = self._instruments[series.instrument_id]
            if series.listing_id is not None:
                listing = self._listings[series.listing_id]

        return InstrumentMatch(
            target_type=alias.target_type,
            target_id=alias.target_id,
            instrument_id=instrument.id,
            listing_id=listing.id if listing else None,
            series_id=series.id if series else None,
            display_symbol=series.display_symbol if series else instrument.display_symbol,
            display_name=series.display_name if series else instrument.display_name,
            asset_class=instrument.asset_class,
            venue=listing.venue if listing else alias.venue,
            series_kind=series.kind if series else None,
            futures_spec=instrument.futures_spec,
            confidence=alias.confidence,
        )


class MarketDataGateway:
    def __init__(
        self,
        *,
        catalog: InstrumentCatalog,
        providers: Sequence[MarketDataProvider] = (),
        candle_cache: CandleCache | None = None,
        quote_cache: QuoteCache | None = None,
        retry_delays: Sequence[float] = (0.25, 0.75),
        sleeper: Callable[[float], None] = time.sleep,
        circuit_failure_threshold: int = 3,
        circuit_cooldown_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._catalog = catalog
        self._providers = {
            provider.provider_id.lower(): provider
            for provider in providers
        }
        self._candle_cache = candle_cache
        self._quote_cache = quote_cache
        self._retry_delays = tuple(retry_delays)
        self._sleeper = sleeper
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_cooldown_seconds = circuit_cooldown_seconds
        self._clock = clock
        self._provider_failures: dict[str, int] = {}
        self._circuit_open_until: dict[str, float] = {}
        self._singleflight_registry_lock = Lock()
        self._singleflight_locks: dict[object, tuple[Lock, int]] = {}

    def search_instruments(self, query: InstrumentSearch) -> list[InstrumentMatch]:
        return self._catalog.search(query)

    def resolve_instrument(self, query: InstrumentSearch) -> Instrument | None:
        return self._catalog.resolve_instrument(query)

    def has_series(self, series_id: str) -> bool:
        return self._catalog.has_series(series_id)

    def get_candles(self, query: CandleQuery) -> CandleSeries:
        with self._singleflight(("candles", query)):
            return self._get_candles(query)

    def _get_candles(self, query: CandleQuery) -> CandleSeries:
        if not self._catalog.has_series(query.series_id):
            raise MarketDataError(
                "unknown_market_series",
                f"unknown market series: {query.series_id}",
            )
        if query.start.tzinfo is None or query.end.tzinfo is None:
            raise ValueError("candle query timestamps must be timezone-aware")
        if query.start >= query.end:
            raise ValueError("candle query start must be before end")

        failures: list[str] = []
        failure_codes: list[str] = []
        instrument_id, listing_id = self._catalog.series_identity(query.series_id)
        mappings = self._catalog.provider_mappings(
            target_type="series",
            target_id=query.series_id,
        )
        stale_candidates: list[CandleSeries] = []
        if (
            self._candle_cache is not None
            and query.freshness != "require_fresh"
        ):
            for mapping in mappings:
                cached = self._candle_cache.get(mapping, query)
                if cached is not None:
                    return cached
                if query.freshness == "allow_stale":
                    stale_getter = getattr(
                        self._candle_cache,
                        "get_stale",
                        None,
                    )
                    stale = (
                        stale_getter(mapping, query)
                        if stale_getter is not None
                        else None
                    )
                    if stale is not None:
                        stale_candidates.append(stale)

        for mapping in mappings:
            provider = self._providers.get(mapping.provider_id)
            if provider is None:
                continue
            if self._is_circuit_open(mapping.provider_id):
                failures.append(f"{mapping.provider_id}:circuit_open")
                failure_codes.append("circuit_open")
                continue
            try:
                response = self._fetch_candles_with_retry(provider, mapping, query)
                candles, quality = self._validate_candles(response.candles, query)
            except MarketDataError as exc:
                if exc.code in TRANSIENT_PROVIDER_ERRORS:
                    self._record_provider_failure(mapping.provider_id)
                failures.append(f"{mapping.provider_id}:{exc.code}")
                failure_codes.append(exc.code)
                continue
            self._record_provider_success(mapping.provider_id)
            series = CandleSeries(
                series_id=query.series_id,
                instrument_id=instrument_id,
                listing_id=listing_id,
                timeframe=query.timeframe,
                candles=candles,
                requested_start=query.start.astimezone(timezone.utc),
                requested_end=query.end.astimezone(timezone.utc),
                actual_start=candles[0].open_time,
                actual_end=candles[-1].open_time,
                source=SourceMetadata(
                    provider_id=mapping.provider_id,
                    provider_symbol=mapping.provider_symbol,
                    provider_exchange=mapping.provider_exchange,
                    fetched_at=response.fetched_at,
                ),
                quality=quality,
            )
            if self._candle_cache is not None:
                self._candle_cache.put(mapping, query, series)
            return series

        if failure_codes and set(failure_codes) == {"unsupported_timeframe"}:
            raise MarketDataError(
                "unsupported_timeframe",
                f"no provider supports timeframe {query.timeframe}",
            )
        stale_eligible_errors = TRANSIENT_PROVIDER_ERRORS | {"circuit_open"}
        if (
            query.freshness == "allow_stale"
            and stale_candidates
            and failure_codes
            and set(failure_codes) <= stale_eligible_errors
        ):
            stale = stale_candidates[0]
            warnings = tuple(
                dict.fromkeys((*stale.quality.warnings, "stale_data"))
            )
            return replace(
                stale,
                source=replace(stale.source, cache_status="stale"),
                quality=QualityReport(
                    status="warning",
                    warnings=warnings,
                ),
            )
        detail = ", ".join(failures) if failures else "no configured provider mapping"
        raise MarketDataError(
            "market_data_unavailable",
            f"candles unavailable for {query.series_id}: {detail}",
        )

    def _fetch_candles_with_retry(
        self,
        provider: MarketDataProvider,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> ProviderCandleResponse:
        for attempt in range(len(self._retry_delays) + 1):
            try:
                return provider.fetch_candles(mapping, query)
            except MarketDataError as exc:
                if (
                    exc.code not in TRANSIENT_PROVIDER_ERRORS
                    or attempt == len(self._retry_delays)
                ):
                    raise
                self._sleeper(self._retry_delays[attempt])
        raise AssertionError("retry loop exhausted without returning or raising")

    @staticmethod
    def _validate_candles(
        candles: Sequence[Candle],
        query: CandleQuery,
    ) -> tuple[tuple[Candle, ...], QualityReport]:
        normalized: dict[datetime, Candle] = {}
        warnings: list[str] = []
        for candle in candles:
            if candle.open_time.tzinfo is None:
                raise MarketDataError(
                    "data_quality_rejected",
                    "candle timestamp must be timezone-aware",
                )
            open_time = candle.open_time.astimezone(timezone.utc)
            values = (candle.open, candle.high, candle.low, candle.close)
            if not all(math.isfinite(value) for value in values):
                raise MarketDataError(
                    "data_quality_rejected",
                    f"non-finite OHLC value at {open_time.isoformat()}",
                )
            if candle.volume is not None and not math.isfinite(candle.volume):
                raise MarketDataError(
                    "data_quality_rejected",
                    f"non-finite volume at {open_time.isoformat()}",
                )
            if (
                candle.low > min(candle.open, candle.close)
                or candle.high < max(candle.open, candle.close)
                or candle.low > candle.high
            ):
                raise MarketDataError(
                    "data_quality_rejected",
                    f"invalid OHLC range at {open_time.isoformat()}",
                )
            if not query.start <= open_time < query.end:
                warnings.append("out_of_range_bar_removed")
                continue
            if open_time in normalized:
                warnings.append("duplicate_bar_removed")
            normalized[open_time] = replace(candle, open_time=open_time)

        ordered = tuple(normalized[key] for key in sorted(normalized))
        if not ordered:
            raise MarketDataError(
                "coverage_unavailable",
                "provider returned no usable candles in the requested range",
            )
        if query.purpose == "backtest" and any(
            not candle.is_closed for candle in ordered
        ):
            raise MarketDataError(
                "data_quality_rejected",
                "backtest candles must all be closed",
            )
        if query.purpose == "backtest":
            duration = _timeframe_duration(query.timeframe)
            if duration is None:
                raise MarketDataError(
                    "unsupported_timeframe",
                    f"unsupported timeframe {query.timeframe}",
                )
            # Raw request boundaries can fall in an overnight/weekend/holiday
            # closure. Without a session calendar, allow the longest common
            # closure while still rejecting providers that return only a small
            # tail of a materially longer request.
            boundary_tolerance = max(duration * 3, timedelta(days=4))
            if (
                ordered[0].open_time - query.start > boundary_tolerance
                or query.end - ordered[-1].open_time > boundary_tolerance
            ):
                raise MarketDataError(
                    "coverage_unavailable",
                    "provider does not cover the requested backtest range",
                )
        unique_warnings = tuple(dict.fromkeys(warnings))
        return (
            ordered,
            QualityReport(
                status="warning" if unique_warnings else "ok",
                warnings=unique_warnings,
            ),
        )

    def _is_circuit_open(self, provider_id: str) -> bool:
        open_until = self._circuit_open_until.get(provider_id)
        if open_until is None:
            return False
        if self._clock() < open_until:
            return True
        self._circuit_open_until.pop(provider_id, None)
        return False

    def _record_provider_failure(self, provider_id: str) -> None:
        failures = self._provider_failures.get(provider_id, 0) + 1
        self._provider_failures[provider_id] = failures
        if failures >= self._circuit_failure_threshold:
            self._circuit_open_until[provider_id] = (
                self._clock() + self._circuit_cooldown_seconds
            )

    def _record_provider_success(self, provider_id: str) -> None:
        self._provider_failures.pop(provider_id, None)
        self._circuit_open_until.pop(provider_id, None)

    def get_quote(self, query: QuoteQuery) -> QuoteSnapshot:
        with self._singleflight(("quote", query)):
            return self._get_quote(query)

    def _get_quote(self, query: QuoteQuery) -> QuoteSnapshot:
        if not self._catalog.has_target(query.target_type, query.target_id):
            raise MarketDataError(
                "unknown_market_target",
                f"unknown {query.target_type}: {query.target_id}",
            )

        failures: list[str] = []
        mappings = self._catalog.provider_mappings(
            target_type=query.target_type,
            target_id=query.target_id,
        )
        if query.preferred_providers:
            priorities = {
                provider_id.lower(): index
                for index, provider_id in enumerate(query.preferred_providers)
            }
            mappings = tuple(sorted(
                mappings,
                key=lambda mapping: priorities.get(
                    mapping.provider_id,
                    len(priorities),
                ),
            ))
        if self._quote_cache is not None:
            for mapping in mappings:
                cached = self._quote_cache.get(mapping, query)
                if cached is not None:
                    return cached

        for mapping in mappings:
            provider = self._providers.get(mapping.provider_id)
            if provider is None:
                continue
            if self._is_circuit_open(mapping.provider_id):
                failures.append(f"{mapping.provider_id}:circuit_open")
                continue
            try:
                response = self._fetch_quote_with_retry(provider, mapping, query)
                response = self._validate_quote_response(response)
            except MarketDataError as exc:
                if exc.code in TRANSIENT_PROVIDER_ERRORS:
                    self._record_provider_failure(mapping.provider_id)
                failures.append(f"{mapping.provider_id}:{exc.code}")
                continue
            self._record_provider_success(mapping.provider_id)
            quote = QuoteSnapshot(
                target_type=query.target_type,
                target_id=query.target_id,
                bid=response.bid,
                ask=response.ask,
                last=response.last,
                as_of=response.as_of,
                source=SourceMetadata(
                    provider_id=mapping.provider_id,
                    provider_symbol=mapping.provider_symbol,
                    provider_exchange=mapping.provider_exchange,
                    fetched_at=response.fetched_at,
                ),
                quality=QualityReport(status="ok"),
                open=response.open,
                high=response.high,
                low=response.low,
                previous_close=response.previous_close,
                volume=response.volume,
                currency=response.currency,
                recent_prices=response.recent_prices,
            )
            if self._quote_cache is not None:
                self._quote_cache.put(mapping, query, quote)
            return quote

        detail = ", ".join(failures) if failures else "no configured provider mapping"
        raise MarketDataError(
            "market_data_unavailable",
            f"quote unavailable for {query.target_id}: {detail}",
        )

    @staticmethod
    def _validate_quote_response(
        response: ProviderQuoteResponse,
    ) -> ProviderQuoteResponse:
        if response.as_of.tzinfo is None or response.fetched_at.tzinfo is None:
            raise MarketDataError(
                "data_quality_rejected",
                "quote timestamps must be timezone-aware",
            )
        numeric_values = (
            response.bid,
            response.ask,
            response.last,
            response.open,
            response.high,
            response.low,
            response.previous_close,
            response.volume,
        )
        if any(
            value is not None and not math.isfinite(value)
            for value in numeric_values
        ):
            raise MarketDataError(
                "data_quality_rejected",
                "quote contains a non-finite numeric value",
            )
        if (
            response.bid is not None
            and response.ask is not None
            and response.bid > response.ask
        ):
            raise MarketDataError(
                "data_quality_rejected",
                "quote bid must not exceed ask",
            )
        if (
            response.low is not None
            and response.high is not None
            and response.low > response.high
        ):
            raise MarketDataError(
                "data_quality_rejected",
                "quote low must not exceed high",
            )
        if response.volume is not None and response.volume < 0:
            raise MarketDataError(
                "data_quality_rejected",
                "quote volume must not be negative",
            )
        if any(
            observed_at.tzinfo is None or not math.isfinite(price)
            for observed_at, price in response.recent_prices
        ):
            raise MarketDataError(
                "data_quality_rejected",
                "quote price history must contain finite values and timezone-aware timestamps",
            )
        return replace(
            response,
            as_of=response.as_of.astimezone(timezone.utc),
            fetched_at=response.fetched_at.astimezone(timezone.utc),
            recent_prices=tuple(
                (observed_at.astimezone(timezone.utc), price)
                for observed_at, price in response.recent_prices
            ),
        )

    def _fetch_quote_with_retry(
        self,
        provider: MarketDataProvider,
        mapping: ProviderMapping,
        query: QuoteQuery,
    ) -> ProviderQuoteResponse:
        for attempt in range(len(self._retry_delays) + 1):
            try:
                return provider.fetch_quote(mapping, query)
            except MarketDataError as exc:
                if (
                    exc.code not in TRANSIENT_PROVIDER_ERRORS
                    or attempt == len(self._retry_delays)
                ):
                    raise
                self._sleeper(self._retry_delays[attempt])
        raise AssertionError("retry loop exhausted without returning or raising")

    @contextmanager
    def _singleflight(self, key: object):
        with self._singleflight_registry_lock:
            lock, users = self._singleflight_locks.get(key, (Lock(), 0))
            self._singleflight_locks[key] = (lock, users + 1)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._singleflight_registry_lock:
                current_lock, current_users = self._singleflight_locks[key]
                if current_users == 1:
                    self._singleflight_locks.pop(key, None)
                else:
                    self._singleflight_locks[key] = (
                        current_lock,
                        current_users - 1,
                    )


def default_catalog() -> InstrumentCatalog:
    catalog = InstrumentCatalog()

    _seed_spot_series(catalog)
    _seed_futures_series(catalog)
    _seed_crypto_series(catalog)
    _seed_equity_series(catalog)
    _seed_index_series(catalog)
    _seed_reference_instruments(catalog)

    return catalog


def _seed_spot_series(catalog: InstrumentCatalog) -> None:
    xau_spot = Instrument(
        id="instrument:spot:xau-usd",
        asset_class="spot",
        display_symbol="XAU/USD",
        display_name="Gold Spot / U.S. Dollar",
    )
    catalog.add_instrument(xau_spot)
    catalog.add_series(
        MarketSeries(
            id="series:spot:xau-usd:consolidated",
            instrument_id=xau_spot.id,
            kind="consolidated",
            display_symbol="XAU/USD",
            display_name="Gold Spot / U.S. Dollar",
        ),
    )
    catalog.add_alias(
        Alias(
            value="XAUUSD",
            target_type="series",
            target_id="series:spot:xau-usd:consolidated",
            asset_class="spot",
        ),
    )

    other_pairs = (
        ("XAG", "USD", "Silver Spot / U.S. Dollar"),
        ("EUR", "USD", "Euro / U.S. Dollar"),
        ("GBP", "USD", "British Pound / U.S. Dollar"),
        ("USD", "JPY", "U.S. Dollar / Japanese Yen"),
        ("AUD", "USD", "Australian Dollar / U.S. Dollar"),
        ("USD", "CAD", "U.S. Dollar / Canadian Dollar"),
        ("USD", "CHF", "U.S. Dollar / Swiss Franc"),
    )
    for base, quote, name in other_pairs:
        pair_key = f"{base.lower()}-{quote.lower()}"
        instrument_id = f"instrument:spot:{pair_key}"
        series_id = f"series:spot:{pair_key}:consolidated"
        catalog.add_instrument(
            Instrument(
                id=instrument_id,
                asset_class="spot",
                display_symbol=f"{base}/{quote}",
                display_name=name,
            ),
        )
        catalog.add_series(
            MarketSeries(
                id=series_id,
                instrument_id=instrument_id,
                kind="consolidated",
                display_symbol=f"{base}/{quote}",
                display_name=name,
            ),
        )
        for alias_value in (f"{base}{quote}", f"{base}/{quote}"):
            catalog.add_alias(
                Alias(
                    value=alias_value,
                    target_type="series",
                    target_id=series_id,
                    asset_class="spot",
                ),
            )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="twelve_data",
                target_type="series",
                target_id=series_id,
                provider_symbol=f"{base}/{quote}",
            ),
        )
        yahoo_symbols = {
            ("EUR", "USD"): "EURUSD=X",
            ("GBP", "USD"): "GBPUSD=X",
            ("USD", "JPY"): "JPY=X",
            ("AUD", "USD"): "AUDUSD=X",
            ("USD", "CAD"): "CAD=X",
            ("USD", "CHF"): "CHF=X",
        }
        yahoo_symbol = yahoo_symbols.get((base, quote))
        if yahoo_symbol is not None:
            catalog.add_provider_mapping(
                ProviderMapping(
                    provider_id="yahoo",
                    target_type="series",
                    target_id=series_id,
                    provider_symbol=yahoo_symbol,
                ),
            )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="tradingview",
                target_type="series",
                target_id=series_id,
                provider_symbol=f"{base}{quote}",
                provider_exchange="OANDA",
            ),
        )
    catalog.add_alias(
        Alias(
            value="XAUUSD",
            target_type="series",
            target_id="series:spot:xau-usd:consolidated",
            asset_class="spot",
            provider="tradingview",
        ),
    )
    catalog.add_alias(
        Alias(
            value="XAU/USD",
            target_type="series",
            target_id="series:spot:xau-usd:consolidated",
            asset_class="spot",
        ),
    )
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="twelve_data",
            target_type="series",
            target_id="series:spot:xau-usd:consolidated",
            provider_symbol="XAU/USD",
        ),
    )
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="tradingview",
            target_type="series",
            target_id="series:spot:xau-usd:consolidated",
            provider_symbol="XAUUSD",
            provider_exchange="OANDA",
        ),
    )


def _seed_futures_series(catalog: InstrumentCatalog) -> None:
    products = (
        ("NQ", "E-mini Nasdaq-100 Futures", "CME_MINI"),
        ("MNQ", "Micro E-mini Nasdaq-100 Futures", "CME_MINI"),
        ("ES", "E-mini S&P 500 Futures", "CME_MINI"),
        ("MES", "Micro E-mini S&P 500 Futures", "CME_MINI"),
        ("GC", "Gold Futures", "COMEX"),
        ("MGC", "Micro Gold Futures", "COMEX"),
    )
    for symbol, name, venue in products:
        normalized = symbol.lower()
        instrument_id = f"instrument:futures:{normalized}"
        series_id = f"series:futures:{normalized}:front"
        catalog.add_instrument(
            Instrument(
                id=instrument_id,
                asset_class="futures",
                display_symbol=symbol,
                display_name=name,
                futures_spec=FUTURES_CONTRACT_SPECS[symbol],
            ),
        )
        catalog.add_series(
            MarketSeries(
                id=series_id,
                instrument_id=instrument_id,
                kind="continuous_future",
                display_symbol=symbol,
                display_name=f"{name} Continuous",
            ),
        )
        catalog.add_alias(
            Alias(
                value=symbol,
                target_type="series",
                target_id=series_id,
                asset_class="futures",
                venue=venue,
            ),
        )
        catalog.add_alias(
            Alias(
                value=f"{symbol}1!",
                target_type="series",
                target_id=series_id,
                asset_class="futures",
                venue=venue,
                provider="tradingview",
            ),
        )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="tradingview",
                target_type="series",
                target_id=series_id,
                provider_symbol=f"{symbol}1!",
                provider_exchange=venue,
                provider_timezone=FUTURES_CONTRACT_SPECS[symbol].timezone,
            ),
        )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="yahoo",
                target_type="series",
                target_id=series_id,
                provider_symbol=f"{symbol}=F",
            ),
        )


def _seed_crypto_series(catalog: InstrumentCatalog) -> None:
    assets = (
        ("BTC", "Bitcoin"),
        ("ETH", "Ethereum"),
        ("SOL", "Solana"),
        ("XRP", "XRP"),
    )
    for symbol, name in assets:
        pair_key = f"{symbol.lower()}-usd"
        instrument_id = f"instrument:crypto:{pair_key}"
        catalog.add_instrument(
            Instrument(
                id=instrument_id,
                asset_class="crypto",
                display_symbol=f"{symbol}/USD",
                display_name=f"{name} / U.S. Dollar",
            ),
        )
        consolidated_id = f"series:crypto:{pair_key}:consolidated"
        catalog.add_series(
            MarketSeries(
                id=consolidated_id,
                instrument_id=instrument_id,
                kind="consolidated",
                display_symbol=f"{symbol}/USD",
                display_name=f"{name} / U.S. Dollar (Consolidated)",
            ),
        )
        for alias_value in (f"{symbol}USD", f"{symbol}/USD"):
            catalog.add_alias(
                Alias(
                    value=alias_value,
                    target_type="series",
                    target_id=consolidated_id,
                    asset_class="crypto",
                    confidence=0.9,
                ),
            )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="twelve_data",
                target_type="series",
                target_id=consolidated_id,
                provider_symbol=f"{symbol}/USD",
            ),
        )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="yahoo",
                target_type="series",
                target_id=consolidated_id,
                provider_symbol=f"{symbol}-USD",
            ),
        )

        for venue in ("BINANCE", "COINBASE"):
            venue_key = venue.lower()
            listing_id = f"listing:crypto:{pair_key}:{venue_key}"
            series_id = f"series:crypto:{pair_key}:{venue_key}"
            catalog.add_listing(
                Listing(
                    id=listing_id,
                    instrument_id=instrument_id,
                    venue=venue,
                    listing_symbol=f"{symbol}USD",
                    timezone="UTC",
                ),
            )
            catalog.add_series(
                MarketSeries(
                    id=series_id,
                    instrument_id=instrument_id,
                    listing_id=listing_id,
                    kind="listing",
                    display_symbol=f"{venue}:{symbol}USD",
                    display_name=f"{name} / U.S. Dollar ({venue.title()})",
                ),
            )
            for alias_value in (f"{symbol}USD", f"{symbol}/USD"):
                catalog.add_alias(
                    Alias(
                        value=alias_value,
                        target_type="series",
                        target_id=series_id,
                        asset_class="crypto",
                        venue=venue,
                    ),
                )
            if venue == "COINBASE":
                catalog.add_provider_mapping(
                    ProviderMapping(
                        provider_id="twelve_data",
                        target_type="series",
                        target_id=series_id,
                        provider_symbol=f"{symbol}/USD",
                        provider_exchange="Coinbase",
                    ),
                )
                catalog.add_provider_mapping(
                    ProviderMapping(
                        provider_id="tradingview",
                        target_type="series",
                        target_id=series_id,
                        provider_symbol=f"{symbol}USD",
                        provider_exchange="COINBASE",
                    ),
                )


def _seed_equity_series(catalog: InstrumentCatalog) -> None:
    equities = (
        ("AAPL", "Apple Inc.", "XNAS", "NASDAQ"),
        ("TSLA", "Tesla, Inc.", "XNAS", "NASDAQ"),
        ("SPY", "SPDR S&P 500 ETF Trust", "ARCX", "AMEX"),
        ("QQQ", "Invesco QQQ Trust", "XNAS", "NASDAQ"),
        ("IWM", "iShares Russell 2000 ETF", "ARCX", "AMEX"),
        ("DIA", "SPDR Dow Jones Industrial Average ETF", "ARCX", "AMEX"),
        ("TLT", "iShares 20+ Year Treasury Bond ETF", "XNAS", "NASDAQ"),
        ("HYG", "iShares iBoxx High Yield Corporate Bond ETF", "ARCX", "AMEX"),
        ("USO", "United States Oil Fund", "ARCX", "AMEX"),
        ("GLD", "SPDR Gold Shares", "ARCX", "AMEX"),
        ("SLV", "iShares Silver Trust", "ARCX", "AMEX"),
    )
    for symbol, name, venue, provider_exchange in equities:
        symbol_key = symbol.lower()
        instrument_id = f"instrument:equity:{symbol_key}"
        venue_key = venue.lower()
        listing_id = f"listing:equity:{symbol_key}:{venue_key}"
        series_id = f"series:equity:{symbol_key}:{venue_key}"
        catalog.add_instrument(
            Instrument(
                id=instrument_id,
                asset_class="equity",
                display_symbol=symbol,
                display_name=name,
            ),
        )
        catalog.add_listing(
            Listing(
                id=listing_id,
                instrument_id=instrument_id,
                venue=venue,
                listing_symbol=symbol,
                timezone="America/New_York",
            ),
        )
        catalog.add_series(
            MarketSeries(
                id=series_id,
                instrument_id=instrument_id,
                listing_id=listing_id,
                kind="listing",
                display_symbol=symbol,
                display_name=name,
            ),
        )
        catalog.add_alias(
            Alias(
                value=symbol,
                target_type="series",
                target_id=series_id,
                asset_class="equity",
                venue=venue,
            ),
        )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="twelve_data",
                target_type="series",
                target_id=series_id,
                provider_symbol=symbol,
            ),
        )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="yahoo",
                target_type="series",
                target_id=series_id,
                provider_symbol=symbol,
            ),
        )
        catalog.add_provider_mapping(
            ProviderMapping(
                provider_id="tradingview",
                target_type="series",
                target_id=series_id,
                provider_symbol=symbol,
                provider_exchange=provider_exchange,
                provider_timezone="America/New_York",
            ),
        )


def _seed_index_series(catalog: InstrumentCatalog) -> None:
    instrument_id = "instrument:index:spx500"
    series_id = "series:index:spx500:consolidated"
    catalog.add_instrument(
        Instrument(
            id=instrument_id,
            asset_class="index",
            display_symbol="SPX500",
            display_name="S&P 500 Index",
        ),
    )
    catalog.add_series(
        MarketSeries(
            id=series_id,
            instrument_id=instrument_id,
            kind="consolidated",
            display_symbol="SPX500",
            display_name="S&P 500 Index",
        ),
    )
    catalog.add_alias(
        Alias(
            value="SPX500",
            target_type="series",
            target_id=series_id,
            asset_class="index",
        ),
    )
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="twelve_data",
            target_type="series",
            target_id=series_id,
            provider_symbol="SPX",
        ),
    )
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="yahoo",
            target_type="series",
            target_id=series_id,
            provider_symbol="^GSPC",
        ),
    )
    catalog.add_provider_mapping(
        ProviderMapping(
            provider_id="tradingview",
            target_type="series",
            target_id=series_id,
            provider_symbol="SPX",
            provider_exchange="SP",
            provider_timezone="America/New_York",
        ),
    )


def _seed_reference_instruments(catalog: InstrumentCatalog) -> None:
    """Canonical identities used by features that do not request price series yet."""
    references = (
        (
            Instrument(
                id="instrument:commodity:wti",
                asset_class="commodity",
                display_symbol="WTI",
                display_name="West Texas Intermediate Crude Oil",
            ),
            ("WTI", "USOIL"),
        ),
        (
            Instrument(
                id="instrument:index:ndx",
                asset_class="index",
                display_symbol="NDX",
                display_name="Nasdaq-100 Index",
            ),
            ("NDX", "NASDAQ 100"),
        ),
    )
    for instrument, aliases in references:
        catalog.add_instrument(instrument)
        for alias in aliases:
            catalog.add_alias(
                Alias(
                    value=alias,
                    target_type="instrument",
                    target_id=instrument.id,
                    asset_class=instrument.asset_class,
                ),
            )
