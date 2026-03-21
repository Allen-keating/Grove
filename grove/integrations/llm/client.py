# grove/integrations/llm/client.py
"""Claude API client with concurrency control, retry, and cost logging."""
import asyncio
import logging
import time
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", max_concurrency: int = 3):
        self.model = model
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._anthropic = anthropic.AsyncAnthropic(api_key=api_key)
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def chat(self, system_prompt, messages, max_tokens=4096) -> str:
        async with self._semaphore:
            start = time.monotonic()
            response = await self._anthropic.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                timeout=60.0,
            )
            elapsed = time.monotonic() - start
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            logger.info("LLM call: %d in / %d out tokens, %.1fs", input_tokens, output_tokens, elapsed)
            return response.content[0].text

    @property
    def total_tokens(self) -> dict[str, int]:
        return {"input": self._total_input_tokens, "output": self._total_output_tokens}
