import pytest
from httpx import AsyncClient, ASGITransport

from db import get_db
from main import app


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


async def _auth(client: AsyncClient, email: str):
    r = await client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


@pytest.fixture
async def auth_headers(client):
    return await _auth(client, "a@example.com")


@pytest.fixture
async def second_auth_headers(client):
    return await _auth(client, "b@example.com")


@pytest.mark.anyio
async def test_create_portfolio(client, auth_headers):
    r = await client.post(
        "/api/portfolio/portfolios",
        json={"name": "CNY 组合", "currency": "CNY"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"]
    assert data["name"] == "CNY 组合"
    assert data["currency"] == "CNY"
    assert data["entry_count"] == 0


@pytest.mark.anyio
async def test_update_portfolio(client, auth_headers):
    r = await client.post(
        "/api/portfolio/portfolios",
        json={"name": "Old", "currency": "CNY"},
        headers=auth_headers,
    )
    pid = r.json()["data"]["id"]
    r = await client.patch(
        f"/api/portfolio/portfolios/{pid}",
        json={"name": "New", "currency": "EUR"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "New"
    assert data["currency"] == "EUR"


@pytest.mark.anyio
async def test_user_isolation_on_portfolios(client, auth_headers, second_auth_headers):
    r = await client.post(
        "/api/portfolio/portfolios",
        json={"name": "mine", "currency": "CNY"},
        headers=auth_headers,
    )
    pid = r.json()["data"]["id"]

    # user B cannot list user A's portfolios
    r = await client.get("/api/portfolio/portfolios", headers=second_auth_headers)
    assert r.json()["data"]["items"] == []

    # user B cannot update / delete user A's portfolio
    r = await client.patch(
        f"/api/portfolio/portfolios/{pid}",
        json={"name": "hack"},
        headers=second_auth_headers,
    )
    assert r.status_code == 404

    r = await client.delete(f"/api/portfolio/portfolios/{pid}", headers=second_auth_headers)
    assert r.status_code == 404
