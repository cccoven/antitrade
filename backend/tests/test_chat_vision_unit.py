from pathlib import Path

import pytest
from pydantic import ValidationError

from models import UploadedAsset
from routers.chat import SendMessageRequest
from services.chat import ChatService, _append_input_context


def test_send_message_request_accepts_image_only():
    request = SendMessageRequest(content="", attachment_ids=["asset-1"])
    assert request.attachment_ids == ["asset-1"]


def test_send_message_request_rejects_empty_and_duplicate_attachments():
    with pytest.raises(ValidationError):
        SendMessageRequest(content="")
    with pytest.raises(ValidationError):
        SendMessageRequest(content="analyze", attachment_ids=["same", "same"])


def test_multimodal_content_uses_data_url_and_high_detail(tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "LLM_VISION_DETAIL", "high")
    path = Path(tmp_path) / "chart.png"
    path.write_bytes(b"chart-bytes")
    asset = UploadedAsset(
        id="asset-1", user_id="user-1", file_path=str(path),
        original_name="chart.png", mime_type="image/png", width=1280, height=720,
        size_bytes=11, created_at="2026-07-20T00:00:00+00:00",
    )

    content = ChatService._multimodal_content("analyze", [asset])

    assert isinstance(content, list)
    assert content[0] == {"type": "input_text", "text": "analyze"}
    assert content[1]["detail"] == "high"
    assert content[1]["image_url"].startswith("data:image/png;base64,")


def test_multimodal_content_converts_for_chat_completions(tmp_path, monkeypatch):
    import config
    from agents.models.chatcmpl_converter import Converter

    monkeypatch.setattr(config, "LLM_VISION_DETAIL", "high")
    path = Path(tmp_path) / "chart.png"
    path.write_bytes(b"chart-bytes")
    asset = UploadedAsset(
        id="asset-1", user_id="user-1", file_path=str(path),
        original_name="chart.png", mime_type="image/png", width=1280, height=720,
        size_bytes=11, created_at="2026-07-20T00:00:00+00:00",
    )

    content = ChatService._multimodal_content("analyze", [asset])
    converted = Converter.extract_all_content(content)

    assert converted[0] == {"type": "text", "text": "analyze"}
    assert converted[1]["type"] == "image_url"
    assert converted[1]["image_url"]["detail"] == "high"
    assert converted[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_context_append_preserves_image_parts():
    message = {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "/stock AAPL"},
            {"type": "input_image", "image_url": "data:image/png;base64,AA=="},
        ],
    }

    updated = _append_input_context(message, "market context")

    assert updated["content"][0]["text"].endswith("market context")
    assert updated["content"][1] == message["content"][1]
