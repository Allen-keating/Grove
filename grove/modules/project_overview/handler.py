"""Project Overview Report module — management-level project status."""
import json
import logging

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_project_overview_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.project_overview.collectors import OverviewDataCollector
from grove.modules.project_overview.prompts import OVERVIEW_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


class ProjectOverviewModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.config = config
        self._storage = storage
        self._collector = OverviewDataCollector(github, config.project.repo, storage)

    @subscribe(EventType.CRON_PROJECT_OVERVIEW)
    @subscribe(EventType.INTERNAL_PROJECT_OVERVIEW)
    async def on_project_overview(self, event: Event) -> None:
        chat_id = event.payload.get("chat_id", self.config.lark.chat_id)
        logger.info("Generating project overview report...")

        data = self._collector.collect()
        snapshots = self._collector.load_7day_snapshots()
        trends = self._collector.compute_trends(snapshots)

        # PRD completion check
        prd_completion = await self._check_prd_completion(data)

        # LLM analysis
        milestones_text = "\n".join(
            f"- {m['title']}: {m['closed_issues']}/{m['open_issues'] + m['closed_issues']}"
            f" (due: {m.get('due_on', 'N/A')})"
            for m in data["milestones"]
        ) or "暂无"

        prd_text = "未生成逆向 PRD"
        if prd_completion:
            prd_text = (
                f"已完成: {prd_completion.get('done', 0)}, "
                f"进行中: {prd_completion.get('in_progress', 0)}, "
                f"未开始: {prd_completion.get('not_started', 0)}"
            )

        analysis = await self._analyze(data, milestones_text, prd_text)

        # Build milestone summary for card
        ms_summary = [
            {
                "title": m["title"],
                "progress_pct": round(m["closed_issues"] / max(m["open_issues"] + m["closed_issues"], 1) * 100),
                "open": m["open_issues"],
                "closed": m["closed_issues"],
            }
            for m in data["milestones"]
        ]

        # Send card
        card = build_project_overview_card(
            date=data["date"], health=analysis.get("health", "🟡 需关注"),
            milestones=ms_summary, trends=trends,
            prd_completion=prd_completion,
            risks=analysis.get("risks", []),
            suggestions=analysis.get("suggestions", ""),
        )
        await self.lark.send_card(chat_id, card)

        # Create GitHub issue
        report_body = self._build_report_markdown(data, trends, prd_completion, analysis)
        self._collector.github.create_issue(
            repo=self.config.project.repo,
            title=f"📊 项目进度总览 — {data['date']}",
            body=report_body, labels=["project-overview"],
        )

        # Save snapshot
        self._storage.write_json(
            f"memory/snapshots/{data['date']}-overview.json",
            {**data, "trends": trends, "prd_completion": prd_completion, "analysis": analysis},
        )
        logger.info("Project overview report sent")

    async def _check_prd_completion(self, data: dict) -> dict | None:
        try:
            doc_info = self._storage.read_yaml("memory/project-scan/reverse-prd-doc-id.yml")
            doc_id = doc_info.get("doc_id")
            if not doc_id:
                return None
            prd_content = await self.lark.read_doc(doc_id)
            return {"done": data["closed_issues"], "in_progress": data["open_issues"],
                    "not_started": 0}
        except (FileNotFoundError, Exception):
            return None

    async def _analyze(self, data: dict, milestones_text: str, prd_text: str) -> dict:
        prompt = OVERVIEW_ANALYSIS_PROMPT.format(
            completion_rate=data["completion_rate"],
            closed_this_week=len(data.get("recent_commits", [])),
            new_this_week=data["open_issues"],
            milestones=milestones_text,
            prd_completion=prd_text,
        )
        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请分析。"}],
                max_tokens=1024,
            )
            return json.loads(response)
        except Exception:
            logger.warning("Overview analysis LLM call failed")
            return {"health": "🟡 需关注", "risks": [], "suggestions": "LLM 分析失败，请手动检查。"}

    def _build_report_markdown(self, data, trends, prd_completion, analysis) -> str:
        lines = [
            f"# 📊 项目进度总览 — {data['date']}\n",
            f"**健康度：** {analysis.get('health', 'N/A')}\n",
            "## 概览\n",
            f"- Issues 完成率: {data['completion_rate']}% ({data['closed_issues']}/{data['total_issues']})",
            f"- 开放 Issues: {data['open_issues']}",
            f"- 开放 PRs: {len(data['open_prs'])}\n",
        ]
        if data["milestones"]:
            lines.append("## 里程碑\n")
            for m in data["milestones"]:
                total = m["open_issues"] + m["closed_issues"]
                pct = round(m["closed_issues"] / max(total, 1) * 100)
                lines.append(f"- **{m['title']}** — {pct}% ({m['closed_issues']}/{total})")
        if analysis.get("risks"):
            lines.append("\n## 风险\n")
            for r in analysis["risks"]:
                lines.append(f"- ⚠️ {r}")
        lines.append(f"\n## 建议\n\n{analysis.get('suggestions', '')}")
        return "\n".join(lines)
