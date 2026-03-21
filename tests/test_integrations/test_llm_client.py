# tests/test_integrations/test_llm_client.py
from unittest.mock import AsyncMock, MagicMock, patch
from grove.integrations.llm.client import LLMClient


class TestLLMClient:
    def test_client_init(self):
        with patch("grove.integrations.llm.client.anthropic.AsyncAnthropic"):
            client = LLMClient(api_key="test_key", model="claude-sonnet-4-6")
            assert client.model == "claude-sonnet-4-6"
            assert client._semaphore._value == 3

    def test_client_custom_concurrency(self):
        with patch("grove.integrations.llm.client.anthropic.AsyncAnthropic"):
            client = LLMClient(api_key="test_key", model="claude-sonnet-4-6", max_concurrency=5)
            assert client._semaphore._value == 5

    async def test_chat_calls_anthropic(self):
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

        with patch("grove.integrations.llm.client.anthropic.AsyncAnthropic",
                    return_value=mock_anthropic):
            client = LLMClient(api_key="test_key", model="claude-sonnet-4-6")
            result = await client.chat(
                system_prompt="You are an AI PM.",
                messages=[{"role": "user", "content": "Hello"}],
            )
            assert result == "Hello from Claude"

    async def test_chat_timeout(self):
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_response.usage = MagicMock(input_tokens=1, output_tokens=1)
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

        with patch("grove.integrations.llm.client.anthropic.AsyncAnthropic",
                    return_value=mock_anthropic):
            client = LLMClient(api_key="test_key")
            await client.chat(system_prompt="test", messages=[{"role": "user", "content": "hi"}])
            call_kwargs = mock_anthropic.messages.create.call_args
            assert call_kwargs.kwargs.get("timeout") == 60.0
