import pytest
from unittest.mock import AsyncMock, MagicMock
from grove.modules.prd_baseline.handler import PRDBaselineModule


@pytest.fixture
def baseline_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    lark = AsyncMock()
    github = MagicMock()
    config = MagicMock()
    config.project.repo = "org/repo"
    config.lark.chat_id = "oc_test"
    config.lark.space_id = "spc_test"
    config.doc_sync.github_docs_path = "docs/prd/"
    storage = MagicMock()
    storage.read_json.side_effect = FileNotFoundError
    storage.read_yaml.side_effect = FileNotFoundError
    return PRDBaselineModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config, storage=storage,
    )


class TestPRDFinalized:
    @pytest.mark.asyncio
    async def test_sends_merge_card(self, baseline_module):
        event = MagicMock()
        event.payload = {"topic": "用户反馈", "github_path": "docs/prd/prd-用户反馈.md"}
        baseline_module.github.read_file.return_value = "# 用户反馈\n\n反馈收集系统"
        await baseline_module.on_prd_finalized(event)
        baseline_module.lark.send_card.assert_called_once()


class TestCardAction:
    @pytest.mark.asyncio
    async def test_confirm_merge_adds_to_tracking(self, baseline_module):
        baseline_module._storage.read_json.side_effect = None
        baseline_module._storage.read_json.return_value = {"features": {}}
        baseline_module.github.read_file.return_value = "# Baseline\n\n## 功能清单\n\n### ⬚ 待开发\n\n## 里程碑\n"
        baseline_module._storage.read_yaml.side_effect = FileNotFoundError
        event = MagicMock()
        event.payload = {"action": {"value": {
            "action": "confirm_baseline_merge", "topic": "反馈系统", "prd_path": "prd-反馈系统.md",
        }}}
        await baseline_module.on_card_action(event)
        baseline_module._storage.write_json.assert_called()
        baseline_module.lark.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_ignores_unknown_actions(self, baseline_module):
        event = MagicMock()
        event.payload = {"action": {"value": {"action": "accept"}}}
        await baseline_module.on_card_action(event)
        baseline_module.lark.send_text.assert_not_called()


class TestReorganize:
    @pytest.mark.asyncio
    async def test_reorganize_calls_llm(self, baseline_module):
        baseline_module.github.read_file.return_value = "# Baseline\n\n## 功能清单\n"
        baseline_module.llm.chat.return_value = "# Baseline\n\n## 功能清单\n\n### ✅ 已实现\n\n### 🔄 进行中\n\n### ⬚ 待开发\n"
        baseline_module._storage.read_yaml.side_effect = FileNotFoundError
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await baseline_module.on_reorganize(event)
        baseline_module.llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_reorganize_no_baseline(self, baseline_module):
        baseline_module.github.read_file.side_effect = Exception("not found")
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await baseline_module.on_reorganize(event)
        assert any("未找到" in str(c) for c in baseline_module.lark.send_text.call_args_list)
