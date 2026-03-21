# grove/modules/pr_review/handler.py
"""PR Review module — requirement alignment checking."""
import logging
import re
from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.pr_review.prompts import PR_ALIGNMENT_PROMPT, DIFF_SUMMARY_PROMPT

logger = logging.getLogger(__name__)

class PRReviewModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config

    @subscribe(EventType.PR_OPENED)
    async def on_pr_opened(self, event: Event) -> None:
        pr_data = event.payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        pr_title = pr_data.get("title", "")
        pr_body = pr_data.get("body", "") or ""
        repo = event.payload.get("repository", {}).get("full_name", self.config.project.repo)
        logger.info("Reviewing PR #%s: %s", pr_number, pr_title)
        try:
            diff = self.github.get_pr_diff(repo, pr_number)
        except Exception:
            logger.exception("Failed to get diff for PR #%s", pr_number)
            return
        diff_summary = await self.llm.chat(
            system_prompt=DIFF_SUMMARY_PROMPT.format(diff=diff[:8000]),
            messages=[{"role": "user", "content": "请总结代码变更。"}], max_tokens=512)
        related_issues = re.findall(r"#(\d+)", pr_body)
        related_str = ", ".join(f"#{n}" for n in related_issues) if related_issues else "无关联 Issue"
        prd_content = "未找到关联的 PRD 文档。"
        try:
            prd_content = await self.lark.read_doc(self.config.lark.space_id)
        except Exception:
            logger.debug("Could not read PRD for PR #%s", pr_number)
        review = await self.llm.chat(
            system_prompt=PR_ALIGNMENT_PROMPT.format(
                pr_number=pr_number, pr_title=pr_title, related_issues=related_str,
                diff_summary=diff_summary, prd_content=prd_content[:4000]),
            messages=[{"role": "user", "content": "请进行需求对齐分析。"}], max_tokens=1024)
        self.github.add_pr_comment(repo, pr_number, review)
        logger.info("Posted alignment review on PR #%s", pr_number)
        if "⚠️" in review and "无" not in review.split("⚠️")[1][:20]:
            await self.lark.send_text(self.config.lark.chat_id,
                f"PR #{pr_number}「{pr_title}」需求对齐检查发现遗漏项，请查看 PR 评论。")
