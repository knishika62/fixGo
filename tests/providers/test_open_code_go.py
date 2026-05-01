"""Tests for the OpenCode Go provider."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.defaults import OPENCODE_GO_DEFAULT_BASE
from providers.open_code_go import OpenCodeGoProvider
from providers.registry import PROVIDER_FACTORIES


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "test-model"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.5
        self.top_p = 0.9
        self.system = "System prompt"
        self.stop_sequences = ["STOP"]
        self.tools = []
        self.extra_body = {}
        self.thinking = MagicMock()
        self.thinking.enabled = True
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    """Mock the global rate limiter to prevent waiting."""
    with patch("providers.openai_compat.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value
        instance.wait_if_blocked = AsyncMock(return_value=False)

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        yield instance


@pytest.fixture
def open_code_go_provider(provider_config):
    return OpenCodeGoProvider(provider_config)


@pytest.mark.asyncio
async def test_init(provider_config):
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = OpenCodeGoProvider(provider_config)
        assert provider._api_key == "test_key"
        assert provider._base_url == "https://test.api.nvidia.com/v1"
        mock_openai.assert_called_once()


@pytest.mark.asyncio
async def test_init_uses_default_base_url():
    from providers.base import ProviderConfig

    config = ProviderConfig(api_key="test_key")
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = OpenCodeGoProvider(config)
        assert provider._base_url == OPENCODE_GO_DEFAULT_BASE
        mock_openai.assert_called_once()


@pytest.mark.asyncio
async def test_build_request_body(open_code_go_provider):
    req = MockRequest()
    body = open_code_go_provider._build_request_body(req)

    assert body["model"] == "test-model"
    assert body["temperature"] == 0.5
    assert len(body["messages"]) == 2  # System + User
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][0]["content"] == "System prompt"
    assert body["messages"][1]["role"] == "user"
    assert body["messages"][1]["content"] == "Hello"
    assert "extra_body" not in body


@pytest.mark.asyncio
async def test_build_request_body_omits_reasoning_when_disabled(open_code_go_provider):
    req = MockRequest()
    req.thinking.enabled = False
    body = open_code_go_provider._build_request_body(req, thinking_enabled=False)

    messages = body["messages"]
    assert not any("reasoning_content" in m for m in messages)


@pytest.mark.asyncio
async def test_stream_response_text(open_code_go_provider):
    req = MockRequest()

    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [
        MagicMock(
            delta=MagicMock(content="Hello", reasoning_content=""),
            finish_reason=None,
        )
    ]
    mock_chunk1.usage = None

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [
        MagicMock(
            delta=MagicMock(content=" World", reasoning_content=""),
            finish_reason="stop",
        )
    ]
    mock_chunk2.usage = MagicMock(completion_tokens=10)

    async def mock_stream():
        yield mock_chunk1
        yield mock_chunk2

    with patch.object(
        open_code_go_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [e async for e in open_code_go_provider.stream_response(req)]

    assert len(events) > 0
    assert "event: message_start" in events[0]

    text_content = ""
    for e in events:
        if "event: content_block_delta" in e and '"text_delta"' in e:
            for line in e.splitlines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "delta" in data and "text" in data["delta"]:
                        text_content += data["delta"]["text"]

    assert "Hello World" in text_content
    assert any("event: message_stop" in e for e in events)


def test_registry_factory():
    assert "open_code_go" in PROVIDER_FACTORIES
