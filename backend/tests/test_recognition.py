"""Tests for the recognition service and router."""

import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from auth_dependency import get_current_user
from db import get_db
from main import app
from models import BillingAccount


@pytest.fixture(autouse=True)
def pro_dependencies(db, user_id):
    now = datetime.now(timezone.utc)
    db.add(BillingAccount(
        user_id=user_id,
        plan="pro",
        status="active",
        current_period_start=now.isoformat(),
        current_period_end=(now + timedelta(days=30)).isoformat(),
        cancel_at_period_end=False,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    ))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user_id
    yield
    app.dependency_overrides.clear()


def test_parse_returns_demo_trades(monkeypatch):
    """Upload a CSV file and verify the demo provider returns parsed trades."""
    monkeypatch.setattr("config.LLM_PROVIDER", "demo")

    csv_content = b"symbol,direction,open_price,close_price\nXAUUSD,long,2340.5,2365.0\n"
    with TestClient(app) as client:
        response = client.post(
            "/api/recognition/parse",
            files={"file": ("trades.csv", io.BytesIO(csv_content), "text/csv")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    data = payload["data"]
    assert "trades" in data
    assert len(data["trades"]) > 0
    assert data["trades"][0]["symbol"] == "XAUUSD"


def test_parse_rejects_unsupported_type(monkeypatch):
    """Upload a PDF file and verify it is rejected with 400."""
    monkeypatch.setattr("config.LLM_PROVIDER", "demo")

    pdf_content = b"%PDF-1.4 fake pdf content"
    with TestClient(app) as client:
        response = client.post(
            "/api/recognition/parse",
            files={"file": ("report.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert payload["data"] is None


def test_parse_requires_pro_without_masking_billing_error(db, user_id):
    db.query(BillingAccount).filter(BillingAccount.user_id == user_id).delete()
    db.commit()

    with TestClient(app) as client:
        response = client.post(
            "/api/recognition/parse",
            files={"file": ("trades.csv", io.BytesIO(b"symbol,direction\n"), "text/csv")},
        )

    assert response.status_code == 402
    assert response.json()["data"]["feature"] == "recognition.parse"
