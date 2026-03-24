# tests/test_modules/test_daily_report/test_collectors.py
from unittest.mock import AsyncMock

import pytest
from grove.modules.daily_report.collectors import DailyDataCollector

@pytest.mark.asyncio
class TestDailyDataCollector:
    @pytest.fixture
    def collector(self):
        github = AsyncMock()
        github.list_recent_commits.return_value = [
            {"sha": "abc1234", "message": "fix login", "author": "zhangsan", "date": "2026-03-21T10:00:00"},
            {"sha": "def5678", "message": "add API", "author": "lisi", "date": "2026-03-21T11:00:00"},
            {"sha": "ghi9012", "message": "add API v2", "author": "lisi", "date": "2026-03-21T12:00:00"},
        ]
        github.list_open_prs.return_value = [
            {"number": 45, "title": "Login UI", "author": "zhangsan",
             "created_at": "2026-03-20T10:00:00", "updated_at": "2026-03-20T10:00:00", "review_requested": True},
        ]
        github.list_issues.return_value = []
        github.list_milestones.return_value = [
            {"number": 1, "title": "MVP v1.0", "due_on": "2026-04-01T00:00:00", "open_issues": 6, "closed_issues": 12},
        ]
        return DailyDataCollector(github=github, repo="org/repo")

    async def test_collect_commits_per_member(self, collector):
        data = await collector.collect()
        assert data["commits_by_member"]["lisi"] == 2
        assert data["commits_by_member"]["zhangsan"] == 1

    async def test_collect_open_prs(self, collector):
        data = await collector.collect()
        assert len(data["open_prs"]) == 1

    async def test_collect_milestones(self, collector):
        data = await collector.collect()
        assert data["milestones"][0]["title"] == "MVP v1.0"

    async def test_collect_total_commits(self, collector):
        data = await collector.collect()
        assert data["total_commits"] == 3



@pytest.mark.asyncio
class TestDailyDataCollectorEnhanced:
    async def test_collect_with_classification(self):
        github = AsyncMock()
        github.list_recent_commits.return_value = [
            {"sha": "abc1234", "message": "feat: add login", "author": "zhangsan", "date": "2026-03-21T10:00:00"},
            {"sha": "def5678", "message": "fix: null check", "author": "lisi", "date": "2026-03-21T11:00:00"},
            {"sha": "ghi9012", "message": "docs: update readme", "author": "lisi", "date": "2026-03-21T12:00:00"},
        ]
        github.list_recent_commits_detailed.return_value = [
            {"sha": "abc1234", "message": "feat: add login", "author": "zhangsan", "date": "2026-03-21T10:00:00", "files": [{"filename": "login.py", "status": "added", "additions": 50, "deletions": 0}]},
            {"sha": "def5678", "message": "fix: null check", "author": "lisi", "date": "2026-03-21T11:00:00", "files": [{"filename": "api.py", "status": "modified", "additions": 2, "deletions": 1}]},
            {"sha": "ghi9012", "message": "docs: update readme", "author": "lisi", "date": "2026-03-21T12:00:00", "files": [{"filename": "README.md", "status": "modified", "additions": 5, "deletions": 2}]},
        ]
        github.list_open_prs.return_value = []
        github.list_issues.return_value = []
        github.list_milestones.return_value = []
        collector = DailyDataCollector(github=github, repo="org/repo")
        llm = AsyncMock()
        data = await collector.collect_with_classification(llm=llm)
        assert data["commits_by_type"]["feature"] == 1
        assert data["commits_by_type"]["bugfix"] == 1
        assert data["commits_by_type"]["docs"] == 1
        assert len(data["commit_details"]) == 3
        # LLM should NOT have been called (all conventional commits)
        llm.chat.assert_not_called()

    async def test_collect_with_classification_empty(self):
        github = AsyncMock()
        github.list_recent_commits.return_value = []
        github.list_recent_commits_detailed.return_value = []
        github.list_open_prs.return_value = []
        github.list_issues.return_value = []
        github.list_milestones.return_value = []
        collector = DailyDataCollector(github=github, repo="org/repo")
        data = await collector.collect_with_classification()
        assert data["commits_by_type"] == {}
        assert data["commit_details"] == []
