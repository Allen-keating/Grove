# tests/test_modules/test_prd_generator/test_handler.py
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.core.storage import Storage
from grove.modules.prd_generator.handler import PRDGeneratorModule
from grove.modules.prd_generator.conversation import ConversationManager


class TestPRDGeneratorModule:
    @pytest.fixture
    def module(self, grove_dir: Path):
        bus = EventBus()
        llm = MagicMock()
        lark = MagicMock()
        lark.send_text = AsyncMock()
        lark.create_doc = AsyncMock(return_value="doc_test_123")
        github = MagicMock()
        storage = Storage(grove_dir)
        config = MagicMock()
        config.lark.space_id = "spc_test"
        config.project.repo = "org/repo"
        config.doc_sync.github_docs_path = "docs/prd/"
        conv_manager = ConversationManager(storage)
        module = PRDGeneratorModule(
            bus=bus, llm=llm, lark=lark, github=github,
            config=config, conv_manager=conv_manager,
        )
        bus.register(module)
        return module, bus, conv_manager

    async def test_new_requirement_starts_conversation(self, module):
        mod, bus, conv_mgr = module
        mod.llm.chat = AsyncMock(return_value="目标用户是谁？")

        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend")
        event = Event(
            type=EventType.INTERNAL_NEW_REQUIREMENT, source="internal",
            payload={"topic": "暗黑模式", "original_text": "我想加个暗黑模式", "chat_id": "oc_test"},
            member=member,
        )
        await bus.dispatch(event)

        conv = conv_mgr.get_active_for_chat("oc_test")
        assert conv is not None
        assert conv.topic == "暗黑模式"
        mod.lark.send_text.assert_called_once()

    async def test_generates_prd_when_ready(self, module):
        mod, bus, conv_mgr = module

        conv = conv_mgr.create(chat_id="oc_test", initiator_github="zhangsan", topic="暗黑模式")
        conv.add_message("user", "我想加个暗黑模式")
        conv.add_message("assistant", "目标用户是谁？")
        conv.add_message("user", "所有用户")
        conv_mgr.save(conv)

        call_count = 0
        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "READY_TO_GENERATE"
            return "# 暗黑模式 — PRD\n\n## 1. 概述\n\n暗黑模式功能..."

        mod.llm.chat = AsyncMock(side_effect=mock_chat)

        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend")
        event = Event(
            type=EventType.LARK_MESSAGE, source="internal",
            payload={"text": "所有用户", "chat_id": "oc_test", "intent": "continue_conversation"},
            member=member,
        )

        await mod._on_continue_conversation(event)
        mod.lark.create_doc.assert_called_once()
