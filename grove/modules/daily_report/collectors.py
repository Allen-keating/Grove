# grove/modules/daily_report/collectors.py
"""Data collection from GitHub for daily reports."""
import logging
from datetime import datetime, timedelta, timezone
from grove.integrations.github.client import GitHubClient

logger = logging.getLogger(__name__)

class DailyDataCollector:
    def __init__(self, github: GitHubClient, repo: str):
        self.github = github
        self.repo = repo

    def collect(self) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        commits = self.github.list_recent_commits(self.repo, since=since)
        commits_by_member: dict[str, int] = {}
        for c in commits:
            author = c["author"]
            commits_by_member[author] = commits_by_member.get(author, 0) + 1
        open_prs = self.github.list_open_prs(self.repo)
        issues = self.github.list_issues(self.repo, state="open")
        milestones = self.github.list_milestones(self.repo)
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_commits": len(commits), "commits": commits,
            "commits_by_member": commits_by_member,
            "open_prs": open_prs, "open_issues_count": len(issues),
            "milestones": milestones,
        }
