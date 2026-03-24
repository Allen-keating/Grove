# tests/test_integrations/test_llm_client.py
from unittest.mock import AsyncMock, MagicMock, patch
from grove.integrations.llm.client import LLMClient


class TestLLMClient:
    def test_client_init(self):
        with patch("grove.integrations.llm.client.AsyncOpenAI"):
            client = LLMClient(api_key="test_key", model="glm-5")
            assert client.model == "glm-5"
            assert client._semaphore._value == 3

    def test_client_custom_concurrency(self):
        with patch("grove.integrations.llm.client.AsyncOpenAI"):
            client = LLMClient(api_key="test_key", model="glm-5", max_concurrency=5)
            assert client._semaphore._value == 5

    async def test_chat_calls_llm(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello from LLM"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("grove.integrations.llm.client.AsyncOpenAI",
                    return_value=mock_client):
            client = LLMClient(api_key="test_key", model="glm-5")
            result = await client.chat(
                system_prompt="You are an AI PM.",
                messages=[{"role": "user", "content": "Hello"}],
            )
            assert result == "Hello from LLM"

    async def test_chat_timeout(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_response.usage = MagicMock(prompt_tokens=1, completion_tokens=1)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("grove.integrations.llm.client.AsyncOpenAI",
                    return_value=mock_client):
            client = LLMClient(api_key="test_key")
            await client.chat(system_prompt="test", messages=[{"role": "user", "content": "hi"}])
            call_kwargs = mock_client.chat.completions.create.call_args
            assert call_kwargs.kwargs.get("timeout") == 60.0
