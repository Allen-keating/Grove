import pytest
from unittest.mock import AsyncMock, MagicMock
from grove.modules.project_scanner.handler import ProjectScannerModule


@pytest.fixture
def scanner_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    lark = AsyncMock()
    github = MagicMock()
    config = MagicMock()
    config.project.repo = "org/repo"
    config.project.name = "TestProject"
    config.lark.chat_id = "oc_test"
    config.lark.space_id = "spc_test"
    storage = MagicMock()
    storage.exists.return_value = False
    storage.read_yaml.side_effect = FileNotFoundError
    return ProjectScannerModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config, storage=storage,
    )


class TestProjectScanner:
    @pytest.mark.asyncio
    async def test_empty_repo_sends_message(self, scanner_module):
        scanner_module.github.get_repo_tree.return_value = []
        scanner_module.github.list_recent_commits_detailed.return_value = []
        scanner_module.github.list_issues.return_value = []
        scanner_module.github.list_milestones.return_value = []
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await scanner_module.on_scan_project(event)
        calls = scanner_module.lark.send_text.call_args_list
        assert any("数据不足" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_concurrent_scan_rejected(self, scanner_module):
        """Second scan while first is running should be rejected."""
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        # Acquire lock manually to simulate in-progress scan
        await scanner_module._scan_lock.acquire()
        await scanner_module.on_scan_project(event)
        calls = scanner_module.lark.send_text.call_args_list
        assert any("正在进行中" in str(c) for c in calls)
        scanner_module._scan_lock.release()

    @pytest.mark.asyncio
    async def test_scan_calls_analyzer(self, scanner_module):
        """Full scan flow calls analyzer methods in order."""
        from grove.integrations.github.models import IssueData
        scanner_module.github.get_repo_tree.return_value = [
            {"path": "main.py", "type": "blob", "size": 100}
        ]
        scanner_module.github.list_recent_commits_detailed.return_value = [
            {"sha": "abc1234", "message": "feat: init", "author": "alice",
             "date": "2026-03-01", "files": [{"filename": "main.py"}]}
        ]
        scanner_module.github.list_issues.return_value = [
            IssueData(number=1, title="Test Issue", body="", state="open", labels=[], assignees=[])
        ]
        scanner_module.github.list_milestones.return_value = []
        scanner_module.github.read_file.side_effect = Exception("not found")

        scanner_module._analyzer.analyze_architecture = AsyncMock(return_value="Architecture info")
        scanner_module._analyzer.analyze_features = AsyncMock(return_value=[
            {"name": "Feature 1", "status": "completed", "description": "Test feature"}
        ])
        scanner_module._analyzer.generate_reverse_prd = AsyncMock(return_value="# PRD Content")
        scanner_module.lark.create_doc = AsyncMock(return_value="doc_123")

        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await scanner_module.on_scan_project(event)

        scanner_module._analyzer.analyze_architecture.assert_called_once()
        scanner_module._analyzer.analyze_features.assert_called_once()
        scanner_module._analyzer.generate_reverse_prd.assert_called_once()
        # Should have written files to GitHub
        assert scanner_module.github.write_file.call_count == 2
