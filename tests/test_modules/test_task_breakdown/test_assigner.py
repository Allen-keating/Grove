# tests/test_modules/test_task_breakdown/test_assigner.py
from pathlib import Path
import pytest
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.assigner import TaskAssigner
from grove.modules.task_breakdown.decomposer import DecomposedTask


class TestTaskAssigner:
    @pytest.fixture
    def assigner(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        member_module = MemberModule(resolver=resolver, storage=storage)
        return TaskAssigner(resolver=resolver, member_module=member_module)

    def test_assign_frontend_task(self, assigner):
        task = DecomposedTask(title="登录页面 UI", required_skills=["react", "css"],
                             labels=["frontend", "P0"])
        suggestion = assigner.suggest(task)
        assert suggestion is not None
        assert suggestion.github == "zhangsan"

    def test_assign_backend_task(self, assigner):
        task = DecomposedTask(title="用户 API", required_skills=["python", "fastapi"],
                             labels=["backend", "P0"])
        suggestion = assigner.suggest(task)
        assert suggestion is not None
        assert suggestion.github == "lisi"

    def test_assign_considers_load(self, assigner):
        for i in range(5):
            assigner._member_module._tasks["zhangsan"].append(
                {"issue_number": i, "issue_title": f"Task {i}", "status": "assigned"})
        task = DecomposedTask(title="React Fix", required_skills=["react"],
                             labels=["frontend", "P1"])
        suggestion = assigner.suggest(task)
        assert suggestion is not None
        # wangwu has react skill and 0 load, should be preferred over busy zhangsan
        assert suggestion.github == "wangwu"

    def test_no_match_returns_none(self, assigner):
        task = DecomposedTask(title="iOS App", required_skills=["swift", "ios"],
                             labels=["mobile", "P0"])
        suggestion = assigner.suggest(task)
        assert suggestion is None
