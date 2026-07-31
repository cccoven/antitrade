"""Authoritative slash-command registry and parser for the AI assistant."""

from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class AssistantCommandSpec:
    name: str
    usage: str
    tool_names: frozenset[str]
    argument_required: bool = False


@dataclass(frozen=True)
class ParsedAssistantCommand:
    specs: tuple[AssistantCommandSpec, ...]
    argument: str

    @property
    def spec(self) -> AssistantCommandSpec:
        return self.specs[0]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.specs)

    @property
    def tool_names(self) -> frozenset[str]:
        return frozenset().union(*(spec.tool_names for spec in self.specs))

    @property
    def is_multiple(self) -> bool:
        return len(self.specs) > 1


@dataclass(frozen=True)
class MarketCommandArguments:
    asset_class: str
    symbol: str
    interval: str


@dataclass(frozen=True)
class OpportunityCommandArguments:
    market: str | None = None
    symbol: str | None = None
    direction: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    target_price: float | None = None
    quantity: float | None = None
    interval: str = "1day"
    account_size: float | None = None
    plan_id: str | None = None
    strategy_id: str | None = None
    setup_type: str | None = None
    confidence: int | None = None
    thesis: str = ""


class AssistantCommandError(ValueError):
    def __init__(self, code: str, command: str, usage: str | None = None):
        super().__init__(code)
        self.code = code
        self.command = command
        self.usage = usage


_COMMANDS = (
    AssistantCommandSpec(
        "/stock", "/stock <symbol> [interval]", frozenset({"get_stock_market_data"}), True,
    ),
    AssistantCommandSpec(
        "/forex", "/forex <pair> [interval]", frozenset({"get_forex_market_data"}), True,
    ),
    AssistantCommandSpec(
        "/crypto", "/crypto <pair> [interval]", frozenset({"get_crypto_market_data"}), True,
    ),
    AssistantCommandSpec(
        "/futures", "/futures <symbol> [interval]",
        frozenset({"get_futures_market_data"}), True,
    ),
    AssistantCommandSpec(
        "/check",
        "/check <market> <symbol> <long|short> entry=<price> stop=<price> [target=<price>] [quantity=<size>]",
        frozenset({"check_trade_opportunity"}),
        True,
    ),
    AssistantCommandSpec(
        "/macro", "/macro <topic or FRED series>", frozenset({"get_macro_data"}), True,
    ),
    AssistantCommandSpec(
        "/news", "/news [topic or symbol]",
        frozenset({"list_feed_news", "get_market_briefing"}),
    ),
    AssistantCommandSpec(
        "/journal", "/journal [question or filters]",
        frozenset({"get_journal_stats", "list_trades", "get_daily_review"}),
    ),
    AssistantCommandSpec(
        "/portfolio", "/portfolio [portfolio or question]",
        frozenset({"list_portfolios", "get_portfolio_summary", "list_portfolio_entries"}),
    ),
    AssistantCommandSpec(
        "/strategy", "/strategy [strategy or question]",
        frozenset({"list_strategies", "get_strategy", "search_knowledge"}),
    ),
    AssistantCommandSpec(
        "/review", "/review [YYYY-MM-DD or question]",
        frozenset({"get_daily_review", "get_journal_stats", "list_trades"}),
    ),
    AssistantCommandSpec(
        "/remember", "/remember <preference or style note>",
        frozenset({"list_memories", "remember_memory", "forget_memories"}), True,
    ),
    AssistantCommandSpec("/help", "/help", frozenset()),
)

COMMANDS = {item.name: item for item in _COMMANDS}
_COMMAND_TOKEN_PATTERN = re.compile(
    r"(?<!\S)(/[a-z][\w-]*)(?=\s|$)",
    re.IGNORECASE,
)
_MARKET_COMMAND_ASSET_CLASSES = {
    "/stock": "stock",
    "/forex": "forex",
    "/crypto": "crypto",
    "/futures": "futures",
}
MARKET_INTERVALS = frozenset({
    "1min", "5min", "15min", "30min", "45min",
    "1h", "2h", "4h", "1day", "1week", "1month",
})


def list_assistant_commands() -> list[str]:
    return [item.name for item in _COMMANDS]


def command_help_markdown(lang: str) -> str:
    rows = "\n".join(f"- `{item.usage}`" for item in _COMMANDS)
    if lang == "zh":
        return f"当前支持的命令：\n\n{rows}\n\n选择命令后补充参数或问题再发送。"
    return f"Available commands:\n\n{rows}\n\nChoose a command, add any arguments or question, then send it."


def command_error_markdown(error: AssistantCommandError, lang: str) -> str:
    if error.code == "missing_argument":
        if lang == "zh":
            return f"`{error.command}` 缺少必要参数。用法：`{error.usage}`"
        return f"`{error.command}` is missing a required argument. Usage: `{error.usage}`"
    if error.code == "invalid_arguments":
        if lang == "zh":
            return f"`{error.command}` 参数无效。用法：`{error.usage}`"
        return f"Invalid arguments for `{error.command}`. Usage: `{error.usage}`"
    if lang == "zh":
        return f"不支持命令 `{error.command}`。输入 `/help` 查看当前可用命令。"
    return f"Unknown command `{error.command}`. Enter `/help` to see available commands."


def parse_assistant_command(content: str) -> ParsedAssistantCommand | None:
    stripped = content.lstrip()
    if stripped.startswith("/"):
        leading_token = stripped.split(maxsplit=1)[0].lower()
        if leading_token not in COMMANDS:
            raise AssistantCommandError("unknown_command", leading_token)

    specs: list[AssistantCommandSpec] = []
    seen: set[str] = set()

    def remove_known_command(match: re.Match[str]) -> str:
        spec = COMMANDS.get(match.group(1).lower())
        if spec is None:
            return match.group(0)
        if spec.name not in seen:
            seen.add(spec.name)
            specs.append(spec)
        return ""

    argument = _COMMAND_TOKEN_PATTERN.sub(remove_known_command, content)
    if not specs:
        return None
    argument = re.sub(r"[ \t]{2,}", " ", argument)
    argument = re.sub(r"[ \t]*\n[ \t]*", "\n", argument).strip()
    missing = next(
        (spec for spec in specs if spec.argument_required and not argument),
        None,
    )
    if missing is not None:
        raise AssistantCommandError("missing_argument", missing.name, missing.usage)
    return ParsedAssistantCommand(specs=tuple(specs), argument=argument)


def parse_market_command_arguments(command: ParsedAssistantCommand) -> MarketCommandArguments | None:
    asset_class = _MARKET_COMMAND_ASSET_CLASSES.get(command.spec.name)
    if asset_class is None:
        return None
    parts = command.argument.split()
    if len(parts) not in {1, 2}:
        raise AssistantCommandError(
            "invalid_arguments", command.spec.name, command.spec.usage,
        )
    interval = parts[1].lower() if len(parts) == 2 else "1day"
    if interval not in MARKET_INTERVALS:
        raise AssistantCommandError(
            "invalid_arguments", command.spec.name, command.spec.usage,
        )
    symbol = parts[0].strip()
    if not symbol or len(symbol) > 40:
        raise AssistantCommandError(
            "invalid_arguments", command.spec.name, command.spec.usage,
        )
    return MarketCommandArguments(
        asset_class=asset_class,
        symbol=symbol,
        interval=interval,
    )


def _finite_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError("not_a_number") from exc
    if not math.isfinite(parsed):
        raise ValueError("not_finite")
    return parsed


def parse_opportunity_command_arguments(
    command: ParsedAssistantCommand,
) -> OpportunityCommandArguments | None:
    if command.spec.name != "/check":
        return None
    parts = command.argument.split()
    usage = command.spec.usage
    if len(parts) == 1 and parts[0].startswith("plan="):
        plan_id = parts[0].split("=", 1)[1].strip()
        if not plan_id:
            raise AssistantCommandError("invalid_arguments", command.spec.name, usage)
        return OpportunityCommandArguments(plan_id=plan_id)
    if len(parts) < 5:
        raise AssistantCommandError("invalid_arguments", command.spec.name, usage)

    market, symbol, direction = parts[:3]
    market = market.lower()
    direction = direction.lower()
    if market not in {"stock", "forex", "crypto", "futures"} or direction not in {"long", "short"}:
        raise AssistantCommandError("invalid_arguments", command.spec.name, usage)

    raw: dict[str, str] = {}
    aliases = {
        "entry": "entry_price", "stop": "stop_loss", "target": "target_price",
        "account": "account_size", "plan": "plan_id", "strategy": "strategy_id",
        "setup": "setup_type",
    }
    allowed = {
        "entry_price", "stop_loss", "target_price", "quantity", "interval",
        "account_size", "plan_id", "strategy_id", "setup_type", "confidence", "thesis",
    }
    for token in parts[3:]:
        if "=" not in token:
            raise AssistantCommandError("invalid_arguments", command.spec.name, usage)
        key, value = token.split("=", 1)
        key = aliases.get(key.lower(), key.lower())
        if key not in allowed or not value or key in raw:
            raise AssistantCommandError("invalid_arguments", command.spec.name, usage)
        raw[key] = value
    if "entry_price" not in raw or "stop_loss" not in raw:
        raise AssistantCommandError("invalid_arguments", command.spec.name, usage)

    try:
        numeric = {
            key: _finite_float(raw[key])
            for key in ("entry_price", "stop_loss", "target_price", "quantity", "account_size")
            if key in raw
        }
        confidence = int(raw["confidence"]) if "confidence" in raw else None
    except (ValueError, TypeError) as exc:
        raise AssistantCommandError("invalid_arguments", command.spec.name, usage) from exc
    interval = raw.get("interval", "1day").lower()
    if (
        interval not in MARKET_INTERVALS
        or numeric["entry_price"] == numeric["stop_loss"]
        or numeric.get("quantity", 1) <= 0
        or numeric.get("account_size", 1) <= 0
        or (confidence is not None and not 0 <= confidence <= 10)
    ):
        raise AssistantCommandError("invalid_arguments", command.spec.name, usage)

    return OpportunityCommandArguments(
        market=market,
        symbol=symbol,
        direction=direction,
        entry_price=numeric["entry_price"],
        stop_loss=numeric["stop_loss"],
        target_price=numeric.get("target_price"),
        quantity=numeric.get("quantity"),
        interval=interval,
        account_size=numeric.get("account_size"),
        plan_id=raw.get("plan_id"),
        strategy_id=raw.get("strategy_id"),
        setup_type=raw.get("setup_type"),
        confidence=confidence,
        thesis=raw.get("thesis", ""),
    )
