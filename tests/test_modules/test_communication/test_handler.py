# tests/test_modules/test_communication/test_handler.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.modules.communication.handler import CommunicationModule
from grove.modules.communication.intent_parser import ParsedIntent, Intent


class TestCommunicationModule:
    @pytest.fixture
    def module(self):
        bus = EventBus()
        llm = MagicMock()
        lark = MagicMock()
        lark.send_text = AsyncMock()
        github = MagicMock()
        config = MagicMock()
        config.lark.chat_id = "oc_test"
        config.project.repo = "org/repo"
        module = CommunicationModule(bus=bus, llm=llm, lark=lark, github=github, config=config)
        bus.register(module)
        return module, bus

    async def test_lark_message_without_member_is_ignored(self, module):
        mod, bus = module
        event = Event(type=EventType.LARK_MESSAGE, source="lark",
                     payload={"text": "hello", "chat_id": "oc_test", "sender_id": "ou_unknown"},
                     member=None)
        await bus.dispatch(event)
        # No crash, no send_text call
        mod.lark.send_text.assert_not_called()

    async def test_new_requirement_emits_internal_event(self, module):
        mod, bus = module
        received = []

        class Listener:
            from grove.core.event_bus import subscribe
            @subscribe(EventType.INTERNAL_NEW_REQUIREMENT)
            async def on_req(self, event):
                received.append(event)

        bus.register(Listener())
        mod._intent_parser.parse = AsyncMock(
            return_value=ParsedIntent(intent=Intent.NEW_REQUIREMENT, topic="暗黑模式", confidence=0.9))

        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend")
        event = Event(type=EventType.LARK_MESSAGE, source="lark",
                     payload={"text": "我想加个暗黑模式", "chat_id": "oc_test", "sender_id": "ou_xxx"},
                     member=member)
        await bus.dispatch(event)
        assert len(received) == 1
        assert received[0].payload["topic"] == "暗黑模式"

    async def test_query_progress_responds(self, module):
        mod, bus = module
        mod._intent_parser.parse = AsyncMock(
            return_value=ParsedIntent(intent=Intent.QUERY_PROGRESS, confidence=0.9))
        mod.llm.chat = AsyncMock(return_value="当前 MVP 进度 60%。")

        member = Member(name="李四", github="lisi", lark_id="ou_xxx", role="backend", authority="lead")
        event = Event(type=EventType.LARK_MESSAGE, source="lark",
                     payload={"text": "目前进度怎么样", "chat_id": "oc_test", "sender_id": "ou_xxx"},
                     member=member)
        await bus.dispatch(event)
        mod.lark.send_text.assert_called_once()


class TestCommunicationToggle:
    @pytest.fixture
    def module_with_registry(self, grove_dir: Path):
        from grove.core.module_registry import ModuleRegistry
        from grove.core.storage import Storage
        bus = EventBus()
        llm = MagicMock()
        lark = MagicMock()
        lark.send_text = AsyncMock()
        github = MagicMock()
        config = MagicMock()
        config.lark.chat_id = "oc_test"
        storage = Storage(grove_dir)
        registry = ModuleRegistry(bus=bus, storage=storage)

        class DummyMod:
            pass
        registry.add("pr_review", DummyMod(), enabled=True)

        module = CommunicationModule(
            bus=bus, llm=llm, lark=lark, github=github,
            config=config, registry=registry,
        )
        bus.register(module)
        return module, bus, registry

    async def test_toggle_disable_by_owner(self, module_with_registry):
        mod, bus, registry = module_with_registry
        mod._intent_parser.parse = AsyncMock(
            return_value=ParsedIntent(intent=Intent.TOGGLE_MODULE, topic="disable:pr_review", confidence=0.95))
        member = Member(name="Allen", github="allen", lark_id="ou_xxx", role="fullstack", authority="owner")
        event = Event(type=EventType.LARK_MESSAGE, source="lark",
                     payload={"text": "关闭 PR 审查", "chat_id": "oc_test"},
                     member=member)
        await bus.dispatch(event)
        mod.lark.send_text.assert_called_once()
        assert "已关闭" in mod.lark.send_text.call_args[0][1]

    async def test_toggle_rejected_for_member(self, module_with_registry):
        mod, bus, registry = module_with_registry
        mod._intent_parser.parse = AsyncMock(
            return_value=ParsedIntent(intent=Intent.TOGGLE_MODULE, topic="disable:pr_review", confidence=0.95))
        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend", authority="member")
        event = Event(type=EventType.LARK_MESSAGE, source="lark",
                     payload={"text": "关闭 PR 审查", "chat_id": "oc_test"},
                     member=member)
        await bus.dispatch(event)
        assert "owner 权限" in mod.lark.send_text.call_args[0][1]
