# tests/test_integrations/test_lark_cards.py
from grove.integrations.lark.cards import build_notification_card, build_task_assignment_card


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
