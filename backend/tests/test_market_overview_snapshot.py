from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from services.market_overview_snapshot import (
    MarketOverviewSnapshotCache,
    Snapshot,
    SqlAlchemySnapshotStore,
)


class MemoryStore:
    def __init__(self, snapshot: Snapshot | None = None):
        self.snapshot = snapshot
        self.saved: list[Snapshot] = []

    def load(self, key: str) -> Snapshot | None:
        del key
        return self.snapshot

    def save(self, key: str, snapshot: Snapshot) -> None:
        del key
        self.snapshot = snapshot
        self.saved.append(snapshot)


class RecordingExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, job):
        self.jobs.append(job)


def test_cold_cache_fetches_and_persists_before_returning():
    now = datetime(2026, 7, 27, 4, 0, tzinfo=timezone.utc)
    store = MemoryStore()
    calls = []
    cache = MarketOverviewSnapshotCache(
        key="overview:v1",
        store=store,
        fetcher=lambda: calls.append("fetch") or {"quotes": {"items": []}},
        clock=lambda: now,
        executor=RecordingExecutor(),
    )

    result = cache.get()

    assert calls == ["fetch"]
    assert len(store.saved) == 1
    assert result["cache"] == {
        "status": "fresh",
        "fetched_at": now.isoformat(),
    }


def test_stale_cache_returns_immediately_and_refreshes_once_in_background():
    now = datetime(2026, 7, 27, 4, 2, tzinfo=timezone.utc)
    old = Snapshot(
        payload={"quotes": {"items": [{"symbol": "SPY", "price": 100}]}},
        fetched_at=now - timedelta(minutes=2),
    )
    store = MemoryStore(old)
    executor = RecordingExecutor()
    calls = []
    cache = MarketOverviewSnapshotCache(
        key="overview:v1",
        store=store,
        fetcher=lambda: calls.append("fetch") or {
            "quotes": {"items": [{"symbol": "SPY", "price": 101}]},
        },
        fresh_for=timedelta(seconds=60),
        clock=lambda: now,
        executor=executor,
    )

    first = cache.get()
    second = cache.get()

    assert first["quotes"]["items"][0]["price"] == 100
    assert first["cache"]["status"] == "stale"
    assert second["cache"]["status"] == "stale"
    assert calls == []
    assert len(executor.jobs) == 1

    executor.jobs[0]()

    assert calls == ["fetch"]
    assert store.snapshot.payload["quotes"]["items"][0]["price"] == 101


def test_failed_background_refresh_keeps_last_successful_snapshot():
    now = datetime(2026, 7, 27, 4, 2, tzinfo=timezone.utc)
    old = Snapshot(
        payload={"quotes": {"items": [{"symbol": "SPY", "price": 100}]}},
        fetched_at=now - timedelta(minutes=2),
    )
    store = MemoryStore(old)
    executor = RecordingExecutor()

    def fail():
        raise RuntimeError("provider unavailable")

    cache = MarketOverviewSnapshotCache(
        key="overview:v1",
        store=store,
        fetcher=fail,
        fresh_for=timedelta(seconds=60),
        clock=lambda: now,
        executor=executor,
    )

    result = cache.get()
    executor.jobs[0]()

    assert result["quotes"]["items"][0]["price"] == 100
    assert store.snapshot is old
    assert store.saved == []


def test_sql_store_survives_cache_instance_recreation(db):
    @contextmanager
    def sessions():
        yield db

    now = datetime(2026, 7, 27, 4, 0, tzinfo=timezone.utc)
    first_store = SqlAlchemySnapshotStore(sessions)
    first_store.save(
        "overview:test",
        Snapshot(payload={"states": {"risk": "risk_on"}}, fetched_at=now),
    )
    db.expire_all()

    second_store = SqlAlchemySnapshotStore(sessions)
    loaded = second_store.load("overview:test")

    assert loaded == Snapshot(
        payload={"states": {"risk": "risk_on"}},
        fetched_at=now,
    )
