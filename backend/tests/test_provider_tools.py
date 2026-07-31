import pytest


def test_create_provider_demo(monkeypatch):
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "demo")
    from services.analyzer import create_provider
    from providers.demo_provider import DemoProvider
    assert isinstance(create_provider(), DemoProvider)


def test_create_provider_anthropic(monkeypatch):
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_MODEL", "claude-x")
    from services.analyzer import create_provider
    from providers.anthropic_provider import AnthropicProvider
    assert isinstance(create_provider(), AnthropicProvider)


def test_create_provider_rejects_claude_cli(monkeypatch):
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "claude_cli")
    from services.analyzer import create_provider
    with pytest.raises(ValueError):
        create_provider()
