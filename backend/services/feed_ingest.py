"""Feed ingestion: fetch → parse → dedupe → classify → store. Per-source isolated."""

import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import FeedItem
from services.feed_language import detect_feed_language
from services.feed_sources import FeedSource, enabled_sources
from services.feed_taxonomy import classify

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; AntiTradeRadar/1.0)"

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Titles sometimes arrive wrapped in HTML (e.g. <b>…</b>). Keep plain text."""
    return _TAG_RE.sub("", text).strip()


def _entry_url(entry) -> str | None:
    return entry.get("link") or entry.get("id")


def _entry_summary(entry) -> str:
    return (entry.get("summary") or entry.get("description") or "")[:2000]


def _entry_published(entry) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()


def ingest_entries(session: Session, source: FeedSource, entries: list) -> int:
    """Insert classified, de-duplicated items from parsed entries. Returns insert count."""
    inserted = 0
    seen: set[str] = set()
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        url = _entry_url(entry)
        if not url or url in seen:
            continue
        exists = session.execute(
            select(FeedItem.id).where(FeedItem.url == url)
        ).scalar_one_or_none()
        if exists:
            continue
        seen.add(url)
        title = _strip_html(entry.get("title", ""))
        summary = _entry_summary(entry)
        category, symbols = classify(title, summary)
        session.add(FeedItem(
            id=str(uuid4()), url=url, source_key=source.key,
            title=title, summary=summary,
            published_at=_entry_published(entry), fetched_at=now,
            category=category, symbols=symbols,
            lang=detect_feed_language(title, summary, source.lang),
        ))
        inserted += 1
    return inserted


def repair_feed_item_languages(session: Session) -> int:
    """Correct legacy rows whose source language does not match their content."""
    repaired = 0
    items = session.execute(select(FeedItem)).scalars().all()
    for item in items:
        detected = detect_feed_language(item.title, item.summary, item.lang)
        if detected == item.lang:
            continue
        item.lang = detected
        repaired += 1
    if repaired:
        session.commit()
    return repaired


def ingest_source(session: Session, source: FeedSource) -> int:
    """Fetch + parse + ingest ONE source. Isolated: logs and returns 0 on failure."""
    try:
        parsed = feedparser.parse(source.url, request_headers={"User-Agent": _UA})
        entries = parsed.get("entries", [])
        n = ingest_entries(session, source, entries)
        session.commit()
        logger.info("radar ingest %s: %d new", source.key, n)
        return n
    except Exception:
        session.rollback()
        logger.warning("radar ingest failed for %s", source.key, exc_info=True)
        return 0


def ingest_all(session: Session) -> int:
    """Ingest every enabled source. One source failing never blocks others."""
    return sum(ingest_source(session, s) for s in enabled_sources())
