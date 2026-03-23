# tests/test_modules/test_communication/test_intent_parser.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.core.events import Member
from grove.modules.communication.intent_parser import IntentParser, Intent


class TestIntent:
    def test_intent_types_exist(self):
        assert Intent.NEW_REQUIREMENT == "new_requirement"
        assert Intent.QUERY_PROGRESS == "query_progress"
        assert Intent.REQUEST_TASK_CHANGE == "request_task_change"
        assert Intent.REQUEST_BREAKDOWN == "request_breakdown"
        assert Intent.GENERAL_CHAT == "general_chat"
        assert Intent.UNKNOWN == "unknown"


class TestIntentParser:
    @pytest.fixture
    def parser(self):
        mock_llm = MagicMock()
        return IntentParser(llm=mock_llm)

    async def test_parse_new_requirement(self, parser):
        parser.llm.chat = AsyncMock(return_value='{"intent": "new_requirement", "topic": "暗黑模式", "confidence": 0.95}')
        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend")
        result = await parser.parse("我想加个暗黑模式", member)
        assert result.intent == Intent.NEW_REQUIREMENT
        assert result.topic == "暗黑模式"

    async def test_parse_query_progress(self, parser):
        parser.llm.chat = AsyncMock(return_value='{"intent": "query_progress", "topic": "", "confidence": 0.9}')
        member = Member(name="李四", github="lisi", lark_id="ou_xxx", role="backend")
        result = await parser.parse("目前进度怎么样？", member)
        assert result.intent == Intent.QUERY_PROGRESS

    async def test_parse_general_chat(self, parser):
        parser.llm.chat = AsyncMock(return_value='{"intent": "general_chat", "topic": "", "confidence": 0.8}')
        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend")
        result = await parser.parse("今天天气不错", member)
        assert result.intent == Intent.GENERAL_CHAT

    async def test_parse_handles_invalid_json(self, parser):
        parser.llm.chat = AsyncMock(return_value="not valid json")
        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend")
        result = await parser.parse("hello", member)
        assert result.intent == Intent.UNKNOWN


class TestIntentParserContext:
    @pytest.mark.asyncio
    async def test_dispatch_negotiate_priority(self):
        """Active dispatch + p2p chat → DISPATCH_NEGOTIATE without LLM call."""
        llm = AsyncMock()
        parser = IntentParser(llm=llm)
        member = Member(name="Test", github="test", lark_id="ou_test", role="backend")
        context = {"has_active_dispatch": True, "chat_type": "p2p"}
        result = await parser.parse("去掉 #205", member, context=context)
        assert result.intent == Intent.DISPATCH_NEGOTIATE
        assert result.confidence == 0.95
        llm.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_negotiate_not_in_group(self):
        """Active dispatch but group chat → normal LLM parsing."""
        llm = AsyncMock()
        llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.8}'
        parser = IntentParser(llm=llm)
        member = Member(name="Test", github="test", lark_id="ou_test", role="backend")
        context = {"has_active_dispatch": True, "chat_type": "group"}
        result = await parser.parse("去掉 #205", member, context=context)
        assert result.intent == Intent.GENERAL_CHAT
        llm.chat.assert_called_once()


class TestRuleMatch:
    """Test rule-based fast path — these should NOT call LLM."""

    @pytest.fixture
    def parser(self):
        llm = AsyncMock()
        return IntentParser(llm=llm)

    @pytest.fixture
    def member(self):
        return Member(name="Test", github="test", lark_id="ou_test", role="backend")

    async def test_toggle_disable_pr_review(self, parser, member):
        result = await parser.parse("关闭 PR 审查", member)
        assert result.intent == Intent.TOGGLE_MODULE
        assert result.topic == "disable:pr_review"
        assert result.confidence == 1.0
        parser.llm.chat.assert_not_called()

    async def test_toggle_enable_daily_report(self, parser, member):
        result = await parser.parse("开启每日巡检", member)
        assert result.intent == Intent.TOGGLE_MODULE
        assert result.topic == "enable:daily_report"
        parser.llm.chat.assert_not_called()

    async def test_toggle_with_alias(self, parser, member):
        result = await parser.parse("禁用巡检", member)
        assert result.intent == Intent.TOGGLE_MODULE
        assert result.topic == "disable:daily_report"
        parser.llm.chat.assert_not_called()

    async def test_toggle_unknown_module_falls_to_llm(self, parser, member):
        parser.llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.7}'
        result = await parser.parse("关闭不存在的模块", member)
        assert result.intent == Intent.GENERAL_CHAT
        parser.llm.chat.assert_called_once()

    async def test_query_module_status(self, parser, member):
        result = await parser.parse("模块状态", member)
        assert result.intent == Intent.QUERY_MODULE_STATUS
        parser.llm.chat.assert_not_called()

    async def test_query_module_status_variant(self, parser, member):
        result = await parser.parse("哪些功能开着？", member)
        assert result.intent == Intent.QUERY_MODULE_STATUS
        parser.llm.chat.assert_not_called()

    async def test_scan_project(self, parser, member):
        result = await parser.parse("扫描项目", member)
        assert result.intent == Intent.SCAN_PROJECT
        parser.llm.chat.assert_not_called()

    async def test_scan_project_variant(self, parser, member):
        result = await parser.parse("帮我更新项目文档", member)
        assert result.intent == Intent.SCAN_PROJECT
        parser.llm.chat.assert_not_called()

    async def test_project_overview(self, parser, member):
        result = await parser.parse("项目总览", member)
        assert result.intent == Intent.QUERY_PROJECT_OVERVIEW
        parser.llm.chat.assert_not_called()

    async def test_ambiguous_falls_to_llm(self, parser, member):
        parser.llm.chat.return_value = '{"intent": "query_progress", "topic": "", "confidence": 0.9}'
        result = await parser.parse("张三手上几个任务？", member)
        assert result.intent == Intent.QUERY_PROGRESS
        parser.llm.chat.assert_called_once()

    async def test_general_chat_falls_to_llm(self, parser, member):
        parser.llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.8}'
        result = await parser.parse("今天天气不错", member)
        assert result.intent == Intent.GENERAL_CHAT
        parser.llm.chat.assert_called_once()

    # -- Negation: "不想扫描项目" should NOT match SCAN_PROJECT --

    async def test_negation_skips_rules(self, parser, member):
        parser.llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.8}'
        result = await parser.parse("我不想扫描项目", member)
        assert result.intent == Intent.GENERAL_CHAT
        parser.llm.chat.assert_called_once()

    async def test_negation_bu_yao(self, parser, member):
        parser.llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.7}'
        result = await parser.parse("不要关闭 PR 审查", member)
        assert result.intent == Intent.GENERAL_CHAT
        parser.llm.chat.assert_called_once()

    async def test_negation_bie(self, parser, member):
        parser.llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.7}'
        result = await parser.parse("别扫描项目了", member)
        assert result.intent == Intent.GENERAL_CHAT
        parser.llm.chat.assert_called_once()

    # -- Inverted word order: "把 PR 审查关闭" --

    async def test_toggle_inverted_order(self, parser, member):
        result = await parser.parse("把 PR 审查关闭", member)
        assert result.intent == Intent.TOGGLE_MODULE
        assert result.topic == "disable:pr_review"
        parser.llm.chat.assert_not_called()

    async def test_toggle_inverted_with_prefix(self, parser, member):
        result = await parser.parse("帮我把每日巡检开启", member)
        assert result.intent == Intent.TOGGLE_MODULE
        assert result.topic == "enable:daily_report"
        parser.llm.chat.assert_not_called()

    # -- LLM returns rule-only intent → clamped to UNKNOWN --

    async def test_llm_returns_rule_intent_clamped(self, parser, member):
        parser.llm.chat.return_value = '{"intent": "toggle_module", "topic": "disable:pr_review", "confidence": 0.8}'
        result = await parser.parse("间接提到了模块开关", member)
        assert result.intent == Intent.UNKNOWN
