"""User-confirmed long-term memory for the AI assistant."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from models import AssistantMemory

_MAX_MEMORIES = 50
_MAX_MEMORY_LENGTH = 500
_DEFAULT_CONTEXT_LIMIT = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_to_dict(row: AssistantMemory) -> dict:
    return {
        "id": row.id,
        "content": row.content,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class AssistantMemoryService:
    def __init__(self, session: Session):
        self.session = session

    def list_memories(self, user_id: str, limit: int = _DEFAULT_CONTEXT_LIMIT) -> list[dict]:
        capped = min(max(limit, 1), _MAX_MEMORIES)
        rows = self.session.execute(
            select(AssistantMemory)
            .where(AssistantMemory.user_id == user_id)
            .order_by(AssistantMemory.updated_at.desc(), AssistantMemory.id.desc())
            .limit(capped)
        ).scalars().all()
        return [_memory_to_dict(row) for row in rows]

    def list_by_ids(self, user_id: str, memory_ids: list[str]) -> list[dict]:
        unique_ids = list(dict.fromkeys(memory_ids))
        if not unique_ids:
            return []
        rows = self.session.execute(
            select(AssistantMemory).where(
                AssistantMemory.user_id == user_id,
                AssistantMemory.id.in_(unique_ids),
            )
        ).scalars().all()
        found = {row.id: _memory_to_dict(row) for row in rows}
        return [found[memory_id] for memory_id in unique_ids if memory_id in found]

    def create_memory(self, user_id: str, content: str) -> dict:
        normalized = content.strip()
        if not normalized or len(normalized) > _MAX_MEMORY_LENGTH:
            raise ValueError("invalid_memory")

        existing = self.session.execute(
            select(AssistantMemory).where(
                AssistantMemory.user_id == user_id,
                AssistantMemory.content == normalized,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _memory_to_dict(existing)

        count = self.session.execute(
            select(func.count()).select_from(AssistantMemory)
            .where(AssistantMemory.user_id == user_id)
        ).scalar_one()
        if count >= _MAX_MEMORIES:
            raise ValueError("memory_limit")

        now = _now()
        row = AssistantMemory(
            id=str(uuid4()), user_id=user_id, content=normalized,
            created_at=now, updated_at=now,
        )
        self.session.add(row)
        self.session.commit()
        return _memory_to_dict(row)

    def delete_memories(self, user_id: str, memory_ids: list[str]) -> int:
        unique_ids = list(dict.fromkeys(memory_ids))
        if not unique_ids:
            return 0
        result = self.session.execute(
            delete(AssistantMemory).where(
                AssistantMemory.user_id == user_id,
                AssistantMemory.id.in_(unique_ids),
            )
        )
        self.session.commit()
        return result.rowcount
