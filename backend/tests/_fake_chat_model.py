"""Offline scripted Agents SDK model: one tool call, then echo the tool result.

Turn 1 emits a get_journal_stats tool call; turn 2 (once the tool output is in the
input) streams "结果: <output>" as the final answer. Mirrors the real streaming path.
"""

from typing import Any, AsyncIterator

from agents import Model, ModelResponse, Usage
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseTextDeltaEvent,
)
from openai.types.responses.response import Response

_FID = "__fake__"


def _response(output: list) -> Response:
    return Response(
        id=_FID, created_at=0, model="fake", object="response", output=output,
        tool_choice="auto", tools=[], parallel_tool_calls=False,
    )


def _find_tool_output(input: Any) -> str | None:
    if not isinstance(input, list):
        return None
    for item in input:
        it = item if isinstance(item, dict) else getattr(item, "__dict__", {})
        if it.get("type") == "function_call_output":
            return it.get("output")
    return None


class FakeToolThenAnswer(Model):
    async def get_response(self, *args, **kwargs) -> ModelResponse:  # pragma: no cover
        raise NotImplementedError("streaming only")

    async def stream_response(self, system_instructions, input, model_settings, tools,
                              output_schema, handoffs, tracing, *,
                              previous_response_id=None, conversation_id=None, prompt=None) -> AsyncIterator[Any]:
        tool_output = _find_tool_output(input)
        if tool_output is not None:
            text = f"结果: {tool_output}"
            yield ResponseTextDeltaEvent(
                delta=text, content_index=0, item_id=_FID, output_index=0,
                sequence_number=0, type="response.output_text.delta", logprobs=[],
            )
            msg = ResponseOutputMessage(
                id=_FID, role="assistant", type="message", status="completed",
                content=[ResponseOutputText(text=text, type="output_text", annotations=[])],
            )
            yield ResponseCompletedEvent(
                response=_response([msg]), type="response.completed", sequence_number=1,
            )
        else:
            call = ResponseFunctionToolCall(
                name="get_journal_stats", arguments="{}", call_id="call_1",
                type="function_call", id=_FID,
            )
            yield ResponseCompletedEvent(
                response=_response([call]), type="response.completed", sequence_number=0,
            )

    def get_retry_advice(self, request):
        return None

    async def close(self) -> None:
        return None


class FakeDeleteThenAnswer(Model):
    """Turn 1 calls delete_trades; turn 2 streams a short confirmation."""

    def __init__(self, trade_ids):
        self._ids = trade_ids

    async def get_response(self, *args, **kwargs) -> ModelResponse:  # pragma: no cover
        raise NotImplementedError("streaming only")

    async def stream_response(self, system_instructions, input, model_settings, tools,
                              output_schema, handoffs, tracing, *,
                              previous_response_id=None, conversation_id=None, prompt=None) -> AsyncIterator[Any]:
        import json as _json

        tool_output = _find_tool_output(input)
        if tool_output is not None:
            text = f"完成: {tool_output}"
            yield ResponseTextDeltaEvent(
                delta=text, content_index=0, item_id=_FID, output_index=0,
                sequence_number=0, type="response.output_text.delta", logprobs=[],
            )
            msg = ResponseOutputMessage(
                id=_FID, role="assistant", type="message", status="completed",
                content=[ResponseOutputText(text=text, type="output_text", annotations=[])],
            )
            yield ResponseCompletedEvent(
                response=_response([msg]), type="response.completed", sequence_number=1,
            )
        else:
            call = ResponseFunctionToolCall(
                name="delete_trades",
                arguments=_json.dumps({"trade_ids": self._ids}),
                call_id="call_del",
                type="function_call",
                id=_FID,
            )
            yield ResponseCompletedEvent(
                response=_response([call]), type="response.completed", sequence_number=0,
            )

    def get_retry_advice(self, request):
        return None

    async def close(self) -> None:
        return None


class FakeRememberThenAnswer(Model):
    """Turn 1 saves a memory; turn 2 streams a short confirmation."""

    def __init__(self, content: str):
        self._content = content

    async def get_response(self, *args, **kwargs) -> ModelResponse:  # pragma: no cover
        raise NotImplementedError("streaming only")

    async def stream_response(self, system_instructions, input, model_settings, tools,
                              output_schema, handoffs, tracing, *,
                              previous_response_id=None, conversation_id=None, prompt=None) -> AsyncIterator[Any]:
        import json as _json

        tool_output = _find_tool_output(input)
        if tool_output is not None:
            text = f"完成: {tool_output}"
            yield ResponseTextDeltaEvent(
                delta=text, content_index=0, item_id=_FID, output_index=0,
                sequence_number=0, type="response.output_text.delta", logprobs=[],
            )
            msg = ResponseOutputMessage(
                id=_FID, role="assistant", type="message", status="completed",
                content=[ResponseOutputText(text=text, type="output_text", annotations=[])],
            )
            yield ResponseCompletedEvent(
                response=_response([msg]), type="response.completed", sequence_number=1,
            )
        else:
            call = ResponseFunctionToolCall(
                name="remember_memory",
                arguments=_json.dumps({"content": self._content}),
                call_id="call_mem",
                type="function_call",
                id=_FID,
            )
            yield ResponseCompletedEvent(
                response=_response([call]), type="response.completed", sequence_number=0,
            )

    def get_retry_advice(self, request):
        return None

    async def close(self) -> None:
        return None
