# tests/test_modules/test_daily_report/test_handler.py
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.modules.daily_report.handler import DailyReportModule

class TestDailyReportModule:
    @pytest.fixture
    def module(self, grove_dir: Path, sample_team_yml: Path):
        bus = EventBus()
        llm = MagicMock()
        llm.chat = AsyncMock(return_value="1. 建议 A\n2. 建议 B")
        lark = MagicMock()
        lark.send_card = AsyncMock()
        lark.send_text = AsyncMock()
        github = MagicMock()
        github.list_recent_commits = MagicMock(return_value=[
            {"sha": "abc", "message": "fix", "author": "zhangsan", "date": "2026-03-21T10:00:00"},
        ])
        github.list_open_prs = MagicMock(return_value=[])
        github.list_issues = MagicMock(return_value=[])
        github.list_milestones = MagicMock(return_value=[])
        github.create_issue = MagicMock(return_value=MagicMock(number=100))
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"
        module = DailyReportModule(bus=bus, llm=llm, lark=lark, github=github,
                                    config=config, resolver=resolver, storage=storage)
        bus.register(module)
        return module, bus, grove_dir

    async def test_cron_triggers_report(self, module):
        mod, bus, grove_dir = module
        event = Event(type=EventType.CRON_DAILY_REPORT, source="scheduler", payload={})
        await bus.dispatch(event)
        mod.lark.send_card.assert_called_once()
        mod.github.create_issue.assert_called_once()
        call_kwargs = mod.github.create_issue.call_args
        assert "daily-report" in (call_kwargs.kwargs.get("labels") or call_kwargs[1].get("labels", []))

    async def test_saves_snapshot(self, module):
        mod, bus, grove_dir = module
        event = Event(type=EventType.CRON_DAILY_REPORT, source="scheduler", payload={})
        await bus.dispatch(event)
        snapshots = list((grove_dir / "memory" / "snapshots").glob("*.json"))
        assert len(snapshots) == 1
