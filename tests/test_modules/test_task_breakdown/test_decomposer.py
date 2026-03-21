# tests/test_modules/test_task_breakdown/test_decomposer.py
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.modules.task_breakdown.decomposer import TaskDecomposer, DecomposedTask


class TestDecomposedTask:
    def test_create(self):
        task = DecomposedTask(title="实现登录页面 UI", body="描述...",
                             labels=["frontend", "P0"], estimated_days=3,
                             required_skills=["react", "css"])
        assert task.title == "实现登录页面 UI"
        assert "P0" in task.labels
        assert task.estimated_days == 3


class TestTaskDecomposer:
    @pytest.fixture
    def decomposer(self):
        return TaskDecomposer(llm=MagicMock())

    async def test_decompose_prd(self, decomposer):
        mock_response = json.dumps({"tasks": [
            {"title": "实现登录页面 UI", "body": "描述", "labels": ["frontend", "P0"],
             "estimated_days": 3, "required_skills": ["react", "css"]},
            {"title": "实现登录 API", "body": "后端", "labels": ["backend", "P0"],
             "estimated_days": 2, "required_skills": ["python", "fastapi"]},
        ]})
        decomposer.llm.chat = AsyncMock(return_value=mock_response)
        tasks = await decomposer.decompose("暗黑模式", "# PRD内容...")
        assert len(tasks) == 2
        assert tasks[0].title == "实现登录页面 UI"
        assert tasks[1].required_skills == ["python", "fastapi"]

    async def test_decompose_handles_invalid_json(self, decomposer):
        decomposer.llm.chat = AsyncMock(return_value="not json")
        tasks = await decomposer.decompose("topic", "content")
        assert tasks == []
