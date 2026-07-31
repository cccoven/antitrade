"""Persistent cache adapter for normalized Candle Series."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import MarketCandle, MarketCandleCoverage
from services.market_gateway import (
    Candle,
    CandleQuery,
    CandleSeries,
    ProviderMapping,
    QualityReport,
    SourceMetadata,
)

logger = logging.getLogger(__name__)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqlAlchemyCandleCache:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def get(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> CandleSeries | None:
        try:
            return self._get(mapping, query)
        except SQLAlchemyError as exc:
            logger.warning("Market candle cache read failed: %s", exc)
            return None

    def _get(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> CandleSeries | None:
        requested_start = _utc(query.start)
        requested_end = _utc(query.end)
        with self._session_factory() as session:
            coverage = session.execute(
                select(MarketCandleCoverage).where(
                    MarketCandleCoverage.provider_id == mapping.provider_id,
                    MarketCandleCoverage.series_id == query.series_id,
                    MarketCandleCoverage.timeframe == query.timeframe,
                    MarketCandleCoverage.purpose == query.purpose,
                    MarketCandleCoverage.requested_start == requested_start,
                    MarketCandleCoverage.requested_end == requested_end,
                ),
            ).scalar_one_or_none()
            if coverage is None:
                return None

            rows = session.execute(
                select(MarketCandle)
                .where(
                    MarketCandle.provider_id == mapping.provider_id,
                    MarketCandle.series_id == query.series_id,
                    MarketCandle.timeframe == query.timeframe,
                    MarketCandle.open_time >= requested_start,
                    MarketCandle.open_time < requested_end,
                )
                .order_by(MarketCandle.open_time),
            ).scalars().all()
            if not rows:
                return None

            candles = tuple(
                Candle(
                    open_time=_utc(row.open_time),
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                    is_closed=row.is_closed,
                )
                for row in rows
            )
            try:
                warnings = tuple(json.loads(coverage.quality_warnings))
            except (json.JSONDecodeError, TypeError):
                warnings = ("invalid_cached_quality_metadata",)
            return CandleSeries(
                series_id=query.series_id,
                instrument_id=coverage.instrument_id,
                listing_id=coverage.listing_id,
                timeframe=query.timeframe,
                candles=candles,
                requested_start=requested_start,
                requested_end=requested_end,
                actual_start=candles[0].open_time,
                actual_end=candles[-1].open_time,
                source=SourceMetadata(
                    provider_id=coverage.provider_id,
                    provider_symbol=coverage.provider_symbol,
                    provider_exchange=coverage.provider_exchange,
                    fetched_at=_utc(coverage.fetched_at),
                    cache_status="hit",
                ),
                quality=QualityReport(
                    status=coverage.quality_status,
                    warnings=warnings,
                ),
            )

    def put(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
        series: CandleSeries,
    ) -> None:
        try:
            self._put(mapping, query, series)
        except SQLAlchemyError as exc:
            logger.warning("Market candle cache write failed: %s", exc)

    def get_stale(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
    ) -> CandleSeries | None:
        # Version one treats exact closed-history coverage as long-lived. This
        # hook keeps stale fallback policy in the gateway and allows a future
        # TTL-aware cache to expose expired-but-usable coverage safely.
        del mapping, query
        return None

    def _put(
        self,
        mapping: ProviderMapping,
        query: CandleQuery,
        series: CandleSeries,
    ) -> None:
        requested_start = _utc(query.start)
        requested_end = _utc(query.end)
        with self._session_factory() as session:
            for candle in series.candles:
                session.merge(
                    MarketCandle(
                        provider_id=mapping.provider_id,
                        series_id=query.series_id,
                        timeframe=query.timeframe,
                        open_time=_utc(candle.open_time),
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                        is_closed=candle.is_closed,
                        fetched_at=_utc(series.source.fetched_at),
                    ),
                )

            coverage = session.execute(
                select(MarketCandleCoverage).where(
                    MarketCandleCoverage.provider_id == mapping.provider_id,
                    MarketCandleCoverage.series_id == query.series_id,
                    MarketCandleCoverage.timeframe == query.timeframe,
                    MarketCandleCoverage.purpose == query.purpose,
                    MarketCandleCoverage.requested_start == requested_start,
                    MarketCandleCoverage.requested_end == requested_end,
                ),
            ).scalar_one_or_none()
            if coverage is None:
                coverage = MarketCandleCoverage(
                    id=str(uuid4()),
                    provider_id=mapping.provider_id,
                    series_id=query.series_id,
                    instrument_id=series.instrument_id,
                    listing_id=series.listing_id,
                    timeframe=query.timeframe,
                    purpose=query.purpose,
                    requested_start=requested_start,
                    requested_end=requested_end,
                    provider_symbol=series.source.provider_symbol,
                    provider_exchange=series.source.provider_exchange,
                    fetched_at=_utc(series.source.fetched_at),
                    quality_status=series.quality.status,
                    quality_warnings=json.dumps(series.quality.warnings),
                )
                session.add(coverage)
            else:
                coverage.fetched_at = _utc(series.source.fetched_at)
                coverage.quality_status = series.quality.status
                coverage.quality_warnings = json.dumps(series.quality.warnings)
            session.commit()
