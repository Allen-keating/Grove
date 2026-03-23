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
