"""Small, deterministic language checks for feed content and briefings."""

import re

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _script_language(text: str) -> str | None:
    cjk_count = len(_CJK_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))
    if cjk_count >= 2 and cjk_count * 2 >= latin_count:
        return "zh"
    if latin_count >= 6 and latin_count > cjk_count * 2:
        return "en"
    return None


def detect_feed_language(title: str, summary: str = "", fallback: str = "en") -> str:
    """Detect Chinese/English from content, preferring the headline."""
    return (
        _script_language(title)
        or _script_language(f"{title} {summary}")
        or fallback
    )


def feed_text_matches_language(
    title: str,
    summary: str,
    expected_language: str,
) -> bool:
    return detect_feed_language(title, summary, expected_language) == expected_language


def briefing_content_matches_language(content: object, expected_language: str) -> bool:
    """Reject a briefing whose reader-facing text clearly uses the wrong script."""
    if not isinstance(content, dict):
        return False

    texts: list[str] = []
    for hot_item in content.get("hot", []):
        if isinstance(hot_item, dict):
            texts.append(str(hot_item.get("title", "")))

    for section in content.get("sections", []):
        if not isinstance(section, dict):
            continue
        for point in section.get("points", []):
            if isinstance(point, dict):
                texts.append(str(point.get("text", "")))
            else:
                texts.append(str(point))

    combined = " ".join(texts)
    return _script_language(combined) in (None, expected_language)
