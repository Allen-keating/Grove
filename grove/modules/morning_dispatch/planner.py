"""LLM-based per-member daily task planning."""
import json
import logging

from grove.core.events import Member
from grove.integrations.llm.client import LLMClient
from grove.modules.morning_dispatch.prompts import TASK_PLAN_PROMPT

logger = logging.getLogger(__name__)


class TaskPlanner:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def plan_for_member(
        self, member: Member, current_load: int,
        yesterday_commits: str, open_issues: str, milestones: str,
    ) -> dict:
        prompt = TASK_PLAN_PROMPT.format(
            member_name=member.name, member_role=member.role,
            member_skills=", ".join(member.skills),
            current_load=current_load,
            yesterday_commits=yesterday_commits or "无",
            open_issues=open_issues, milestones=milestones,
        )
        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请规划今日任务。"}],
                max_tokens=1024,
            )
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Task plan LLM returned non-JSON for %s, retrying", member.name)
            try:
                response = await self.llm.chat(
                    system_prompt=prompt + "\n重要：只输出 JSON！",
                    messages=[{"role": "user", "content": "请规划今日任务。只输出 JSON。"}],
                    max_tokens=1024,
                )
                return json.loads(response)
            except Exception:
                logger.exception("Task plan failed for %s", member.name)
                return {"tasks": [], "summary": "任务生成失败"}
        except Exception:
            logger.exception("Task plan failed for %s", member.name)
            return {"tasks": [], "summary": "任务生成失败"}
