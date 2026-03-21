# tests/test_modules/test_member/test_handler.py
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.modules.member.handler import MemberModule


class TestMemberModule:
    @pytest.fixture
    def module(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        bus = EventBus()
        module = MemberModule(resolver=resolver, storage=storage)
        bus.register(module)
        return module, bus

    def test_get_member_tasks_empty(self, module):
        mod, bus = module
        tasks = mod.get_tasks("zhangsan")
        assert tasks == []

    def test_get_member_load(self, module):
        mod, bus = module
        load = mod.get_load("zhangsan")
        assert load == 0

    async def test_task_assigned_updates_cache(self, module):
        mod, bus = module
        event = Event(
            type=EventType.INTERNAL_TASK_ASSIGNED, source="internal",
            payload={"github_username": "zhangsan", "issue_number": 23, "issue_title": "登录页面 UI"},
        )
        await bus.dispatch(event)
        tasks = mod.get_tasks("zhangsan")
        assert len(tasks) == 1
        assert tasks[0]["issue_number"] == 23
        assert mod.get_load("zhangsan") == 1

    async def test_multiple_tasks_tracked(self, module):
        mod, bus = module
        for i, title in enumerate(["Task A", "Task B", "Task C"]):
            await bus.dispatch(Event(
                type=EventType.INTERNAL_TASK_ASSIGNED, source="internal",
                payload={"github_username": "zhangsan", "issue_number": i + 1, "issue_title": title},
            ))
        assert mod.get_load("zhangsan") == 3

    def test_get_all_loads(self, module):
        mod, bus = module
        loads = mod.get_all_loads()
        assert "zhangsan" in loads
        assert "lisi" in loads
        assert all(v == 0 for v in loads.values())
