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


async def _make_portfolio(client, headers, name="CNY 组合", currency="CNY"):
    r = await client.post(
        "/api/portfolio/portfolios",
        json={"name": name, "currency": currency},
        headers=headers,
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


async def _create_entry(client, headers, pid, **overrides):
    payload = {"name": "茅台", "category": "证券", "platform": "富途", "amount": 100000.0}
    payload.update(overrides)
    r = await client.post(
        f"/api/portfolio/portfolios/{pid}/entries",
        json=payload, headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.anyio
async def test_create_entry_returns_fields(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    e = await _create_entry(client, auth_headers, pid)
    assert e["id"]
    assert e["portfolio_id"] == pid
    assert "currency" not in e


@pytest.mark.anyio
async def test_create_entry_rejects_negative_amount(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    r = await client.post(
        f"/api/portfolio/portfolios/{pid}/entries",
        json={"name": "bad", "category": "证券", "amount": -1},
        headers=auth_headers,
    )
    assert r.status_code in (400, 422)


@pytest.mark.anyio
async def test_list_entries_scoped_to_portfolio(client, auth_headers):
    p1 = await _make_portfolio(client, auth_headers, name="A", currency="CNY")
    p2 = await _make_portfolio(client, auth_headers, name="B", currency="USD")
    await _create_entry(client, auth_headers, p1, name="in-A")
    await _create_entry(client, auth_headers, p2, name="in-B")
    r1 = await client.get(f"/api/portfolio/portfolios/{p1}/entries", headers=auth_headers)
    r2 = await client.get(f"/api/portfolio/portfolios/{p2}/entries", headers=auth_headers)
    assert [e["name"] for e in r1.json()["data"]["items"]] == ["in-A"]
    assert [e["name"] for e in r2.json()["data"]["items"]] == ["in-B"]


@pytest.mark.anyio
async def test_update_and_delete_entry(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    e = await _create_entry(client, auth_headers, pid)
    r = await client.patch(
        f"/api/portfolio/entries/{e['id']}",
        json={"amount": 200000.0, "notes": "upd"}, headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["amount"] == 200000.0
    r = await client.delete(f"/api/portfolio/entries/{e['id']}", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.anyio
async def test_cross_user_entry_access_blocked(client, auth_headers, second_auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    e = await _create_entry(client, auth_headers, pid)
    r = await client.patch(
        f"/api/portfolio/entries/{e['id']}",
        json={"amount": 999}, headers=second_auth_headers,
    )
    assert r.status_code == 404
    r = await client.delete(f"/api/portfolio/entries/{e['id']}", headers=second_auth_headers)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_list_filter_by_category(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    await _create_entry(client, auth_headers, pid, name="A", category="证券")
    await _create_entry(client, auth_headers, pid, name="B", category="现金")
    r = await client.get(
        f"/api/portfolio/portfolios/{pid}/entries",
        params={"category": "现金"}, headers=auth_headers,
    )
    assert [e["name"] for e in r.json()["data"]["items"]] == ["B"]


@pytest.mark.anyio
async def test_categories_list_excludes_crypto(client, auth_headers):
    r = await client.get("/api/portfolio/categories", headers=auth_headers)
    names = [c["name"] for c in r.json()["data"]["items"]]
    assert "加密" not in names
    assert "证券" in names
    assert "负债" in names


@pytest.mark.anyio
async def test_category_collision_block(client, auth_headers):
    r = await client.post(
        "/api/portfolio/categories",
        json={"name": "证券", "kind": "asset"}, headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.anyio
async def test_category_delete_blocked_when_in_use(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    r = await client.post(
        "/api/portfolio/categories",
        json={"name": "NFT", "kind": "asset"}, headers=auth_headers,
    )
    cid = r.json()["data"]["id"]
    await _create_entry(client, auth_headers, pid, category="NFT")
    r = await client.delete(f"/api/portfolio/categories/{cid}", headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["data"]["entry_count"] >= 1


@pytest.mark.anyio
async def test_preferences_and_rates_endpoints_gone(client, auth_headers):
    for path in ("/api/portfolio/preferences", "/api/portfolio/rates"):
        r = await client.get(path, headers=auth_headers)
        assert r.status_code == 404


@pytest.mark.anyio
async def test_summary_empty(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    r = await client.get(f"/api/portfolio/portfolios/{pid}/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["portfolio"]["id"] == pid
    assert data["portfolio"]["currency"] == "CNY"
    assert data["totals"] == {"assets": 0, "liabilities": 0, "net_worth": 0}


@pytest.mark.anyio
async def test_summary_computes_totals_with_liability(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    await _create_entry(client, auth_headers, pid, name="cash", category="现金", amount=100000.0)
    await _create_entry(client, auth_headers, pid, name="aapl", category="证券", amount=65000.0)
    await _create_entry(client, auth_headers, pid, name="mortgage", category="负债", amount=50000.0)
    r = await client.get(f"/api/portfolio/portfolios/{pid}/summary", headers=auth_headers)
    data = r.json()["data"]
    assert data["totals"]["assets"] == 165000.0
    assert data["totals"]["liabilities"] == 50000.0
    assert data["totals"]["net_worth"] == 115000.0


@pytest.mark.anyio
async def test_summary_groups_by_category_and_platform(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    await _create_entry(client, auth_headers, pid, name="a", category="证券", platform="富途", amount=100)
    await _create_entry(client, auth_headers, pid, name="b", category="证券", platform="招商", amount=200)
    await _create_entry(client, auth_headers, pid, name="c", category="现金", platform="招商", amount=300)
    r = await client.get(f"/api/portfolio/portfolios/{pid}/summary", headers=auth_headers)
    data = r.json()["data"]
    by_cat = {x["name"]: x for x in data["by_category"]}
    by_plat = {x["name"]: x for x in data["by_platform"]}
    assert by_cat["证券"]["total"] == 300.0
    assert by_cat["证券"]["count"] == 2
    assert by_cat["证券"]["kind"] == "asset"
    assert by_cat["现金"]["total"] == 300.0
    assert by_plat["富途"]["total"] == 100.0
    assert by_plat["招商"]["total"] == 500.0


@pytest.mark.anyio
async def test_summary_blocks_cross_user(client, auth_headers, second_auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    r = await client.get(f"/api/portfolio/portfolios/{pid}/summary", headers=second_auth_headers)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_export_csv_excludes_currency_column(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    await _create_entry(client, auth_headers, pid, name="a", amount=100.0)
    r = await client.get(f"/api/portfolio/portfolios/{pid}/entries/export", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    assert "name,category,platform,amount,notes" in body
    assert "currency" not in body.splitlines()[0]
    assert "a,证券,富途,100.0" in body


@pytest.mark.anyio
async def test_import_csv_ignores_legacy_currency_column(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    csv_text = (
        "name,category,platform,currency,amount,notes\n"
        "a,証券,富途,CNY,100,\n"
        "b,NFT,OpenSea,USD,200,legacy import\n"
    )
    files = {"file": ("legacy.csv", csv_text.encode("utf-8"), "text/csv")}
    r = await client.post(
        f"/api/portfolio/portfolios/{pid}/entries/import",
        files=files, headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["inserted"] == 2
    r = await client.get(f"/api/portfolio/portfolios/{pid}/entries", headers=auth_headers)
    names = {e["name"] for e in r.json()["data"]["items"]}
    assert names == {"a", "b"}


@pytest.mark.anyio
async def test_import_csv_rejects_oversized(client, auth_headers):
    pid = await _make_portfolio(client, auth_headers)
    big = ("name,category,amount\n" + "a,证券,1\n" * 500000).encode("utf-8")
    assert len(big) > 5 * 1024 * 1024
    files = {"file": ("big.csv", big, "text/csv")}
    r = await client.post(
        f"/api/portfolio/portfolios/{pid}/entries/import",
        files=files, headers=auth_headers,
    )
    assert r.status_code == 413
