# tests/test_integrations/test_lark_cards.py
from grove.integrations.lark.cards import build_notification_card, build_task_assignment_card
from grove.integrations.lark.cards import build_project_overview_card, build_dispatch_summary_card


class TestLarkCards:
    def test_notification_card(self):
        card = build_notification_card("Test", "Content")
        assert card["header"]["title"]["content"] == "Test"

    def test_task_assignment_card(self):
        card = build_task_assignment_card(
            task_title="实现登录页面 UI", issue_number=23,
            priority="P0", estimated_days=3, assignee_name="张三", repo="org/repo",
        )
        assert card["header"]["title"]["content"] == "🌳 Grove — 新任务分配"
        elements = card["elements"]
        actions = [e for e in elements if e.get("tag") == "action"]
        assert len(actions) == 1
        buttons = actions[0]["actions"]
        assert len(buttons) == 3


class TestProjectOverviewCard:
    def test_builds_valid_card(self):
        card = build_project_overview_card(
            date="2026-03-23",
            health="🟢 正常",
            milestones=[{"title": "v1.0", "progress_pct": 80, "open": 2, "closed": 8}],
            trends={"closed_issues": 12, "merged_prs": 8, "new_issues": 5},
            prd_completion={"done": 6, "in_progress": 3, "not_started": 1},
            risks=["v1.0 可能延期"],
            suggestions="建议加速前端开发",
        )
        assert card["header"]["title"]["content"] == "📊 项目进度总览 — 2026-03-23"
        assert card["header"]["template"] == "purple"
        assert len(card["elements"]) > 0

    def test_no_prd_completion(self):
        card = build_project_overview_card(
            date="2026-03-23", health="🟡 需关注",
            milestones=[], trends={}, prd_completion=None,
            risks=[], suggestions="",
        )
        # Should not have PRD section
        content_texts = [e.get("text", {}).get("content", "") for e in card["elements"] if e.get("tag") == "div"]
        assert not any("PRD 完成度" in t for t in content_texts)

class TestDispatchSummaryCard:
    def test_builds_valid_card(self):
        card = build_dispatch_summary_card(
            date="2026-03-23",
            member_tasks=[
                {"name": "Alice", "tasks": [{"priority": "P0", "issue_number": 201, "title": "API"}], "confirmed": True},
                {"name": "Bob", "tasks": [{"priority": "P1", "issue_number": 202, "title": "UI"}], "confirmed": False},
            ],
        )
        assert card["header"]["title"]["content"] == "🌳 今日团队任务 — 2026-03-23"
        assert card["header"]["template"] == "green"
        content = card["elements"][0]["text"]["content"]
        assert "Alice" in content
        assert "⏰ 未确认" in content
        assert "#201" in content

    def test_empty_members(self):
        card = build_dispatch_summary_card(date="2026-03-23", member_tasks=[])
        assert card["header"]["title"]["content"] == "🌳 今日团队任务 — 2026-03-23"
