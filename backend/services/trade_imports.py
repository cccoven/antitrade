"""Reviewable, deterministic trade import drafts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models import TradeImportBatch, TradeImportRow
from services.instruments import FUTURES_SPECS
from services.journal import JournalService
from services.recognition import parse_file
from services.uploads import UploadService

UTC = timezone.utc
MAX_IMPORT_ROWS = 2000

FIELD_ALIASES = {
    "symbol": {"symbol", "ticker", "instrument", "contract", "品种", "合约", "代码"},
    "direction": {"direction", "position", "方向"},
    "side": {"side", "action", "buy_sell", "买卖"},
    "open_price": {"open_price", "entry_price", "entry", "开仓价", "入场价"},
    "close_price": {"close_price", "exit_price", "exit", "平仓价", "离场价"},
    "price": {"price", "fill_price", "成交价"},
    "quantity": {"quantity", "qty", "size", "filled", "数量", "成交量"},
    "open_time": {"open_time", "entry_time", "opened_at", "开仓时间"},
    "close_time": {"close_time", "exit_time", "closed_at", "平仓时间"},
    "executed_at": {"executed_at", "fill_time", "trade_time", "time", "成交时间"},
    "fees": {"fees", "fee", "commission", "手续费", "佣金"},
    "pnl": {"pnl", "profit", "realized_pnl", "盈亏", "收益"},
    "external_id": {"external_id", "trade_id", "order_id", "fill_id", "成交编号"},
    "account_ref": {"account", "account_id", "账户"},
    "currency": {"currency", "币种"},
}


def _batch_dict(row: TradeImportBatch, rows: list[TradeImportRow] | None = None) -> dict:
    data = {
        "id": row.id,
        "asset_id": row.asset_id,
        "source_kind": row.source_kind,
        "source_name": row.source_name,
        "status": row.status,
        "mapping": row.mapping or {},
        "summary": row.summary or {},
        "error_code": row.error_code,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "committed_at": row.committed_at,
    }
    if rows is not None:
        data["rows"] = [{
            "id": item.id,
            "row_number": item.row_number,
            "record_kind": item.record_kind,
            "status": item.status,
            "raw_data": item.raw_data or {},
            "normalized_data": item.normalized_data or {},
            "issues": item.issues or [],
            "fingerprint": item.fingerprint,
            "trade_id": item.trade_id,
        } for item in rows]
    return data


def _clean_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    return value


def _number(value, field: str, issues: list[dict], *, required: bool = False):
    if value in (None, ""):
        if required:
            issues.append({"code": f"missing_{field}", "severity": "error"})
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        issues.append({"code": f"invalid_{field}", "severity": "error"})
        return None
    if not math.isfinite(number):
        issues.append({"code": f"invalid_{field}", "severity": "error"})
        return None
    return number


def _timestamp(value, field: str, issues: list[dict], timezone_name: str | None):
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = pd.to_datetime(value).to_pydatetime()
        except Exception:
            issues.append({"code": f"invalid_{field}", "severity": "error"})
            return None
    if parsed.tzinfo is None:
        if not timezone_name:
            issues.append({"code": f"ambiguous_{field}_timezone", "severity": "warning"})
            parsed = parsed.replace(tzinfo=UTC)
        else:
            try:
                parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
            except ZoneInfoNotFoundError:
                issues.append({"code": "invalid_timezone", "severity": "error"})
                return None
    return parsed.astimezone(UTC).isoformat()


def _direction(value) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"long", "buy", "b", "多", "买", "买入"}:
        return "long"
    if text in {"short", "sell", "s", "空", "卖", "卖出"}:
        return "short"
    return None


def _side(value) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"buy", "b", "long", "买", "买入"}:
        return "buy"
    if text in {"sell", "s", "short", "卖", "卖出"}:
        return "sell"
    return None


def _auto_mapping(columns: list[str]) -> dict[str, str]:
    lowered = {str(column).strip().lower(): str(column) for column in columns}
    mapping: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lowered:
                mapping[field] = lowered[alias.lower()]
                break
    return mapping


def _fingerprint(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_row(raw: dict, mapping: dict[str, str], row_number: int):
    value = lambda field: _clean_value(raw.get(mapping.get(field, "")))
    timezone_name = str(mapping.get("__timezone") or "").strip() or None
    is_fill = "price" in mapping and "side" in mapping
    issues: list[dict] = []
    symbol = str(value("symbol") or "").strip().upper()
    if not symbol:
        issues.append({"code": "missing_symbol", "severity": "error"})

    if is_fill:
        side = _side(value("side"))
        if side is None:
            issues.append({"code": "invalid_side", "severity": "error"})
        normalized = {
            "source": "file_import",
            "account_ref": str(value("account_ref") or ""),
            "external_id": str(value("external_id") or ""),
            "symbol": symbol,
            "side": side,
            "quantity": _number(value("quantity"), "quantity", issues, required=True),
            "price": _number(value("price"), "price", issues, required=True),
            "executed_at": _timestamp(
                value("executed_at"), "executed_at", issues, timezone_name,
            ),
            "fee": _number(value("fees"), "fees", issues) or 0,
            "currency": str(value("currency") or ""),
        }
        if normalized["executed_at"] is None:
            issues.append({"code": "missing_executed_at", "severity": "error"})
        kind = "fill"
    else:
        direction = _direction(value("direction"))
        if direction is None:
            issues.append({"code": "invalid_direction", "severity": "error"})
        normalized = {
            "symbol": symbol,
            "direction": direction,
            "open_price": _number(value("open_price"), "open_price", issues),
            "close_price": _number(value("close_price"), "close_price", issues),
            "quantity": _number(value("quantity"), "quantity", issues),
            "open_time": _timestamp(value("open_time"), "open_time", issues, timezone_name),
            "close_time": _timestamp(value("close_time"), "close_time", issues, timezone_name),
            "fees": _number(value("fees"), "fees", issues) or 0,
            "pnl": _number(value("pnl"), "pnl", issues),
            "source": "file_import",
        }
        kind = "trade"

    status = "invalid" if any(item["severity"] == "error" for item in issues) else (
        "warning" if issues else "valid"
    )
    return {
        "row_number": row_number,
        "record_kind": kind,
        "status": status,
        "raw_data": {str(key): _clean_value(value) for key, value in raw.items()},
        "normalized_data": normalized,
        "issues": issues,
        "fingerprint": _fingerprint(normalized) if status != "invalid" else None,
    }


def _read_structured(path: Path, kind: str) -> list[dict]:
    if kind == "csv":
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        return [dict(row) for row in csv.DictReader(io.StringIO(text))]
    if kind == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("trades", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("invalid_import_shape")
        return [dict(row) for row in rows if isinstance(row, dict)]
    if kind == "xlsx":
        frame = pd.read_excel(path)
        return frame.to_dict(orient="records")
    raise ValueError("unsupported_import_type")


def _summary(rows: list[TradeImportRow] | list[dict]) -> dict:
    counts = defaultdict(int)
    for row in rows:
        status = row.status if isinstance(row, TradeImportRow) else row["status"]
        counts[status] += 1
    return {
        "total": len(rows),
        "valid": counts["valid"],
        "warning": counts["warning"],
        "invalid": counts["invalid"],
        "duplicate": counts["duplicate"],
        "committed": counts["committed"],
    }


def _point_value(symbol: str) -> float:
    compact = symbol.upper().replace("/", "").replace("-", "")
    return float(FUTURES_SPECS.get(compact, {}).get("point_value", 1.0))


def _assemble_fills(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("account_ref", ""), row["symbol"])].append(row)
    trades: list[dict] = []
    for (_, symbol), fills in grouped.items():
        fills.sort(key=lambda item: item["executed_at"])
        position = 0.0
        average = 0.0
        opened_at = None
        accumulated_fees = 0.0
        for fill in fills:
            delta = float(fill["quantity"]) * (1 if fill["side"] == "buy" else -1)
            price = float(fill["price"])
            fee = float(fill.get("fee") or 0)
            if position == 0 or position * delta > 0:
                new_abs = abs(position) + abs(delta)
                average = (
                    (average * abs(position) + price * abs(delta)) / new_abs
                    if new_abs else price
                )
                position += delta
                opened_at = opened_at or fill["executed_at"]
                accumulated_fees += fee
                continue

            close_quantity = min(abs(position), abs(delta))
            direction = "long" if position > 0 else "short"
            pnl_points = price - average if position > 0 else average - price
            allocated_fee = accumulated_fees + fee
            trades.append({
                "symbol": symbol,
                "direction": direction,
                "open_price": average,
                "close_price": price,
                "quantity": close_quantity,
                "open_time": opened_at,
                "close_time": fill["executed_at"],
                "fees": allocated_fee,
                "pnl": pnl_points * close_quantity * _point_value(symbol) - allocated_fee,
                "source": "file_import",
            })
            remaining = position + delta
            if remaining == 0:
                position = 0
                average = 0
                opened_at = None
                accumulated_fees = 0
            elif position * remaining > 0:
                position = remaining
                accumulated_fees = 0
            else:
                position = remaining
                average = price
                opened_at = fill["executed_at"]
                accumulated_fees = 0
        if position:
            trades.append({
                "symbol": symbol,
                "direction": "long" if position > 0 else "short",
                "open_price": average,
                "close_price": None,
                "quantity": abs(position),
                "open_time": opened_at,
                "close_time": None,
                "fees": accumulated_fees,
                "pnl": None,
                "source": "file_import",
            })
    return trades


class TradeImportModule:
    def __init__(self, session: Session):
        self.session = session

    async def prepare_import(
        self, user_id: str, asset_id: str, source_hint: str | None = None,
    ) -> dict:
        asset = UploadService(self.session).get_asset(asset_id, user_id)
        if asset is None:
            raise ValueError("import_asset_not_found")
        kind = source_hint or self._source_kind(asset.mime_type, asset.original_name or "")
        now = datetime.now(UTC).isoformat()
        batch = TradeImportBatch(
            id=str(uuid4()), user_id=user_id, asset_id=asset_id,
            source_kind=kind, source_name=asset.original_name or "",
            status="preparing", mapping={}, summary={}, error_code=None,
            created_at=now, updated_at=now, committed_at=None,
        )
        self.session.add(batch)
        self.session.commit()
        try:
            if kind == "image":
                parsed = await parse_file(
                    Path(asset.file_path).read_bytes(),
                    asset.mime_type,
                    asset.original_name or "",
                )
                raw_rows = parsed.get("trades", [])
                mapping = {
                    field: field for field in (
                        "symbol", "direction", "open_price", "close_price",
                        "quantity", "open_time", "close_time", "fees", "pnl",
                    )
                }
            else:
                raw_rows = _read_structured(Path(asset.file_path), kind)
                columns = list(raw_rows[0].keys()) if raw_rows else []
                mapping = _auto_mapping(columns)
            if len(raw_rows) > MAX_IMPORT_ROWS:
                raise ValueError("import_too_many_rows")
            batch.mapping = mapping
            self._replace_rows(batch, raw_rows, mapping)
            return self.get_import(user_id, batch.id)  # type: ignore[return-value]
        except Exception:
            batch.status = "failed"
            batch.error_code = "import_prepare_failed"
            batch.updated_at = datetime.now(UTC).isoformat()
            self.session.commit()
            raise

    def revise_import(
        self, user_id: str, batch_id: str, mapping: dict[str, str],
    ) -> dict | None:
        batch = self._get_batch(user_id, batch_id)
        if batch is None:
            return None
        if batch.status in {"committed", "cancelled"}:
            raise ValueError("import_not_editable")
        asset = UploadService(self.session).get_asset(batch.asset_id, user_id)
        if asset is None:
            raise ValueError("import_asset_not_found")
        if batch.source_kind == "image":
            raise ValueError("image_mapping_not_editable")
        raw_rows = _read_structured(Path(asset.file_path), batch.source_kind)
        batch.mapping = mapping
        self._replace_rows(batch, raw_rows, mapping)
        return self.get_import(user_id, batch_id)

    def get_import(self, user_id: str, batch_id: str) -> dict | None:
        batch = self._get_batch(user_id, batch_id)
        if batch is None:
            return None
        rows = self.session.execute(
            select(TradeImportRow)
            .where(TradeImportRow.batch_id == batch.id)
            .order_by(TradeImportRow.row_number)
        ).scalars().all()
        return _batch_dict(batch, rows)

    def cancel_import(self, user_id: str, batch_id: str) -> dict | None:
        batch = self._get_batch(user_id, batch_id)
        if batch is None:
            return None
        if batch.status == "committed":
            raise ValueError("import_already_committed")
        batch.status = "cancelled"
        batch.updated_at = datetime.now(UTC).isoformat()
        self.session.commit()
        return _batch_dict(batch)

    def commit_import(self, user_id: str, batch_id: str) -> dict | None:
        batch = self._get_batch(user_id, batch_id)
        if batch is None:
            return None
        if batch.status == "committed":
            return self.get_import(user_id, batch_id)
        if batch.status != "ready":
            raise ValueError("import_not_ready")
        rows = self.session.execute(
            select(TradeImportRow)
            .where(
                TradeImportRow.batch_id == batch.id,
                TradeImportRow.status.in_(("valid", "warning")),
            )
            .order_by(TradeImportRow.row_number)
        ).scalars().all()
        direct = [
            dict(row.normalized_data) for row in rows if row.record_kind == "trade"
        ]
        fills = [
            dict(row.normalized_data) for row in rows if row.record_kind == "fill"
        ]
        trades = direct + _assemble_fills(fills)
        if not trades:
            raise ValueError("import_has_no_valid_trades")
        batch.status = "committing"
        try:
            created = JournalService(self.session).batch_create_trades(
                trades, user_id, _commit=False,
            )
            direct_index = 0
            for row in rows:
                row.status = "committed"
                if row.record_kind == "trade":
                    row.trade_id = created[direct_index]["id"]
                    direct_index += 1
                row.updated_at = datetime.now(UTC).isoformat()
            batch.status = "committed"
            batch.committed_at = datetime.now(UTC).isoformat()
            batch.updated_at = batch.committed_at
            batch.summary = {
                **(batch.summary or {}),
                "created_trades": len(created),
            }
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self.get_import(user_id, batch_id)

    def _replace_rows(
        self, batch: TradeImportBatch, raw_rows: list[dict], mapping: dict[str, str],
    ) -> None:
        self.session.execute(
            delete(TradeImportRow).where(TradeImportRow.batch_id == batch.id)
        )
        normalized_rows = [
            _normalize_row(raw, mapping, index)
            for index, raw in enumerate(raw_rows, start=1)
        ]
        seen: set[str] = set()
        committed = set(
            self.session.execute(
                select(TradeImportRow.fingerprint).where(
                    TradeImportRow.status == "committed",
                    TradeImportRow.fingerprint.isnot(None),
                )
            ).scalars().all()
        )
        now = datetime.now(UTC).isoformat()
        stored: list[TradeImportRow] = []
        for item in normalized_rows:
            fingerprint = item["fingerprint"]
            if fingerprint and (fingerprint in seen or fingerprint in committed):
                item["status"] = "duplicate"
                item["issues"].append({"code": "duplicate_record", "severity": "warning"})
            if fingerprint:
                seen.add(fingerprint)
            row = TradeImportRow(
                id=str(uuid4()), batch_id=batch.id, created_at=now, updated_at=now,
                **item,
            )
            self.session.add(row)
            stored.append(row)
        self.session.flush()
        batch.summary = _summary(stored)
        batch.status = (
            "ready"
            if stored and not any(row.status == "invalid" for row in stored)
            else "needs_review"
        )
        batch.error_code = None
        batch.updated_at = now
        self.session.commit()

    def _get_batch(self, user_id: str, batch_id: str) -> TradeImportBatch | None:
        return self.session.execute(
            select(TradeImportBatch).where(
                TradeImportBatch.id == batch_id,
                TradeImportBatch.user_id == user_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def _source_kind(mime_type: str, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if mime_type.startswith("image/"):
            return "image"
        if mime_type == "text/csv" or suffix == ".csv":
            return "csv"
        if mime_type == "application/json" or suffix == ".json":
            return "json"
        if suffix == ".xlsx" or "spreadsheetml" in mime_type:
            return "xlsx"
        raise ValueError("unsupported_import_type")
