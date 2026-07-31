"""Portfolio service: Portfolios CRUD + portfolio-scoped entries/categories/summary/import-export."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Portfolio, PortfolioCategory, PortfolioEntry

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _row_to_entry(row: PortfolioEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "portfolio_id": row.portfolio_id,
        "name": row.name,
        "category": row.category,
        "platform": row.platform,
        "amount": float(row.amount),
        "notes": row.notes or "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


CSV_COLUMNS = ["name", "category", "platform", "amount", "notes"]


def parse_csv_rows(csv_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a CSV into row dicts; currency column (if any) is ignored.

    Header must include name/category/amount (platform + notes optional).
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"name", "category", "amount"}
    headers = set(reader.fieldnames or [])
    missing = required - headers
    if missing:
        return [], [{"row": 1, "reason": f"missing required column(s): {sorted(missing)}"}]

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for idx, raw in enumerate(reader, start=2):
        if not any((raw.get(c) or "").strip() for c in CSV_COLUMNS):
            continue
        name = (raw.get("name") or "").strip()
        category = (raw.get("category") or "").strip()
        if not name or not category:
            errors.append({"row": idx, "reason": "missing required field (name/category)"})
            continue
        amount_raw = (raw.get("amount") or "").strip()
        try:
            amount = float(amount_raw)
        except ValueError:
            errors.append({"row": idx, "reason": f"amount is not numeric: {amount_raw!r}"})
            continue
        if amount < 0:
            errors.append({"row": idx, "reason": "amount must be non-negative"})
            continue
        rows.append({
            "name": name, "category": category,
            "platform": (raw.get("platform") or "").strip() or None,
            "amount": amount, "notes": (raw.get("notes") or "").strip(),
        })
    return rows, errors


# ---------------------------------------------------------------------------
# PortfoliosService
# ---------------------------------------------------------------------------

class PortfoliosService:
    """CRUD on Portfolio entities. User-scoped."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, *, user_id: str, name: str, currency: str) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("name is required")
        if not currency.strip():
            raise ValueError("currency is required")
        pid = str(uuid4())
        now = _now_iso()
        portfolio = Portfolio(
            id=pid,
            user_id=user_id,
            name=name.strip(),
            currency=currency.strip(),
            created_at=now,
            updated_at=now,
        )
        self.session.add(portfolio)
        self.session.commit()
        return {
            "id": pid,
            "name": name.strip(),
            "currency": currency.strip(),
            "entry_count": 0,
            "created_at": now,
            "updated_at": now,
        }

    def list(self, *, user_id: str) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(
                Portfolio.id,
                Portfolio.name,
                Portfolio.currency,
                Portfolio.created_at,
                Portfolio.updated_at,
                func.count(PortfolioEntry.id).label("entry_count"),
            )
            .outerjoin(PortfolioEntry, PortfolioEntry.portfolio_id == Portfolio.id)
            .where(Portfolio.user_id == user_id)
            .group_by(
                Portfolio.id,
                Portfolio.name,
                Portfolio.currency,
                Portfolio.created_at,
                Portfolio.updated_at,
            )
            .order_by(Portfolio.created_at.desc())
        ).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "currency": r.currency,
                "entry_count": int(r.entry_count),
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]

    def get(self, portfolio_id: str, *, user_id: str) -> dict[str, Any] | None:
        row = self.session.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        count = self.session.execute(
            select(func.count(PortfolioEntry.id)).where(PortfolioEntry.portfolio_id == portfolio_id)
        ).scalar_one()
        return {
            "id": row.id,
            "name": row.name,
            "currency": row.currency,
            "entry_count": int(count),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def update(self, portfolio_id: str, *, user_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"name", "currency"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None and str(v).strip()}
        if not updates:
            return self.get(portfolio_id, user_id=user_id)
        updates["updated_at"] = _now_iso()
        result = self.session.execute(
            update(Portfolio)
            .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
            .values(**updates)
        )
        self.session.commit()
        if result.rowcount == 0:
            return None
        return self.get(portfolio_id, user_id=user_id)

    def delete(self, portfolio_id: str, *, user_id: str) -> int | None:
        """Returns the number of deleted entries, or None if not found."""
        # Count entries before deleting
        portfolio = self.session.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        ).scalar_one_or_none()
        if portfolio is None:
            return None
        entry_count = self.session.execute(
            select(func.count(PortfolioEntry.id)).where(PortfolioEntry.portfolio_id == portfolio_id)
        ).scalar_one()
        self.session.execute(
            delete(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        )
        self.session.commit()
        return int(entry_count)


# ---------------------------------------------------------------------------
# EntryService
# ---------------------------------------------------------------------------

class EntryService:
    """Entry operations scoped to a portfolio + its owning user."""

    def __init__(self, session: Session):
        self.session = session

    def _assert_portfolio_owner(self, portfolio_id: str, user_id: str) -> None:
        row = self.session.execute(
            select(Portfolio.user_id).where(Portfolio.id == portfolio_id)
        ).scalar_one_or_none()
        if row is None or row != user_id:
            raise PermissionError("portfolio not found or not owned by user")

    def _portfolio_for_entry(self, entry_id: str) -> tuple[str, str] | None:
        row = self.session.execute(
            select(Portfolio.id, Portfolio.user_id)
            .join(PortfolioEntry, PortfolioEntry.portfolio_id == Portfolio.id)
            .where(PortfolioEntry.id == entry_id)
        ).first()
        if row is None:
            return None
        return row.id, row.user_id

    def create(
        self, *, portfolio_id: str, user_id: str, name: str, category: str,
        amount: float, platform: str | None = None, notes: str = "",
    ) -> dict[str, Any]:
        self._assert_portfolio_owner(portfolio_id, user_id)
        if amount < 0:
            raise ValueError("amount must be non-negative")
        eid = str(uuid4())
        now = _now_iso()
        entry = PortfolioEntry(
            id=eid,
            portfolio_id=portfolio_id,
            name=name,
            category=category,
            platform=platform,
            amount=float(amount),
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        self.session.add(entry)
        self.session.commit()
        return self.get(eid, user_id=user_id)  # type: ignore[return-value]

    def get(self, entry_id: str, *, user_id: str) -> dict[str, Any] | None:
        info = self._portfolio_for_entry(entry_id)
        if info is None or info[1] != user_id:
            return None
        row = self.session.execute(
            select(PortfolioEntry).where(PortfolioEntry.id == entry_id)
        ).scalar_one_or_none()
        return _row_to_entry(row) if row else None

    def list(
        self, *, portfolio_id: str, user_id: str,
        category: str | None = None, platform: str | None = None,
        search: str | None = None, sort: str = "updated_at_desc",
    ) -> list[dict[str, Any]]:
        self._assert_portfolio_owner(portfolio_id, user_id)
        conditions = [PortfolioEntry.portfolio_id == portfolio_id]
        if category:
            conditions.append(PortfolioEntry.category == category)
        if platform:
            conditions.append(PortfolioEntry.platform == platform)
        if search:
            conditions.append(PortfolioEntry.name.ilike(f"%{search}%"))

        order_map = {
            "updated_at_desc": PortfolioEntry.updated_at.desc(),
            "updated_at_asc": PortfolioEntry.updated_at.asc(),
            "amount_desc": PortfolioEntry.amount.desc(),
            "amount_asc": PortfolioEntry.amount.asc(),
            "name_asc": PortfolioEntry.name.asc(),
            "name_desc": PortfolioEntry.name.desc(),
        }
        order = order_map.get(sort, PortfolioEntry.updated_at.desc())
        rows = self.session.execute(
            select(PortfolioEntry).where(*conditions).order_by(order)
        ).scalars().all()
        return [_row_to_entry(r) for r in rows]

    def update(self, entry_id: str, *, user_id: str, **fields: Any) -> dict[str, Any] | None:
        info = self._portfolio_for_entry(entry_id)
        if info is None:
            return None
        if info[1] != user_id:
            raise PermissionError("entry not owned by user")

        allowed = {"name", "category", "platform", "amount", "notes"}
        nullable = {"platform", "notes"}
        updates = {
            k: v for k, v in fields.items()
            if k in allowed and (v is not None or k in nullable)
        }
        if "amount" in updates and updates["amount"] is not None and updates["amount"] < 0:
            raise ValueError("amount must be non-negative")
        if not updates:
            return self.get(entry_id, user_id=user_id)
        updates["updated_at"] = _now_iso()
        self.session.execute(
            update(PortfolioEntry).where(PortfolioEntry.id == entry_id).values(**updates)
        )
        self.session.commit()
        return self.get(entry_id, user_id=user_id)

    def delete(self, entry_id: str, *, user_id: str) -> bool:
        info = self._portfolio_for_entry(entry_id)
        if info is None:
            return False
        if info[1] != user_id:
            raise PermissionError("entry not owned by user")
        self.session.execute(delete(PortfolioEntry).where(PortfolioEntry.id == entry_id))
        self.session.commit()
        return True

    def batch_delete(self, ids: list[str], *, user_id: str) -> int:
        if not ids:
            return 0
        # Subquery: entry ids that belong to the user's portfolios
        owned_portfolio_ids = select(Portfolio.id).where(Portfolio.user_id == user_id).scalar_subquery()
        result = self.session.execute(
            delete(PortfolioEntry)
            .where(PortfolioEntry.id.in_(ids), PortfolioEntry.portfolio_id.in_(owned_portfolio_ids))
        )
        self.session.commit()
        return result.rowcount


# ---------------------------------------------------------------------------
# CategoryService
# ---------------------------------------------------------------------------

class CategoryService:
    def __init__(self, session: Session):
        self.session = session

    def list(self, *, user_id: str) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(PortfolioCategory)
            .where(
                (PortfolioCategory.user_id.is_(None)) | (PortfolioCategory.user_id == user_id)
            )
            .order_by(PortfolioCategory.sort_order, PortfolioCategory.name)
        ).scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "kind": r.kind,
                "sort_order": r.sort_order,
                "is_preset": r.user_id is None,
            }
            for r in rows
        ]

    def create(self, *, user_id: str, name: str, kind: str) -> dict[str, Any]:
        if kind not in ("asset", "liability"):
            raise ValueError("kind must be 'asset' or 'liability'")
        # Check for collision with presets OR user's own categories
        existing = self.session.execute(
            select(PortfolioCategory).where(
                PortfolioCategory.name == name,
                (PortfolioCategory.user_id.is_(None)) | (PortfolioCategory.user_id == user_id),
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"category name '{name}' already exists")
        cid = str(uuid4())
        try:
            stmt = pg_insert(PortfolioCategory).values(
                id=cid, user_id=user_id, name=name, kind=kind, sort_order=100
            )
            self.session.execute(stmt)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise ValueError(f"category name '{name}' already exists")
        return {"id": cid, "name": name, "kind": kind, "sort_order": 100, "is_preset": False}

    def entry_count(self, *, user_id: str, name: str) -> int:
        count = self.session.execute(
            select(func.count(PortfolioEntry.id))
            .join(Portfolio, Portfolio.id == PortfolioEntry.portfolio_id)
            .where(Portfolio.user_id == user_id, PortfolioEntry.category == name)
        ).scalar_one()
        return int(count)

    def delete(self, cat_id: str, *, user_id: str) -> tuple[bool, str, int]:
        row = self.session.execute(
            select(PortfolioCategory).where(PortfolioCategory.id == cat_id)
        ).scalar_one_or_none()
        if row is None:
            return False, "not_found", 0
        if row.user_id is None:
            return False, "preset_readonly", 0
        if row.user_id != user_id:
            return False, "not_found", 0
        count = self.entry_count(user_id=user_id, name=row.name)
        if count > 0:
            return False, "has_entries", count
        self.session.execute(delete(PortfolioCategory).where(PortfolioCategory.id == cat_id))
        self.session.commit()
        return True, "", 0


# ---------------------------------------------------------------------------
# CsvService
# ---------------------------------------------------------------------------

class CsvService:
    def __init__(self, session: Session):
        self.session = session

    def import_csv(self, *, portfolio_id: str, user_id: str, csv_text: str) -> dict[str, Any]:
        # Assert ownership once upfront
        portfolio = self.session.execute(
            select(Portfolio.user_id).where(Portfolio.id == portfolio_id)
        ).scalar_one_or_none()
        if portfolio is None or portfolio != user_id:
            raise PermissionError("portfolio not found")

        rows, errors = parse_csv_rows(csv_text)
        if not rows:
            return {"inserted": 0, "skipped": len(errors), "errors": errors}

        known_cats = self.session.execute(
            select(PortfolioCategory.name).where(
                (PortfolioCategory.user_id.is_(None)) | (PortfolioCategory.user_id == user_id)
            )
        ).scalars().all()
        known = set(known_cats)
        now = _now_iso()
        inserted = 0

        for r in rows:
            if r["category"] not in known:
                stmt = pg_insert(PortfolioCategory).values(
                    id=str(uuid4()), user_id=user_id, name=r["category"], kind="asset", sort_order=100
                ).on_conflict_do_nothing()
                self.session.execute(stmt)
                known.add(r["category"])
            entry = PortfolioEntry(
                id=str(uuid4()),
                portfolio_id=portfolio_id,
                name=r["name"],
                category=r["category"],
                platform=r["platform"],
                amount=r["amount"],
                notes=r["notes"],
                created_at=now,
                updated_at=now,
            )
            self.session.add(entry)
            inserted += 1

        self.session.commit()
        return {"inserted": inserted, "skipped": len(errors), "errors": errors}

    def export_csv(self, *, portfolio_id: str, user_id: str) -> str | None:
        portfolio = self.session.execute(
            select(Portfolio.user_id).where(Portfolio.id == portfolio_id)
        ).scalar_one_or_none()
        if portfolio is None or portfolio != user_id:
            return None
        entries = self.session.execute(
            select(PortfolioEntry)
            .where(PortfolioEntry.portfolio_id == portfolio_id)
            .order_by(PortfolioEntry.updated_at.desc())
        ).scalars().all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(CSV_COLUMNS)
        for e in entries:
            writer.writerow([e.name, e.category, e.platform or "", e.amount, e.notes])
        return buf.getvalue()


# ---------------------------------------------------------------------------
# SummaryService
# ---------------------------------------------------------------------------

class SummaryService:
    def __init__(self, session: Session):
        self.session = session

    def build(self, portfolio_id: str, *, user_id: str) -> dict[str, Any] | None:
        pf = self.session.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        ).scalar_one_or_none()
        if pf is None:
            return None

        cats = self.session.execute(
            select(PortfolioCategory.name, PortfolioCategory.kind).where(
                (PortfolioCategory.user_id.is_(None)) | (PortfolioCategory.user_id == user_id)
            )
        ).all()
        kind_map = {c.name: c.kind for c in cats}

        entries = self.session.execute(
            select(
                PortfolioEntry.name,
                PortfolioEntry.category,
                PortfolioEntry.platform,
                PortfolioEntry.amount,
            ).where(PortfolioEntry.portfolio_id == portfolio_id)
        ).all()

        totals_assets = 0.0
        totals_liab = 0.0
        by_category: dict[str, dict[str, Any]] = {}
        by_platform: dict[str, dict[str, Any]] = {}
        for e in entries:
            kind = kind_map.get(e.category, "asset")
            if kind == "liability":
                totals_liab += e.amount
            else:
                totals_assets += e.amount

            cb = by_category.setdefault(
                e.category,
                {"name": e.category, "kind": kind, "total": 0.0, "count": 0},
            )
            cb["total"] += e.amount
            cb["count"] += 1

            platform = e.platform or ""
            pb = by_platform.setdefault(
                platform, {"name": platform, "total": 0.0, "count": 0}
            )
            pb["total"] += e.amount
            pb["count"] += 1

        return {
            "portfolio": {"id": pf.id, "name": pf.name, "currency": pf.currency},
            "totals": {
                "assets": round(totals_assets, 2),
                "liabilities": round(totals_liab, 2),
                "net_worth": round(totals_assets - totals_liab, 2),
            },
            "by_category": sorted(
                ({**c, "total": round(c["total"], 2)} for c in by_category.values()),
                key=lambda x: -x["total"],
            ),
            "by_platform": sorted(
                ({**p, "total": round(p["total"], 2)} for p in by_platform.values()),
                key=lambda x: -x["total"],
            ),
        }
