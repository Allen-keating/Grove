# tests/test_modules/test_daily_report/test_collectors.py
from unittest.mock import MagicMock
import pytest
from grove.modules.daily_report.collectors import DailyDataCollector

class TestDailyDataCollector:
    @pytest.fixture
    def collector(self):
        github = MagicMock()
        github.list_recent_commits = MagicMock(return_value=[
            {"sha": "abc1234", "message": "fix login", "author": "zhangsan", "date": "2026-03-21T10:00:00"},
            {"sha": "def5678", "message": "add API", "author": "lisi", "date": "2026-03-21T11:00:00"},
            {"sha": "ghi9012", "message": "add API v2", "author": "lisi", "date": "2026-03-21T12:00:00"},
        ])
        github.list_open_prs = MagicMock(return_value=[
            {"number": 45, "title": "Login UI", "author": "zhangsan",
             "created_at": "2026-03-20T10:00:00", "updated_at": "2026-03-20T10:00:00", "review_requested": True},
        ])
        github.list_issues = MagicMock(return_value=[])
        github.list_milestones = MagicMock(return_value=[
            {"number": 1, "title": "MVP v1.0", "due_on": "2026-04-01T00:00:00", "open_issues": 6, "closed_issues": 12},
        ])
        return DailyDataCollector(github=github, repo="org/repo")

    def test_collect_commits_per_member(self, collector):
        data = collector.collect()
        assert data["commits_by_member"]["lisi"] == 2
        assert data["commits_by_member"]["zhangsan"] == 1

    def test_collect_open_prs(self, collector):
        data = collector.collect()
        assert len(data["open_prs"]) == 1

    def test_collect_milestones(self, collector):
        data = collector.collect()
        assert data["milestones"][0]["title"] == "MVP v1.0"

    def test_collect_total_commits(self, collector):
        data = collector.collect()
        assert data["total_commits"] == 3
