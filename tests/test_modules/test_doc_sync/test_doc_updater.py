# tests/test_modules/test_doc_sync/test_doc_updater.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.modules.doc_sync.doc_updater import DocUpdater
from grove.modules.doc_sync.diff_classifier import ChangeClassification

class TestDocUpdater:
    @pytest.fixture
    def updater(self):
        llm = MagicMock()
        llm.chat = AsyncMock(return_value="更新后的内容...")
        lark = MagicMock()
        lark.update_doc = AsyncMock()
        lark.send_text = AsyncMock()
        lark.send_card = AsyncMock()
        lark.read_doc = AsyncMock(return_value="# PRD\n\n内容...")
        config = MagicMock()
        config.lark.chat_id = "oc_test"
        config.doc_sync.auto_update_level = "moderate"
        return DocUpdater(llm=llm, lark=lark, config=config)

    async def test_small_change_auto_updates(self, updater):
        c = ChangeClassification(is_product_change=True, severity="small",
                                  description="修改超时", affected_prd_sections=["技术约束"])
        await updater.apply(c, pr_number=45, doc_id="doc123")
        updater.lark.update_doc.assert_called_once()
        updater.lark.send_text.assert_called_once()

    async def test_medium_change_sends_confirmation(self, updater):
        c = ChangeClassification(is_product_change=True, severity="medium",
                                  description="新增微信支付", affected_prd_sections=["支付模块"])
        await updater.apply(c, pr_number=45, doc_id="doc123")
        updater.lark.send_card.assert_called_once()
        updater.lark.update_doc.assert_not_called()

    async def test_large_change_sends_discussion(self, updater):
        c = ChangeClassification(is_product_change=True, severity="large",
                                  description="新增暗黑模式", affected_prd_sections=["功能模块"])
        await updater.apply(c, pr_number=45, doc_id="doc123")
        updater.lark.send_text.assert_called_once()

    async def test_non_product_change_skips(self, updater):
        c = ChangeClassification(is_product_change=False)
        await updater.apply(c, pr_number=45, doc_id="doc123")
        updater.lark.update_doc.assert_not_called()
        updater.lark.send_card.assert_not_called()
