import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from main import app
from db import get_db
from models import TradeImage
from tests.test_uploads import PNG_1X1


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(db, tmp_path, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _register(client: AsyncClient, email: str):
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


async def _upload(client: AsyncClient, headers):
    resp = await client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("chart.png", PNG_1X1, "image/png")},
    )
    assert resp.status_code == 200
    return resp.json()["data"]


@pytest.mark.anyio
async def test_create_trade_with_images_returns_nested_images(client):
    headers = await _register(client, "trade-images@example.com")
    first = await _upload(client, headers)
    second = await _upload(client, headers)

    resp = await client.post(
        "/api/journal/trades",
        headers=headers,
        json={
            "symbol": "XAUUSD",
            "direction": "long",
            "open_time": "2026-04-24T09:00:00Z",
            "image_asset_ids": [first["id"], second["id"]],
        },
    )

    assert resp.status_code == 200
    trade = resp.json()["data"]
    assert [img["asset_id"] for img in trade["images"]] == [first["id"], second["id"]]
    assert [img["sort_order"] for img in trade["images"]] == [0, 1]
    assert trade["images"][0]["url"] == f"/api/uploads/{first['id']}"


@pytest.mark.anyio
async def test_update_trade_replaces_image_associations(client):
    headers = await _register(client, "replace-images@example.com")
    first = await _upload(client, headers)
    second = await _upload(client, headers)
    third = await _upload(client, headers)
    create = await client.post(
        "/api/journal/trades",
        headers=headers,
        json={
            "symbol": "BTCUSD",
            "direction": "short",
            "image_asset_ids": [first["id"], second["id"]],
        },
    )
    trade_id = create.json()["data"]["id"]

    resp = await client.put(
        f"/api/journal/trades/{trade_id}",
        headers=headers,
        json={"image_asset_ids": [third["id"], first["id"]]},
    )

    assert resp.status_code == 200
    images = resp.json()["data"]["images"]
    assert [img["asset_id"] for img in images] == [third["id"], first["id"]]
    assert [img["sort_order"] for img in images] == [0, 1]


@pytest.mark.anyio
async def test_list_and_get_trades_include_images(client):
    headers = await _register(client, "list-images@example.com")
    asset = await _upload(client, headers)
    create = await client.post(
        "/api/journal/trades",
        headers=headers,
        json={
            "symbol": "ETHUSD",
            "direction": "long",
            "image_asset_ids": [asset["id"]],
        },
    )
    trade_id = create.json()["data"]["id"]

    listed = await client.get("/api/journal/trades", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["images"][0]["asset_id"] == asset["id"]

    fetched = await client.get(f"/api/journal/trades/{trade_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["data"]["images"][0]["asset_id"] == asset["id"]


@pytest.mark.anyio
async def test_cross_user_asset_binding_is_rejected(client):
    owner = await _register(client, "owner-images@example.com")
    other = await _register(client, "other-images@example.com")
    asset = await _upload(client, owner)

    resp = await client.post(
        "/api/journal/trades",
        headers=other,
        json={
            "symbol": "XAUUSD",
            "direction": "long",
            "image_asset_ids": [asset["id"]],
        },
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 400


@pytest.mark.anyio
async def test_delete_trade_deletes_image_associations(client, db):
    headers = await _register(client, "delete-images@example.com")
    asset = await _upload(client, headers)
    create = await client.post(
        "/api/journal/trades",
        headers=headers,
        json={
            "symbol": "XAUUSD",
            "direction": "long",
            "image_asset_ids": [asset["id"]],
        },
    )
    trade_id = create.json()["data"]["id"]

    delete = await client.delete(f"/api/journal/trades/{trade_id}", headers=headers)
    assert delete.status_code == 200

    count = db.execute(select(func.count()).select_from(TradeImage)).scalar_one()
    assert count == 0


@pytest.mark.anyio
async def test_batch_create_rejects_image_asset_ids_without_creating_trades(client, db):
    headers = await _register(client, "batch-images@example.com")
    asset = await _upload(client, headers)

    resp = await client.post(
        "/api/journal/trades/batch",
        headers=headers,
        json={
            "trades": [
                {"symbol": "XAUUSD", "direction": "long"},
                {
                    "symbol": "BTCUSD",
                    "direction": "short",
                    "image_asset_ids": [asset["id"]],
                },
            ],
        },
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 400
    assert resp.json()["message"] == "Images are not supported in batch create"
    from models import Trade
    count = db.execute(select(func.count()).select_from(Trade)).scalar_one()
    assert count == 0
