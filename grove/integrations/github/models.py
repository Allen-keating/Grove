# grove/integrations/github/models.py
"""GitHub data models."""
from dataclasses import dataclass, field


@dataclass
class IssueData:
    number: int
    title: str
    body: str = ""
    state: str = "open"
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    milestone: str | None = None


@dataclass
class PRData:
    number: int
    title: str
    body: str = ""
    state: str = "open"
    diff: str = ""
    files_changed: list[str] = field(default_factory=list)
    author: str = ""


@dataclass
class CommitData:
    sha: str
    message: str
    author: str
    timestamp: str
    files_changed: list[str] = field(default_factory=list)
