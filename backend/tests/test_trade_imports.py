import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from models import Trade, UploadedAsset
from services.trade_imports import TradeImportModule


NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc).isoformat()


def _asset(db, user_id, tmp_path, content, name="trades.csv", mime="text/csv"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    row = UploadedAsset(
        id=str(uuid4()), user_id=user_id, file_path=str(path),
        original_name=name, mime_type=mime, width=None, height=None,
        size_bytes=path.stat().st_size, created_at=NOW,
    )
    db.add(row)
    db.commit()
    return row


def test_prepare_known_csv_and_commit_is_idempotent(db, user_id, tmp_path):
    asset = _asset(
        db, user_id, tmp_path,
        "symbol,direction,open_price,close_price,quantity,open_time,close_time,fees,pnl\n"
        "AAPL,long,200,210,2,2026-07-22T10:00:00Z,2026-07-22T12:00:00Z,1,19\n",
    )
    module = TradeImportModule(db)
    draft = asyncio.run(module.prepare_import(user_id, asset.id))
    assert draft["status"] == "ready"
    assert draft["summary"]["valid"] == 1

    committed = module.commit_import(user_id, draft["id"])
    assert committed["status"] == "committed"
    assert committed["summary"]["created_trades"] == 1
    assert module.commit_import(user_id, draft["id"])["summary"]["created_trades"] == 1
    assert db.query(Trade).filter(Trade.user_id == user_id).count() == 1


def test_fill_rows_assemble_partial_close(db, user_id, tmp_path):
    asset = _asset(
        db, user_id, tmp_path,
        "symbol,side,price,quantity,executed_at,fees\n"
        "MNQ,buy,22000,2,2026-07-22T10:00:00Z,1\n"
        "MNQ,sell,22010,1,2026-07-22T11:00:00Z,1\n"
        "MNQ,sell,22020,1,2026-07-22T12:00:00Z,1\n",
    )
    module = TradeImportModule(db)
    draft = asyncio.run(module.prepare_import(user_id, asset.id))
    assert draft["status"] == "ready"
    committed = module.commit_import(user_id, draft["id"])
    assert committed["summary"]["created_trades"] == 2
    trades = db.query(Trade).filter(Trade.user_id == user_id).all()
    assert [trade.pnl for trade in trades] == [18.0, 39.0]


def test_naive_timestamp_requires_review_warning(db, user_id, tmp_path):
    asset = _asset(
        db, user_id, tmp_path,
        "symbol,direction,open_time\nAAPL,long,2026-07-22 10:00:00\n",
    )
    module = TradeImportModule(db)
    draft = asyncio.run(module.prepare_import(user_id, asset.id))
    assert draft["status"] == "ready"
    assert draft["summary"]["warning"] == 1
    assert draft["rows"][0]["issues"][0]["code"] == "ambiguous_open_time_timezone"


def test_user_cannot_read_other_users_import(db, user_id, tmp_path):
    asset = _asset(db, user_id, tmp_path, "symbol,direction\nAAPL,long\n")
    module = TradeImportModule(db)
    draft = asyncio.run(module.prepare_import(user_id, asset.id))
    assert module.get_import("someone-else", draft["id"]) is None
