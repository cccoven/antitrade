"""Persistent stale-while-revalidate snapshots for the market overview."""

from __future__ import annotations

import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable, ContextManager, Protocol

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import db
from models import MarketDashboardSnapshot
from services.market_research import get_market_overview


logger = logging.getLogger(__name__)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Snapshot:
    payload: dict
    fetched_at: datetime


class SnapshotStore(Protocol):
    def load(self, key: str) -> Snapshot | None: ...

    def save(self, key: str, snapshot: Snapshot) -> None: ...


class SqlAlchemySnapshotStore:
    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
    ) -> None:
        self._session_factory = session_factory

    def load(self, key: str) -> Snapshot | None:
        try:
            with self._session_factory() as session:
                row = session.get(MarketDashboardSnapshot, key)
                if row is None:
                    return None
                return Snapshot(
                    payload=dict(row.payload),
                    fetched_at=_utc(row.fetched_at),
                )
        except SQLAlchemyError:
            logger.warning("market overview snapshot read failed", exc_info=True)
            return None

    def save(self, key: str, snapshot: Snapshot) -> None:
        try:
            with self._session_factory() as session:
                session.merge(MarketDashboardSnapshot(
                    key=key,
                    payload=snapshot.payload,
                    fetched_at=snapshot.fetched_at,
                    updated_at=datetime.now(timezone.utc),
                ))
                session.commit()
        except SQLAlchemyError:
            logger.warning("market overview snapshot write failed", exc_info=True)


class MarketOverviewSnapshotCache:
    def __init__(
        self,
        *,
        key: str,
        store: SnapshotStore,
        fetcher: Callable[[], dict],
        fresh_for: timedelta = timedelta(seconds=60),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        executor: Executor | None = None,
    ) -> None:
        self._key = key
        self._store = store
        self._fetcher = fetcher
        self._fresh_for = fresh_for
        self._clock = clock
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="market-overview-refresh",
        )
        self._refresh_lock = Lock()
        self._queue_lock = Lock()
        self._refresh_queued = False

    def get(self) -> dict:
        snapshot = self._store.load(self._key)
        if snapshot is None:
            snapshot = self._refresh_if_missing()
        stale = self._is_stale(snapshot)
        if stale:
            self._queue_refresh()
        return self._response(snapshot, stale=stale)

    def refresh(self, fetcher: Callable[[], dict] | None = None) -> dict:
        with self._refresh_lock:
            snapshot = Snapshot(
                payload=(fetcher or self._fetcher)(),
                fetched_at=self._clock(),
            )
            self._store.save(self._key, snapshot)
        return self._response(snapshot, stale=False)

    def _refresh_if_missing(self) -> Snapshot:
        with self._refresh_lock:
            existing = self._store.load(self._key)
            if existing is not None:
                return existing
            snapshot = Snapshot(
                payload=self._fetcher(),
                fetched_at=self._clock(),
            )
            self._store.save(self._key, snapshot)
            return snapshot

    def _is_stale(self, snapshot: Snapshot) -> bool:
        return _utc(self._clock()) - _utc(snapshot.fetched_at) > self._fresh_for

    def _queue_refresh(self) -> None:
        with self._queue_lock:
            if self._refresh_queued:
                return
            self._refresh_queued = True

        def run() -> None:
            try:
                self.refresh()
            except Exception:
                logger.warning(
                    "market overview background refresh failed",
                    exc_info=True,
                )
            finally:
                with self._queue_lock:
                    self._refresh_queued = False

        self._executor.submit(run)

    @staticmethod
    def _response(snapshot: Snapshot, *, stale: bool) -> dict:
        return {
            **snapshot.payload,
            "cache": {
                "status": "stale" if stale else "fresh",
                "fetched_at": snapshot.fetched_at.isoformat(),
            },
        }


_overview_cache = MarketOverviewSnapshotCache(
    key="market-overview:v2",
    store=SqlAlchemySnapshotStore(lambda: db.SessionLocal()),
    fetcher=get_market_overview,
)


def get_market_overview_snapshot() -> dict:
    return _overview_cache.get()


def refresh_market_overview_snapshot(*, force_refresh: bool = False) -> dict:
    if force_refresh:
        return _overview_cache.refresh(lambda: get_market_overview(force_refresh=True))
    return _overview_cache.refresh()
