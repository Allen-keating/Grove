"""Resolve team members from team.yml by GitHub username or Lark ID."""

from grove.core.events import Member
from grove.core.storage import Storage


class MemberResolver:
    """Load team.yml and provide lookup by GitHub username or Lark Open ID."""

    def __init__(self, storage: Storage):
        self._by_github: dict[str, Member] = {}
        self._by_lark: dict[str, Member] = {}
        self._members: list[Member] = []
        self._load(storage)

    def _load(self, storage: Storage) -> None:
        data = storage.read_yaml("team.yml")
        for entry in data.get("team", []):
            member = Member(
                name=entry["name"],
                github=entry["github"],
                lark_id=entry["lark_id"],
                role=entry["role"],
                skills=entry.get("skills", []),
                authority=entry.get("authority", "member"),
            )
            self._by_github[member.github] = member
            self._by_lark[member.lark_id] = member
            self._members.append(member)

    @property
    def members(self) -> list[Member]:
        return list(self._members)

    def by_github(self, username: str) -> Member | None:
        return self._by_github.get(username)

    def by_lark_id(self, lark_id: str) -> Member | None:
        return self._by_lark.get(lark_id)

    def all(self) -> list[Member]:
        return list(self._members)
