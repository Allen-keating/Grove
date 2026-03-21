# grove/modules/daily_report/handler.py
"""Daily report module — collect, analyze, report, archive."""
import logging
from datetime import datetime, timezone
from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_daily_report_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.daily_report.collectors import DailyDataCollector
from grove.modules.daily_report.analyzer import ReportAnalyzer
from grove.modules.daily_report.prompts import REPORT_POLISH_PROMPT

logger = logging.getLogger(__name__)

class DailyReportModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig,
                 resolver: MemberResolver, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._collector = DailyDataCollector(github=github, repo=config.project.repo)
        self._analyzer = ReportAnalyzer(
            team_members=[m.github for m in resolver.all() if m.role != "design"])
        self._storage = storage

    @subscribe(EventType.CRON_DAILY_REPORT)
    async def on_daily_report(self, event: Event) -> None:
        logger.info("Generating daily report...")
        data = self._collector.collect()
        risks = self._analyzer.analyze(data)
        milestone_summary = self._analyzer.get_milestone_summary(data)
        suggestions = await self._generate_suggestions(data, risks, milestone_summary)
        self._save_snapshot(data, risks)
        card = build_daily_report_card(
            date=data["date"], milestone_summary=milestone_summary,
            member_activity=data["commits_by_member"],
            risks=[{"severity": r.severity, "description": r.description} for r in risks],
            suggestions=suggestions)
        await self.lark.send_card(self.config.lark.chat_id, card)
        report_body = self._build_github_report(data, risks, milestone_summary, suggestions)
        self.github.create_issue(
            repo=self.config.project.repo,
            title=f"📋 每日站会报告 — {data['date']}",
            body=report_body, labels=["daily-report"])
        for risk in risks:
            if risk.severity == "high":
                await self.bus.dispatch(Event(
                    type=EventType.INTERNAL_RISK_DETECTED, source="internal",
                    payload={"risk_type": risk.risk_type, "description": risk.description, "mention": risk.mention}))
        logger.info("Daily report sent (risks: %d)", len(risks))

    async def _generate_suggestions(self, data, risks, milestone_summary) -> str:
        prompt = REPORT_POLISH_PROMPT.format(
            date=data["date"],
            milestone_summary="\n".join(
                f"- {ms['title']}: {ms['progress_pct']}% ({ms['closed']}/{ms['closed']+ms['open']})"
                for ms in milestone_summary) or "暂无里程碑",
            member_activity="\n".join(f"- {m}: {c} commits" for m, c in data["commits_by_member"].items()),
            risks="\n".join(f"- [{r.severity}] {r.description}" for r in risks) or "无风险")
        return await self.llm.chat(system_prompt=prompt,
                                    messages=[{"role": "user", "content": "请给出建议。"}], max_tokens=512)

    def _save_snapshot(self, data, risks):
        snapshot = {**data, "risks": [{"type": r.risk_type, "severity": r.severity, "desc": r.description} for r in risks]}
        self._storage.write_json(f"memory/snapshots/{data['date']}.json", snapshot)

    def _build_github_report(self, data, risks, milestone_summary, suggestions) -> str:
        lines = [f"# 📋 每日站会报告 — {data['date']}\n"]
        lines.append("## 整体进度\n")
        for ms in milestone_summary:
            lines.append(f"里程碑「{ms['title']}」进度：{ms['progress_pct']}%（{ms['closed']}/{ms['closed']+ms['open']}）\n")
        lines.append("## 👥 成员动态\n")
        lines.extend(["| 成员 | 昨日 Commits | 状态 |", "|------|-------------|------|"])
        for member, count in data["commits_by_member"].items():
            status = "🟢 正常" if count > 0 else "🔴 无活动"
            lines.append(f"| @{member} | {count} | {status} |")
        lines.append("\n## ⚠️ 风险项\n")
        if risks:
            for r in risks:
                icon = "🔴" if r.severity == "high" else "🟡"
                lines.append(f"- {icon} {r.description}")
        else:
            lines.append("✅ 无风险项")
        lines.append(f"\n## 💡 建议\n\n{suggestions}")
        return "\n".join(lines)
