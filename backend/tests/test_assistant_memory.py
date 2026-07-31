import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest

from agents.tool_context import ToolContext

from models import User
from services.agent import build_agent, build_agent_tools
from services.memory import AssistantMemoryService


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


def _invoke(tool, args: dict) -> str:
    ctx = ToolContext(context=None, tool_name=tool.name, tool_call_id="test",
                      tool_arguments=json.dumps(args))
    return asyncio.run(tool.on_invoke_tool(ctx, json.dumps(args)))


def test_memory_service_is_user_scoped_and_deduplicates(db, user_id):
    service = AssistantMemoryService(db)
    first = service.create_memory(user_id, "I prefer risk per trade below 1%.")
    duplicate = service.create_memory(user_id, "I prefer risk per trade below 1%.")
    other = str(uuid.uuid4())
    db.add(User(id=other, email="memory-other@test", password="x", name="Other",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    other_memory = service.create_memory(other, "I trade only London open.")

    assert duplicate["id"] == first["id"]
    assert [m["content"] for m in service.list_memories(user_id)] == [first["content"]]
    assert service.delete_memories(user_id, [other_memory["id"]]) == 0
    assert service.list_memories(other)[0]["id"] == other_memory["id"]


@pytest.mark.parametrize("content", ["", " " * 5, "x" * 501])
def test_memory_service_rejects_invalid_content(db, user_id, content):
    with pytest.raises(ValueError, match="invalid_memory"):
        AssistantMemoryService(db).create_memory(user_id, content)


def test_memory_tools_list_remember_and_forget(db, user_id):
    tools = build_agent_tools(db, user_id)
    remembered = json.loads(_invoke(_tool(tools, "remember_memory"), {
        "content": "I prefer concise pre-market briefings.",
    }))
    memory_id = remembered["memory"]["id"]

    listed = json.loads(_invoke(_tool(tools, "list_memories"), {}))
    assert listed["memories"] == [remembered["memory"]]

    deleted = json.loads(_invoke(_tool(tools, "forget_memories"), {"memory_ids": [memory_id]}))
    assert deleted == {"deleted": 1}
    assert json.loads(_invoke(_tool(tools, "list_memories"), {})) == {"memories": []}


def test_build_agent_injects_user_memory_into_every_conversation(db, user_id):
    service = AssistantMemoryService(db)
    for index in range(21):
        service.create_memory(user_id, f"Preference {index}: I trade only the London session.")

    agent = build_agent(db, user_id, lang="en")

    assert "Long-term memory" in agent.instructions
    assert "Preference 0: I trade only the London session." in agent.instructions
    assert "Preference 20: I trade only the London session." in agent.instructions
