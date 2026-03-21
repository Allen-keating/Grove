# grove/modules/task_breakdown/decomposer.py
"""LLM-based PRD decomposition into tasks."""
import json
import logging
from dataclasses import dataclass, field
from grove.integrations.llm.client import LLMClient
from grove.modules.task_breakdown.prompts import DECOMPOSE_PROMPT

logger = logging.getLogger(__name__)

@dataclass
class DecomposedTask:
    title: str
    body: str = ""
    labels: list[str] = field(default_factory=list)
    estimated_days: int = 1
    required_skills: list[str] = field(default_factory=list)

class TaskDecomposer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def decompose(self, topic: str, prd_content: str) -> list[DecomposedTask]:
        try:
            prompt = DECOMPOSE_PROMPT.format(topic=topic, prd_content=prd_content)
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请拆解任务。"}],
                max_tokens=4096,
            )
            data = json.loads(response)
            return [
                DecomposedTask(
                    title=t["title"], body=t.get("body", ""),
                    labels=t.get("labels", []), estimated_days=t.get("estimated_days", 1),
                    required_skills=t.get("required_skills", []),
                )
                for t in data.get("tasks", [])
            ]
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Task decomposition failed: %s", exc)
            return []
