import pytest


def test_fake_embeddings_dim_and_overlap(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMBEDDINGS_PROVIDER", "demo")
    from services.rag import create_embeddings
    emb = create_embeddings()
    v = emb.embed_query("黄金 趋势 gold trend")
    assert len(v) == 1536
    import math
    def cos(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0
    related = emb.embed_query("黄金 趋势")
    unrelated = emb.embed_query("比特币 套利 btc arbitrage")
    assert cos(v, related) > cos(v, unrelated)


def test_create_embeddings_openai(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMBEDDINGS_PROVIDER", "openai")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://x/v1")
    from services.rag import create_embeddings
    from langchain_openai import OpenAIEmbeddings
    assert isinstance(create_embeddings(), OpenAIEmbeddings)


def test_embeddings_uses_separate_endpoint(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMBEDDINGS_PROVIDER", "openai")
    monkeypatch.setattr(config, "EMBEDDINGS_BASE_URL", "https://emb.example/v1")
    monkeypatch.setattr(config, "EMBEDDINGS_API_KEY", "embkey")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://chat.example/v1")
    monkeypatch.setattr(config, "LLM_API_KEY", "chatkey")
    from services.rag import create_embeddings
    emb = create_embeddings()
    assert "emb.example" in (emb.openai_api_base or "")


def test_embeddings_falls_back_to_llm_endpoint(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMBEDDINGS_PROVIDER", "openai")
    monkeypatch.setattr(config, "EMBEDDINGS_BASE_URL", None)
    monkeypatch.setattr(config, "EMBEDDINGS_API_KEY", None)
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://chat.example/v1")
    monkeypatch.setattr(config, "LLM_API_KEY", "chatkey")
    from services.rag import create_embeddings
    emb = create_embeddings()
    assert "chat.example" in (emb.openai_api_base or "")
