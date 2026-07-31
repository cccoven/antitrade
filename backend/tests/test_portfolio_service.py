import pytest
from models import User
from datetime import datetime, timezone
from services.portfolio import EntryService, PortfoliosService


@pytest.fixture
def u1(db):
    """Insert a user with id 'u1' into the transactional session."""
    db.add(User(id="u1", email="u1@test.com", password="x", name="",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    return "u1"


@pytest.fixture
def portfolio_id(db, u1):
    p = PortfoliosService(db).create(user_id="u1", name="CNY 组合", currency="CNY")
    return p["id"]


def test_create_entry_returns_expected_shape(db, portfolio_id, u1):
    svc = EntryService(db)
    entry = svc.create(portfolio_id=portfolio_id, user_id="u1", name="a", category="现金", amount=100.0)
    assert entry["name"] == "a"
    assert entry["portfolio_id"] == portfolio_id
    assert "currency" not in entry


def test_create_entry_rejects_negative_amount(db, portfolio_id, u1):
    svc = EntryService(db)
    with pytest.raises(ValueError):
        svc.create(portfolio_id=portfolio_id, user_id="u1", name="a", category="现金", amount=-5)


def test_create_entry_rejects_wrong_user(db, portfolio_id, u1):
    svc = EntryService(db)
    with pytest.raises(PermissionError):
        svc.create(portfolio_id=portfolio_id, user_id="other_user", name="a", category="现金", amount=10)


def test_list_entries_scoped_to_portfolio(db, u1):
    ps = PortfoliosService(db)
    p1 = ps.create(user_id="u1", name="A", currency="CNY")
    p2 = ps.create(user_id="u1", name="B", currency="USD")
    es = EntryService(db)
    es.create(portfolio_id=p1["id"], user_id="u1", name="in-A", category="现金", amount=1)
    es.create(portfolio_id=p2["id"], user_id="u1", name="in-B", category="现金", amount=2)
    assert [e["name"] for e in es.list(portfolio_id=p1["id"], user_id="u1")] == ["in-A"]
    assert [e["name"] for e in es.list(portfolio_id=p2["id"], user_id="u1")] == ["in-B"]


def test_update_and_delete_entry_checks_portfolio_owner(db, portfolio_id, u1):
    es = EntryService(db)
    entry = es.create(portfolio_id=portfolio_id, user_id="u1", name="a", category="现金", amount=100)

    updated = es.update(entry["id"], user_id="u1", amount=200)
    assert updated["amount"] == 200

    with pytest.raises(PermissionError):
        es.update(entry["id"], user_id="other_user", amount=999)

    with pytest.raises(PermissionError):
        es.delete(entry["id"], user_id="other_user")

    assert es.delete(entry["id"], user_id="u1") is True


def test_batch_delete_only_touches_own_entries(db, u1):
    ps = PortfoliosService(db)
    p_self = ps.create(user_id="u1", name="Self", currency="CNY")
    p_other = ps.create(user_id="other_user", name="Other", currency="CNY")
    es = EntryService(db)
    e1 = es.create(portfolio_id=p_self["id"], user_id="u1", name="e1", category="现金", amount=1)
    e2 = es.create(portfolio_id=p_other["id"], user_id="other_user", name="e2", category="现金", amount=2)

    deleted = es.batch_delete([e1["id"], e2["id"]], user_id="u1")
    assert deleted == 1
    assert es.list(portfolio_id=p_other["id"], user_id="other_user")[0]["name"] == "e2"
