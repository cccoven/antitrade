import pytest
from providers.demo_provider import DemoProvider


@pytest.mark.asyncio
async def test_demo_provider_stream_yields_tokens():
    provider = DemoProvider()
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]
    chunks = []
    async for chunk in provider.stream(messages):
        chunks.append(chunk)

    assert len(chunks) > 0
    full = "".join(chunks)
    assert len(full) > 0


@pytest.mark.asyncio
async def test_demo_provider_stream_from_single_user_message():
    provider = DemoProvider()
    messages = [{"role": "user", "content": "分析一下我的交易"}]
    chunks = []
    async for chunk in provider.stream(messages):
        chunks.append(chunk)

    assert len(chunks) > 0
