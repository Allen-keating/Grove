# tests/test_modules/test_daily_report/test_analyzer.py
import pytest
from grove.modules.daily_report.analyzer import ReportAnalyzer

class TestReportAnalyzer:
    @pytest.fixture
    def sample_data(self):
        return {
            "date": "2026-03-21", "total_commits": 10,
            "commits_by_member": {"zhangsan": 3, "lisi": 5, "wangwu": 0, "zhaoliu": 2},
            "open_prs": [
                {"number": 45, "title": "Login UI", "author": "zhangsan",
                 "created_at": "2026-03-19T10:00:00", "updated_at": "2026-03-19T10:00:00", "review_requested": True},
            ],
            "open_issues_count": 18,
            "milestones": [
                {"number": 1, "title": "MVP v1.0", "due_on": "2026-03-26T00:00:00", "open_issues": 6, "closed_issues": 12},
            ],
        }

    def test_detect_inactive_members(self, sample_data):
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        risks = analyzer.analyze(sample_data)
        inactive = [r for r in risks if r.risk_type == "inactive_member"]
        assert len(inactive) == 1
        assert "wangwu" in inactive[0].description

    def test_detect_stale_prs(self, sample_data):
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        risks = analyzer.analyze(sample_data)
        stale = [r for r in risks if r.risk_type == "stale_pr"]
        assert len(stale) == 1
        assert "#45" in stale[0].description

    def test_milestone_progress(self, sample_data):
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        summary = analyzer.get_milestone_summary(sample_data)
        assert summary[0]["progress_pct"] == 67

    def test_no_risks_when_healthy(self):
        data = {"date": "2026-03-21", "total_commits": 10,
                "commits_by_member": {"zhangsan": 3, "lisi": 3, "wangwu": 2, "zhaoliu": 2},
                "open_prs": [], "open_issues_count": 10, "milestones": []}
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        risks = analyzer.analyze(data)
        assert len(risks) == 0
