"""Data collection for project overview reports."""
import logging
from datetime import datetime, timedelta, timezone

from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient

logger = logging.getLogger(__name__)


class OverviewDataCollector:
    def __init__(self, github: GitHubClient, repo: str, storage: Storage):
        self.github = github
        self.repo = repo
        self._storage = storage

    def collect(self) -> dict:
        all_issues = self.github.list_issues(self.repo, state="all")
        open_issues = [i for i in all_issues if i.state == "open"]
        closed_issues = [i for i in all_issues if i.state == "closed"]
        total = len(all_issues)
        completion_rate = round(len(closed_issues) / total * 100) if total > 0 else 0

        since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent_commits = self.github.list_recent_commits_detailed(
            self.repo, since=since_7d, max_commits=200)

        open_prs = self.github.list_open_prs(self.repo)
        milestones = self.github.list_milestones(self.repo)

        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_issues": total,
            "open_issues": len(open_issues),
            "closed_issues": len(closed_issues),
            "completion_rate": completion_rate,
            "recent_commits": recent_commits,
            "open_prs": open_prs,
            "milestones": milestones,
        }

    def load_7day_snapshots(self) -> list[dict]:
        snapshots = []
        for i in range(7):
            date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            try:
                snap = self._storage.read_json(f"memory/snapshots/{date}.json")
                snapshots.append(snap)
            except FileNotFoundError:
                continue
        return snapshots

    def compute_trends(self, snapshots: list[dict]) -> dict:
        if not snapshots:
            return {"closed_issues": 0, "merged_prs": 0, "new_issues": 0}
        total_commits = sum(s.get("total_commits", 0) for s in snapshots)
        return {
            "closed_issues": total_commits,
            "merged_prs": len(snapshots),
            "new_issues": 0,
        }
