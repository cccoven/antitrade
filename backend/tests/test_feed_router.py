import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from db import get_db
from models import FeedItem


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(db):
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _auth(client):
    r = await client.post("/api/auth/register",
                          json={"email": f"{uuid.uuid4()}@t.test", "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


def _seed(db, category="crypto", symbols=None):
    now = datetime.now(timezone.utc).isoformat()
    db.add(FeedItem(id=str(uuid.uuid4()), url=f"https://x/{uuid.uuid4()}",
                    source_key="s", title="BTC up", summary="body",
                    published_at=now, fetched_at=now, category=category,
                    symbols=symbols or ["instrument:crypto:btc-usd"], lang="en"))
    db.flush()


@pytest.mark.anyio
async def test_list_items_public(client, db):
    _seed(db)
    r = await client.get("/api/feed/items")
    assert r.status_code == 200 and r.json()["code"] == 0
    assert r.json()["data"]["total"] == 1


@pytest.mark.anyio
async def test_list_items_category_filter(client, db):
    _seed(db, category="crypto")
    _seed(db, category="macro", symbols=[])
    r = await client.get("/api/feed/items", params={"category": "macro"})
    assert r.json()["data"]["total"] == 1
    assert r.json()["data"]["items"][0]["category"] == "macro"


@pytest.mark.anyio
async def test_briefing_latest_empty_returns_null(client, db):
    r = await client.get("/api/feed/briefing/latest", params={"lang": "en"})
    assert r.status_code == 200
    assert r.json()["data"] is None


@pytest.mark.anyio
async def test_bookmarks_require_auth(client, db):
    r = await client.get("/api/feed/bookmarks")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_bookmark_flow(client, db):
    _seed(db)
    from sqlalchemy import select
    item_id = db.execute(select(FeedItem.id)).scalar_one()
    headers = await _auth(client)
    r = await client.post("/api/feed/bookmarks", json={"feed_item_id": item_id}, headers=headers)
    assert r.status_code == 200
    bm_id = r.json()["data"]["id"]
    r = await client.get("/api/feed/bookmarks", headers=headers)
    assert len(r.json()["data"]) == 1
    r = await client.delete(f"/api/feed/bookmarks/{bm_id}", headers=headers)
    assert r.json()["data"] == {"ok": True}


@pytest.mark.anyio
async def test_bookmark_unknown_item_returns_404(client, db):
    headers = await _auth(client)
    r = await client.post("/api/feed/bookmarks", json={"feed_item_id": "does-not-exist"}, headers=headers)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_bookmark_items_require_auth(client, db):
    r = await client.get("/api/feed/bookmarks/items")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_bookmark_items_returns_full_content(client, db):
    _seed(db)
    headers = await _auth(client)
    item_id = (await client.get("/api/feed/items")).json()["data"]["items"][0]["id"]
    await client.post("/api/feed/bookmarks", json={"feed_item_id": item_id}, headers=headers)

    r = await client.get("/api/feed/bookmarks/items", headers=headers)
    assert r.status_code == 200 and r.json()["code"] == 0
    data = r.json()["data"]
    assert data["total"] == 1
    row = data["items"][0]
    assert row["id"] == item_id
    assert row["title"] == "BTC up"          # full content present
    assert row["bookmark_id"]                # bookmark metadata present
    assert row["bookmarked_at"]


@pytest.mark.anyio
async def test_bookmark_items_newest_bookmark_first(client, db):
    # Seed two items; bookmark the SECOND one first, then the first.
    _seed(db, category="crypto")
    _seed(db, category="macro", symbols=[])
    headers = await _auth(client)
    items = (await client.get("/api/feed/items")).json()["data"]["items"]
    id_a, id_b = items[0]["id"], items[1]["id"]
    await client.post("/api/feed/bookmarks", json={"feed_item_id": id_b}, headers=headers)
    await client.post("/api/feed/bookmarks", json={"feed_item_id": id_a}, headers=headers)

    r = await client.get("/api/feed/bookmarks/items", headers=headers)
    ids = [it["id"] for it in r.json()["data"]["items"]]
    assert ids == [id_a, id_b]   # most recently bookmarked first


@pytest.mark.anyio
async def test_bookmark_items_isolated_per_user(client, db):
    _seed(db)
    item_id = (await client.get("/api/feed/items")).json()["data"]["items"][0]["id"]
    headers_a = await _auth(client)
    headers_b = await _auth(client)
    await client.post("/api/feed/bookmarks", json={"feed_item_id": item_id}, headers=headers_a)

    r = await client.get("/api/feed/bookmarks/items", headers=headers_b)
    assert r.json()["data"]["total"] == 0   # user B sees none of user A's bookmarks
