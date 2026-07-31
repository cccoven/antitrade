import pytest


def test_agent_mode_turn_limits_are_bounded():
    from services.agent import agent_max_turns, agent_model_settings, normalize_agent_mode

    assert agent_max_turns("quick") == 4
    assert agent_max_turns("standard") == 8
    assert agent_max_turns("research") == 12
    assert normalize_agent_mode("unknown") == "standard"
    assert agent_model_settings("quick").max_tokens == 700
    assert agent_model_settings("standard").max_tokens == 1600
    assert agent_model_settings("research").max_tokens == 3200
    assert agent_model_settings("standard").parallel_tool_calls is False


def test_web_search_tool_requires_enable_and_configuration(db, user_id, monkeypatch):
    import config
    from services.agent import build_agent_tools

    monkeypatch.setattr(config, "TAVILY_API_KEY", "test-key")
    default_names = {tool.name for tool in build_agent_tools(db, user_id)}
    enabled_names = {
        tool.name for tool in build_agent_tools(db, user_id, enable_web_search=True)
    }

    assert "web_search" not in default_names
    assert "web_search" in enabled_names


@pytest.mark.asyncio
async def test_demo_prompt_optimizer_returns_structured_prompt(monkeypatch):
    import config
    from services.prompt_optimizer import optimize_prompt

    monkeypatch.setattr(config, "LLM_PROVIDER", "demo")
    optimized = await optimize_prompt("分析 AAPL", "zh")

    assert "分析 AAPL" in optimized
    assert "核心结论" in optimized
