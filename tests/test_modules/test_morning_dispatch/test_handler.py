import pytest
from unittest.mock import AsyncMock, MagicMock
from grove.core.events import Event, EventType, Member
from grove.modules.morning_dispatch.handler import MorningDispatchModule


@pytest.fixture
def dispatch_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    llm.chat.return_value = '{"tasks": [{"issue_number": 1, "title": "Task 1", "reason": "P0"}], "summary": "Do task 1"}'
    lark = AsyncMock()
    github = MagicMock()
    from grove.integrations.github.models import IssueData
    github.list_issues.return_value = [
        IssueData(number=1, title="Task 1", body="", state="open", labels=["P0"], assignees=[]),
    ]
    github.list_milestones.return_value = []
    config = MagicMock()
    config.project.repo = "org/repo"
    config.lark.chat_id = "oc_test"
    config.dispatch.confirm_deadline_minutes = 75
    config.dispatch.max_negotiate_rounds = 10
    storage = MagicMock()
    storage.exists.return_value = False
    storage.read_json.side_effect = FileNotFoundError
    resolver = MagicMock()
    member = Member(name="Alice", github="alice", lark_id="ou_alice", role="backend", skills=["python"])
    resolver.all.return_value = [member]
    member_module = MagicMock()
    member_module.get_load.return_value = 0
    return MorningDispatchModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config,
        storage=storage, resolver=resolver, member_module=member_module,
    )


class TestMorningDispatch:
    @pytest.mark.asyncio
    async def test_no_issues_skips_dispatch(self, dispatch_module):
        dispatch_module.github.list_issues.return_value = []
        event = MagicMock()
        event.payload = {}
        await dispatch_module.on_morning_dispatch(event)
        dispatch_module.lark.send_text.assert_called_once()
        assert "无待办" in dispatch_module.lark.send_text.call_args[0][1]

    @pytest.mark.asyncio
    async def test_sends_private_message_to_members(self, dispatch_module):
        event = MagicMock()
        event.payload = {}
        await dispatch_module.on_morning_dispatch(event)
        dispatch_module.lark.send_private.assert_called()
        msg = dispatch_module.lark.send_private.call_args[0][1]
        assert "早上好" in msg

    @pytest.mark.asyncio
    async def test_writes_session(self, dispatch_module):
        event = MagicMock()
        event.payload = {}
        await dispatch_module.on_morning_dispatch(event)
        dispatch_module._storage.write_json.assert_called()
        path = dispatch_module._storage.write_json.call_args[0][0]
        assert "dispatch" in path
        assert "alice" in path

    @pytest.mark.asyncio
    async def test_negotiate_confirm(self, dispatch_module):
        """Member confirms tasks via negotiate event."""
        # Set up storage to return a session
        session_data = {
            "status": "negotiating",
            "tasks": [{"issue_number": 1, "title": "Task 1"}],
            "messages": [],
            "confirmed_at": None,
        }
        dispatch_module._storage.read_json.side_effect = None
        dispatch_module._storage.read_json.return_value = session_data

        member = Member(name="Alice", github="alice", lark_id="ou_alice", role="backend")
        event = MagicMock()
        event.member = member
        event.payload = {"text": "确认", "chat_id": "p2p_chat"}
        await dispatch_module.on_dispatch_negotiate(event)
        # Should send confirmation
        calls = dispatch_module.lark.send_private.call_args_list
        assert any("确认" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_negotiate_no_session(self, dispatch_module):
        """Negotiate with no active session sends rejection."""
        dispatch_module._storage.read_json.side_effect = FileNotFoundError
        member = Member(name="Alice", github="alice", lark_id="ou_alice", role="backend")
        event = MagicMock()
        event.member = member
        event.payload = {"text": "去掉 #1", "chat_id": "p2p"}
        await dispatch_module.on_dispatch_negotiate(event)
        calls = dispatch_module.lark.send_private.call_args_list
        assert any("公示" in str(c) for c in calls)
