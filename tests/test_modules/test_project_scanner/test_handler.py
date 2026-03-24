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
        scanner_module.github.list_milestones.return_value = []
        scanner_module.github.list_open_prs.return_value = []
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
        scanner_module.github.list_milestones.return_value = []
        scanner_module.github.list_open_prs.return_value = []
        scanner_module.github.read_file.side_effect = Exception("not found")
        scanner_module.github.read_file_head.side_effect = Exception("not found")

        scanner_module._analyzer.analyze_architecture = AsyncMock(return_value="Architecture info")
        scanner_module._analyzer.cluster_features = AsyncMock(return_value=[
            {"feature": "Feature 1", "commits": ["abc1234"], "description": "Test feature"}
        ])
        scanner_module._analyzer.generate_baseline = AsyncMock(return_value="# Baseline Content\n\n## 功能清单\n\n### ✅ 已实现\n\n### 🔄 进行中\n\n### ⬚ 待开发\n")
        scanner_module.lark.create_doc = AsyncMock(return_value="doc_123")
        # Mark as confirmed so it doesn't send cold-start card
        scanner_module._storage.read_yaml.side_effect = lambda p: {"confirmed": True} if "confirmed" in p else (_ for _ in ()).throw(FileNotFoundError)

        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await scanner_module.on_scan_project(event)

        scanner_module._analyzer.analyze_architecture.assert_called_once()
        scanner_module._analyzer.cluster_features.assert_called_once()
        scanner_module._analyzer.generate_baseline.assert_called_once()
