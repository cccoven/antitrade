import asyncio
import re
from typing import AsyncIterator

from providers import LLMProvider
from i18n import t


_RE_ZH = re.compile(r"以下\s+([^:]+):([A-Z0-9=!^._-]+)\s+在\s+(.+?)\s+时间框架")
_RE_EN = re.compile(r"following\s+([^:]+):([A-Z0-9=!^._-]+)\s+.*?on the\s+(.+?)\s+timeframe", re.IGNORECASE)


class DemoProvider(LLMProvider):
    """Deterministic provider for local UI testing."""

    async def complete(self, prompt: str) -> str:
        if "trading review assistant" in prompt.lower() or "交易复盘助手" in prompt:
            import json as _json
            return _json.dumps({
                "action": "title_suggestions",
                "suggestions": [
                    "Daily Review: Patient Execution",
                    "Trading Review: Controlled Risk",
                    "Session Notes: Process First",
                ],
                "content": "Today focused on execution quality, risk control, and reviewing whether entries matched the written plan.",
            }, ensure_ascii=False)

        # Diagnosis / trading coach
        if "交易教练" in prompt or "trading coach" in prompt.lower():
            return """## Portfolio Diagnosis

### Overall Performance
- Win rate and profit factor are within acceptable ranges for demo analysis.
- Risk-reward ratio shows room for improvement.

### Pattern Analysis
- Trading frequency is consistent.
- Losses tend to cluster around specific market conditions.

### Recommendations
1. Review position sizing strategy for losing trades.
2. Consider reducing exposure during high-volatility events.
3. Maintain a trading journal for ongoing self-assessment.
"""

        # Recognition / trade-record parsing
        if "trading record parser" in prompt.lower() or "交易记录解析" in prompt:
            import json as _json
            return _json.dumps({
                "trades": [
                    {"symbol": "XAUUSD", "direction": "long", "open_price": 2340.5, "close_price": 2365.0, "quantity": 1.0, "open_time": "2026-04-10T14:30:00Z", "close_time": "2026-04-10T16:45:00Z", "fees": 3.2},
                    {"symbol": "BTCUSD", "direction": "short", "open_price": 70000.0, "close_price": 69500.0, "quantity": 0.1, "open_time": "2026-04-11T09:00:00Z", "close_time": "2026-04-11T11:30:00Z", "fees": 5.0},
                ],
                "confidence": 0.92,
            })

        exchange = "DEMO"
        symbol = "SYMBOL"
        interval = ""
        lang = "zh"

        match = _RE_ZH.search(prompt)
        if match:
            lang = "zh"
        else:
            match = _RE_EN.search(prompt)
            if match:
                lang = "en"

        if match:
            exchange = match.group(1)
            symbol = match.group(2)
            interval = match.group(3)

        return f"""## {t("demo.title", lang)}

**{t("demo.interval_label", lang)}**: {interval}

### {t("demo.trend_title", lang)}
- {t("demo.trend_body", lang)}

### {t("demo.levels_title", lang)}
- {t("demo.levels_support", lang)}
- {t("demo.levels_resistance", lang)}

### {t("demo.risk_title", lang)}
- {t("demo.risk_body_1", lang)}
- {t("demo.risk_body_2", lang)}

### {t("demo.suggestion_title", lang)}
1. {t("demo.suggestion_body_1", lang)}
2. {t("demo.suggestion_body_2", lang)}
"""

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Stream demo response in small chunks."""
        prompt = "\n".join(m["content"] for m in messages if m["role"] == "user")
        result = await self.complete(prompt)
        chunk_size = 4
        for i in range(0, len(result), chunk_size):
            yield result[i:i + chunk_size]
            await asyncio.sleep(0.02)
