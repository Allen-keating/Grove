import pytest
from unittest.mock import AsyncMock, MagicMock
from grove.modules.project_overview.handler import ProjectOverviewModule


@pytest.fixture
def overview_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    llm.chat.return_value = '{"health": "🟢 正常", "risks": [], "suggestions": "继续保持"}'
    lark = AsyncMock()
    github = MagicMock()
    github.list_issues.return_value = []
    github.list_recent_commits_detailed.return_value = []
    github.list_open_prs.return_value = []
    github.list_milestones.return_value = []
    config = MagicMock()
    config.project.repo = "org/repo"
    config.lark.chat_id = "oc_test"
    storage = MagicMock()
    storage.read_json.side_effect = FileNotFoundError
    storage.read_yaml.side_effect = FileNotFoundError
    return ProjectOverviewModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config, storage=storage,
    )


class TestProjectOverview:
    @pytest.mark.asyncio
    async def test_generates_report(self, overview_module):
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await overview_module.on_project_overview(event)
        overview_module.lark.send_card.assert_called_once()
        overview_module._collector.github.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_saves_snapshot(self, overview_module):
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await overview_module.on_project_overview(event)
        overview_module._storage.write_json.assert_called_once()
        path = overview_module._storage.write_json.call_args[0][0]
        assert "overview.json" in path

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self, overview_module):
        overview_module.llm.chat.side_effect = Exception("LLM down")
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await overview_module.on_project_overview(event)
        # Should still send card with fallback analysis
        overview_module.lark.send_card.assert_called_once()
