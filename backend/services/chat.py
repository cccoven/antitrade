"""Chat service — DB-backed multi-conversation AI assistant with tool calling."""

import asyncio
import base64
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from i18n import t
from models import ChatConversation, ChatMessage, ChatMessageAttachment, UploadedAsset
from services.uploads import SUPPORTED_IMAGE_TYPES

logger = logging.getLogger(__name__)

_TITLE_MAX = 30
_WORK_PREVIEW_MAX = 1200
_PENDING_APPROVAL_TTL = timedelta(minutes=30)
_MODEL_HISTORY_MAX_MESSAGES = 80
_MODEL_HISTORY_TOKEN_BUDGET = 24_000
MAX_CHAT_ATTACHMENTS = 4
MAX_CHAT_ATTACHMENT_BYTES = 16 * 1024 * 1024
_ARTIFACT_TOOL_TYPES = {
    "get_stock_market_data": "market_snapshot",
    "get_forex_market_data": "market_snapshot",
    "get_crypto_market_data": "market_snapshot",
    "get_futures_market_data": "market_snapshot",
    "check_trade_opportunity": "opportunity_check",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(value: Any) -> str:
    """Return a bounded, user-visible preview of real tool input/output."""
    if isinstance(value, str):
        try:
            value = json.dumps(json.loads(value), ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            pass
    elif value is not None:
        try:
            value = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            value = str(value)
    text = "" if value is None else str(value)
    if len(text) <= _WORK_PREVIEW_MAX:
        return text
    return f"{text[:_WORK_PREVIEW_MAX]}…"


def _new_work_log() -> dict:
    return {
        "status": "running",
        "started_at": _now(),
        "completed_at": None,
        "duration_ms": 0,
        "items": [],
    }


def _copy_work_log(work: dict) -> dict:
    return {**work, "items": [dict(item) for item in work.get("items", [])]}


def _finish_work_log(work: dict, status: str, segment_started: float) -> None:
    work["status"] = status
    work["completed_at"] = _now()
    work["duration_ms"] = int(work.get("duration_ms", 0) + (time.monotonic() - segment_started) * 1000)


def _reasoning_summary(raw_item: Any) -> str:
    """Expose provider-authored reasoning summaries, never private reasoning content."""
    summaries = getattr(raw_item, "summary", None) or []
    return "\n".join(
        text for summary in summaries
        if (text := getattr(summary, "text", "").strip())
    )


def _tool_artifact(tool_name: str, call_id: str, output: Any) -> dict | None:
    artifact_type = _ARTIFACT_TOOL_TYPES.get(tool_name)
    if artifact_type is None:
        return None
    if isinstance(output, str):
        try:
            data = json.loads(output)
        except (TypeError, ValueError):
            return None
    elif isinstance(output, dict):
        data = output
    else:
        return None
    return {
        "id": call_id,
        "type": artifact_type,
        "version": 1,
        "data": data,
    }


def _asset_dict(row: UploadedAsset) -> dict:
    return {
        "id": row.id,
        "url": f"/api/uploads/{row.id}",
        "original_name": row.original_name,
        "mime_type": row.mime_type,
        "width": row.width,
        "height": row.height,
        "size_bytes": row.size_bytes,
        "created_at": row.created_at,
    }


def _message_dict(
    row: ChatMessage, attachments: list[UploadedAsset] | None = None,
) -> dict:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "work": row.work_log,
        "artifacts": row.artifacts or [],
        "attachments": [_asset_dict(asset) for asset in attachments or []],
        "created_at": row.created_at,
    }


def _estimate_tokens(text: str) -> int:
    """Conservative tokenizer-free estimate for mixed Chinese/ASCII chat text."""
    non_ascii = sum(1 for char in text if ord(char) > 127)
    ascii_chars = len(text) - non_ascii
    return non_ascii + (ascii_chars + 3) // 4 + 4


def _input_text(content: str | list[dict]) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(
        str(part.get("text", ""))
        for part in content
        if isinstance(part, dict) and part.get("type") == "input_text"
    )


def _append_input_context(message: dict, context: str) -> dict:
    content = message["content"]
    if isinstance(content, str):
        return {**message, "content": f"{content}\n\n{context}"}

    parts = [dict(part) for part in content]
    for part in parts:
        if part.get("type") == "input_text":
            part["text"] = f"{part.get('text', '')}\n\n{context}"
            break
    else:
        parts.insert(0, {"type": "input_text", "text": context})
    return {**message, "content": parts}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ChatService:
    """Persists conversations/messages and streams tool-augmented answers."""

    def __init__(self, session: Session):
        self.session = session

    # ---- conversations ----------------------------------------------------

    def _first_sort_order(
        self,
        user_id: str,
    ) -> int:
        current_min = self.session.scalar(
            select(func.min(ChatConversation.sort_order)).where(
                ChatConversation.user_id == user_id,
            )
        )
        return current_min - 1 if current_min is not None else 0

    def _first_pinned_order(self, user_id: str) -> int:
        current_min = self.session.scalar(
            select(func.min(ChatConversation.pinned_order)).where(
                ChatConversation.user_id == user_id,
                ChatConversation.pinned_at.is_not(None),
            )
        )
        return current_min - 1 if current_min is not None else 0

    def create_conversation(self, user_id: str, title: str = "") -> dict:
        cid = str(uuid4())
        now = _now()
        conv = ChatConversation(
            id=cid,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
            sort_order=self._first_sort_order(user_id),
        )
        self.session.add(conv)
        self.session.commit()
        return {
            "id": cid,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "pinned_at": None,
            "sort_order": conv.sort_order,
        }

    def list_conversations(self, user_id: str) -> list[dict]:
        rows = self.session.execute(
            select(ChatConversation)
            .where(ChatConversation.user_id == user_id)
            .order_by(
                ChatConversation.pinned_at.is_(None),
                func.coalesce(ChatConversation.pinned_order, ChatConversation.sort_order),
                ChatConversation.updated_at.desc(),
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "pinned_at": r.pinned_at,
                "sort_order": r.sort_order,
            }
            for r in rows
        ]

    def get_conversation(self, conversation_id: str, user_id: str) -> dict | None:
        row = self.session.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "pinned_at": row.pinned_at,
            "sort_order": row.sort_order,
        }

    def update_conversation(
        self, conversation_id: str, user_id: str,
        *, title: str | None = None, pinned: bool | None = None,
    ) -> dict | None:
        row = self.session.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None

        now = _now()
        if title is not None:
            row.title = title
        if pinned is not None and pinned != (row.pinned_at is not None):
            if pinned:
                row.pinned_at = now
                row.pinned_order = self._first_pinned_order(user_id)
            else:
                row.pinned_at = None
                row.pinned_order = None
        row.updated_at = now
        self.session.commit()
        return self.get_conversation(conversation_id, user_id)

    def reorder_conversations(
        self,
        user_id: str,
        conversation_ids: list[str],
    ) -> list[dict] | None:
        if len(conversation_ids) != len(set(conversation_ids)):
            return None

        rows = self.session.execute(
            select(ChatConversation).where(ChatConversation.user_id == user_id)
        ).scalars().all()
        rows_by_id = {row.id: row for row in rows}
        if set(conversation_ids) != set(rows_by_id):
            return None

        available_sort_orders = sorted(
            row.sort_order for row in rows if row.pinned_at is None
        )
        unpinned_index = 0
        pinned_index = 0
        for conversation_id in conversation_ids:
            row = rows_by_id[conversation_id]
            if row.pinned_at is not None:
                row.pinned_order = pinned_index
                pinned_index += 1
            else:
                row.sort_order = available_sort_orders[unpinned_index]
                unpinned_index += 1
        self.session.commit()
        return self.list_conversations(user_id)

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        result = self.session.execute(
            delete(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
        self.session.commit()
        return result.rowcount > 0

    # ---- messages ---------------------------------------------------------

    def _attachment_map(
        self, message_ids: list[str],
    ) -> dict[str, list[UploadedAsset]]:
        if not message_ids:
            return {}
        rows = self.session.execute(
            select(ChatMessageAttachment, UploadedAsset)
            .join(UploadedAsset, UploadedAsset.id == ChatMessageAttachment.asset_id)
            .where(ChatMessageAttachment.message_id.in_(message_ids))
            .order_by(
                ChatMessageAttachment.message_id,
                ChatMessageAttachment.sort_order,
                ChatMessageAttachment.id,
            )
        ).all()
        result: dict[str, list[UploadedAsset]] = {}
        for attachment, asset in rows:
            result.setdefault(attachment.message_id, []).append(asset)
        return result

    def validate_attachment_ids(
        self, user_id: str, attachment_ids: list[str],
    ) -> list[UploadedAsset]:
        if len(attachment_ids) > MAX_CHAT_ATTACHMENTS:
            raise ValueError("invalid_attachments")
        if len(attachment_ids) != len(set(attachment_ids)):
            raise ValueError("invalid_attachments")
        if not attachment_ids:
            return []

        rows = self.session.execute(
            select(UploadedAsset).where(
                UploadedAsset.id.in_(attachment_ids),
                UploadedAsset.user_id == user_id,
            )
        ).scalars().all()
        by_id = {row.id: row for row in rows}
        if set(by_id) != set(attachment_ids):
            raise ValueError("invalid_attachments")

        assets = [by_id[asset_id] for asset_id in attachment_ids]
        if (
            any(asset.mime_type not in SUPPORTED_IMAGE_TYPES for asset in assets)
            or sum(asset.size_bytes for asset in assets) > MAX_CHAT_ATTACHMENT_BYTES
            or any(not Path(asset.file_path).is_file() for asset in assets)
        ):
            raise ValueError("invalid_attachments")
        return assets

    @staticmethod
    def _multimodal_content(text: str, assets: list[UploadedAsset]) -> str | list[dict]:
        if not assets:
            return text
        from config import LLM_VISION_DETAIL

        detail = LLM_VISION_DETAIL if LLM_VISION_DETAIL in {"auto", "low", "high"} else "high"
        parts: list[dict] = [{"type": "input_text", "text": text}]
        for asset in assets:
            try:
                encoded = base64.b64encode(Path(asset.file_path).read_bytes()).decode("ascii")
            except OSError:
                logger.warning("Chat attachment file missing: %s", asset.id)
                continue
            parts.append({
                "type": "input_image",
                "image_url": f"data:{asset.mime_type};base64,{encoded}",
                "detail": detail,
            })
        return parts if len(parts) > 1 else text

    def get_messages(self, conversation_id: str, user_id: str) -> list[dict]:
        if self.get_conversation(conversation_id, user_id) is None:
            return []
        rows = self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        ).scalars().all()
        attachments = self._attachment_map([row.id for row in rows])
        return [_message_dict(row, attachments.get(row.id)) for row in rows]

    def get_message_page(
        self, conversation_id: str, user_id: str, *, limit: int = 100, offset: int = 0,
    ) -> dict | None:
        conversation = self.session.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if conversation is None:
            return None

        capped = min(max(limit, 1), 200)
        start = max(offset, 0)
        rows = self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .offset(start)
            .limit(capped + 1)
        ).scalars().all()
        has_more = len(rows) > capped
        page_rows = list(reversed(rows[:capped]))
        attachments = self._attachment_map([row.id for row in page_rows])
        messages = [_message_dict(row, attachments.get(row.id)) for row in page_rows]
        return {
            "messages": messages,
            "pending": self._pending_view(conversation),
            "page": {
                "limit": capped,
                "offset": start,
                "has_more": has_more,
                "next_offset": start + capped if has_more else None,
            },
        }

    def _model_history(
        self, conversation_id: str, *, include_images: bool = True,
    ) -> list[dict]:
        rows = self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(_MODEL_HISTORY_MAX_MESSAGES)
        ).scalars().all()

        selected: list[ChatMessage] = []
        tokens = 0
        for row in rows:
            cost = _estimate_tokens(row.content)
            if selected and tokens + cost > _MODEL_HISTORY_TOKEN_BUDGET:
                break
            selected.append(row)
            tokens += cost
        included: dict[str, list[UploadedAsset]] = {}
        if include_images:
            attachment_map = self._attachment_map([row.id for row in selected])
            remaining = MAX_CHAT_ATTACHMENTS
            for row in selected:
                if row.role != "user" or remaining == 0:
                    continue
                assets = attachment_map.get(row.id, [])[:remaining]
                if assets:
                    included[row.id] = assets
                    remaining -= len(assets)

        return [
            {
                "role": row.role,
                "content": self._multimodal_content(
                    row.content, included.get(row.id, []),
                ),
            }
            for row in reversed(selected)
        ]

    def _latest_user_content(self, conversation_id: str) -> str:
        return self.session.execute(
            select(ChatMessage.content)
            .where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        ).scalar_one_or_none() or ""

    def add_message(
        self, conversation_id: str, role: str, content: str, *, work: dict | None = None,
        artifacts: list[dict] | None = None, attachment_ids: list[str] | None = None,
        user_id: str | None = None,
    ) -> str:
        assets: list[UploadedAsset] = []
        if attachment_ids:
            if user_id is None:
                raise ValueError("invalid_attachments")
            assets = self.validate_attachment_ids(user_id, attachment_ids)
        now = _now()
        message_id = str(uuid4())
        msg = ChatMessage(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            work_log=work,
            artifacts=artifacts or None,
            created_at=now,
        )
        self.session.add(msg)
        for sort_order, asset in enumerate(assets):
            self.session.add(ChatMessageAttachment(
                id=str(uuid4()),
                message_id=message_id,
                asset_id=asset.id,
                sort_order=sort_order,
                created_at=now,
            ))

        # Title from the first user message; always bump updated_at.
        if role == "user":
            row = self.session.execute(
                select(ChatConversation).where(ChatConversation.id == conversation_id)
            ).scalar_one_or_none()
            if row is not None and not row.title:
                self.session.execute(
                    update(ChatConversation)
                    .where(ChatConversation.id == conversation_id)
                    .values(title=content[:_TITLE_MAX], updated_at=now)
                )
        self.session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(updated_at=now)
        )
        self.session.commit()
        return message_id

    def replace_last_user_turn(
        self, conversation_id: str, user_id: str, content: str,
        attachment_ids: list[str] | None = None,
    ) -> bool:
        """Replace the latest user message and remove the answer generated after it."""
        if self.get_conversation(conversation_id, user_id) is None:
            return False

        rows = self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        ).scalars().all()
        last_user_index = next(
            (index for index in range(len(rows) - 1, -1, -1) if rows[index].role == "user"),
            -1,
        )
        if last_user_index < 0:
            return False

        previous_user = rows[last_user_index]
        previous_attachments = self._attachment_map([previous_user.id]).get(
            previous_user.id, [],
        )
        assets = (
            previous_attachments
            if attachment_ids is None
            else self.validate_attachment_ids(user_id, attachment_ids)
        )
        removed_ids = [row.id for row in rows[last_user_index:]]
        self.session.execute(delete(ChatMessage).where(ChatMessage.id.in_(removed_ids)))

        now = _now()
        message_id = str(uuid4())
        self.session.add(ChatMessage(
            id=message_id,
            conversation_id=conversation_id,
            role="user",
            content=content,
            created_at=now,
        ))
        for sort_order, asset in enumerate(assets):
            self.session.add(ChatMessageAttachment(
                id=str(uuid4()),
                message_id=message_id,
                asset_id=asset.id,
                sort_order=sort_order,
                created_at=now,
            ))

        conversation_values: dict = {
            "updated_at": now,
            "pending_state": None,
            "pending_at": None,
        }
        if not any(row.role == "user" for row in rows[:last_user_index]):
            conversation_values["title"] = content[:_TITLE_MAX]
        self.session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(**conversation_values)
        )
        self.session.commit()
        return True

    # ---- streaming answer -------------------------------------------------

    def _pending_view(self, conversation: ChatConversation) -> dict | None:
        pending = conversation.pending_state
        if pending is None:
            return None

        pending_at = _parse_timestamp(conversation.pending_at)
        expires_at = pending_at + _PENDING_APPROVAL_TTL if pending_at else None
        items = [dict(item) for item in pending.get("items", [])]
        expired = (
            expires_at is None
            or datetime.now(timezone.utc) >= expires_at
            or not items
        )
        work = _copy_work_log(pending.get("work") or _new_work_log())
        if expired:
            work["status"] = "expired"
            work["completed_at"] = expires_at.isoformat() if expires_at else _now()
        return {
            "items": items,
            "work": work,
            "pending_at": conversation.pending_at,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "expired": expired,
        }

    def _clear_pending(self, conversation_id: str) -> None:
        self.session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(pending_state=None, pending_at=None)
        )
        self.session.commit()

    def _clear_pending_if(self, conversation_id: str, user_id: str, pending_at: str | None) -> bool:
        pending_match = (
            ChatConversation.pending_at == pending_at
            if pending_at is not None
            else ChatConversation.pending_at.is_(None)
        )
        result = self.session.execute(
            update(ChatConversation)
            .where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
                ChatConversation.pending_state.is_not(None),
                pending_match,
            )
            .values(pending_state=None, pending_at=None)
        )
        self.session.commit()
        return result.rowcount == 1

    def _claim_pending(self, conversation_id: str, user_id: str, pending_at: str | None) -> bool:
        """Atomically consume one approval state before any write tool can run."""
        return self._clear_pending_if(conversation_id, user_id, pending_at)

    def _persist_interrupt(
        self, conversation_id: str, state_json: dict, mode: str, web_search: bool,
        work: dict, items: list[dict],
    ) -> None:
        self.session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(pending_state={
                "run_state": state_json,
                "options": {"mode": mode, "web_search": web_search},
                "work": work,
                "items": items,
            }, pending_at=_now())
        )
        self.session.commit()

    async def _drain(
        self, result, parts: list[str], work: dict, artifacts: list[dict],
    ):
        """Map real SDK text, reasoning-summary, and tool events to client events."""
        from agents.items import ReasoningItem, ToolCallItem, ToolCallOutputItem
        from openai.types.responses import ResponseTextDeltaEvent

        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                text = event.data.delta
                if text:
                    parts.append(text)
                    yield text
                continue

            if event.type != "run_item_stream_event":
                continue

            if event.name == "tool_called" and isinstance(event.item, ToolCallItem):
                call_id = event.item.call_id or str(uuid4())
                raw_item = event.item.raw_item
                arguments = (
                    raw_item.get("arguments") if isinstance(raw_item, dict)
                    else getattr(raw_item, "arguments", None)
                )
                item = next(
                    (entry for entry in work["items"] if entry.get("id") == call_id),
                    None,
                )
                if item is None:
                    item = {"id": call_id, "kind": "tool"}
                    work["items"].append(item)
                item.update({
                    "status": "running",
                    "title": event.item.title or event.item.tool_name or "tool",
                    "tool_name": event.item.tool_name or "tool",
                    "input": _preview(arguments),
                    "output": None,
                    "started_at": item.get("started_at") or _now(),
                    "completed_at": None,
                })
                yield {"type": "work_item", "item": dict(item)}
                continue

            if event.name == "tool_output" and isinstance(event.item, ToolCallOutputItem):
                call_id = event.item.call_id or str(uuid4())
                item = next(
                    (entry for entry in work["items"] if entry.get("id") == call_id),
                    None,
                )
                if item is None:
                    item = {
                        "id": call_id,
                        "kind": "tool",
                        "title": "tool",
                        "tool_name": "tool",
                        "input": "",
                        "started_at": _now(),
                    }
                    work["items"].append(item)
                item.update({
                    "status": "completed",
                    "output": _preview(event.item.output),
                    "completed_at": _now(),
                })
                yield {"type": "work_item", "item": dict(item)}
                artifact = _tool_artifact(
                    item.get("tool_name") or "tool", call_id, event.item.output,
                )
                if artifact is not None:
                    artifacts.append(artifact)
                    yield {"type": "artifact", "artifact": artifact}
                continue

            if event.name == "reasoning_item_created" and isinstance(event.item, ReasoningItem):
                summary = _reasoning_summary(event.item.raw_item)
                if summary:
                    raw_id = getattr(event.item.raw_item, "id", None) or str(uuid4())
                    item = {
                        "id": raw_id,
                        "kind": "reasoning",
                        "status": "completed",
                        "content": summary,
                        "started_at": _now(),
                        "completed_at": _now(),
                    }
                    work["items"].append(item)
                    yield {"type": "work_item", "item": dict(item)}

    async def _stream_answer(
        self, conversation_id: str, user_id: str, lang: str,
        mode: str, web_search: bool,
    ) -> AsyncIterator[str | dict]:
        from agents import Runner

        from services.agent import (
            agent_max_turns,
            agent_run_timeout,
            build_agent,
            is_vision_available,
            normalize_agent_mode,
        )
        from services.action_enrich import enrich_interruption
        from services.assistant_commands import (
            AssistantCommandError,
            command_error_markdown,
            command_help_markdown,
            parse_opportunity_command_arguments,
            parse_assistant_command,
            parse_market_command_arguments,
        )

        history = self._model_history(
            conversation_id, include_images=is_vision_available(),
        )

        latest_content = next(
            (_input_text(item["content"]) for item in reversed(history) if item["role"] == "user"),
            "",
        )
        try:
            command = parse_assistant_command(latest_content)
            deterministic_command = (
                command if command is not None and not command.is_multiple else None
            )
            market_command = (
                parse_market_command_arguments(deterministic_command)
                if deterministic_command is not None else None
            )
            opportunity_command = (
                parse_opportunity_command_arguments(deterministic_command)
                if deterministic_command is not None else None
            )
        except AssistantCommandError as exc:
            response = command_error_markdown(exc, lang)
            self.add_message(conversation_id, "assistant", response)
            yield response
            return
        if command is not None and command.names == ("/help",):
            response = command_help_markdown(lang)
            self.add_message(conversation_id, "assistant", response)
            yield response
            return

        mode = normalize_agent_mode(mode)
        parts: list[str] = []
        artifacts: list[dict] = []
        work = _new_work_log()
        segment_started = time.monotonic()
        try:
            yield {"type": "work_start", "work": _copy_work_log(work)}

            command_tools_resolved = False
            if market_command is not None:
                from services.market_research import get_market_snapshot

                call_id = str(uuid4())
                market_input = {
                    "asset_class": market_command.asset_class,
                    "symbol": market_command.symbol,
                    "interval": market_command.interval,
                }
                market_item = {
                    "id": call_id,
                    "kind": "tool",
                    "status": "running",
                    "title": f"get_{market_command.asset_class}_market_data",
                    "tool_name": f"get_{market_command.asset_class}_market_data",
                    "input": _preview(market_input),
                    "output": None,
                    "started_at": _now(),
                    "completed_at": None,
                }
                work["items"].append(market_item)
                yield {"type": "work_item", "item": dict(market_item)}
                market_result = await asyncio.to_thread(
                    get_market_snapshot,
                    market_command.asset_class,
                    market_command.symbol,
                    market_command.interval,
                )
                market_item.update({
                    "status": "failed" if market_result.get("error") else "completed",
                    "output": _preview(market_result),
                    "completed_at": _now(),
                })
                yield {"type": "work_item", "item": dict(market_item)}
                artifact = _tool_artifact(
                    market_item["tool_name"], call_id, market_result,
                )
                if artifact is not None:
                    artifacts.append(artifact)
                    yield {"type": "artifact", "artifact": artifact}

                if market_result.get("error"):
                    response_key = (
                        "chat.market.not_configured"
                        if market_result["error"] == "market_data_not_configured"
                        else "chat.market.unavailable"
                    )
                    response = t(response_key, lang)
                    parts.append(response)
                    yield response
                    _finish_work_log(work, "error", segment_started)
                    self.add_message(
                        conversation_id, "assistant", response,
                        work=_copy_work_log(work), artifacts=artifacts,
                    )
                    yield {"type": "work_end", "work": _copy_work_log(work)}
                    return

                for index in range(len(history) - 1, -1, -1):
                    if history[index]["role"] == "user":
                        history[index] = _append_input_context(
                            history[index],
                            f"{t('chat.market.context', lang)}\n"
                            f"<market_snapshot>\n"
                            f"{json.dumps(market_result, ensure_ascii=False, default=str)}\n"
                            f"</market_snapshot>",
                        )
                        break
                command_tools_resolved = True

            if opportunity_command is not None:
                from services.opportunity_check import check_trade_opportunity
                from services.market_research import get_market_snapshot

                opportunity_input = asdict(opportunity_command)
                call_id = str(uuid4())
                opportunity_item = {
                    "id": call_id,
                    "kind": "tool",
                    "status": "running",
                    "title": "check_trade_opportunity",
                    "tool_name": "check_trade_opportunity",
                    "input": _preview(opportunity_input),
                    "output": None,
                    "started_at": _now(),
                    "completed_at": None,
                }
                work["items"].append(opportunity_item)
                yield {"type": "work_item", "item": dict(opportunity_item)}
                opportunity_snapshot = None
                if opportunity_command.market and opportunity_command.symbol:
                    opportunity_snapshot = await asyncio.to_thread(
                        get_market_snapshot,
                        opportunity_command.market,
                        opportunity_command.symbol,
                        opportunity_command.interval,
                    )
                opportunity_result = check_trade_opportunity(
                    self.session,
                    user_id,
                    **opportunity_input,
                    snapshot=opportunity_snapshot,
                )
                opportunity_item.update({
                    "status": "failed" if opportunity_result.get("error") else "completed",
                    "output": _preview(opportunity_result),
                    "completed_at": _now(),
                })
                yield {"type": "work_item", "item": dict(opportunity_item)}
                artifact = _tool_artifact(
                    "check_trade_opportunity", call_id, opportunity_result,
                )
                if artifact is not None:
                    artifacts.append(artifact)
                    yield {"type": "artifact", "artifact": artifact}

                if opportunity_result.get("error"):
                    response = t("chat.opportunity.unavailable", lang)
                    parts.append(response)
                    yield response
                    _finish_work_log(work, "error", segment_started)
                    self.add_message(
                        conversation_id, "assistant", response,
                        work=_copy_work_log(work), artifacts=artifacts,
                    )
                    yield {"type": "work_end", "work": _copy_work_log(work)}
                    return

                for index in range(len(history) - 1, -1, -1):
                    if history[index]["role"] == "user":
                        history[index] = _append_input_context(
                            history[index],
                            f"{t('chat.opportunity.context', lang)}\n"
                            f"<opportunity_check>\n"
                            f"{json.dumps(opportunity_result, ensure_ascii=False, default=str)}\n"
                            f"</opportunity_check>",
                        )
                        break
                command_tools_resolved = True

            if web_search:
                from services.web_search import is_web_search_available, search_web

                if not is_web_search_available():
                    response = t("chat.web_search.unavailable", lang)
                    parts.append(response)
                    yield response
                    _finish_work_log(work, "error", segment_started)
                    self.add_message(
                        conversation_id, "assistant", response, work=_copy_work_log(work),
                    )
                    yield {"type": "work_end", "work": _copy_work_log(work)}
                    return

                search_query = command.argument if command and command.argument else latest_content
                search_item = {
                    "id": str(uuid4()),
                    "kind": "tool",
                    "status": "running",
                    "title": "web_search",
                    "tool_name": "web_search",
                    "input": _preview({"query": search_query, "max_results": 5}),
                    "output": None,
                    "started_at": _now(),
                    "completed_at": None,
                }
                work["items"].append(search_item)
                yield {"type": "work_item", "item": dict(search_item)}
                search_result = await asyncio.to_thread(search_web, search_query, 5)
                search_item.update({
                    "status": "failed" if search_result.get("error") else "completed",
                    "output": _preview(search_result),
                    "completed_at": _now(),
                })
                yield {"type": "work_item", "item": dict(search_item)}
                for index in range(len(history) - 1, -1, -1):
                    if history[index]["role"] == "user":
                        history[index] = _append_input_context(
                            history[index],
                            f"{t('chat.web_search.context', lang)}\n"
                            f"<web_search_results>\n"
                            f"{json.dumps(search_result, ensure_ascii=False, default=str)}\n"
                            f"</web_search_results>",
                        )
                        break

            agent = build_agent(
                self.session, user_id, lang, mode=mode, enable_web_search=web_search,
                command=command, command_tools_resolved=command_tools_resolved,
            )
            # The request Session has finished its read-only setup work. Release its
            # connection while the remote model and isolated tool Sessions run.
            self.session.rollback()
            async with asyncio.timeout(agent_run_timeout(mode)):
                result = Runner.run_streamed(
                    agent, input=history, max_turns=agent_max_turns(mode),
                )
                async for event in self._drain(result, parts, work, artifacts):
                    yield event

                state = result.to_state()
                interruptions = state.get_interruptions()
                if interruptions:
                    interruption_ids = {item.raw_item.call_id for item in interruptions}
                    for item in work["items"]:
                        if item.get("id") in interruption_ids and item.get("status") == "running":
                            item["status"] = "pending_approval"
                    _finish_work_log(work, "interrupted", segment_started)
                    items = [
                        enrich_interruption(self.session, user_id, item, lang)
                        for item in interruptions
                    ]
                    self._persist_interrupt(
                        conversation_id, state.to_json(), mode, web_search,
                        _copy_work_log(work), items,
                    )
                    if parts or artifacts:
                        self.add_message(
                            conversation_id, "assistant", "".join(parts),
                            artifacts=artifacts,
                        )
                    yield {"type": "work_end", "work": _copy_work_log(work)}
                    yield {"type": "interrupt", "items": items}
                    return

            _finish_work_log(work, "completed", segment_started)
            self.add_message(
                conversation_id, "assistant", "".join(parts), work=_copy_work_log(work),
                artifacts=artifacts,
            )
            yield {"type": "work_end", "work": _copy_work_log(work)}
        except (asyncio.CancelledError, GeneratorExit):
            if work.get("status") == "running":
                for item in work["items"]:
                    if item.get("status") == "running":
                        item["status"] = "failed"
                        item["completed_at"] = _now()
                _finish_work_log(work, "error", segment_started)
                notice = t("chat.cancelled", lang)
                content = "".join(parts)
                content = f"{content}\n\n{notice}" if content else notice
                self.add_message(
                    conversation_id, "assistant", content, work=_copy_work_log(work),
                    artifacts=artifacts,
                )
            raise
        except Exception as exc:
            logger.exception("Chat stream failed", exc_info=exc)
            err = f"\n\n**{t('chat.error', lang)}**"
            parts.append(err)
            yield err
            for item in work["items"]:
                if item.get("status") == "running":
                    item["status"] = "failed"
                    item["completed_at"] = _now()
            _finish_work_log(work, "error", segment_started)
            self.add_message(
                conversation_id, "assistant", "".join(parts), work=_copy_work_log(work),
                artifacts=artifacts,
            )
            yield {"type": "work_end", "work": _copy_work_log(work)}

    async def send_message(
        self, conversation_id: str, user_id: str, content: str, lang: str = "zh",
        mode: str = "standard", web_search: bool = False,
        attachment_ids: list[str] | None = None,
    ) -> AsyncIterator[str | dict]:
        if attachment_ids:
            from services.agent import is_vision_available

            if not is_vision_available():
                raise ValueError("vision_unavailable")
        self._clear_pending(conversation_id)
        self.add_message(
            conversation_id, "user", content,
            attachment_ids=attachment_ids, user_id=user_id,
        )
        stream = self._stream_answer(
            conversation_id, user_id, lang, mode, web_search,
        )
        try:
            async for chunk in stream:
                yield chunk
        finally:
            await stream.aclose()

    async def regenerate_last_answer(
        self, conversation_id: str, user_id: str, lang: str = "zh",
        mode: str = "standard", web_search: bool = False,
    ) -> AsyncIterator[str | dict]:
        stream = self._stream_answer(
            conversation_id, user_id, lang, mode, web_search,
        )
        try:
            async for chunk in stream:
                yield chunk
        finally:
            await stream.aclose()

    async def resume_run(
        self, conversation_id: str, user_id: str, decisions: list[dict], lang: str = "zh",
    ) -> AsyncIterator[str | dict]:
        from agents import Runner, RunState

        from services.agent import build_agent
        from services.assistant_commands import AssistantCommandError, parse_assistant_command

        row = self.session.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if row is None or row.pending_state is None:
            yield {"type": "error", "code": "no_pending_approval",
                   "content": t("chat.pending.missing", lang)}
            return

        pending = row.pending_state
        pending_at = row.pending_at
        pending_view = self._pending_view(row)
        if pending_view is None or pending_view["expired"]:
            self._clear_pending_if(conversation_id, user_id, pending_at)
            yield {"type": "error", "code": "pending_expired",
                   "content": t("chat.pending.expired", lang)}
            return
        if "run_state" in pending:
            state_json = pending["run_state"]
            options = pending.get("options", {})
        else:
            # Backward compatibility for interruptions created before run options existed.
            state_json = pending
            options = {}
        mode = options.get("mode", "standard")
        web_search = bool(options.get("web_search", False))
        work = _copy_work_log(pending.get("work") or _new_work_log())
        work["status"] = "running"
        work["completed_at"] = None
        segment_started = time.monotonic()
        from services.agent import agent_max_turns, agent_run_timeout

        latest_content = self._latest_user_content(conversation_id)
        try:
            command = parse_assistant_command(latest_content)
        except AssistantCommandError:
            command = None

        agent = build_agent(
            self.session, user_id, lang, mode=mode, enable_web_search=web_search,
            command=command,
        )
        try:
            state = await RunState.from_json(agent, state_json)
        except Exception:
            logger.exception("resume: from_json failed")
            self._clear_pending_if(conversation_id, user_id, pending_at)
            yield {"type": "error", "content": t("chat.error", lang)}
            return

        interruptions = state.get_interruptions()
        interruption_ids = [item.raw_item.call_id for item in interruptions]
        decision_ids = [decision.get("call_id") for decision in decisions]
        valid_decisions = {"approve", "reject"}
        if (
            len(decision_ids) != len(set(decision_ids))
            or set(decision_ids) != set(interruption_ids)
            or any(decision.get("decision") not in valid_decisions for decision in decisions)
        ):
            yield {"type": "error", "code": "invalid_decisions",
                   "content": t("chat.pending.invalid", lang)}
            return

        if not self._claim_pending(conversation_id, user_id, pending_at):
            yield {"type": "error", "code": "pending_already_consumed",
                   "content": t("chat.pending.consumed", lang)}
            return

        decision_by_id = {d["call_id"]: d["decision"] for d in decisions}
        for item in interruptions:
            call_id = item.raw_item.call_id
            if decision_by_id[call_id] == "approve":
                state.approve(item)
            else:
                state.reject(item)

        parts: list[str] = []
        artifacts: list[dict] = []
        try:
            yield {"type": "work_start", "work": _copy_work_log(work)}
            async with asyncio.timeout(agent_run_timeout(mode)):
                result = Runner.run_streamed(
                    agent, input=state, max_turns=agent_max_turns(mode),
                )
                async for event in self._drain(result, parts, work, artifacts):
                    yield event

                new_state = result.to_state()
                more = new_state.get_interruptions()
                if more:
                    from services.action_enrich import enrich_interruption

                    interruption_ids = {item.raw_item.call_id for item in more}
                    for item in work["items"]:
                        if item.get("id") in interruption_ids and item.get("status") == "running":
                            item["status"] = "pending_approval"
                    _finish_work_log(work, "interrupted", segment_started)
                    items = [
                        enrich_interruption(self.session, user_id, item, lang)
                        for item in more
                    ]
                    self._persist_interrupt(
                        conversation_id, new_state.to_json(), mode, web_search,
                        _copy_work_log(work), items,
                    )
                    if parts or artifacts:
                        self.add_message(
                            conversation_id, "assistant", "".join(parts),
                            artifacts=artifacts,
                        )
                    yield {"type": "work_end", "work": _copy_work_log(work)}
                    yield {"type": "interrupt", "items": items}
                    return

            _finish_work_log(work, "completed", segment_started)
            self.add_message(
                conversation_id, "assistant", "".join(parts), work=_copy_work_log(work),
                artifacts=artifacts,
            )
            yield {"type": "work_end", "work": _copy_work_log(work)}
        except (asyncio.CancelledError, GeneratorExit):
            if work.get("status") == "running":
                for item in work["items"]:
                    if item.get("status") == "running":
                        item["status"] = "failed"
                        item["completed_at"] = _now()
                _finish_work_log(work, "error", segment_started)
                notice = t("chat.cancelled", lang)
                content = "".join(parts)
                content = f"{content}\n\n{notice}" if content else notice
                self.add_message(
                    conversation_id, "assistant", content, work=_copy_work_log(work),
                    artifacts=artifacts,
                )
            raise
        except Exception as exc:
            logger.exception("resume stream failed", exc_info=exc)
            err = f"\n\n**{t('chat.error', lang)}**"
            parts.append(err)
            yield err
            for item in work["items"]:
                if item.get("status") == "running":
                    item["status"] = "failed"
                    item["completed_at"] = _now()
            _finish_work_log(work, "error", segment_started)
            self.add_message(
                conversation_id, "assistant", "".join(parts), work=_copy_work_log(work),
                artifacts=artifacts,
            )
            yield {"type": "work_end", "work": _copy_work_log(work)}
