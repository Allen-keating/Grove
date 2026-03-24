# tests/test_modules/test_task_breakdown/test_handler.py
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.handler import TaskBreakdownModule
from grove.modules.task_breakdown.decomposer import DecomposedTask


class TestTaskBreakdownModule:
    @pytest.fixture
    def module(self, grove_dir: Path, sample_team_yml: Path):
        bus = EventBus()
        llm = MagicMock()
        lark = MagicMock()
        lark.send_text = AsyncMock()
        lark.send_card = AsyncMock()
        lark.read_doc = AsyncMock(return_value="# PRD Content")
        github = AsyncMock()
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        member_module = MemberModule(resolver=resolver, storage=storage)
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"

        module = TaskBreakdownModule(
            bus=bus, llm=llm, lark=lark, github=github,
            config=config, member_module=member_module, resolver=resolver,
        )
        bus.register(module)
        bus.register(member_module)
        return module, bus

    async def test_prd_finalized_triggers_decomposition(self, module):
        mod, bus = module
        mod._decomposer.decompose = AsyncMock(return_value=[
            DecomposedTask(title="Task A", body="desc", labels=["frontend", "P0"],
                          estimated_days=2, required_skills=["react"]),
        ])
        from grove.integrations.github.models import IssueData
        mod.github.create_issue = AsyncMock(return_value=IssueData(
            number=42, title="Task A", body="desc", labels=["frontend", "P0"]))

        event = Event(type=EventType.INTERNAL_PRD_FINALIZED, source="internal",
                     payload={"topic": "暗黑模式", "prd_doc_id": "doc123"})
        await bus.dispatch(event)
        mod.github.create_issue.assert_called_once()
        mod.lark.send_card.assert_called()

    async def test_card_action_accept_assigns_issue(self, module):
        mod, bus = module
        mod.github.update_issue = AsyncMock()
        mod._pending_assignments[42] = {
            "assignee_github": "zhangsan", "task_title": "Task A",
        }
        event = Event(type=EventType.LARK_CARD_ACTION, source="lark",
                     payload={"action": {"value": {"action": "accept", "issue_number": 42}}},
                     member=Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend"))
        await bus.dispatch(event)
        mod.github.update_issue.assert_called_once_with("org/repo", 42, assignee="zhangsan")
