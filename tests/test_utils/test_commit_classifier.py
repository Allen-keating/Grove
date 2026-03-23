import pytest
from unittest.mock import AsyncMock
from grove.utils.commit_classifier import classify_commit, classify_commit_by_rule


class TestCommitClassifierRules:
    def test_feat_prefix(self):
        assert classify_commit_by_rule("feat: add login") == "feature"

    def test_fix_prefix(self):
        assert classify_commit_by_rule("fix: null pointer") == "bugfix"

    def test_docs_prefix(self):
        assert classify_commit_by_rule("docs: update README") == "docs"

    def test_refactor_prefix(self):
        assert classify_commit_by_rule("refactor: extract helper") == "refactor"

    def test_chore_prefix(self):
        assert classify_commit_by_rule("chore: bump deps") == "chore"

    def test_test_prefix(self):
        assert classify_commit_by_rule("test: add unit tests") == "chore"

    def test_ci_prefix(self):
        assert classify_commit_by_rule("ci: fix pipeline") == "chore"

    def test_unknown_returns_none(self):
        assert classify_commit_by_rule("did something weird") is None

    def test_feat_with_scope(self):
        assert classify_commit_by_rule("feat(auth): add OAuth") == "feature"

    def test_fix_with_breaking(self):
        assert classify_commit_by_rule("fix!: breaking change") == "bugfix"


@pytest.mark.asyncio
class TestClassifyCommitAsync:
    async def test_rule_match_no_llm_call(self):
        llm = AsyncMock()
        result = await classify_commit("feat: add feature", [], llm=llm)
        assert result == "feature"
        llm.chat.assert_not_called()

    async def test_fallback_to_llm(self):
        llm = AsyncMock()
        llm.chat.return_value = '{"type": "feature"}'
        result = await classify_commit("implemented the new dashboard", ["dashboard.py"], llm=llm)
        assert result == "feature"
        llm.chat.assert_called_once()

    async def test_llm_failure_returns_chore(self):
        llm = AsyncMock()
        llm.chat.side_effect = Exception("LLM down")
        result = await classify_commit("mystery commit", [], llm=llm)
        assert result == "chore"

    async def test_no_llm_returns_chore(self):
        result = await classify_commit("mystery commit", [])
        assert result == "chore"

    async def test_llm_invalid_type_returns_chore(self):
        llm = AsyncMock()
        llm.chat.return_value = '{"type": "invalid_type"}'
        result = await classify_commit("some commit", ["file.py"], llm=llm)
        assert result == "chore"
