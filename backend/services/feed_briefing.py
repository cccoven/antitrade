"""Batch briefing: fold recent feed items into a highlights + categories JSON."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from i18n import t
from models import FeedBriefing, FeedItem
from services.feed_language import (
    briefing_content_matches_language,
    feed_text_matches_language,
)

logger = logging.getLogger(__name__)


def _recent_items(session: Session, window_hours: int, lang: str) -> list[FeedItem]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    # published_at is ISO8601 text; lexical compare works for same-format UTC strings.
    # Scope to the briefing's language so an "en" briefing never folds in zh items
    # (titles pass through verbatim, so mixing languages leaks the wrong script).
    items = session.execute(
        select(FeedItem)
        .where(FeedItem.fetched_at >= cutoff, FeedItem.lang == lang)
        .order_by(FeedItem.fetched_at.desc())
        .limit(80)
    ).scalars().all()
    return [
        item for item in items
        if feed_text_matches_language(item.title, item.summary, lang)
    ]


def build_rule_briefing(items: list[FeedItem]) -> dict:
    """Deterministic fallback briefing: no LLM. Groups by category."""
    by_cat: dict[str, list[FeedItem]] = defaultdict(list)
    for it in items:
        by_cat[it.category].append(it)

    hot = [{"title": it.title, "sources": 1, "id": it.id} for it in items[:5]]
    sections = [
        {"category": cat,
         "points": [{"text": i.title, "id": i.id} for i in cat_items[:5]]}
        for cat, cat_items in by_cat.items()
    ]
    return {"hot": hot, "sections": sections}


def _build_prompt(items: list[FeedItem], lang: str) -> str:
    # Enumerate with a stable index so the model can reference the source item
    # it drew each highlight/point from; we resolve the index back to an id.
    lines = [f"[{i}] [{it.category}] {it.title} ({it.source_key})"
             for i, it in enumerate(items)]
    return t("feed.briefing_prompt", lang,
             lang_name=t("feed.lang_name", lang), items="\n".join(lines))


def _resolve_refs(content: dict, items: list[FeedItem]) -> dict:
    """Map each entry's `ref` index back to a feed item id (best-effort).

    Normalizes to the storage shape the frontend expects:
      hot:      [{title, sources, id?}]
      sections: [{category, points: [{text, id?}]}]
    A missing/out-of-range ref simply yields no id (entry stays non-clickable).
    """
    def id_for(ref) -> str | None:
        return items[ref].id if isinstance(ref, int) and 0 <= ref < len(items) else None

    for h in content.get("hot", []):
        if isinstance(h, dict):
            rid = id_for(h.pop("ref", None))
            if rid:
                h["id"] = rid
    for s in content.get("sections", []):
        pts = s.get("points", []) if isinstance(s, dict) else []
        norm = []
        for p in pts:
            if isinstance(p, dict):
                rid = id_for(p.pop("ref", None))
                norm.append({"text": p.get("text", ""), **({"id": rid} if rid else {})})
            else:
                norm.append({"text": str(p)})
        if isinstance(s, dict):
            s["points"] = norm
    return content


def _valid_briefing(content) -> bool:
    if not isinstance(content, dict):
        return False
    hot, sections = content.get("hot"), content.get("sections")
    if not isinstance(hot, list) or not isinstance(sections, list):
        return False
    if not all(isinstance(h, dict) and "title" in h for h in hot):
        return False
    if not all(isinstance(s, dict) and "category" in s and isinstance(s.get("points"), list)
               for s in sections):
        return False
    return True


async def _llm_briefing(items: list[FeedItem], lang: str) -> tuple[dict, str] | None:
    from services.analyzer import create_provider
    provider = create_provider()
    if provider.__class__.__name__ == "DemoProvider":
        return None  # demo → use rule fallback
    try:
        raw = await provider.complete(_build_prompt(items, lang))
        content = json.loads(raw)
        if (
            _valid_briefing(content)
            and briefing_content_matches_language(content, lang)
        ):
            return _resolve_refs(content, items), provider.__class__.__name__
    except Exception:
        logger.warning("radar briefing LLM failed, using rule fallback", exc_info=True)
    return None


def generate_briefing(session: Session, lang: str, window_hours: int) -> FeedBriefing | None:
    """Generate + persist a briefing for the window. Returns None when no items."""
    items = _recent_items(session, window_hours, lang)
    if not items:
        return None

    content, model = build_rule_briefing(items), "rule"
    # LLM path is best-effort; the demo provider short-circuits to the rule fallback.
    try:
        import asyncio
        llm = asyncio.run(_llm_briefing(items, lang))
        if llm is not None:
            content, model = llm
    except RuntimeError:
        # Only trips if called from an already-running event loop (async caller);
        # the scheduler calls this from a sync worker thread, so asyncio.run works there.
        logger.warning("radar briefing could not run LLM path, using rule fallback", exc_info=True)

    briefing = FeedBriefing(
        id=str(uuid4()), generated_at=datetime.now(timezone.utc).isoformat(),
        lang=lang, window=f"{window_hours}h", content=content, model=model,
    )
    session.add(briefing)
    session.commit()
    return briefing
