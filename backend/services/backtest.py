"""Backtest strategy persistence and restart-safe run orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pandas as pd
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backtest_schema import StrategyConfigModel, normalize_date_range
from models import BacktestRun, BacktestStrategy
from services.market_data import resolve_legacy_series_id
from services.market_data_runtime import get_market_data_gateway
from services.market_gateway import CandleQuery, MarketDataError

logger = logging.getLogger(__name__)


class BacktestService:
    """Expose strategy and run operations through one small interface."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Strategy persistence
    # ------------------------------------------------------------------

    def create_strategy(self, user_id: str, name: str, config: dict) -> dict:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Strategy name is required")
        normalized_config = self._normalize_config(config)
        now = self._now()
        strategy = BacktestStrategy(
            id=str(uuid4()),
            user_id=user_id,
            name=normalized_name,
            config=json.dumps(normalized_config, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        self.session.add(strategy)
        self.session.commit()
        return self._strategy_to_dict(strategy)

    def list_strategies(self, user_id: str) -> list[dict]:
        rows = self.session.execute(
            select(BacktestStrategy)
            .where(BacktestStrategy.user_id == user_id)
            .order_by(BacktestStrategy.created_at.desc())
        ).scalars().all()
        return [self._strategy_to_dict(row) for row in rows]

    def get_strategy(self, user_id: str, strategy_id: str) -> dict | None:
        row = self.session.execute(
            select(BacktestStrategy).where(
                BacktestStrategy.id == strategy_id,
                BacktestStrategy.user_id == user_id,
            )
        ).scalar_one_or_none()
        return self._strategy_to_dict(row) if row else None

    def update_strategy(
        self,
        user_id: str,
        strategy_id: str,
        name: str | None = None,
        config: dict | None = None,
    ) -> dict | None:
        row = self.session.execute(
            select(BacktestStrategy).where(
                BacktestStrategy.id == strategy_id,
                BacktestStrategy.user_id == user_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None

        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise ValueError("Strategy name is required")
            row.name = normalized_name
        if config is not None:
            row.config = json.dumps(self._normalize_config(config), ensure_ascii=False)
        row.updated_at = self._now()
        self.session.commit()
        return self._strategy_to_dict(row)

    def delete_strategy(self, user_id: str, strategy_id: str) -> bool:
        result = self.session.execute(
            delete(BacktestStrategy).where(
                BacktestStrategy.id == strategy_id,
                BacktestStrategy.user_id == user_id,
            )
        )
        self.session.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Persistent runs
    # ------------------------------------------------------------------

    def create_run(
        self,
        user_id: str,
        strategy_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        strategy = self.get_strategy(user_id, strategy_id)
        if strategy is None:
            raise ValueError("Strategy not found")
        return self._create_run_record(
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_name=strategy["name"],
            strategy_config=strategy["config"],
            run_kind="standard",
            analysis_config=None,
            date_from=date_from,
            date_to=date_to,
        )

    def create_analysis_run(
        self,
        user_id: str,
        strategy_id: str,
        *,
        run_kind: str,
        analysis_config: dict,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        if run_kind not in {"optimization", "validation", "walk_forward"}:
            raise ValueError(f"Unsupported backtest run kind: {run_kind}")
        strategy = self.get_strategy(user_id, strategy_id)
        if strategy is None:
            raise ValueError("Strategy not found")
        return self._create_run_record(
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_name=strategy["name"],
            strategy_config=strategy["config"],
            run_kind=run_kind,
            analysis_config=analysis_config,
            date_from=date_from,
            date_to=date_to,
        )

    def rerun(self, user_id: str, run_id: str) -> dict | None:
        source = self.session.execute(
            select(BacktestRun).where(
                BacktestRun.id == run_id,
                BacktestRun.user_id == user_id,
            )
        ).scalar_one_or_none()
        if source is None:
            return None
        return self._create_run_record(
            user_id=user_id,
            strategy_id=source.strategy_id,
            strategy_name=source.strategy_name,
            strategy_config=self._load_json(source.strategy_config),
            run_kind=source.run_kind,
            analysis_config=(
                self._load_json(source.analysis_config)
                if source.analysis_config
                else None
            ),
            date_from=source.requested_date_from,
            date_to=source.requested_date_to,
        )

    def _create_run_record(
        self,
        *,
        user_id: str,
        strategy_id: str | None,
        strategy_name: str,
        strategy_config: dict,
        run_kind: str,
        analysis_config: dict | None,
        date_from: str | None,
        date_to: str | None,
    ) -> dict:
        date_from, date_to = normalize_date_range(date_from, date_to)
        normalized_config = self._normalize_config(strategy_config)
        now = self._now()
        run = BacktestRun(
            id=str(uuid4()),
            strategy_id=strategy_id,
            user_id=user_id,
            strategy_name=strategy_name,
            strategy_config=json.dumps(normalized_config, ensure_ascii=False),
            run_kind=run_kind,
            analysis_config=(
                json.dumps(analysis_config, ensure_ascii=False)
                if analysis_config
                else None
            ),
            status="queued",
            requested_date_from=date_from,
            requested_date_to=date_to,
            actual_date_from=None,
            actual_date_to=None,
            result=None,
            error=None,
            created_at=now,
            started_at=None,
            completed_at=None,
            updated_at=now,
        )
        self.session.add(run)
        self.session.commit()
        self._schedule_run(run.id)
        return self._run_to_dict(run, include_result=False)

    def list_runs(
        self,
        user_id: str,
        *,
        strategy_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        query = select(BacktestRun).where(BacktestRun.user_id == user_id)
        if strategy_id:
            query = query.where(BacktestRun.strategy_id == strategy_id)
        if status:
            query = query.where(BacktestRun.status == status)
        rows = self.session.execute(
            query.order_by(BacktestRun.created_at.desc())
            .offset(max(offset, 0))
            .limit(min(max(limit, 1), 200))
        ).scalars().all()
        return [self._run_to_dict(row, include_result=False) for row in rows]

    def count_runs(
        self,
        user_id: str,
        *,
        strategy_id: str | None = None,
        status: str | None = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(BacktestRun)
            .where(BacktestRun.user_id == user_id)
        )
        if strategy_id:
            query = query.where(BacktestRun.strategy_id == strategy_id)
        if status:
            query = query.where(BacktestRun.status == status)
        return int(self.session.scalar(query) or 0)

    def get_run(self, user_id: str, run_id: str) -> dict | None:
        row = self.session.execute(
            select(BacktestRun).where(
                BacktestRun.id == run_id,
                BacktestRun.user_id == user_id,
            )
        ).scalar_one_or_none()
        return self._run_to_dict(row, include_result=True) if row else None

    def delete_run(self, user_id: str, run_id: str) -> bool:
        result = self.session.execute(
            delete(BacktestRun).where(
                BacktestRun.id == run_id,
                BacktestRun.user_id == user_id,
                BacktestRun.status.not_in(("queued", "running")),
            )
        )
        self.session.commit()
        return result.rowcount > 0

    # Backwards-compatible names while frontend callers migrate to /runs.
    run_backtest = create_run

    def get_backtest_job(self, job_id: str, user_id: str | None = None) -> dict | None:
        if user_id is None:
            row = self.session.get(BacktestRun, job_id)
            return self._run_to_dict(row, include_result=True) if row else None
        return self.get_run(user_id, job_id)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @staticmethod
    def _schedule_run(run_id: str) -> None:
        asyncio.get_running_loop().create_task(BacktestService.execute_run(run_id))

    @staticmethod
    async def execute_run(run_id: str) -> None:
        from db import SessionLocal

        with SessionLocal() as session:
            now = BacktestService._now()
            claimed = session.execute(
                update(BacktestRun)
                .where(
                    BacktestRun.id == run_id,
                    BacktestRun.status == "queued",
                )
                .values(
                    status="running",
                    started_at=now,
                    updated_at=now,
                    error=None,
                )
                .returning(
                    BacktestRun.strategy_config,
                    BacktestRun.run_kind,
                    BacktestRun.analysis_config,
                    BacktestRun.requested_date_from,
                    BacktestRun.requested_date_to,
                )
            ).mappings().one_or_none()
            if claimed is None:
                session.rollback()
                return
            session.commit()

            config = BacktestService._load_json(claimed["strategy_config"])
            run_kind = claimed["run_kind"]
            analysis_config = (
                BacktestService._load_json(claimed["analysis_config"])
                if claimed["analysis_config"]
                else {}
            )
            date_from = claimed["requested_date_from"]
            date_to = claimed["requested_date_to"]

        try:
            result, actual_from, actual_to = await BacktestService._calculate_result(
                config,
                date_from,
                date_to,
                run_kind=run_kind,
                analysis_config=analysis_config,
            )
        except Exception as exc:
            logger.exception("Backtest run failed", exc_info=exc)
            with SessionLocal() as session:
                run = session.get(BacktestRun, run_id)
                if run:
                    now = BacktestService._now()
                    run.status = "failed"
                    run.error = BacktestService._public_error(exc)
                    run.completed_at = now
                    run.updated_at = now
                    session.commit()
            return

        with SessionLocal() as session:
            run = session.get(BacktestRun, run_id)
            if run is None:
                return
            now = BacktestService._now()
            run.status = "completed"
            run.actual_date_from = actual_from
            run.actual_date_to = actual_to
            run.result = json.dumps(result, ensure_ascii=False)
            run.error = None
            run.completed_at = now
            run.updated_at = now
            session.commit()

    @staticmethod
    async def _calculate_result(
        config: dict,
        date_from: str | None,
        date_to: str | None,
        *,
        run_kind: str = "standard",
        analysis_config: dict | None = None,
    ) -> tuple[dict, str, str]:
        symbol = config["symbol"]
        interval = config["interval"]
        gateway = get_market_data_gateway()
        series_id = config.get("series_id") or resolve_legacy_series_id(
            gateway,
            symbol,
            "",
        )
        if not series_id:
            raise ValueError(f"Market symbol is unknown or ambiguous: {symbol}")

        query_end = BacktestService._backtest_query_time(date_to, end=True)
        if date_to is None:
            query_end = BacktestService._align_to_timeframe(query_end, interval)
        query_start = (
            BacktestService._backtest_query_time(date_from, end=False)
            if date_from
            else query_end - timedelta(days=config["lookback_months"] * 30)
        )
        candle_series = await asyncio.to_thread(
            gateway.get_candles,
            CandleQuery(
                series_id=series_id,
                timeframe=interval,
                start=query_start,
                end=query_end,
                purpose="backtest",
            ),
        )
        frame = pd.DataFrame(
            {
                "open": [candle.open for candle in candle_series.candles],
                "high": [candle.high for candle in candle_series.candles],
                "low": [candle.low for candle in candle_series.candles],
                "close": [candle.close for candle in candle_series.candles],
                "volume": [candle.volume for candle in candle_series.candles],
            },
            index=pd.DatetimeIndex(
                [candle.open_time for candle in candle_series.candles],
            ),
        )
        frame = BacktestService._filter_date_range(frame, date_from, date_to)
        if frame.empty:
            raise ValueError("No market data is available in the selected date range")

        if run_kind == "standard":
            from services.backtesting_py_adapter import BacktestingPyAdapter

            result = await asyncio.to_thread(BacktestingPyAdapter().run, config, frame)
        else:
            from services.backtest_analysis import BacktestAnalysis

            analysis = BacktestAnalysis()
            method = {
                "optimization": analysis.optimize,
                "validation": analysis.validate_out_of_sample,
                "walk_forward": analysis.walk_forward,
            }.get(run_kind)
            if method is None:
                raise ValueError(f"Unsupported backtest run kind: {run_kind}")
            result = await asyncio.to_thread(
                method,
                config,
                frame,
                analysis_config or {},
            )
        result["market_data"] = {
            "series_id": candle_series.series_id,
            "provider": candle_series.source.provider_id,
            "provider_symbol": candle_series.source.provider_symbol,
            "provider_exchange": candle_series.source.provider_exchange,
            "cache_status": candle_series.source.cache_status,
            "requested_start": candle_series.requested_start.isoformat(),
            "requested_end": candle_series.requested_end.isoformat(),
            "actual_start": candle_series.actual_start.isoformat(),
            "actual_end": candle_series.actual_end.isoformat(),
            "quality_status": candle_series.quality.status,
            "quality_warnings": list(candle_series.quality.warnings),
        }
        return (
            result,
            BacktestService._iso_index_value(frame.index[0]),
            BacktestService._iso_index_value(frame.index[-1]),
        )

    @staticmethod
    async def resume_pending_runs() -> int:
        """Requeue interrupted runs during application startup."""

        from db import SessionLocal

        with SessionLocal() as session:
            interrupted = session.execute(
                select(BacktestRun).where(
                    BacktestRun.status.in_(("queued", "running")),
                )
            ).scalars().all()
            for run in interrupted:
                run.status = "queued"
                run.started_at = None
                run.updated_at = BacktestService._now()
            session.commit()
            run_ids = [run.id for run in interrupted]

        for run_id in run_ids:
            BacktestService._schedule_run(run_id)
        return len(run_ids)

    # ------------------------------------------------------------------
    # Serialization and validation
    # ------------------------------------------------------------------

    @staticmethod
    def _strategy_to_dict(row: BacktestStrategy) -> dict:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "name": row.name,
            "config": BacktestService._normalize_config(
                BacktestService._load_json(row.config)
            ),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _run_to_dict(row: BacktestRun, *, include_result: bool) -> dict:
        payload = {
            "id": row.id,
            "run_id": row.id,
            "job_id": row.id,
            "strategy_id": row.strategy_id,
            "strategy_name": row.strategy_name,
            "strategy_config": BacktestService._normalize_config(
                BacktestService._load_json(row.strategy_config)
            ),
            "run_kind": row.run_kind,
            "analysis_config": (
                BacktestService._load_json(row.analysis_config)
                if row.analysis_config
                else None
            ),
            "status": row.status,
            "requested_date_from": row.requested_date_from,
            "requested_date_to": row.requested_date_to,
            "actual_date_from": row.actual_date_from,
            "actual_date_to": row.actual_date_to,
            "error": row.error,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "updated_at": row.updated_at,
        }
        if include_result:
            payload["result"] = (
                BacktestService._load_json(row.result) if row.result else None
            )
        return payload

    @staticmethod
    def _normalize_config(config: dict) -> dict:
        normalized = StrategyConfigModel.model_validate(config).model_dump(mode="json")
        gateway = get_market_data_gateway()
        series_id = normalized.get("series_id")
        if series_id:
            if not gateway.has_series(series_id):
                raise ValueError(f"Unknown market series: {series_id}")
            return normalized

        resolved = resolve_legacy_series_id(
            gateway,
            normalized["symbol"],
            "",
        )
        if resolved:
            normalized["series_id"] = resolved
        return normalized

    @staticmethod
    def _load_json(value: str) -> dict:
        try:
            loaded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _backtest_query_time(value: str | None, *, end: bool) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        if end and len(value) == 10:
            return parsed + timedelta(days=1)
        return parsed

    @staticmethod
    def _align_to_timeframe(value: datetime, timeframe: str) -> datetime:
        utc_value = value.astimezone(timezone.utc)
        if timeframe == "M":
            return utc_value.replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        if timeframe == "W":
            midnight = utc_value.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            return midnight - timedelta(days=midnight.weekday())
        seconds = {
            "1": 60,
            "5": 300,
            "15": 900,
            "60": 3600,
            "240": 14_400,
            "D": 86_400,
        }.get(timeframe)
        if seconds is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        aligned_timestamp = int(utc_value.timestamp()) // seconds * seconds
        return datetime.fromtimestamp(aligned_timestamp, timezone.utc)

    @staticmethod
    def _public_error(exc: Exception) -> str:
        if isinstance(exc, MarketDataError):
            return {
                "unsupported_timeframe": (
                    "The selected timeframe is not supported for this market"
                ),
                "coverage_unavailable": (
                    "Market data does not fully cover the selected period"
                ),
                "data_quality_rejected": (
                    "Market data failed validation for this backtest"
                ),
            }.get(exc.code, "Market data is temporarily unavailable")
        if isinstance(exc, ValueError):
            return str(exc)
        return "The backtest could not be completed"

    @staticmethod
    def _filter_date_range(
        frame: pd.DataFrame,
        date_from: str | None,
        date_to: str | None,
    ) -> pd.DataFrame:
        if not date_from and not date_to:
            return frame
        result = frame.copy()
        if not isinstance(result.index, pd.DatetimeIndex):
            result.index = pd.to_datetime(result.index, errors="coerce")
            result = result.loc[~result.index.isna()]

        def align(value: str) -> pd.Timestamp:
            timestamp = pd.Timestamp(value)
            if result.index.tz is not None and timestamp.tzinfo is None:
                return timestamp.tz_localize(result.index.tz)
            if result.index.tz is None and timestamp.tzinfo is not None:
                return timestamp.tz_localize(None)
            return timestamp

        if date_from:
            result = result.loc[result.index >= align(date_from)]
        if date_to:
            end = align(date_to)
            if len(date_to) == 10:
                result = result.loc[result.index < end + pd.Timedelta(days=1)]
            else:
                result = result.loc[result.index <= end]
        return result

    @staticmethod
    def _iso_index_value(value) -> str:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
