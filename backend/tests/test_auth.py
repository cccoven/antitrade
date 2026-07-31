"""Tests for auth service, router, and dependency."""

from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from db import get_db
from models import (
    BillingAccount,
    ChatConversation,
    ChatMessage,
    ChatMessageAttachment,
    FeedBookmark,
    FeedItem,
    MfaLoginChallenge,
    MfaRecoveryCode,
    Portfolio,
    PortfolioEntry,
    Trade,
    TradeImage,
    TradeRuleResult,
    UploadedAsset,
    User,
    UserMfaFactor,
    UserOAuthIdentity,
)
from services.google_auth import GoogleAuthError


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


async def _register(client: AsyncClient, email="test@example.com", password="secret123", name=None):
    payload = {"email": email, "password": password}
    if name is not None:
        payload["name"] = name
    return await client.post("/api/auth/register", json=payload)


async def _login(client: AsyncClient, email="test@example.com", password="secret123"):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def _google_login(client: AsyncClient, credential="google-id-token"):
    return await client.post("/api/auth/google", json={"credential": credential})


async def _enable_mfa(
    client: AsyncClient,
    token: str,
    password: str = "secret123",
):
    headers = {"Authorization": f"Bearer {token}", "Accept-Language": "en"}
    start_resp = await client.post(
        "/api/auth/mfa/setup/start",
        json={"current_password": password},
        headers=headers,
    )
    assert start_resp.status_code == 200
    secret = start_resp.json()["data"]["manual_key"]
    setup_code = pyotp.TOTP(secret).at(
        datetime.now(timezone.utc) - timedelta(seconds=30)
    )
    confirm_resp = await client.post(
        "/api/auth/mfa/setup/confirm",
        json={"code": setup_code},
        headers=headers,
    )
    assert confirm_resp.status_code == 200
    return secret, confirm_resp.json()["data"]


@pytest.mark.anyio
async def test_register(client: AsyncClient):
    resp = await _register(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "token" in body["data"]
    assert body["data"]["user"]["email"] == "test@example.com"
    assert body["data"]["user"]["name"] == "test"  # derived from email


@pytest.mark.anyio
async def test_register_with_name(client: AsyncClient):
    resp = await _register(client, email="named@example.com", name="Alice")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["user"]["name"] == "Alice"


@pytest.mark.anyio
async def test_register_duplicate_email(client: AsyncClient):
    await _register(client, email="dup@example.com")
    resp = await _register(client, email="dup@example.com")
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400
    assert "already registered" in body["message"].lower()


@pytest.mark.anyio
async def test_register_invalid_email(client: AsyncClient):
    resp = await _register(client, email="not-an-email")
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400
    assert "email" in body["message"].lower()


@pytest.mark.anyio
async def test_register_short_password(client: AsyncClient):
    resp = await _register(client, email="short@example.com", password="12345")
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400
    assert "6 characters" in body["message"].lower()


@pytest.mark.anyio
async def test_login(client: AsyncClient):
    await _register(client, email="login@example.com", password="mypassword")
    resp = await _login(client, email="login@example.com", password="mypassword")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["mfa_required"] is False
    assert "token" in body["data"]
    assert body["data"]["user"]["email"] == "login@example.com"


@pytest.mark.anyio
async def test_login_wrong_password(client: AsyncClient):
    await _register(client, email="wrong@example.com", password="correct")
    resp = await _login(client, email="wrong@example.com", password="incorrect")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 401
    assert "invalid" in body["message"].lower()


@pytest.mark.anyio
async def test_google_login_creates_and_reuses_user(client: AsyncClient, db, monkeypatch):
    monkeypatch.setattr(
        "services.auth.verify_google_id_token",
        lambda _credential: {
            "sub": "google-subject-1",
            "email": "google-user@example.com",
            "name": "Google User",
            "hosted_domain": "",
        },
    )

    first = await _google_login(client)
    second = await _google_login(client)

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["mfa_required"] is False
    assert first_data["user"] == second_data["user"]
    assert first_data["user"]["name"] == "Google User"
    assert first_data["user"]["has_password"] is False
    users = db.execute(
        select(User).where(User.email == "google-user@example.com")
    ).scalars().all()
    assert len(users) == 1
    identity = db.execute(select(UserOAuthIdentity)).scalar_one()
    assert identity.subject == "google-subject-1"
    assert identity.user_id == first_data["user"]["id"]


@pytest.mark.anyio
async def test_google_login_links_existing_verified_email(client: AsyncClient, db, monkeypatch):
    registered = await _register(
        client,
        email="linked@example.com",
        password="secret123",
        name="Existing Name",
    )
    user_id = registered.json()["data"]["user"]["id"]
    monkeypatch.setattr(
        "services.auth.verify_google_id_token",
        lambda _credential: {
            "sub": "google-linked-subject",
            "email": "linked@example.com",
            "name": "Google Name",
            "hosted_domain": "example.com",
        },
    )

    response = await _google_login(client)

    assert response.status_code == 200
    assert response.json()["data"]["user"]["id"] == user_id
    assert response.json()["data"]["user"]["name"] == "Existing Name"
    identity = db.execute(select(UserOAuthIdentity)).scalar_one()
    assert identity.user_id == user_id


@pytest.mark.anyio
async def test_google_user_can_set_local_password(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        "services.auth.verify_google_id_token",
        lambda _credential: {
            "sub": "google-password-subject",
            "email": "google-password@example.com",
            "name": "Google Password",
            "hosted_domain": "",
        },
    )
    google_response = await _google_login(client)
    token = google_response.json()["data"]["token"]

    password_response = await client.put(
        "/api/auth/password",
        json={"new_password": "newsecret456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert password_response.status_code == 200
    assert password_response.json()["data"]["user"]["has_password"] is True
    local_login = await _login(
        client,
        email="google-password@example.com",
        password="newsecret456",
    )
    assert local_login.status_code == 200


@pytest.mark.anyio
async def test_google_login_rejects_invalid_credential(client: AsyncClient, monkeypatch):
    def reject(_credential):
        raise GoogleAuthError("Invalid Google credential")

    monkeypatch.setattr("services.auth.verify_google_id_token", reject)

    response = await _google_login(client, credential="invalid")

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid Google credential"


@pytest.mark.anyio
async def test_google_config_reports_runtime_client_id(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        "routers.auth.GOOGLE_CLIENT_ID",
        "client.apps.googleusercontent.com",
    )

    response = await client.get("/api/auth/google/config")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "enabled": True,
        "client_id": "client.apps.googleusercontent.com",
    }


@pytest.mark.anyio
async def test_get_me_with_token(client: AsyncClient):
    reg_resp = await _register(client, email="me@example.com")
    token = reg_resp.json()["data"]["token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["email"] == "me@example.com"


@pytest.mark.anyio
async def test_get_me_without_token(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_update_profile(client: AsyncClient):
    reg_resp = await _register(client, email="profile@example.com")
    token = reg_resp.json()["data"]["token"]

    resp = await client.put(
        "/api/auth/profile",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "New Name"


@pytest.mark.anyio
async def test_change_password_replaces_login_password(client: AsyncClient):
    reg_resp = await _register(client, email="password@example.com", password="secret123")
    token = reg_resp.json()["data"]["token"]

    resp = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "newsecret456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    replacement_token = resp.json()["data"]["token"]
    assert replacement_token != token
    assert (await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )).status_code == 401
    assert (await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {replacement_token}"},
    )).status_code == 200
    assert (await _login(client, email="password@example.com", password="secret123")).status_code == 401
    assert (await _login(client, email="password@example.com", password="newsecret456")).status_code == 200


@pytest.mark.anyio
async def test_change_password_rejects_wrong_current_password(client: AsyncClient):
    reg_resp = await _register(client, email="wrong-current@example.com", password="secret123")
    token = reg_resp.json()["data"]["token"]

    resp = await client.put(
        "/api/auth/password",
        json={"current_password": "incorrect", "new_password": "newsecret456"},
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "en"},
    )

    assert resp.status_code == 400
    assert resp.json()["message"] == "The current password is incorrect."


@pytest.mark.anyio
async def test_change_password_rejects_short_or_unchanged_password(client: AsyncClient):
    reg_resp = await _register(client, email="password-validation@example.com", password="secret123")
    token = reg_resp.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}", "Accept-Language": "en"}

    short_resp = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "12345"},
        headers=headers,
    )
    unchanged_resp = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "secret123"},
        headers=headers,
    )

    assert short_resp.status_code == 400
    assert short_resp.json()["message"] == "The new password must be at least 6 characters."
    assert unchanged_resp.status_code == 400
    assert unchanged_resp.json()["message"] == "The new password must be different from the current password."


@pytest.mark.anyio
async def test_change_password_requires_authentication(client: AsyncClient):
    resp = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "newsecret456"},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_mfa_login_does_not_issue_token_before_second_factor(
    client: AsyncClient,
):
    reg_resp = await _register(
        client,
        email="mfa-login@example.com",
        password="secret123",
    )
    original_token = reg_resp.json()["data"]["token"]
    secret, enrollment = await _enable_mfa(client, original_token)

    assert len(enrollment["recovery_codes"]) == 10
    replacement_token = enrollment["token"]
    assert (await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {original_token}"},
    )).status_code == 401
    assert (await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {replacement_token}"},
    )).status_code == 200

    login_resp = await _login(
        client,
        email="mfa-login@example.com",
        password="secret123",
    )
    login_data = login_resp.json()["data"]
    assert login_data["mfa_required"] is True
    assert "token" not in login_data

    verify_resp = await client.post(
        "/api/auth/mfa/login/verify",
        json={
            "challenge_token": login_data["challenge"]["token"],
            "code": pyotp.TOTP(secret).now(),
        },
        headers={"Accept-Language": "en"},
    )
    assert verify_resp.status_code == 200
    assert "token" in verify_resp.json()["data"]


@pytest.mark.anyio
async def test_mfa_recovery_code_is_single_use_through_api(client: AsyncClient):
    reg_resp = await _register(
        client,
        email="mfa-recovery@example.com",
        password="secret123",
    )
    _, enrollment = await _enable_mfa(
        client,
        reg_resp.json()["data"]["token"],
    )
    recovery_code = enrollment["recovery_codes"][0]

    first_login = await _login(
        client,
        email="mfa-recovery@example.com",
        password="secret123",
    )
    first_challenge = first_login.json()["data"]["challenge"]["token"]
    first_verify = await client.post(
        "/api/auth/mfa/login/verify",
        json={"challenge_token": first_challenge, "code": recovery_code},
    )
    assert first_verify.status_code == 200

    second_login = await _login(
        client,
        email="mfa-recovery@example.com",
        password="secret123",
    )
    second_challenge = second_login.json()["data"]["challenge"]["token"]
    second_verify = await client.post(
        "/api/auth/mfa/login/verify",
        json={"challenge_token": second_challenge, "code": recovery_code},
        headers={"Accept-Language": "en"},
    )
    assert second_verify.status_code == 401
    assert second_verify.json()["message"] == "The verification or recovery code is invalid."


@pytest.mark.anyio
async def test_mfa_status_and_disable_flow(client: AsyncClient):
    reg_resp = await _register(
        client,
        email="mfa-disable@example.com",
        password="secret123",
    )
    _, enrollment = await _enable_mfa(
        client,
        reg_resp.json()["data"]["token"],
    )
    enabled_token = enrollment["token"]
    headers = {"Authorization": f"Bearer {enabled_token}"}

    status_resp = await client.get("/api/auth/mfa/status", headers=headers)
    assert status_resp.json()["data"]["enabled"] is True
    assert status_resp.json()["data"]["recovery_codes_remaining"] == 10

    disable_resp = await client.post(
        "/api/auth/mfa/disable",
        json={
            "current_password": "secret123",
            "code": enrollment["recovery_codes"][0],
        },
        headers=headers,
    )
    assert disable_resp.status_code == 200
    disabled_token = disable_resp.json()["data"]["token"]
    disabled_status = await client.get(
        "/api/auth/mfa/status",
        headers={"Authorization": f"Bearer {disabled_token}"},
    )
    assert disabled_status.json()["data"]["enabled"] is False

    login_resp = await _login(
        client,
        email="mfa-disable@example.com",
        password="secret123",
    )
    assert login_resp.json()["data"]["mfa_required"] is False


@pytest.mark.anyio
async def test_delete_account_rejects_wrong_password(client: AsyncClient, db):
    reg_resp = await _register(
        client,
        email="delete-wrong-password@example.com",
        password="secret123",
    )
    user_id = reg_resp.json()["data"]["user"]["id"]
    token = reg_resp.json()["data"]["token"]

    resp = await client.request(
        "DELETE",
        "/api/auth/account",
        json={"current_password": "incorrect"},
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "en"},
    )

    assert resp.status_code == 400
    assert resp.json()["message"] == "The current password is incorrect."
    assert db.get(User, user_id) is not None


@pytest.mark.anyio
async def test_delete_account_requires_active_subscription_cancellation(
    client: AsyncClient,
    db,
):
    reg_resp = await _register(
        client,
        email="subscribed-delete@example.com",
        password="secret123",
    )
    user_id = reg_resp.json()["data"]["user"]["id"]
    token = reg_resp.json()["data"]["token"]
    now = "2026-07-24T00:00:00+00:00"
    db.add(BillingAccount(
        user_id=user_id,
        stripe_customer_id="cus_delete_test",
        stripe_subscription_id="sub_delete_test",
        stripe_price_id="price_delete_test",
        plan="pro",
        status="active",
        billing_interval="month",
        cancel_at_period_end=False,
        created_at=now,
        updated_at=now,
    ))
    db.commit()

    resp = await client.request(
        "DELETE",
        "/api/auth/account",
        json={"current_password": "secret123"},
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "en"},
    )

    assert resp.status_code == 400
    assert "cancel" in resp.json()["message"].lower()
    assert db.get(User, user_id) is not None
    assert db.get(BillingAccount, user_id) is not None


@pytest.mark.anyio
async def test_delete_account_removes_user_data_and_uploads(
    client: AsyncClient,
    db,
    monkeypatch,
    tmp_path,
):
    reg_resp = await _register(
        client,
        email="delete-account@example.com",
        password="secret123",
    )
    user_id = reg_resp.json()["data"]["user"]["id"]
    token = reg_resp.json()["data"]["token"]
    _, enrollment = await _enable_mfa(client, token)
    headers = {
        "Authorization": f"Bearer {enrollment['token']}",
        "Accept-Language": "en",
    }
    now = "2026-07-24T00:00:00+00:00"

    upload_root = tmp_path / "uploads"
    user_dir = upload_root / user_id
    user_dir.mkdir(parents=True)
    upload_path = user_dir / "asset.png"
    upload_path.write_bytes(b"test")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))

    trade = Trade(
        id="delete-trade",
        user_id=user_id,
        symbol="AAPL",
        direction="long",
        created_at=now,
        updated_at=now,
    )
    asset = UploadedAsset(
        id="delete-asset",
        user_id=user_id,
        file_path=str(upload_path),
        mime_type="image/png",
        size_bytes=4,
        created_at=now,
    )
    portfolio = Portfolio(
        id="delete-portfolio",
        user_id=user_id,
        name="Primary",
        currency="USD",
        created_at=now,
        updated_at=now,
    )
    conversation = ChatConversation(
        id="delete-conversation",
        user_id=user_id,
        title="Delete me",
        created_at=now,
        updated_at=now,
    )
    feed_item = FeedItem(
        id="shared-feed-item",
        url="https://example.com/delete-account-test",
        source_key="test",
        title="Shared",
        fetched_at=now,
        category="general",
        symbols=[],
        lang="en",
    )
    db.add_all([trade, asset, portfolio, conversation, feed_item])
    db.flush()

    message = ChatMessage(
        id="delete-message",
        conversation_id=conversation.id,
        role="user",
        content="private",
        created_at=now,
    )
    db.add_all([
        TradeImage(
            id="delete-trade-image",
            trade_id=trade.id,
            asset_id=asset.id,
            created_at=now,
        ),
        TradeRuleResult(
            id="delete-rule-result",
            trade_id=trade.id,
            rule_name="Risk",
            rule_type="max_risk",
            weight="important",
            status="passed",
            created_at=now,
        ),
        PortfolioEntry(
            id="delete-entry",
            portfolio_id=portfolio.id,
            name="Cash",
            category="Cash",
            amount=100,
            created_at=now,
            updated_at=now,
        ),
        message,
        FeedBookmark(
            id="delete-bookmark",
            user_id=user_id,
            feed_item_id=feed_item.id,
            created_at=now,
        ),
    ])
    db.flush()
    db.add(ChatMessageAttachment(
        id="delete-message-attachment",
        message_id=message.id,
        asset_id=asset.id,
        created_at=now,
    ))
    db.commit()
    trade_id = trade.id
    asset_id = asset.id
    portfolio_id = portfolio.id
    conversation_id = conversation.id
    message_id = message.id
    feed_item_id = feed_item.id

    resp = await client.request(
        "DELETE",
        "/api/auth/account",
        json={"current_password": "secret123"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["data"] == {"deleted": True}
    db.expire_all()
    for model, row_id in (
        (User, user_id),
        (Trade, trade_id),
        (TradeImage, "delete-trade-image"),
        (TradeRuleResult, "delete-rule-result"),
        (UploadedAsset, asset_id),
        (Portfolio, portfolio_id),
        (PortfolioEntry, "delete-entry"),
        (ChatConversation, conversation_id),
        (ChatMessage, message_id),
        (ChatMessageAttachment, "delete-message-attachment"),
        (FeedBookmark, "delete-bookmark"),
    ):
        assert db.get(model, row_id) is None
    assert db.execute(
        select(FeedItem).where(FeedItem.id == feed_item_id)
    ).scalar_one_or_none() is not None
    for model in (UserMfaFactor, MfaRecoveryCode, MfaLoginChallenge):
        assert db.scalar(select(model.id).where(model.user_id == user_id)) is None
    assert not user_dir.exists()
    assert (await _login(
        client,
        email="delete-account@example.com",
        password="secret123",
    )).status_code == 401
