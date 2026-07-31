import pytest
from httpx import ASGITransport, AsyncClient

from db import get_db
from main import app
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
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


async def _upload_image(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("chart.png", PNG_1X1, "image/png")},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.anyio
async def test_annotations_can_be_saved_before_asset_is_attached_to_trade(client):
    headers = await _register(client, "annotations@example.com")
    asset = await _upload_image(client, headers)

    saved = await client.put(
        f"/api/uploads/{asset['id']}/annotations",
        headers=headers,
        json={
            "items": [
                {"x_ratio": 0.25, "y_ratio": 0.75, "body": "Entry confirmation"},
                {"x_ratio": 0.8, "y_ratio": 0.2, "body": "Exit near resistance"},
            ],
        },
    )

    assert saved.status_code == 200
    items = saved.json()["data"]["items"]
    assert [item["sort_order"] for item in items] == [0, 1]
    assert [item["body"] for item in items] == [
        "Entry confirmation",
        "Exit near resistance",
    ]
    assert all(item["id"] for item in items)

    fetched = await client.get(
        f"/api/uploads/{asset['id']}/annotations",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["items"] == items


@pytest.mark.anyio
async def test_replacing_annotations_removes_old_items_and_reorders(client):
    headers = await _register(client, "replace-annotations@example.com")
    asset = await _upload_image(client, headers)
    url = f"/api/uploads/{asset['id']}/annotations"

    await client.put(
        url,
        headers=headers,
        json={
            "items": [
                {"x_ratio": 0.1, "y_ratio": 0.2, "body": "First"},
                {"x_ratio": 0.3, "y_ratio": 0.4, "body": "Second"},
            ],
        },
    )
    replaced = await client.put(
        url,
        headers=headers,
        json={"items": [{"x_ratio": 0.6, "y_ratio": 0.7, "body": "Only"}]},
    )

    assert replaced.status_code == 200
    items = replaced.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["body"] == "Only"
    assert items[0]["sort_order"] == 0


@pytest.mark.anyio
async def test_annotations_are_scoped_to_asset_owner(client):
    owner_headers = await _register(client, "annotation-owner@example.com")
    other_headers = await _register(client, "annotation-other@example.com")
    asset = await _upload_image(client, owner_headers)
    url = f"/api/uploads/{asset['id']}/annotations"

    fetched = await client.get(url, headers=other_headers)
    assert fetched.status_code == 404

    saved = await client.put(
        url,
        headers=other_headers,
        json={"items": [{"x_ratio": 0.5, "y_ratio": 0.5, "body": "No access"}]},
    )
    assert saved.status_code == 404


@pytest.mark.anyio
async def test_annotations_reject_non_image_assets(client):
    headers = await _register(client, "annotation-file@example.com")
    upload = await client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    asset_id = upload.json()["data"]["id"]

    response = await client.put(
        f"/api/uploads/{asset_id}/annotations",
        headers=headers,
        json={"items": [{"x_ratio": 0.5, "y_ratio": 0.5, "body": "Not an image"}]},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400
