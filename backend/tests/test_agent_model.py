import pytest


def test_create_model_demo(monkeypatch):
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "demo")
    from services.agent import create_model, _DemoModel
    assert isinstance(create_model(), _DemoModel)


def test_create_model_openai(monkeypatch):
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://x/v1")
    monkeypatch.setattr(config, "LLM_MODEL", "gpt-x")
    from services.agent import create_model
    from agents import OpenAIChatCompletionsModel
    assert isinstance(create_model(), OpenAIChatCompletionsModel)


def test_create_model_anthropic(monkeypatch):
    # Anthropic goes through its OpenAI-compatible endpoint (same model class).
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://api.anthropic.com/v1")
    monkeypatch.setattr(config, "LLM_MODEL", "claude-x")
    from services.agent import create_model
    from agents import OpenAIChatCompletionsModel
    assert isinstance(create_model(), OpenAIChatCompletionsModel)


def test_create_model_unknown(monkeypatch):
    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "nope")
    from services.agent import create_model
    with pytest.raises(ValueError):
        create_model()


def test_vision_capability_is_explicit_and_disabled_for_demo(monkeypatch):
    import config
    from services.agent import is_vision_available

    monkeypatch.setattr(config, "LLM_VISION_ENABLED", True)
    monkeypatch.setattr(config, "LLM_PROVIDER", "demo")
    assert is_vision_available() is False

    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    assert is_vision_available() is True

    monkeypatch.setattr(config, "LLM_VISION_ENABLED", False)
    assert is_vision_available() is False
