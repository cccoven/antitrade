"""APScheduler background jobs for radar and notification delivery."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    AUTOMATION_POLL_SECONDS,
    AUTOMATION_TASKS_ENABLED,
    DAILY_MARKET_BRIEFING_REFRESH_MINUTES,
    FEED_BRIEFING_MINUTES, FEED_BRIEFING_WINDOW_HOURS, FEED_INGEST_MINUTES,
    MARKET_OVERVIEW_REFRESH_SECONDS,
)

logger = logging.getLogger(__name__)


def _run_ingest() -> None:
    from db import SessionLocal
    from services.feed_ingest import ingest_all
    session = SessionLocal()
    try:
        ingest_all(session)
    except Exception:
        logger.warning("radar scheduled ingest failed", exc_info=True)
    finally:
        session.close()


def _run_briefing() -> None:
    from db import SessionLocal
    from services.feed_briefing import generate_briefing
    session = SessionLocal()
    try:
        for lang in ("en", "zh"):
            try:
                generate_briefing(session, lang=lang, window_hours=FEED_BRIEFING_WINDOW_HOURS)
            except Exception:
                logger.warning("radar scheduled briefing failed (lang=%s)", lang, exc_info=True)
    finally:
        session.close()


def _run_market_overview_refresh() -> None:
    from services.market_overview_snapshot import refresh_market_overview_snapshot

    try:
        refresh_market_overview_snapshot()
    except Exception:
        logger.warning("market overview scheduled refresh failed", exc_info=True)


def _run_daily_market_briefing_refresh() -> None:
    from db import SessionLocal
    from services.market_briefing import get_daily_market_briefing

    session = SessionLocal()
    try:
        for lang in ("en", "zh"):
            try:
                asyncio.run(get_daily_market_briefing(
                    session=session,
                    lang=lang,
                    force_refresh=True,
                ))
            except Exception:
                logger.warning(
                    "daily market briefing refresh failed (lang=%s)",
                    lang,
                    exc_info=True,
                )
    finally:
        session.close()


def _run_notification_dispatch() -> None:
    from db import SessionLocal
    from services.notification_dispatch import dispatch_pending

    session = SessionLocal()
    try:
        dispatch_pending(session)
    except Exception:
        logger.warning("notification dispatch failed", exc_info=True)
        session.rollback()
    finally:
        session.close()


def _run_notification_cleanup() -> None:
    from db import SessionLocal
    from services.notifications import NotificationService

    session = SessionLocal()
    try:
        deleted = NotificationService(session).cleanup()
        if deleted:
            logger.info("notification retention cleanup deleted %s events", deleted)
    except Exception:
        logger.warning("notification retention cleanup failed", exc_info=True)
        session.rollback()
    finally:
        session.close()


def _run_due_automations() -> None:
    if not AUTOMATION_TASKS_ENABLED:
        return
    from db import SessionLocal
    from services.automation import AutomationModule

    session = SessionLocal()
    try:
        AutomationModule(session).run_due(limit=50)
    except Exception:
        logger.warning("automation due-task poll failed", exc_info=True)
        session.rollback()
    finally:
        session.close()


def _run_market_main_open_publish() -> None:
    from db import SessionLocal
    from services.market_hours import list_market_main_openings
    from services.notifications import (
        NotificationContent,
        NotificationEventInput,
        NotificationService,
        utc_now,
    )

    now = utc_now()
    session = SessionLocal()
    try:
        service = NotificationService(session)
        for opening in list_market_main_openings(now - timedelta(minutes=10), now):
            local_time = opening.starts_at.astimezone(ZoneInfo(opening.timezone))
            local_label = f"{local_time:%Y-%m-%d %H:%M} ({opening.timezone})"
            service.publish(NotificationEventInput(
                event_key=(
                    f"market.session.main_opened:{opening.market_id}:"
                    f"{opening.starts_at.isoformat()}"
                ),
                event_type="market.session.main_opened",
                source="market_hours",
                subject_type="market",
                subject_id=opening.market_id,
                occurred_at=opening.starts_at,
                expires_at=opening.starts_at + timedelta(minutes=10),
                content={
                    "zh": NotificationContent(
                        title=f"{opening.market_name['zh']}已开盘",
                        body=f"主盘交易时段现已开始。市场当地时间：{local_label}",
                        action_url="/market-hours",
                    ),
                    "en": NotificationContent(
                        title=f"{opening.market_name['en']} is open",
                        body=f"The main trading session has started. Market time: {local_label}",
                        action_url="/market-hours",
                    ),
                },
                data={
                    "market_id": opening.market_id,
                    "session_kind": "main",
                    "timezone": opening.timezone,
                    "local_trade_date": opening.local_trade_date.isoformat(),
                },
            ))
    except Exception:
        logger.warning("market opening notification publish failed", exc_info=True)
        session.rollback()
    finally:
        session.close()


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    now = datetime.now(timezone.utc)
    sched.add_job(_run_ingest, IntervalTrigger(minutes=FEED_INGEST_MINUTES),
                  id="radar_ingest", replace_existing=True)
    sched.add_job(_run_briefing, IntervalTrigger(minutes=FEED_BRIEFING_MINUTES),
                  id="radar_briefing", replace_existing=True)
    sched.add_job(_run_notification_dispatch, IntervalTrigger(seconds=15),
                  id="notification_dispatch", replace_existing=True, max_instances=1)
    sched.add_job(_run_notification_cleanup, IntervalTrigger(hours=24),
                  id="notification_cleanup", replace_existing=True, max_instances=1)
    sched.add_job(_run_market_main_open_publish, IntervalTrigger(seconds=30),
                  id="market_main_open_publish", replace_existing=True, max_instances=1)
    sched.add_job(_run_due_automations, IntervalTrigger(seconds=AUTOMATION_POLL_SECONDS),
                  id="automation_due_tasks", replace_existing=True, max_instances=1)
    sched.add_job(
        _run_market_overview_refresh,
        IntervalTrigger(seconds=MARKET_OVERVIEW_REFRESH_SECONDS),
        id="market_overview_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now,
    )
    sched.add_job(
        _run_daily_market_briefing_refresh,
        IntervalTrigger(minutes=DAILY_MARKET_BRIEFING_REFRESH_MINUTES),
        id="daily_market_briefing_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now,
    )
    return sched


_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    from config import SCHEDULER_ENABLED
    if not SCHEDULER_ENABLED or _scheduler is not None:
        return
    _scheduler = build_scheduler()
    _scheduler.start()
    from services.market_hours import missing_notification_calendar_years
    missing_years = missing_notification_calendar_years()
    if missing_years:
        logger.warning("notification market calendars are not verified for years: %s", missing_years)
    logger.info("background scheduler started")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
