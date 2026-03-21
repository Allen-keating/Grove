# grove/modules/daily_report/analyzer.py
"""Progress analysis and risk detection for daily reports."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class RiskItem:
    risk_type: str
    severity: str
    description: str
    mention: str = ""

class ReportAnalyzer:
    def __init__(self, team_members: list[str]):
        self._team_members = team_members

    def analyze(self, data: dict) -> list[RiskItem]:
        risks = []
        risks.extend(self._check_inactive_members(data))
        risks.extend(self._check_stale_prs(data))
        risks.extend(self._check_milestone_risks(data))
        return risks

    def _check_inactive_members(self, data):
        commits_by_member = data.get("commits_by_member", {})
        return [
            RiskItem(risk_type="inactive_member", severity="medium",
                     description=f"{m} 昨日无 commit 活动", mention=m)
            for m in self._team_members if commits_by_member.get(m, 0) == 0
        ]

    def _check_stale_prs(self, data):
        now = datetime.now(timezone.utc)
        risks = []
        for pr in data.get("open_prs", []):
            created = datetime.fromisoformat(pr["created_at"]).replace(tzinfo=timezone.utc)
            age_hours = (now - created).total_seconds() / 3600
            if age_hours > 48:
                risks.append(RiskItem(
                    risk_type="stale_pr", severity="medium",
                    description=f"PR #{pr['number']}「{pr['title']}」已开放 {int(age_hours)}h 未 review",
                    mention=pr["author"]))
        return risks

    def _check_milestone_risks(self, data):
        now = datetime.now(timezone.utc)
        risks = []
        for ms in data.get("milestones", []):
            if not ms.get("due_on"): continue
            due = datetime.fromisoformat(ms["due_on"]).replace(tzinfo=timezone.utc)
            days_left = (due - now).days
            if days_left <= 3 and ms["open_issues"] > 0:
                risks.append(RiskItem(
                    risk_type="milestone_risk", severity="high",
                    description=f"里程碑「{ms['title']}」还有 {days_left} 天截止，剩余 {ms['open_issues']} 个未完成任务"))
        return risks

    def get_milestone_summary(self, data) -> list[dict]:
        return [
            {"title": ms["title"],
             "progress_pct": round(ms["closed_issues"] / (ms["open_issues"] + ms["closed_issues"]) * 100)
                if (ms["open_issues"] + ms["closed_issues"]) > 0 else 0,
             "open": ms["open_issues"], "closed": ms["closed_issues"], "due_on": ms.get("due_on")}
            for ms in data.get("milestones", [])
        ]
