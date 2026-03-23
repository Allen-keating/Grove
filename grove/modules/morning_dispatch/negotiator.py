"""Parse member replies during task negotiation."""
import json
import logging

from grove.integrations.llm.client import LLMClient
from grove.modules.morning_dispatch.prompts import NEGOTIATE_PROMPT

logger = logging.getLogger(__name__)


class TaskNegotiator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def parse_reply(self, current_tasks: list[dict], message: str) -> dict:
        # Quick rule-based check for "confirm"
        clean = message.strip().lower()
        if clean in ("确认", "确定", "ok", "好的", "没问题", "可以"):
            return {"action": "confirm", "issue_number": None, "detail": ""}

        tasks_text = "\n".join(
            f"- #{t['issue_number']} {t['title']}" for t in current_tasks
        )
        prompt = NEGOTIATE_PROMPT.format(current_tasks=tasks_text, message=message)
        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": message}],
                max_tokens=256,
            )
            return json.loads(response)
        except Exception:
            logger.warning("Negotiate parse failed for: %s", message[:80])
            return {"action": "question", "issue_number": None, "detail": message}
