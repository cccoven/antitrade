"""Recognition service — parse uploaded files/images into trade records via LLM."""

import base64
import json
import logging
import re
from io import BytesIO

import pandas as pd

from i18n import t
from services.analyzer import create_provider

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
SUPPORTED_FILE_TYPES = {
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

PARSE_SCHEMA = """{
  "trades": [
    {
      "symbol": "string",
      "direction": "long|short",
      "open_price": 0.0,
      "close_price": 0.0,
      "quantity": 0.0,
      "open_time": "ISO8601",
      "close_time": "ISO8601",
      "fees": 0.0
    }
  ],
  "confidence": 0.0
}"""


async def parse_file(
    file_bytes: bytes,
    content_type: str,
    filename: str,
    lang: str = "zh",
) -> dict:
    """Main entry: dispatch to the appropriate parser based on content type."""
    if content_type in SUPPORTED_IMAGE_TYPES:
        raw = await _parse_image(file_bytes, content_type, lang)
    elif content_type == "text/csv" or (
        content_type == "application/octet-stream"
        and filename.lower().endswith(".csv")
    ):
        text = file_bytes.decode("utf-8", errors="replace")
        raw = await _parse_text(text, lang)
    elif content_type == "application/json" or (
        content_type == "application/octet-stream"
        and filename.lower().endswith(".json")
    ):
        text = file_bytes.decode("utf-8", errors="replace")
        raw = await _parse_text(text, lang)
    elif (
        content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        or (
            content_type == "application/octet-stream"
            and filename.lower().endswith(".xlsx")
        )
    ):
        raw = await _parse_excel(file_bytes, lang)
    else:
        raise ValueError(f"Unsupported file type: {content_type}")

    return _extract_json(raw)


async def _parse_image(
    file_bytes: bytes, content_type: str, lang: str
) -> str:
    """Base64-encode the image, build a prompt, and call the provider."""
    b64 = base64.b64encode(file_bytes).decode("ascii")
    content_text = f"[image: data:{content_type};base64,{b64}]"
    prompt = _build_parse_prompt(content_text, lang)
    provider = create_provider()
    return await provider.complete(prompt)


async def _parse_text(text: str, lang: str) -> str:
    """Take the first 50 lines, build a prompt, and call the provider."""
    lines = text.splitlines()[:50]
    content_text = "\n".join(lines)
    prompt = _build_parse_prompt(content_text, lang)
    provider = create_provider()
    return await provider.complete(prompt)


async def _parse_excel(file_bytes: bytes, lang: str) -> str:
    """Read excel into a text table, build a prompt, and call the provider."""
    df = pd.read_excel(BytesIO(file_bytes))
    content_text = df.to_string(index=False)
    prompt = _build_parse_prompt(content_text, lang)
    provider = create_provider()
    return await provider.complete(prompt)


def _build_parse_prompt(content_text: str, lang: str) -> str:
    """Build the recognition prompt with schema and i18n base text."""
    base = t("recognition.prompt", lang)
    return f"""{base}

Expected output JSON schema:
{PARSE_SCHEMA}

Content:
{content_text}"""


def _extract_json(raw: str) -> dict:
    """Extract JSON from LLM response, handling ```json code blocks."""
    # Try to find a JSON code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)

    # Strip leading/trailing whitespace
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %s", raw[:200])
        return {"trades": [], "confidence": 0.0, "raw": raw}
