import asyncio
import calendar
import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from i18n import t
from models import (
    DailyReview,
    JournalSettings,
    Strategy,
    Trade,
    TradeImage,
    TradePlan,
    TradeRuleResult,
    TradingRule,
    UploadedAsset,
)

logger = logging.getLogger(__name__)


def _compact_symbol_expression(field):
    return func.replace(
        func.replace(func.replace(func.upper(field), "/", ""), "-", ""), "_", "",
    )


@dataclass
class DiagnosisJobEntry:
    job_id: str
    status: str
    created_at: str
    updated_at: str
    result: str | None = None
    error: str | None = None


_diagnosis_jobs: dict[str, DiagnosisJobEntry] = {}


def _trade_to_dict(row: Trade) -> dict:
    """Convert a Trade ORM object to a plain dict, JSON-decoding the tags field."""
    d = {
        "id": row.id,
        "user_id": row.user_id,
        "symbol": row.symbol,
        "series_id": row.series_id,
        "direction": row.direction,
        "position_status": row.position_status,
        "open_price": row.open_price,
        "close_price": row.close_price,
        "quantity": row.quantity,
        "open_time": row.open_time,
        "close_time": row.close_time,
        "fees": row.fees,
        "pnl": row.pnl,
        "tags": [],
        "notes": row.notes or "",
        "ai_review": row.ai_review,
        "exchange": row.exchange,
        "source": row.source,
        "strategy_id": row.strategy_id,
        "plan_id": row.plan_id,
        "target_price": row.target_price,
        "stop_loss": row.stop_loss,
        "setup_type": row.setup_type,
        "emotional_state": row.emotional_state,
        "mistakes": [],
        "confidence": row.confidence,
        "execution_quality": row.execution_quality,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if row.tags:
        try:
            d["tags"] = json.loads(row.tags)
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    if row.mistakes:
        try:
            d["mistakes"] = json.loads(row.mistakes)
        except (json.JSONDecodeError, TypeError):
            d["mistakes"] = []
    return d


class JournalService:
    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert a Trade ORM object to a plain dict, JSON-decoding the tags field."""
        return _trade_to_dict(row)

    def _trade_images(self, trade_ids: list[str], user_id: str) -> dict[str, list[dict]]:
        if not trade_ids:
            return {}

        stmt = (
            select(
                TradeImage.id,
                TradeImage.trade_id,
                TradeImage.asset_id,
                TradeImage.label,
                TradeImage.sort_order,
                TradeImage.created_at,
                UploadedAsset.original_name,
                UploadedAsset.mime_type,
                UploadedAsset.width,
                UploadedAsset.height,
            )
            .join(UploadedAsset, UploadedAsset.id == TradeImage.asset_id)
            .join(Trade, Trade.id == TradeImage.trade_id)
            .where(
                TradeImage.trade_id.in_(trade_ids),
                Trade.user_id == user_id,
                UploadedAsset.user_id == user_id,
            )
            .order_by(TradeImage.sort_order.asc(), TradeImage.created_at.asc())
        )
        rows = self.session.execute(stmt).all()

        images_by_trade: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            image = {
                "id": row.id,
                "asset_id": row.asset_id,
                "label": row.label,
                "sort_order": row.sort_order,
                "created_at": row.created_at,
                "original_name": row.original_name,
                "mime_type": row.mime_type,
                "width": row.width,
                "height": row.height,
                "url": f"/api/uploads/{row.asset_id}",
            }
            images_by_trade[row.trade_id].append(image)
        return images_by_trade

    def _attach_images(self, trades: list[dict], user_id: str) -> list[dict]:
        images_by_trade = self._trade_images([trade["id"] for trade in trades], user_id)
        for trade in trades:
            trade["images"] = images_by_trade.get(trade["id"], [])
        return trades

    def _attach_compliance(self, trades: list[dict]) -> list[dict]:
        if not trades:
            return trades
        rows = self.session.execute(
            select(TradeRuleResult)
            .where(TradeRuleResult.trade_id.in_([trade["id"] for trade in trades]))
            .order_by(TradeRuleResult.created_at.asc())
        ).scalars().all()
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row.trade_id].append({
                "rule_id": row.rule_id,
                "rule_name": row.rule_name,
                "rule_type": row.rule_type,
                "weight": row.weight,
                "status": row.status,
                "detail": row.detail,
            })
        for trade in trades:
            results = grouped.get(trade["id"], [])
            trade["compliance"] = self._compliance_summary(results)
        return trades

    def _attach_trade_details(self, trades: list[dict], user_id: str) -> list[dict]:
        return self._attach_compliance(self._attach_images(trades, user_id))

    def _validate_strategy_owned(self, strategy_id: str | None, user_id: str) -> None:
        if strategy_id is None:
            return
        row = self.session.execute(
            select(Strategy.id).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            raise PermissionError("strategy_not_found")

    def _validate_plan_owned(self, plan_id: str | None, user_id: str) -> None:
        if plan_id is None:
            return
        row = self.session.execute(
            select(TradePlan.id).where(TradePlan.id == plan_id, TradePlan.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            raise PermissionError("plan_not_found")

    def _replace_trade_images(
        self,
        trade_id: str,
        user_id: str,
        image_asset_ids: list[str] | None,
    ) -> None:
        if image_asset_ids is None:
            return

        trade = self.session.execute(
            select(Trade.id).where(Trade.id == trade_id, Trade.user_id == user_id)
        ).scalar_one_or_none()
        if trade is None:
            return

        asset_ids = list(dict.fromkeys(image_asset_ids))
        if asset_ids:
            found_ids = set(
                self.session.execute(
                    select(UploadedAsset.id).where(
                        UploadedAsset.id.in_(asset_ids),
                        UploadedAsset.user_id == user_id,
                    )
                ).scalars().all()
            )
            if found_ids != set(asset_ids):
                raise PermissionError("Invalid image asset")

        self.session.execute(
            delete(TradeImage).where(TradeImage.trade_id == trade_id)
        )
        now = datetime.now(timezone.utc).isoformat()
        for sort_order, asset_id in enumerate(asset_ids):
            self.session.add(
                TradeImage(
                    id=str(uuid4()),
                    trade_id=trade_id,
                    asset_id=asset_id,
                    label="",
                    sort_order=sort_order,
                    created_at=now,
                )
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_trade(
        self,
        symbol: str,
        direction: str,
        series_id: str | None = None,
        open_price: float | None = None,
        close_price: float | None = None,
        quantity: float | None = None,
        open_time: str | None = None,
        close_time: str | None = None,
        fees: float = 0,
        pnl: float | None = None,
        tags: list[str] | None = None,
        notes: str = "",
        source: str = "manual",
        exchange: str | None = None,
        user_id: str = "anonymous",
        image_asset_ids: list[str] | None = None,
        strategy_id: str | None = None,
        plan_id: str | None = None,
        target_price: float | None = None,
        stop_loss: float | None = None,
        setup_type: str | None = None,
        emotional_state: str | None = None,
        mistakes: list[str] | None = None,
        confidence: int | None = None,
        execution_quality: int | None = None,
        position_status: str | None = None,
        _commit: bool = True,
    ) -> dict:
        self._validate_strategy_owned(strategy_id, user_id)
        self._validate_plan_owned(plan_id, user_id)
        series_id = self._validated_or_resolved_series_id(
            series_id,
            symbol,
            exchange,
        )

        trade_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags if tags is not None else [])
        resolved_status = position_status or (
            "closed"
            if any(value is not None for value in (close_price, close_time, pnl))
            else "open"
        )
        if resolved_status not in {"open", "closed"}:
            raise ValueError("invalid_position_status")
        if resolved_status == "open" and any(
            value is not None for value in (close_price, close_time, pnl)
        ):
            raise ValueError("inconsistent_position_status")

        trade = Trade(
            id=trade_id,
            user_id=user_id,
            symbol=symbol,
            series_id=series_id,
            direction=direction,
            position_status=resolved_status,
            open_price=open_price,
            close_price=close_price,
            quantity=quantity,
            open_time=open_time,
            close_time=close_time,
            fees=fees,
            pnl=pnl,
            tags=tags_json,
            notes=notes,
            source=source,
            exchange=exchange,
            strategy_id=strategy_id,
            plan_id=plan_id,
            target_price=target_price,
            stop_loss=stop_loss,
            setup_type=setup_type,
            emotional_state=emotional_state,
            mistakes=json.dumps(mistakes or []),
            confidence=confidence,
            execution_quality=execution_quality,
            created_at=now,
            updated_at=now,
        )
        self.session.add(trade)
        self.session.flush()
        self._replace_trade_images(trade_id, user_id, image_asset_ids)
        self._replace_compliance_results(trade_id, user_id)
        if plan_id:
            self.session.execute(
                update(TradePlan)
                .where(TradePlan.id == plan_id, TradePlan.user_id == user_id)
                .values(status="converted", updated_at=now)
            )
        if _commit:
            self.session.commit()
        return self.get_trade(trade_id, user_id=user_id)  # type: ignore[return-value]

    def get_trade(self, trade_id: str, user_id: str) -> dict | None:
        row = self.session.execute(
            select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        return self._attach_trade_details([_trade_to_dict(row)], user_id)[0]

    @staticmethod
    def _build_sa_filter_clauses(
        user_id: str,
        symbol: str | None = None,
        direction: str | None = None,
        position_status: str | None = None,
        tag: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        """Return a list of SQLAlchemy WHERE conditions for Trade queries."""
        conditions = [Trade.user_id == user_id]
        if symbol is not None:
            conditions.append(Trade.symbol.ilike(f"%{symbol}%"))
        if direction is not None:
            conditions.append(Trade.direction == direction)
        if position_status is not None:
            conditions.append(Trade.position_status == position_status)
        if tag is not None:
            conditions.append(Trade.tags.like(f"%{tag}%"))
        if date_from is not None:
            conditions.append(Trade.open_time >= date_from)
        if date_to is not None:
            conditions.append(Trade.open_time <= date_to)
        return conditions

    def count_trades(
        self,
        user_id: str,
        symbol: str | None = None,
        direction: str | None = None,
        position_status: str | None = None,
        tag: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> int:
        conditions = self._build_sa_filter_clauses(
            user_id, symbol=symbol, direction=direction,
            position_status=position_status, tag=tag,
            date_from=date_from, date_to=date_to,
        )
        result = self.session.execute(
            select(func.count()).select_from(Trade).where(*conditions)
        ).scalar_one()
        return result

    def list_trades(
        self,
        user_id: str,
        symbol: str | None = None,
        direction: str | None = None,
        position_status: str | None = None,
        tag: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        conditions = self._build_sa_filter_clauses(
            user_id, symbol=symbol, direction=direction,
            position_status=position_status, tag=tag,
            date_from=date_from, date_to=date_to,
        )
        rows = self.session.execute(
            select(Trade)
            .where(*conditions)
            .order_by(Trade.open_time.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
        return self._attach_trade_details([_trade_to_dict(r) for r in rows], user_id)

    def list_trades_by_ids(self, trade_ids: list[str], user_id: str) -> list[dict]:
        """Fetch full trade rows for a list of ids, scoped to the given user."""
        if not trade_ids:
            return []
        rows = self.session.execute(
            select(Trade)
            .where(Trade.id.in_(trade_ids), Trade.user_id == user_id)
            .order_by(Trade.open_time.desc())
        ).scalars().all()
        return self._attach_trade_details([_trade_to_dict(r) for r in rows], user_id)

    def resolve_trade_ids_by_filter(
        self,
        user_id: str,
        symbol: str | None = None,
        direction: str | None = None,
        position_status: str | None = None,
        tag: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[str]:
        """Return all trade ids for this user matching the given filter."""
        conditions = self._build_sa_filter_clauses(
            user_id=user_id, symbol=symbol, direction=direction,
            position_status=position_status,
            tag=tag, date_from=date_from, date_to=date_to,
        )
        rows = self.session.execute(
            select(Trade.id).where(*conditions).order_by(Trade.open_time.desc())
        ).scalars().all()
        return list(rows)

    def update_trade(
        self,
        trade_id: str,
        user_id: str,
        image_asset_ids: list[str] | None = None,
        **fields,
    ) -> dict | None:
        if not fields and image_asset_ids is None:
            return self.get_trade(trade_id, user_id=user_id)

        if "strategy_id" in fields:
            self._validate_strategy_owned(fields["strategy_id"], user_id)
        if "plan_id" in fields:
            self._validate_plan_owned(fields["plan_id"], user_id)

        # Check ownership
        existing = self.session.execute(
            select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        ).scalar_one_or_none()
        if existing is None:
            return None

        if fields:
            if any(
                key in fields
                for key in ("series_id", "symbol", "exchange")
            ):
                fields["series_id"] = self._validated_or_resolved_series_id(
                    fields.get("series_id"),
                    fields.get("symbol", existing.symbol),
                    fields.get("exchange", existing.exchange),
                )
            explicit_status = fields.get("position_status")
            if explicit_status is not None and explicit_status not in {"open", "closed"}:
                raise ValueError("invalid_position_status")
            closing_values = {
                "close_price": fields.get("close_price", existing.close_price),
                "close_time": fields.get("close_time", existing.close_time),
                "pnl": fields.get("pnl", existing.pnl),
            }
            inferred_status = (
                "closed"
                if any(value is not None for value in closing_values.values())
                else "open"
            )
            if explicit_status == "open" and inferred_status == "closed":
                raise ValueError("inconsistent_position_status")
            fields["position_status"] = explicit_status or inferred_status
            # JSON-encode tags if provided as a list
            if "tags" in fields and isinstance(fields["tags"], list):
                fields["tags"] = json.dumps(fields["tags"])
            if "mistakes" in fields and isinstance(fields["mistakes"], list):
                fields["mistakes"] = json.dumps(fields["mistakes"])
            fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.session.execute(
                update(Trade)
                .where(Trade.id == trade_id, Trade.user_id == user_id)
                .values(**fields)
            )
        self._replace_trade_images(trade_id, user_id, image_asset_ids)
        self.session.flush()
        self._replace_compliance_results(trade_id, user_id)
        self.session.commit()
        return self.get_trade(trade_id, user_id=user_id)

    def delete_trade(self, trade_id: str, user_id: str) -> bool:
        result = self.session.execute(
            delete(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        )
        self.session.commit()
        return result.rowcount > 0

    def batch_delete_trades(self, trade_ids: list[str], user_id: str) -> int:
        """Delete all trade rows owned by user_id whose id is in trade_ids.
        Returns the number of rows actually deleted.
        """
        if not trade_ids:
            return 0
        result = self.session.execute(
            delete(Trade).where(Trade.id.in_(trade_ids), Trade.user_id == user_id)
        )
        self.session.commit()
        return result.rowcount

    def batch_add_tags(
        self, trade_ids: list[str], user_id: str, tags: list[str]
    ) -> int:
        """Append `tags` to each matching trade's existing tags (order-preserving
        dedup). Returns the number of trades updated.
        """
        if not trade_ids or not tags:
            return 0
        rows = self.session.execute(
            select(Trade.id, Trade.tags)
            .where(Trade.id.in_(trade_ids), Trade.user_id == user_id)
        ).all()

        now = datetime.now(timezone.utc).isoformat()
        updated = 0
        for row in rows:
            existing = []
            if row.tags:
                try:
                    existing = json.loads(row.tags)
                except (json.JSONDecodeError, TypeError):
                    existing = []
            merged: list[str] = []
            seen: set[str] = set()
            for tag in [*existing, *tags]:
                if tag not in seen:
                    seen.add(tag)
                    merged.append(tag)
            self.session.execute(
                update(Trade)
                .where(Trade.id == row.id, Trade.user_id == user_id)
                .values(tags=json.dumps(merged), updated_at=now)
            )
            updated += 1
        self.session.commit()
        return updated

    def batch_create_trades(
        self,
        trades_data: list[dict],
        user_id: str,
        *,
        _commit: bool = True,
    ) -> list[dict]:
        results: list[dict] = []
        try:
            for data in trades_data:
                trade = self.create_trade(user_id=user_id, _commit=False, **data)
                results.append(trade)
            if _commit:
                self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return results

    # ------------------------------------------------------------------
    # Trade plans and rules
    # ------------------------------------------------------------------

    @staticmethod
    def _plan_to_dict(row: TradePlan) -> dict:
        from services.risk_engine import PositionRiskInput, calculate_position_risk

        calculation = calculate_position_risk(PositionRiskInput(
            asset_class=row.market,
            symbol=row.symbol,
            direction=row.direction,
            entry_price=row.entry_price,
            stop_loss=row.stop_loss,
            target_price=row.target_price,
            account_size=row.account_size,
            risk_percent=row.risk_percent,
        ))
        return {
            "id": row.id,
            "symbol": row.symbol,
            "series_id": row.series_id,
            "market": row.market,
            "direction": row.direction,
            "entry_price": row.entry_price,
            "target_price": row.target_price,
            "stop_loss": row.stop_loss,
            "account_size": row.account_size,
            "risk_percent": row.risk_percent,
            "risk_amount": calculation.risk_budget,
            "quantity": calculation.quantity,
            "risk_reward": calculation.reward_risk,
            "thesis": row.thesis,
            "strategy_id": row.strategy_id,
            "status": row.status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def create_trade_plan(self, user_id: str, **fields) -> dict:
        self._validate_strategy_owned(fields.get("strategy_id"), user_id)
        fields["series_id"] = self._validated_or_resolved_series_id(
            fields.get("series_id"),
            fields["symbol"],
            None,
            asset_class=fields.get("market"),
        )
        now = datetime.now(timezone.utc).isoformat()
        row = TradePlan(id=str(uuid4()), user_id=user_id, created_at=now, updated_at=now, **fields)
        self.session.add(row)
        self.session.commit()
        return self._plan_to_dict(row)

    @staticmethod
    def _validated_or_resolved_series_id(
        series_id: str | None,
        symbol: str,
        exchange: str | None,
        *,
        asset_class: str | None = None,
    ) -> str | None:
        from services.market_data import _legacy_asset_class, _legacy_venue
        from services.market_data_runtime import get_market_data_gateway
        from services.market_gateway import InstrumentSearch

        gateway = get_market_data_gateway()
        if series_id:
            if not gateway.has_series(series_id):
                raise ValueError("unknown_market_series")
            return series_id

        resolved_asset_class = {
            "stock": "equity",
            "forex": "spot",
            "metal": "spot",
        }.get(asset_class or "", asset_class) or _legacy_asset_class(symbol)
        if not resolved_asset_class:
            return None
        matches = gateway.search_instruments(
            InstrumentSearch(
                text=symbol,
                asset_class=resolved_asset_class,
                venue=_legacy_venue(
                    resolved_asset_class,
                    exchange or "",
                ),
            ),
        )
        return matches[0].series_id if len(matches) == 1 else None

    def list_trade_plans(self, user_id: str, status: str = "active") -> list[dict]:
        rows = self.session.execute(
            select(TradePlan)
            .where(TradePlan.user_id == user_id, TradePlan.status == status)
            .order_by(TradePlan.updated_at.desc())
        ).scalars().all()
        return [self._plan_to_dict(row) for row in rows]

    def find_matching_trade_plan(
        self,
        user_id: str,
        symbol: str,
        direction: str,
        plan_id: str | None = None,
    ) -> dict | None:
        conditions = [TradePlan.user_id == user_id, TradePlan.status == "active"]
        if plan_id:
            conditions.append(TradePlan.id == plan_id)
        else:
            conditions.extend([
                _compact_symbol_expression(TradePlan.symbol)
                == symbol.strip().upper().replace("/", "").replace("-", "").replace("_", ""),
                TradePlan.direction == direction,
            ])
        row = self.session.execute(
            select(TradePlan).where(*conditions).order_by(TradePlan.updated_at.desc()).limit(1)
        ).scalar_one_or_none()
        return self._plan_to_dict(row) if row is not None else None

    def delete_trade_plan(self, plan_id: str, user_id: str) -> bool:
        result = self.session.execute(
            delete(TradePlan).where(TradePlan.id == plan_id, TradePlan.user_id == user_id)
        )
        self.session.commit()
        return result.rowcount > 0

    @staticmethod
    def _rule_to_dict(row: TradingRule) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "rule_type": row.rule_type,
            "threshold": row.threshold,
            "weight": row.weight,
            "active": bool(row.active),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def create_rule(
        self,
        user_id: str,
        name: str,
        rule_type: str,
        threshold: float | None,
        weight: str,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        row = TradingRule(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            rule_type=rule_type,
            threshold=threshold,
            weight=weight,
            active=1,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.commit()
        return self._rule_to_dict(row)

    def list_rules(self, user_id: str, active_only: bool = False) -> list[dict]:
        conditions = [TradingRule.user_id == user_id]
        if active_only:
            conditions.append(TradingRule.active == 1)
        rows = self.session.execute(
            select(TradingRule).where(*conditions).order_by(TradingRule.created_at.asc())
        ).scalars().all()
        return [self._rule_to_dict(row) for row in rows]

    def update_rule(self, rule_id: str, user_id: str, **fields) -> dict | None:
        row = self.session.execute(
            select(TradingRule).where(TradingRule.id == rule_id, TradingRule.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.session.execute(
            update(TradingRule)
            .where(TradingRule.id == rule_id, TradingRule.user_id == user_id)
            .values(**fields)
        )
        self.session.commit()
        updated_row = self.session.execute(
            select(TradingRule).where(TradingRule.id == rule_id)
        ).scalar_one()
        return self._rule_to_dict(updated_row)

    def delete_rule(self, rule_id: str, user_id: str) -> bool:
        result = self.session.execute(
            delete(TradingRule).where(TradingRule.id == rule_id, TradingRule.user_id == user_id)
        )
        self.session.commit()
        return result.rowcount > 0

    @staticmethod
    def _compliance_summary(results: list[dict]) -> dict:
        weights = {"critical": 3, "important": 2, "nice_to_have": 1}
        applicable = [result for result in results if result["status"] != "not_applicable"]
        possible = sum(weights.get(result["weight"], 1) for result in applicable)
        earned = sum(
            weights.get(result["weight"], 1)
            for result in applicable
            if result["status"] == "passed"
        )
        return {
            "score": round(earned / possible * 100) if possible else None,
            "passed": sum(result["status"] == "passed" for result in results),
            "failed": sum(result["status"] == "failed" for result in results),
            "not_applicable": sum(result["status"] == "not_applicable" for result in results),
            "results": results,
        }

    def _resolve_account_size(self, user_id: str, data: dict) -> float | None:
        if data.get("account_size") is not None:
            return float(data["account_size"])
        plan_id = data.get("plan_id")
        if plan_id:
            value = self.session.execute(
                select(TradePlan.account_size).where(
                    TradePlan.id == plan_id,
                    TradePlan.user_id == user_id,
                )
            ).scalar_one_or_none()
            if value is not None:
                return float(value)
        return self.get_starting_capital(user_id=user_id)

    def _resolve_market(self, user_id: str, data: dict) -> str:
        market = data.get("market") or data.get("asset_class")
        if market:
            return str(market)
        plan_id = data.get("plan_id")
        if plan_id:
            value = self.session.execute(
                select(TradePlan.market).where(
                    TradePlan.id == plan_id,
                    TradePlan.user_id == user_id,
                )
            ).scalar_one_or_none()
            if value:
                return str(value)
        return "stock"

    def evaluate_compliance(
        self,
        user_id: str,
        data: dict,
        exclude_trade_id: str | None = None,
    ) -> dict:
        rules = self.list_rules(user_id, active_only=True)
        results: list[dict] = []
        entry = data.get("open_price") if data.get("open_price") is not None else data.get("entry_price")
        stop = data.get("stop_loss")
        target = data.get("target_price")
        quantity = data.get("quantity")
        account_size = self._resolve_account_size(user_id, data)
        market = self._resolve_market(user_id, data)

        for rule in rules:
            status = "not_applicable"
            detail = ""
            threshold = rule["threshold"]
            rule_type = rule["rule_type"]

            if rule_type == "max_risk_percent":
                if None not in (entry, stop, quantity, account_size) and account_size and account_size > 0:
                    from services.instruments import position_risk_amount

                    risk_amount = position_risk_amount(
                        market, str(data.get("symbol") or ""),
                        float(entry), float(stop), float(quantity),
                    )
                    if risk_amount is not None:
                        actual = risk_amount / account_size * 100
                        status = "passed" if threshold is not None and actual <= threshold else "failed"
                        detail = f"{actual:.2f}% / {threshold:g}%"
            elif rule_type == "min_risk_reward":
                if None not in (entry, stop, target):
                    price_risk = abs(float(entry) - float(stop))
                    reward = (
                        float(target) - float(entry)
                        if data.get("direction") == "long"
                        else float(entry) - float(target)
                    )
                    if price_risk > 0:
                        actual = reward / price_risk
                        status = "passed" if threshold is not None and actual >= threshold else "failed"
                        detail = f"{actual:.2f}R / {threshold:g}R"
            elif rule_type == "max_trades_per_day":
                day = str(data.get("open_time") or datetime.now(timezone.utc).isoformat())[:10]
                conditions = [Trade.user_id == user_id, Trade.open_time.like(f"{day}%")]
                if exclude_trade_id:
                    conditions.append(Trade.id != exclude_trade_id)
                existing = self.session.execute(
                    select(func.count()).select_from(Trade).where(*conditions)
                ).scalar_one()
                actual = int(existing) + 1
                status = "passed" if threshold is not None and actual <= threshold else "failed"
                detail = f"{actual} / {int(threshold or 0)}"
            elif rule_type == "min_confidence":
                confidence = data.get("confidence")
                if confidence is not None:
                    status = "passed" if threshold is not None and confidence >= threshold else "failed"
                    detail = f"{confidence:g} / {threshold:g}"
            elif rule_type == "require_stop_loss":
                status = "passed" if stop is not None else "failed"
            elif rule_type == "require_notes":
                status = "passed" if str(data.get("notes") or data.get("thesis") or "").strip() else "failed"

            results.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "rule_type": rule_type,
                "weight": rule["weight"],
                "status": status,
                "detail": detail,
            })

        return self._compliance_summary(results)

    def get_similar_trade_stats(
        self,
        user_id: str,
        symbol: str,
        direction: str,
        strategy_id: str | None = None,
        setup_type: str | None = None,
    ) -> dict:
        base_conditions = [
            Trade.user_id == user_id,
            Trade.pnl.isnot(None),
            _compact_symbol_expression(Trade.symbol)
            == symbol.strip().upper().replace("/", "").replace("-", "").replace("_", ""),
            Trade.direction == direction,
        ]
        strict_conditions = list(base_conditions)
        match_fields = ["symbol", "direction"]
        if strategy_id:
            strict_conditions.append(Trade.strategy_id == strategy_id)
            match_fields.append("strategy_id")
        if setup_type:
            strict_conditions.append(Trade.setup_type == setup_type)
            match_fields.append("setup_type")

        rows = self.session.execute(select(Trade).where(*strict_conditions)).scalars().all()
        if len(rows) < 10 and len(strict_conditions) > len(base_conditions):
            rows = self.session.execute(select(Trade).where(*base_conditions)).scalars().all()
            match_fields = ["symbol", "direction"]

        pnl_values = [float(row.pnl) for row in rows if row.pnl is not None]
        winners = [value for value in pnl_values if value > 0]
        losers = [value for value in pnl_values if value < 0]
        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        sample_count = len(pnl_values)
        return {
            "sample_count": sample_count,
            "sample_quality": (
                "usable" if sample_count >= 20
                else "limited" if sample_count >= 10
                else "insufficient"
            ),
            "match_fields": match_fields,
            "wins": len(winners),
            "losses": len(losers),
            "win_rate": len(winners) / sample_count * 100 if sample_count else None,
            "total_pnl": sum(pnl_values) if pnl_values else None,
            "average_pnl": sum(pnl_values) / sample_count if sample_count else None,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
            "expectancy": sum(pnl_values) / sample_count if sample_count else None,
        }

    def _replace_compliance_results(self, trade_id: str, user_id: str) -> None:
        trade = self.session.execute(
            select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        ).scalar_one_or_none()
        if trade is None:
            return
        self.session.execute(delete(TradeRuleResult).where(TradeRuleResult.trade_id == trade_id))
        summary = self.evaluate_compliance(
            user_id,
            _trade_to_dict(trade),
            exclude_trade_id=trade_id,
        )
        now = datetime.now(timezone.utc).isoformat()
        for result in summary["results"]:
            self.session.add(TradeRuleResult(
                id=str(uuid4()),
                trade_id=trade_id,
                rule_id=result["rule_id"],
                rule_name=result["rule_name"],
                rule_type=result["rule_type"],
                weight=result["weight"],
                status=result["status"],
                detail=result["detail"],
                created_at=now,
            ))

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_iso(s: str | None) -> datetime | None:
        if s is None:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def compute_stats(self, user_id: str, date_from: str | None = None, date_to: str | None = None) -> dict:
        """Compute aggregate trading statistics for closed trades (pnl IS NOT NULL)."""
        conditions = [Trade.user_id == user_id, Trade.pnl.isnot(None)]
        if date_from is not None:
            conditions.append(Trade.open_time >= date_from)
        if date_to is not None:
            conditions.append(Trade.open_time <= date_to)

        rows = self.session.execute(
            select(Trade)
            .where(*conditions)
            .order_by(func.coalesce(Trade.close_time, Trade.open_time).asc())
        ).scalars().all()

        trades = [_trade_to_dict(r) for r in rows]

        # Net PnL realised before the selected range
        if date_from is not None:
            row = self.session.execute(
                select(func.coalesce(func.sum(Trade.pnl), 0.0))
                .where(
                    Trade.user_id == user_id,
                    Trade.pnl.isnot(None),
                    func.coalesce(Trade.close_time, Trade.open_time) < date_from,
                )
            ).scalar_one()
            pnl_before_range = float(row) if row is not None else 0.0
        else:
            pnl_before_range = 0.0

        if not trades:
            return {
                "total_trades": 0,
                "total_pnl": 0.0,
                "winners": 0,
                "losers": 0,
                "breakeven_trades": 0,
                "total_contracts": 0.0,
                "winning_contracts": 0.0,
                "losing_contracts": 0.0,
                "gross_total_pnl": 0.0,
                "total_fees": 0.0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_from": "",
                "max_drawdown_to": "",
                "max_run_up": 0.0,
                "max_run_up_from": "",
                "max_run_up_to": "",
                "max_consecutive_losses": 0,
                "avg_holding_seconds": 0.0,
                "avg_holding_winners": 0.0,
                "avg_holding_losers": 0.0,
                "longest_holding_all": 0.0,
                "longest_holding_winners": 0.0,
                "longest_holding_losers": 0.0,
                "equity_curve": [],
                "by_symbol": [],
                "by_direction": [],
                "by_tag": [],
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "win_loss_ratio": 0.0,
                "sharpe_ratio": 0.0,
                "by_hour_weekday": [],
                "largest_winner": 0.0,
                "largest_loser": 0.0,
                "std_winner": 0.0,
                "std_loser": 0.0,
                "expectancy": 0.0,
                "per_trade_series": [],
                "distribution_series": [],
                "pnl_by_hour": [],
                "pnl_before_range": pnl_before_range,
            }

        total_trades = len(trades)
        winners = sum(1 for t in trades if t["pnl"] > 0)
        losers = sum(1 for t in trades if t["pnl"] < 0)
        breakeven_trades = total_trades - winners - losers
        total_pnl = sum(t["pnl"] for t in trades)
        win_rate = winners / total_trades if total_trades > 0 else 0.0

        total_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        total_loss = sum(t["pnl"] for t in trades if t["pnl"] < 0)
        gross_profit = total_profit
        gross_loss = abs(total_loss)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else math.inf

        total_fees = sum((t.get("fees") or 0) for t in trades)
        gross_total_pnl = total_pnl + total_fees

        total_contracts = sum((t.get("quantity") or 0) for t in trades)
        winning_contracts = sum((t.get("quantity") or 0) for t in trades if t["pnl"] > 0)
        losing_contracts = sum((t.get("quantity") or 0) for t in trades if t["pnl"] < 0)

        # Equity curve, drawdown, and run-up in one pass.
        equity_curve: list[dict] = []
        equity = 0.0
        baseline_time = trades[0].get("open_time") or trades[0].get("close_time") or ""
        peak = 0.0
        peak_time = baseline_time
        trough = 0.0
        trough_time = baseline_time
        max_drawdown = 0.0
        max_drawdown_from = ""
        max_drawdown_to = ""
        max_run_up = 0.0
        max_run_up_from = ""
        max_run_up_to = ""
        for t in trades:
            equity += t["pnl"]
            equity_time = t.get("close_time") or t.get("open_time") or ""
            if t.get("close_time") is not None or t.get("open_time") is not None:
                equity_curve.append({"time": equity_time, "equity": equity})
            # update peak / trough
            if equity > peak:
                peak = equity
                peak_time = equity_time
            if equity < trough:
                trough = equity
                trough_time = equity_time
            # drawdown candidate: from running peak down to now
            dd = peak - equity
            if dd > max_drawdown:
                max_drawdown = dd
                max_drawdown_from = peak_time
                max_drawdown_to = equity_time
            # run-up candidate: from running trough up to now
            ru = equity - trough
            if ru > max_run_up:
                max_run_up = ru
                max_run_up_from = trough_time
                max_run_up_to = equity_time

        # Max consecutive losses
        max_consecutive_losses = 0
        current_streak = 0
        for t in trades:
            if t["pnl"] < 0:
                current_streak += 1
                if current_streak > max_consecutive_losses:
                    max_consecutive_losses = current_streak
            else:
                current_streak = 0

        # Average holding seconds
        holding_secs: list[float] = []
        winner_holding_secs: list[float] = []
        loser_holding_secs: list[float] = []
        for t in trades:
            open_dt = self._parse_iso(t.get("open_time"))
            close_dt = self._parse_iso(t.get("close_time"))
            if open_dt is not None and close_dt is not None:
                secs = (close_dt - open_dt).total_seconds()
                holding_secs.append(secs)
                if t["pnl"] > 0:
                    winner_holding_secs.append(secs)
                elif t["pnl"] < 0:
                    loser_holding_secs.append(secs)
        avg_holding_seconds = (
            sum(holding_secs) / len(holding_secs) if holding_secs else 0.0
        )
        avg_holding_winners = (
            sum(winner_holding_secs) / len(winner_holding_secs) if winner_holding_secs else 0.0
        )
        avg_holding_losers = (
            sum(loser_holding_secs) / len(loser_holding_secs) if loser_holding_secs else 0.0
        )
        longest_holding_all = max(holding_secs) if holding_secs else 0.0
        longest_holding_winners = max(winner_holding_secs) if winner_holding_secs else 0.0
        longest_holding_losers = max(loser_holding_secs) if loser_holding_secs else 0.0

        # By symbol
        sym_data: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            sym_data[t["symbol"]].append(t)
        by_symbol = [
            {
                "symbol": sym,
                "count": len(group),
                "total_pnl": sum(x["pnl"] for x in group),
                "win_rate": sum(1 for x in group if x["pnl"] > 0) / len(group),
            }
            for sym, group in sym_data.items()
        ]

        # By direction
        dir_data: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            dir_data[t["direction"]].append(t)
        by_direction = [
            {
                "direction": d,
                "count": len(group),
                "total_pnl": sum(x["pnl"] for x in group),
                "win_rate": sum(1 for x in group if x["pnl"] > 0) / len(group),
            }
            for d, group in dir_data.items()
        ]

        # By tag (flattened)
        tag_data: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            tags = t.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    tag_data[tag].append(t)
        by_tag = [
            {
                "tag": tag,
                "count": len(group),
                "total_pnl": sum(x["pnl"] for x in group),
                "win_rate": sum(1 for x in group if x["pnl"] > 0) / len(group),
            }
            for tag, group in tag_data.items()
        ]

        # Avg win / avg loss / win-loss ratio
        win_pnls = [t["pnl"] for t in trades if t["pnl"] > 0]
        loss_pnls = [t["pnl"] for t in trades if t["pnl"] < 0]
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
        avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
        win_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else 0.0

        largest_winner = max(win_pnls) if win_pnls else 0.0
        largest_loser = min(loss_pnls) if loss_pnls else 0.0
        std_winner = (
            math.sqrt(sum((x - avg_win) ** 2 for x in win_pnls) / (len(win_pnls) - 1))
            if len(win_pnls) >= 2 else 0.0
        )
        std_loser = (
            math.sqrt(sum((x - avg_loss) ** 2 for x in loss_pnls) / (len(loss_pnls) - 1))
            if len(loss_pnls) >= 2 else 0.0
        )
        expectancy = (gross_total_pnl / total_trades) if total_trades > 0 else 0.0

        # Sharpe ratio
        daily_pnl: dict[str, float] = defaultdict(float)
        for t in trades:
            close_or_open = t.get("close_time") or t.get("open_time")
            dt = self._parse_iso(close_or_open)
            if dt is not None:
                daily_pnl[dt.date().isoformat()] += t["pnl"]
        daily_values = list(daily_pnl.values())
        if len(daily_values) >= 2:
            daily_mean = sum(daily_values) / len(daily_values)
            daily_var = sum((v - daily_mean) ** 2 for v in daily_values) / (len(daily_values) - 1)
            daily_std = math.sqrt(daily_var)
            sharpe_ratio = (daily_mean / daily_std * math.sqrt(252)) if daily_std > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        # By hour/weekday heatmap
        heatmap_data: dict[tuple[int, int], dict] = {}
        for t in trades:
            open_dt = self._parse_iso(t.get("open_time"))
            if open_dt is None:
                continue
            key = (open_dt.weekday(), open_dt.hour)
            if key not in heatmap_data:
                heatmap_data[key] = {"weekday": key[0], "hour": key[1], "trades": 0, "wins": 0}
            heatmap_data[key]["trades"] += 1
            if t["pnl"] > 0:
                heatmap_data[key]["wins"] += 1
        by_hour_weekday = sorted(heatmap_data.values(), key=lambda x: (x["weekday"], x["hour"]))

        per_trade_series: list[dict] = []
        for t in trades:
            ts = t.get("close_time") or t.get("open_time") or ""
            fees = t.get("fees") or 0
            per_trade_series.append({
                "time": ts,
                "pnl_net": t["pnl"],
                "pnl_gross": t["pnl"] + fees,
            })

        distribution_series = sorted(t["pnl"] for t in trades)

        hour_buckets: dict[int, dict] = {
            h: {"hour": h, "total_pnl": 0.0, "count": 0} for h in range(24)
        }
        for t in trades:
            open_dt = self._parse_iso(t.get("open_time"))
            if open_dt is None:
                continue
            hour_buckets[open_dt.hour]["total_pnl"] += t["pnl"]
            hour_buckets[open_dt.hour]["count"] += 1
        pnl_by_hour = [hour_buckets[h] for h in range(24)]

        return {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "winners": winners,
            "losers": losers,
            "breakeven_trades": breakeven_trades,
            "total_contracts": total_contracts,
            "winning_contracts": winning_contracts,
            "losing_contracts": losing_contracts,
            "gross_total_pnl": gross_total_pnl,
            "total_fees": total_fees,
            "total_profit": total_profit,
            "total_loss": total_loss,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "max_drawdown_from": max_drawdown_from,
            "max_drawdown_to": max_drawdown_to,
            "max_run_up": max_run_up,
            "max_run_up_from": max_run_up_from,
            "max_run_up_to": max_run_up_to,
            "max_consecutive_losses": max_consecutive_losses,
            "avg_holding_seconds": avg_holding_seconds,
            "avg_holding_winners": avg_holding_winners,
            "avg_holding_losers": avg_holding_losers,
            "longest_holding_all": longest_holding_all,
            "longest_holding_winners": longest_holding_winners,
            "longest_holding_losers": longest_holding_losers,
            "equity_curve": equity_curve,
            "by_symbol": by_symbol,
            "by_direction": by_direction,
            "by_tag": by_tag,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": win_loss_ratio,
            "sharpe_ratio": sharpe_ratio,
            "by_hour_weekday": by_hour_weekday,
            "largest_winner": largest_winner,
            "largest_loser": largest_loser,
            "std_winner": std_winner,
            "std_loser": std_loser,
            "expectancy": expectancy,
            "per_trade_series": per_trade_series,
            "distribution_series": distribution_series,
            "pnl_by_hour": pnl_by_hour,
            "pnl_before_range": pnl_before_range,
        }

    @staticmethod
    def _parse_month_key(month: str) -> tuple[date, date]:
        month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
        if month_start.month == 12:
            next_month = date(month_start.year + 1, 1, 1)
        else:
            next_month = date(month_start.year, month_start.month + 1, 1)
        return month_start, next_month

    def compute_calendar_summary(self, month: str, user_id: str) -> dict:
        month_start, next_month = self._parse_month_key(month)
        date_from = f"{month_start.isoformat()}T00:00:00"
        date_to = f"{(next_month - timedelta(days=1)).isoformat()}T23:59:59"

        rows = self.session.execute(
            select(Trade)
            .where(
                Trade.user_id == user_id,
                Trade.open_time >= date_from,
                Trade.open_time <= date_to,
                Trade.pnl.isnot(None),
            )
            .order_by(Trade.open_time.asc())
        ).scalars().all()
        trades = [_trade_to_dict(r) for r in rows]

        daily_groups: dict[str, list[dict]] = defaultdict(list)
        for trade in trades:
            open_dt = self._parse_iso(trade.get("open_time"))
            if open_dt is None:
                continue
            if open_dt.date().month != month_start.month or open_dt.date().year != month_start.year:
                continue
            daily_groups[open_dt.date().isoformat()].append(trade)

        days = []
        for day_key in sorted(daily_groups.keys()):
            group = daily_groups[day_key]
            trade_count = len(group)
            winners = sum(1 for item in group if item["pnl"] > 0)
            days.append({
                "date": day_key,
                "trade_count": trade_count,
                "total_pnl": sum(item["pnl"] for item in group),
                "win_rate": winners / trade_count if trade_count else 0.0,
            })

        cal = calendar.Calendar(firstweekday=6)
        weeks = []
        for week_index, week_dates in enumerate(cal.monthdatescalendar(month_start.year, month_start.month), start=1):
            week_trades: list[dict] = []
            active_days = 0
            for week_date in week_dates:
                if week_date.month != month_start.month:
                    continue
                day_key = week_date.isoformat()
                group = daily_groups.get(day_key, [])
                if group:
                    active_days += 1
                    week_trades.extend(group)

            trade_count = len(week_trades)
            winners = sum(1 for item in week_trades if item["pnl"] > 0)
            weeks.append({
                "week_index": week_index,
                "label": f"Week {week_index}",
                "trade_count": trade_count,
                "active_days": active_days,
                "total_pnl": sum(item["pnl"] for item in week_trades),
                "win_rate": winners / trade_count if trade_count else 0.0,
            })

        return {
            "month": month,
            "days": days,
            "weeks": weeks,
        }

    # ------------------------------------------------------------------
    # Daily Reviews
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_daily_review(user_id: str, review_date: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": "",
            "user_id": user_id,
            "review_date": review_date,
            "title": "",
            "body": "",
            "tags": [],
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _review_to_dict(row: DailyReview) -> dict:
        d = {
            "id": row.id,
            "user_id": row.user_id,
            "review_date": row.review_date,
            "title": row.title or "",
            "body": row.body or "",
            "tags": [],
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        try:
            d["tags"] = json.loads(row.tags or "[]")
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
        return d

    # Keep legacy name for backward compat
    @staticmethod
    def _review_row_to_dict(row) -> dict:
        return JournalService._review_to_dict(row)

    def get_daily_review(self, user_id: str, review_date: str) -> dict:
        row = self.session.execute(
            select(DailyReview).where(
                DailyReview.user_id == user_id,
                DailyReview.review_date == review_date,
            )
        ).scalar_one_or_none()
        if row is None:
            return self._empty_daily_review(user_id, review_date)
        return self._review_to_dict(row)

    def upsert_daily_review(self, user_id: str, review_date: str, **fields) -> dict:
        allowed = {"title", "body", "tags"}
        payload = {k: v for k, v in fields.items() if k in allowed}
        if "tags" in payload:
            payload["tags"] = json.dumps(payload["tags"])

        now = datetime.now(timezone.utc).isoformat()
        existing = self.session.execute(
            select(DailyReview).where(
                DailyReview.user_id == user_id,
                DailyReview.review_date == review_date,
            )
        ).scalar_one_or_none()

        if existing is None:
            review_id = str(uuid4())
            values = {"title": "", "body": "", "tags": "[]", **payload}
            self.session.add(DailyReview(
                id=review_id,
                user_id=user_id,
                review_date=review_date,
                title=values["title"],
                body=values["body"],
                tags=values["tags"],
                created_at=now,
                updated_at=now,
            ))
        elif payload:
            payload["updated_at"] = now
            self.session.execute(
                update(DailyReview)
                .where(DailyReview.user_id == user_id, DailyReview.review_date == review_date)
                .values(**payload)
            )
        else:
            self.session.execute(
                update(DailyReview)
                .where(DailyReview.user_id == user_id, DailyReview.review_date == review_date)
                .values(updated_at=now)
            )

        self.session.commit()
        return self.get_daily_review(user_id=user_id, review_date=review_date)

    def get_daily_review_bundle(
        self,
        user_id: str,
        review_date: str,
        date_from: str,
        date_to: str,
    ) -> dict:
        return {
            "review": self.get_daily_review(user_id=user_id, review_date=review_date),
            "stats": self.compute_stats(
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
            ),
            "trades": self.list_trades(
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
                limit=10000,
                offset=0,
            ),
        }

    @staticmethod
    def _build_daily_review_assist_prompt(
        action: str,
        bundle: dict,
        body: str,
        selection: str,
        lang: str,
    ) -> str:
        system = t("daily_review.assist.prompt", lang)
        action_prompt = t(f"daily_review.assist.{action}", lang)
        payload = {
            "stats": {
                k: v for k, v in bundle["stats"].items()
                if k not in {"equity_curve", "per_trade_series", "distribution_series", "pnl_by_hour"}
            },
            "trades": [
                {
                    "symbol": tr.get("symbol"),
                    "direction": tr.get("direction"),
                    "open_time": tr.get("open_time"),
                    "close_time": tr.get("close_time"),
                    "pnl": tr.get("pnl"),
                    "tags": tr.get("tags", []),
                    "notes": tr.get("notes", ""),
                }
                for tr in bundle["trades"]
            ],
            "body": body,
            "selection": selection,
        }
        return (
            f"{system}\n\n{action_prompt}\n\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}"
        )

    @staticmethod
    def _parse_daily_review_assist(raw: str, action: str) -> dict:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"suggestions": [raw.strip()]}
        suggestions = parsed.get("suggestions")
        if not isinstance(suggestions, list):
            suggestions = []
        cleaned = [str(x).strip() for x in suggestions if str(x).strip()]
        if action != "title":
            cleaned = cleaned[:1]
        else:
            cleaned = cleaned[:3]
        return {"action": action, "suggestions": cleaned}

    async def assist_daily_review(
        self,
        user_id: str,
        review_date: str,
        action: str,
        body: str,
        selection: str,
        date_from: str,
        date_to: str,
        lang: str,
    ) -> dict:
        try:
            from services.analyzer import create_provider

            bundle = self.get_daily_review_bundle(
                user_id=user_id,
                review_date=review_date,
                date_from=date_from,
                date_to=date_to,
            )
            prompt = self._build_daily_review_assist_prompt(action, bundle, body, selection, lang)
            provider = create_provider()
            raw = await provider.complete(prompt)
            return self._parse_daily_review_assist(raw, action)
        except Exception as exc:
            logger.exception("Daily review assist failed", exc_info=exc)
            return {"action": action, "suggestions": []}

    # ------------------------------------------------------------------
    # AI Diagnosis
    # ------------------------------------------------------------------

    @staticmethod
    def _build_diagnosis_prompt(stats: dict, representative: list[dict], lang: str) -> str:
        system = t("diagnosis.prompt", lang)
        _DIAGNOSIS_EXCLUDE = {"equity_curve", "per_trade_series", "distribution_series", "pnl_by_hour"}
        stats_copy = {k: v for k, v in stats.items() if k not in _DIAGNOSIS_EXCLUDE}
        stats_json = json.dumps(stats_copy, ensure_ascii=False, default=str)
        trades_json = json.dumps(representative, ensure_ascii=False, default=str)
        return f"{system}\n\n## Statistics\n{stats_json}\n\n## Representative Trades\n{trades_json}"

    def _get_representative_trades(self, user_id: str, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        """Get top 5 winners + top 5 losers by pnl, deduplicated, limit 20."""
        conditions = [Trade.user_id == user_id, Trade.pnl.isnot(None)]
        if date_from is not None:
            conditions.append(Trade.open_time >= date_from)
        if date_to is not None:
            conditions.append(Trade.open_time <= date_to)
        rows = self.session.execute(
            select(Trade).where(*conditions).order_by(Trade.pnl.asc())
        ).scalars().all()
        trades = [_trade_to_dict(r) for r in rows]
        if not trades:
            return []
        # Bottom 5 (worst) + top 5 (best)
        bottom = trades[:5]
        top = trades[-5:]
        # Deduplicate by id, preserving order
        seen: set[str] = set()
        result: list[dict] = []
        for tr in bottom + top:
            if tr["id"] not in seen:
                seen.add(tr["id"])
                result.append(tr)
        return result[:20]

    def create_diagnosis_job(self, user_id: str, lang: str = "zh", date_from: str | None = None, date_to: str | None = None) -> DiagnosisJobEntry:
        stats = self.compute_stats(user_id=user_id, date_from=date_from, date_to=date_to)
        prompt_stats = {
            **stats,
            "currency_code": self.get_journal_settings(user_id)["currency_code"],
        }
        representative = self._get_representative_trades(user_id=user_id, date_from=date_from, date_to=date_to)

        now = datetime.now(timezone.utc).isoformat()
        job = DiagnosisJobEntry(
            job_id=str(uuid4()),
            status="queued",
            created_at=now,
            updated_at=now,
        )
        _diagnosis_jobs[job.job_id] = job

        async def _run() -> None:
            job.status = "running"
            job.updated_at = datetime.now(timezone.utc).isoformat()
            try:
                from services.analyzer import create_provider
                provider = create_provider()
                prompt = JournalService._build_diagnosis_prompt(prompt_stats, representative, lang)
                result = await provider.complete(prompt)
                job.status = "completed"
                job.result = result
                job.updated_at = datetime.now(timezone.utc).isoformat()
            except Exception as exc:
                logger.exception("Diagnosis job failed", exc_info=exc)
                job.status = "failed"
                job.error = t("diagnosis.error", lang)
                job.updated_at = datetime.now(timezone.utc).isoformat()

        asyncio.create_task(_run())
        return job

    @staticmethod
    def get_diagnosis_job(job_id: str) -> DiagnosisJobEntry | None:
        return _diagnosis_jobs.get(job_id)

    # ------------------------------------------------------------------
    # Settings (journal-scoped key/value)
    # ------------------------------------------------------------------

    def get_journal_settings(self, user_id: str) -> dict:
        row = self.session.execute(
            select(JournalSettings).where(JournalSettings.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            return {"starting_capital": None, "currency_code": None}
        return {
            "starting_capital": row.starting_capital,
            "currency_code": row.currency_code,
        }

    def update_journal_settings(self, user_id: str, updates: dict) -> dict:
        row = self.session.execute(
            select(JournalSettings).where(JournalSettings.user_id == user_id)
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc).isoformat()
        if row is None:
            row = JournalSettings(
                user_id=user_id,
                starting_capital=None,
                currency_code=None,
                updated_at=now,
            )
            self.session.add(row)

        if "starting_capital" in updates:
            row.starting_capital = updates["starting_capital"]
        if "currency_code" in updates:
            row.currency_code = updates["currency_code"]
        row.updated_at = now
        self.session.commit()
        return {
            "starting_capital": row.starting_capital,
            "currency_code": row.currency_code,
        }

    def get_starting_capital(self, user_id: str) -> float | None:
        return self.get_journal_settings(user_id)["starting_capital"]

    def set_starting_capital(
        self, user_id: str, value: float | None
    ) -> float | None:
        settings = self.update_journal_settings(
            user_id, {"starting_capital": value}
        )
        return settings["starting_capital"]
