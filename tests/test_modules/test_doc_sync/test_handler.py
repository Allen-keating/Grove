# tests/test_modules/test_doc_sync/test_handler.py
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import json
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.modules.doc_sync.handler import DocSyncModule

class TestDocSyncModule:
    @pytest.fixture
    def module(self, grove_dir: Path):
        bus = EventBus()
        llm = MagicMock()
        llm.chat = AsyncMock(return_value=json.dumps({
            "is_product_change": True, "severity": "small",
            "description": "修改超时配置", "affected_prd_sections": ["技术约束"]}))
        lark = MagicMock()
        lark.send_text = AsyncMock()
        lark.update_doc = AsyncMock()
        lark.read_doc = AsyncMock(return_value="PRD content")
        github = MagicMock()
        github.get_pr_diff = MagicMock(return_value="diff content")
        storage = Storage(grove_dir)
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"
        config.lark.space_id = "spc_test"
        config.doc_sync.auto_update_level = "moderate"
        module = DocSyncModule(bus=bus, llm=llm, lark=lark, github=github,
                                config=config, storage=storage)
        bus.register(module)
        return module, bus

    async def test_pr_merged_triggers_classification(self, module):
        mod, bus = module
        event = Event(type=EventType.PR_MERGED, source="github",
                     payload={"pull_request": {"number": 45, "title": "Fix timeout", "merged": True},
                              "repository": {"full_name": "org/repo"}})
        await bus.dispatch(event)
        mod.github.get_pr_diff.assert_called_once()
        mod.llm.chat.assert_called()
