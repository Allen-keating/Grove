# tests/test_modules/test_doc_sync/test_diff_classifier.py
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.modules.doc_sync.diff_classifier import DiffClassifier, ChangeClassification

class TestChangeClassification:
    def test_create(self):
        c = ChangeClassification(is_product_change=True, severity="medium",
                                  description="新增微信支付", affected_prd_sections=["支付模块"])
        assert c.is_product_change is True
        assert c.severity == "medium"

class TestDiffClassifier:
    @pytest.fixture
    def classifier(self):
        return DiffClassifier(llm=MagicMock())

    async def test_classify_product_change(self, classifier):
        classifier.llm.chat = AsyncMock(return_value=json.dumps({
            "is_product_change": True, "severity": "medium",
            "description": "新增微信支付", "affected_prd_sections": ["支付模块"]}))
        result = await classifier.classify("diff content", "PR #45: Add wechat pay")
        assert result.is_product_change is True
        assert result.severity == "medium"

    async def test_classify_tech_refactor(self, classifier):
        classifier.llm.chat = AsyncMock(return_value=json.dumps({
            "is_product_change": False, "severity": "none",
            "description": "纯技术重构", "affected_prd_sections": []}))
        result = await classifier.classify("refactor diff", "PR #46: Refactor")
        assert result.is_product_change is False

    async def test_classify_handles_error(self, classifier):
        classifier.llm.chat = AsyncMock(return_value="not json")
        result = await classifier.classify("diff", "PR")
        assert result.is_product_change is False
