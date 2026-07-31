"""Turn a ToolApprovalItem into a human-readable confirmation payload."""

import json

from i18n import t


_TOOL_META = {
    "create_trade": ("create", "trade"),
    "update_trade": ("update", "trade"),
    "delete_trades": ("delete", "trade"),
    "tag_trades": ("tag", "trade"),
    "create_portfolio": ("create", "portfolio"),
    "update_portfolio": ("update", "portfolio"),
    "delete_portfolio": ("delete", "portfolio"),
    "create_entry": ("create", "entry"),
    "update_entry": ("update", "entry"),
    "delete_entries": ("delete", "entry"),
    "create_strategy": ("create", "strategy"),
    "update_strategy": ("update", "strategy"),
    "delete_strategy": ("delete", "strategy"),
    "remember_memory": ("create", "memory"),
    "forget_memories": ("delete", "memory"),
    "create_automation_task": ("create", "automation_task"),
    "update_automation_task": ("update", "automation_task"),
    "delete_automation_task": ("delete", "automation_task"),
}


def _args(item) -> dict:
    raw = getattr(item.raw_item, "arguments", "") or "{}"
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _trade_labels(session, user_id: str, ids: list[str]) -> list[dict]:
    from services.journal import JournalService

    rows = JournalService(session).list_trades_by_ids(ids, user_id=user_id)
    out = []
    for row in rows:
        pnl = row.get("pnl")
        pnl_txt = f"{pnl:+g}" if isinstance(pnl, (int, float)) else ""
        out.append(
            {
                "label": f"{row.get('symbol', '?')} {row.get('direction', '')} {pnl_txt}".strip(),
                "sub": row.get("open_time") or "",
            }
        )
    return out


def _memory_labels(session, user_id: str, ids: list[str]) -> list[dict]:
    from services.memory import AssistantMemoryService

    return [
        {"label": row["content"], "sub": ""}
        for row in AssistantMemoryService(session).list_by_ids(user_id, ids)
    ]


def _entry_labels(session, user_id: str, ids: list[str]) -> list[dict]:
    from services.portfolio import EntryService

    service = EntryService(session)
    preview = []
    for entry_id in ids:
        row = service.get(entry_id, user_id=user_id)
        if row is None:
            preview.append({"label": entry_id, "sub": ""})
            continue
        platform = f" · {row['platform']}" if row.get("platform") else ""
        preview.append({
            "label": f"{row['name']} · {row['amount']:g}",
            "sub": f"{row['category']}{platform}",
        })
    return preview


def _target_preview(session, user_id: str, entity: str, target: str) -> list[dict]:
    if entity == "trade":
        return _trade_labels(session, user_id, [target]) or [{"label": target, "sub": ""}]
    if entity == "entry":
        return _entry_labels(session, user_id, [target])
    if entity == "portfolio":
        from services.portfolio import PortfoliosService

        row = PortfoliosService(session).get(target, user_id=user_id)
        if row:
            return [{
                "label": f"{row['name']} · {row['currency']}",
                "sub": f"{row['entry_count']} entries",
            }]
    if entity == "strategy":
        from services.strategies import StrategyService

        row = StrategyService(session).get_strategy(user_id, target)
        if row:
            return [{"label": row["title"], "sub": ", ".join(row.get("tags", []))}]
    return [{"label": target, "sub": ""}]


def _format_arg(value) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    elif value is None:
        text = "null"
    else:
        text = str(value)
    return text if len(text) <= 240 else f"{text[:240]}…"


def _argument_preview(args: dict, *, exclude: set[str] | None = None) -> list[dict]:
    hidden = exclude or set()
    return [
        {"label": f"{key}: {_format_arg(value)}", "sub": ""}
        for key, value in args.items()
        if key not in hidden
    ]


def enrich_interruption(session, user_id: str, item, lang: str = "zh") -> dict:
    tool_name = item.name
    call_id = item.raw_item.call_id
    action, entity = _TOOL_META.get(tool_name, ("update", "generic"))
    args = _args(item)

    preview: list[dict] = []
    n = 0

    if tool_name in ("delete_trades", "tag_trades"):
        ids = args.get("trade_ids", []) or []
        n = len(ids)
        preview = _trade_labels(session, user_id, ids)
        preview += _argument_preview(args, exclude={"trade_ids"})
    elif tool_name == "forget_memories":
        ids = args.get("memory_ids", []) or []
        n = len(ids)
        preview = _memory_labels(session, user_id, ids)
    elif tool_name == "delete_entries":
        ids = args.get("entry_ids", []) or []
        n = len(ids)
        preview = _entry_labels(session, user_id, ids)
    elif tool_name == "remember_memory":
        content = str(args.get("content") or "")
        preview = [{"label": content, "sub": ""}] if content else []
    elif action == "create":
        preview = _argument_preview(args)
    elif action in ("update", "delete"):
        key = {
            "trade": "trade_id",
            "portfolio": "portfolio_id",
            "entry": "entry_id",
            "strategy": "strategy_id",
            "automation_task": "task_id",
        }.get(entity)
        target = args.get(key) if key else None
        if target:
            preview = _target_preview(session, user_id, entity, str(target))
        preview += _argument_preview(args, exclude={key} if key else set())

    title_key = f"action.{action}.{entity}"
    title = t(title_key, lang)
    if title == title_key:
        title = t("action.generic", lang)
    if "{n}" in title:
        title = title.format(n=n)

    return {
        "call_id": call_id,
        "tool_name": tool_name,
        "action": action,
        "entity": entity,
        "title": title,
        "preview": preview,
    }
