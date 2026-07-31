import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from db import get_db


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


async def _register(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


@pytest.fixture
async def auth_a(client: AsyncClient):
    return await _register(client, "a@example.com")


@pytest.fixture
async def auth_c(client: AsyncClient):
    return await _register(client, "c@example.com")


@pytest.mark.anyio
async def test_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/strategies")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_list_get_patch_delete(client: AsyncClient, auth_a):
    r = await client.post("/api/strategies", json={"title": "x"}, headers=auth_a)
    assert r.status_code == 200 and r.json()["code"] == 0
    sid = r.json()["data"]["id"]

    r = await client.get("/api/strategies", headers=auth_a)
    assert r.json()["data"][0]["title"] == "x"

    r = await client.get(f"/api/strategies/{sid}", headers=auth_a)
    assert r.json()["data"]["body"] == ""

    r = await client.patch(f"/api/strategies/{sid}", json={"body": "hello"}, headers=auth_a)
    assert r.json()["data"]["body"] == "hello"
    assert r.json()["data"]["title"] == "x"

    r = await client.delete(f"/api/strategies/{sid}", headers=auth_a)
    assert r.json()["data"] == {"ok": True}

    r = await client.get(f"/api/strategies/{sid}", headers=auth_a)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_options_returns_id_and_title_only(client: AsyncClient, auth_a):
    await client.post("/api/strategies", json={"title": "T", "body": "BODY"}, headers=auth_a)
    r = await client.get("/api/strategies/options", headers=auth_a)
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    assert set(items[0].keys()) == {"id", "title"}


@pytest.mark.anyio
async def test_isolation_other_user_404(client: AsyncClient, auth_a, auth_c):
    sid = (await client.post("/api/strategies", json={"title": "x"}, headers=auth_a)).json()["data"]["id"]
    r = await client.get(f"/api/strategies/{sid}", headers=auth_c)
    assert r.status_code == 404
    r = await client.patch(f"/api/strategies/{sid}", json={"title": "h"}, headers=auth_c)
    assert r.status_code == 404
    r = await client.delete(f"/api/strategies/{sid}", headers=auth_c)
    assert r.status_code == 404
