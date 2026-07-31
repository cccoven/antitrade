import pytest


def test_command_registry_and_parser_are_authoritative():
    from services.assistant_commands import list_assistant_commands, parse_assistant_command

    assert list_assistant_commands() == [
        "/stock", "/forex", "/crypto", "/futures", "/check", "/macro", "/news", "/journal",
        "/portfolio", "/strategy", "/review", "/remember", "/help",
    ]
    parsed = parse_assistant_command("  /STOCK AAPL 1day")
    assert parsed is not None
    assert parsed.spec.name == "/stock"
    assert parsed.argument == "AAPL 1day"
    assert parse_assistant_command("Analyze AAPL") is None


def test_multiple_commands_share_text_and_preserve_order():
    from services.assistant_commands import parse_assistant_command

    parsed = parse_assistant_command("Compare /stock AAPL with /news and /stock")

    assert parsed is not None
    assert parsed.names == ("/stock", "/news")
    assert parsed.argument == "Compare AAPL with and"
    assert parsed.is_multiple is True
    assert parsed.tool_names == frozenset({
        "get_stock_market_data",
        "list_feed_news",
        "get_market_briefing",
    })


def test_market_command_arguments_are_deterministic():
    from services.assistant_commands import (
        parse_assistant_command,
        parse_market_command_arguments,
    )

    parsed = parse_assistant_command("/futures MNQ 15min")
    args = parse_market_command_arguments(parsed)
    assert args is not None
    assert (args.asset_class, args.symbol, args.interval) == ("futures", "MNQ", "15min")


def test_check_command_arguments_are_typed():
    from services.assistant_commands import (
        parse_assistant_command,
        parse_opportunity_command_arguments,
    )

    parsed = parse_assistant_command(
        "/check futures MNQ long entry=20000 stop=19980 target=20040 quantity=2 interval=5min"
    )
    args = parse_opportunity_command_arguments(parsed)
    assert args is not None
    assert args.market == "futures"
    assert args.entry_price == 20000
    assert args.stop_loss == 19980
    assert args.quantity == 2
    assert args.interval == "5min"


def test_check_command_accepts_plan_id_only():
    from services.assistant_commands import (
        parse_assistant_command,
        parse_opportunity_command_arguments,
    )

    args = parse_opportunity_command_arguments(parse_assistant_command("/check plan=plan-1"))
    assert args is not None and args.plan_id == "plan-1"


@pytest.mark.parametrize("content", [
    "/stock AAPL nonsense",
    "/check stock AAPL long entry=100",
    "/check futures MNQ sideways entry=100 stop=90",
])
def test_typed_command_arguments_reject_invalid_values(content):
    from services.assistant_commands import (
        AssistantCommandError,
        parse_assistant_command,
        parse_market_command_arguments,
        parse_opportunity_command_arguments,
    )

    parsed = parse_assistant_command(content)
    with pytest.raises(AssistantCommandError):
        parse_market_command_arguments(parsed)
        parse_opportunity_command_arguments(parsed)


@pytest.mark.parametrize("content", ["/stock", "/forex   ", "/remember\n"])
def test_commands_validate_required_arguments(content):
    from services.assistant_commands import AssistantCommandError, parse_assistant_command

    with pytest.raises(AssistantCommandError) as exc_info:
        parse_assistant_command(content)
    assert exc_info.value.code == "missing_argument"


def test_unknown_command_is_rejected():
    from services.assistant_commands import AssistantCommandError, parse_assistant_command

    with pytest.raises(AssistantCommandError) as exc_info:
        parse_assistant_command("/does-not-exist something")
    assert exc_info.value.code == "unknown_command"


def test_command_builds_a_tool_scoped_agent(db, user_id, monkeypatch):
    from services.agent import _DemoModel, build_agent
    from services.assistant_commands import parse_assistant_command

    monkeypatch.setattr("services.agent.create_model", lambda: _DemoModel())
    command = parse_assistant_command("/stock AAPL")
    agent = build_agent(db, user_id, command=command)

    assert {tool.name for tool in agent.tools} == {"get_stock_market_data"}
    assert agent.model_settings.tool_choice == "required"


def test_multiple_commands_build_a_combined_tool_scoped_agent(db, user_id, monkeypatch):
    from services.agent import _DemoModel, build_agent
    from services.assistant_commands import parse_assistant_command

    monkeypatch.setattr("services.agent.create_model", lambda: _DemoModel())
    command = parse_assistant_command("/stock /news Compare AAPL")
    agent = build_agent(db, user_id, command=command)

    assert {tool.name for tool in agent.tools} == {
        "get_stock_market_data",
        "list_feed_news",
        "get_market_briefing",
    }
    assert agent.model_settings.tool_choice == "required"


@pytest.mark.asyncio
async def test_help_command_returns_without_running_a_model(db, user_id, monkeypatch):
    from services.chat import ChatService

    def fail_if_called():  # pragma: no cover - assertion helper
        raise AssertionError("/help must not instantiate a model")

    monkeypatch.setattr("services.agent.create_model", fail_if_called)
    service = ChatService(db)
    conversation = service.create_conversation(user_id)

    chunks = []
    async for chunk in service.send_message(conversation["id"], user_id, "/help"):
        chunks.append(chunk)

    answer = "".join(chunk for chunk in chunks if isinstance(chunk, str))
    assert "/stock <symbol>" in answer
    assert service.get_messages(conversation["id"], user_id)[-1]["content"] == answer


@pytest.mark.asyncio
async def test_web_search_option_performs_an_initial_search(
    db, user_id, monkeypatch,
):
    import config
    from services.chat import ChatService
    from tests._fake_chat_model import FakeToolThenAnswer

    queries = []
    monkeypatch.setattr(config, "TAVILY_API_KEY", "test-key")
    monkeypatch.setattr("services.agent.create_model", lambda: FakeToolThenAnswer())
    monkeypatch.setattr(
        "services.web_search.search_web",
        lambda query, max_results=5: queries.append((query, max_results)) or {
            "query": query,
            "results": [{"title": "Current source", "url": "https://example.com"}],
        },
    )
    service = ChatService(db)
    conversation = service.create_conversation(user_id)

    async for _chunk in service.send_message(
        conversation["id"], user_id, "latest NQ news", web_search=True,
    ):
        pass

    assert queries == [("latest NQ news", 5)]
