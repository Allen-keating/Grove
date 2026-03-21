from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.modules.pr_review.handler import PRReviewModule

class TestPRReviewModule:
    @pytest.fixture
    def module(self):
        bus = EventBus()
        llm = MagicMock()
        lark = MagicMock()
        lark.send_text = AsyncMock()
        lark.read_doc = AsyncMock(return_value="# 登录模块 PRD\n\n需要实现登录页面...")
        github = MagicMock()
        github.get_pr_diff = MagicMock(return_value="diff --git a/login.py...")
        github.add_pr_comment = MagicMock()
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"
        config.lark.space_id = "spc_test"
        module = PRReviewModule(bus=bus, llm=llm, lark=lark, github=github, config=config)
        bus.register(module)
        return module, bus

    async def test_pr_opened_posts_review_comment(self, module):
        mod, bus = module
        call_count = 0
        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "- 新增了登录页面组件"
            return "## 🌳 Grove — 需求对齐检查\n\n### 对齐度评估\n代码与需求基本对齐。"
        mod.llm.chat = AsyncMock(side_effect=mock_chat)
        event = Event(type=EventType.PR_OPENED, source="github",
                     payload={"pull_request": {"number": 45, "title": "Add login page", "body": "Fixes #23"},
                              "repository": {"full_name": "org/repo"}},
                     member=Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend"))
        await bus.dispatch(event)
        mod.github.get_pr_diff.assert_called_once()
        mod.github.add_pr_comment.assert_called_once()

    async def test_pr_without_diff_skips(self, module):
        mod, bus = module
        mod.github.get_pr_diff = MagicMock(side_effect=Exception("API error"))
        event = Event(type=EventType.PR_OPENED, source="github",
                     payload={"pull_request": {"number": 99, "title": "Test", "body": ""},
                              "repository": {"full_name": "org/repo"}})
        await bus.dispatch(event)
        mod.github.add_pr_comment.assert_not_called()
