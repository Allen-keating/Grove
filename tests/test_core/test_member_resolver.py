# tests/test_core/test_member_resolver.py
from pathlib import Path
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage


class TestMemberResolver:
    def test_load_team(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        assert len(resolver.members) == 3

    def test_resolve_by_github(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        member = resolver.by_github("zhangsan")
        assert member is not None
        assert member.name == "张三"
        assert member.lark_id == "ou_xxxxxxxx1"
        assert member.role == "frontend"
        assert member.authority == "member"

    def test_resolve_by_github_unknown(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        assert resolver.by_github("unknown_user") is None

    def test_resolve_by_lark_id(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        member = resolver.by_lark_id("ou_xxxxxxxx2")
        assert member is not None
        assert member.name == "李四"
        assert member.github == "lisi"
        assert member.authority == "lead"

    def test_resolve_by_lark_id_unknown(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        assert resolver.by_lark_id("ou_unknown") is None

    def test_skills_loaded(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        member = resolver.by_github("zhangsan")
        assert member.skills == ["react", "typescript", "css"]

    def test_all_members(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        all_members = resolver.all()
        assert len(all_members) == 3
        github_names = [m.github for m in all_members]
        assert "zhangsan" in github_names
        assert "lisi" in github_names
        assert "wangwu" in github_names
