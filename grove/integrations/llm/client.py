# grove/integrations/llm/client.py
"""LLM client with concurrency control, retry, and cost logging.

Supports OpenAI-compatible APIs (DashScope, etc.) and Anthropic Claude.
"""
import asyncio
import logging
import time
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key: str, model: str = "glm-5",
                 base_url: str = "https://coding.dashscope.aliyuncs.com/v1",
                 max_concurrency: int = 3):
        self.model = model
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def chat(self, system_prompt, messages, max_tokens=4096) -> str:
        async with self._semaphore:
            start = time.monotonic()
            full_messages = [{"role": "system", "content": system_prompt}] + messages
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=full_messages,
                timeout=60.0,
                extra_body={"enable_thinking": False},
            )
            elapsed = time.monotonic() - start
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            logger.info("LLM call: %d in / %d out tokens, %.1fs", input_tokens, output_tokens, elapsed)
            return response.choices[0].message.content

    @property
    def total_tokens(self) -> dict[str, int]:
        return {"input": self._total_input_tokens, "output": self._total_output_tokens}
