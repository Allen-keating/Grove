# Phase 1: 基础骨架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the event-driven foundation — core infrastructure, dual-platform ingress, integration clients — so that a GitHub event can flow through the system and produce a Lark notification (and vice versa).

**Architecture:** Single FastAPI process with event bus. GitHub Webhooks and Lark WebSocket feed standardized events into a bus. Modules subscribe via decorators. Three integration clients (GitHub, Lark, LLM) are injected into modules.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, APScheduler, PyGithub, httpx, lark-oapi, anthropic, Docker

**Spec:** `docs/superpowers/specs/2026-03-21-grove-architecture-design.md`

**Scope:** This plan covers Phase 1 only (weeks 1-2). Phases 2-6 will have separate plans.

**Verification criteria (from spec):**
- GitHub 创建 Issue → 飞书群收到通知
- 飞书群 @Grove → GitHub 创建 Issue
- 能识别消息来自哪个团队成员

---

## File Structure

```
grove/
├── main.py                        # App entry: FastAPI + WS + Scheduler startup
├── config.py                      # Load & validate .grove/config.yml
├── core/
│   ├── __init__.py
│   ├── events.py                  # Event dataclass + EventType enum
│   ├── event_bus.py               # EventBus class, @subscribe decorator, dispatch
│   ├── member_resolver.py         # Load team.yml, resolve GitHub/Lark ID → Member
│   └── storage.py                 # Read/write YAML/JSON in .grove/
├── ingress/
│   ├── __init__.py
│   ├── github_webhook.py          # POST /webhook/github + signature verification
│   ├── lark_websocket.py          # Lark WS long-connection client
│   ├── health.py                  # GET /health
│   └── scheduler.py               # APScheduler cron registration
├── integrations/
│   ├── __init__.py
│   ├── github/
│   │   ├── __init__.py
│   │   ├── client.py              # GitHubClient — Issues/PR/Commits API
│   │   └── models.py              # GitHub data models
│   ├── lark/
│   │   ├── __init__.py
│   │   ├── client.py              # LarkClient — messaging/docs API
│   │   ├── cards.py               # Card template builders
│   │   └── models.py              # Lark data models
│   └── llm/
│       ├── __init__.py
│       ├── client.py              # LLMClient — Claude API with semaphore
│       └── prompts.py             # Shared prompt utilities
├── modules/                       # Empty dirs — populated in Phase 2+
│   └── __init__.py
├── templates/
│   └── lark_cards/
│       └── .gitkeep
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .grove/
│   ├── config.example.yml
│   └── team.example.yml
└── tests/
    ├── __init__.py
    ├── conftest.py                # Shared fixtures
    ├── test_core/
    │   ├── __init__.py
    │   ├── test_events.py
    │   ├── test_event_bus.py
    │   ├── test_member_resolver.py
    │   └── test_storage.py
    ├── test_ingress/
    │   ├── __init__.py
    │   ├── test_github_webhook.py
    │   ├── test_health.py
    │   └── test_scheduler.py
    └── test_integrations/
        ├── __init__.py
        ├── test_github_client.py
        ├── test_lark_client.py
        └── test_llm_client.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `grove/__init__.py`
- Create: `grove/core/__init__.py`, `grove/ingress/__init__.py`, `grove/integrations/__init__.py`, `grove/integrations/github/__init__.py`, `grove/integrations/lark/__init__.py`, `grove/integrations/llm/__init__.py`, `grove/modules/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_core/__init__.py`, `tests/test_ingress/__init__.py`, `tests/test_integrations/__init__.py`
- Create: `Dockerfile`, `docker-compose.yml`
- Create: `.grove/config.example.yml`, `.grove/team.example.yml`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "grove"
version = "0.1.0"
description = "AI Product Manager — your team's sixth member"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "apscheduler>=3.10.0",
    "PyGithub>=2.3.0",
    "httpx>=0.27.0",
    "lark-oapi>=1.3.0",
    "anthropic>=0.40.0",
    "pyyaml>=6.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0",
    "httpx",  # for FastAPI TestClient
    "ruff>=0.6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

- [ ] **Step 2: Create all __init__.py files and directory structure**

Create empty `__init__.py` in: `grove/`, `grove/core/`, `grove/ingress/`, `grove/integrations/`, `grove/integrations/github/`, `grove/integrations/lark/`, `grove/integrations/llm/`, `grove/modules/`, `tests/`, `tests/test_core/`, `tests/test_ingress/`, `tests/test_integrations/`.

Create `grove/templates/lark_cards/.gitkeep` (empty).

- [ ] **Step 3: Create conftest.py with shared fixtures**

```python
# tests/conftest.py
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def grove_dir(tmp_path: Path) -> Path:
    """Create a temporary .grove/ directory with example config files."""
    grove = tmp_path / ".grove"
    grove.mkdir()
    (grove / "logs").mkdir()
    (grove / "memory").mkdir()
    (grove / "memory" / "profiles").mkdir()
    (grove / "memory" / "snapshots").mkdir()
    (grove / "memory" / "decisions").mkdir()
    (grove / "memory" / "conversations").mkdir()
    (grove / "docs-sync").mkdir()
    return grove


@pytest.fixture
def sample_team_yml(grove_dir: Path) -> Path:
    """Write a sample team.yml for testing."""
    team_file = grove_dir / "team.yml"
    team_file.write_text(
        """\
version: 1

team:
  - github: zhangsan
    lark_id: "ou_xxxxxxxx1"
    name: 张三
    role: frontend
    skills: [react, typescript, css]
    authority: member
  - github: lisi
    lark_id: "ou_xxxxxxxx2"
    name: 李四
    role: backend
    skills: [python, fastapi, postgresql]
    authority: lead
  - github: wangwu
    lark_id: "ou_xxxxxxxx3"
    name: 王五
    role: fullstack
    skills: [react, node, docker]
    authority: member
""",
        encoding="utf-8",
    )
    return team_file


@pytest.fixture
def sample_config_yml(grove_dir: Path) -> Path:
    """Write a sample config.yml for testing."""
    config_file = grove_dir / "config.yml"
    config_file.write_text(
        """\
version: 1

project:
  name: "Test Project"
  repo: "testorg/testrepo"
  language: "zh-CN"

lark:
  app_id: "test_app_id"
  app_secret: "test_app_secret"
  chat_id: "oc_test"
  space_id: "spc_test"

github:
  app_id: "12345"
  private_key_path: "/tmp/test-key.pem"
  installation_id: "67890"
  webhook_secret: "test_webhook_secret"

llm:
  api_key: "test_api_key"
  model: "claude-sonnet-4-6"

persona:
  name: "Grove"
  tone: "专业但不刻板"
  reminder_intensity: 3
  proactive_messaging: true

work_hours:
  start: "09:00"
  end: "18:00"
  timezone: "Asia/Shanghai"
  workdays: [1, 2, 3, 4, 5]

schedules:
  daily_report: "09:00"
  doc_drift_check: "09:00"

doc_sync:
  auto_update_level: "moderate"
  github_docs_path: "docs/prd/"
""",
        encoding="utf-8",
    )
    return config_file
```

- [ ] **Step 4: Create .grove/ example configs**

`.grove/config.example.yml` — copy the config.yml from spec Section 6.2 with env var placeholders.

`.grove/team.example.yml` — copy the team.yml from spec Section 6.3.

- [ ] **Step 5: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY grove/ grove/

ENV GROVE_DIR=/data/.grove
VOLUME /data/.grove

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "grove.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6: Create docker-compose.yml**

```yaml
services:
  grove:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./.grove:/data/.grove
    env_file:
      - .env
    restart: unless-stopped
```

- [ ] **Step 7: Install dependencies and verify**

Run: `cd /Users/allen/AllenProject/Grove && pip install -e ".[dev]"`
Expected: All dependencies install successfully.

- [ ] **Step 8: Run empty test suite**

Run: `pytest --co -q`
Expected: "no tests ran" (confirms pytest discovers test directories).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with dependencies and Docker config"
```

---

### Task 2: Event Types and Data Models

**Files:**
- Create: `grove/core/events.py`
- Test: `tests/test_core/test_events.py`

- [ ] **Step 1: Write failing tests for Event and EventType**

```python
# tests/test_core/test_events.py
from datetime import datetime, timezone

from grove.core.events import Event, EventType, Member


class TestEventType:
    def test_github_event_types_exist(self):
        assert EventType.PR_OPENED == "pr.opened"
        assert EventType.PR_MERGED == "pr.merged"
        assert EventType.ISSUE_OPENED == "issue.opened"
        assert EventType.ISSUE_UPDATED == "issue.updated"
        assert EventType.ISSUE_COMMENTED == "issue.commented"
        assert EventType.ISSUE_LABELED == "issue.labeled"

    def test_lark_event_types_exist(self):
        assert EventType.LARK_MESSAGE == "lark.message"
        assert EventType.LARK_CARD_ACTION == "lark.card_action"
        assert EventType.LARK_DOC_UPDATED == "lark.doc_updated"

    def test_cron_event_types_exist(self):
        assert EventType.CRON_DAILY_REPORT == "cron.daily_report"
        assert EventType.CRON_DOC_DRIFT_CHECK == "cron.doc_drift_check"

    def test_internal_event_types_exist(self):
        assert EventType.INTERNAL_NEW_REQUIREMENT == "internal.new_requirement"
        assert EventType.INTERNAL_PRD_FINALIZED == "internal.prd_finalized"
        assert EventType.INTERNAL_TASK_ASSIGNED == "internal.task_assigned"
        assert EventType.INTERNAL_RISK_DETECTED == "internal.risk_detected"


class TestMember:
    def test_create_member(self):
        m = Member(name="张三", github="zhangsan", lark_id="ou_xxx1", role="frontend")
        assert m.name == "张三"
        assert m.github == "zhangsan"
        assert m.lark_id == "ou_xxx1"
        assert m.role == "frontend"

    def test_member_optional_fields(self):
        m = Member(name="张三", github="zhangsan", lark_id="ou_xxx1", role="frontend")
        assert m.skills == []
        assert m.authority == "member"


class TestEvent:
    def test_create_event(self):
        event = Event(
            type=EventType.PR_OPENED,
            source="github",
            payload={"pr_number": 42},
        )
        assert event.type == "pr.opened"
        assert event.source == "github"
        assert event.payload == {"pr_number": 42}
        assert event.member is None
        assert event.id.startswith("evt_")

    def test_event_auto_generates_id_and_timestamp(self):
        e1 = Event(type=EventType.PR_OPENED, source="github", payload={})
        e2 = Event(type=EventType.PR_OPENED, source="github", payload={})
        assert e1.id != e2.id
        assert isinstance(e1.timestamp, datetime)

    def test_event_with_member(self):
        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx1", role="frontend")
        event = Event(
            type=EventType.LARK_MESSAGE,
            source="lark",
            payload={"text": "hello"},
            member=member,
        )
        assert event.member.name == "张三"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'grove.core.events'`

- [ ] **Step 3: Implement events.py**

```python
# grove/core/events.py
"""Event types and data models for the Grove event bus."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from dataclasses import dataclass, field
from typing import Any


class EventType(StrEnum):
    """All event types in the Grove system."""

    # GitHub events
    PR_OPENED = "pr.opened"
    PR_MERGED = "pr.merged"
    PR_REVIEW_REQUESTED = "pr.review_requested"
    ISSUE_OPENED = "issue.opened"
    ISSUE_UPDATED = "issue.updated"
    ISSUE_COMMENTED = "issue.commented"
    ISSUE_LABELED = "issue.labeled"

    # Lark events
    LARK_MESSAGE = "lark.message"
    LARK_CARD_ACTION = "lark.card_action"
    LARK_DOC_UPDATED = "lark.doc_updated"

    # Cron events
    CRON_DAILY_REPORT = "cron.daily_report"
    CRON_DOC_DRIFT_CHECK = "cron.doc_drift_check"

    # Internal events (module-to-module)
    INTERNAL_NEW_REQUIREMENT = "internal.new_requirement"
    INTERNAL_PRD_FINALIZED = "internal.prd_finalized"
    INTERNAL_TASK_ASSIGNED = "internal.task_assigned"
    INTERNAL_RISK_DETECTED = "internal.risk_detected"


@dataclass
class Member:
    """A team member resolved from team.yml."""

    name: str
    github: str
    lark_id: str
    role: str
    skills: list[str] = field(default_factory=list)
    authority: str = "member"


def _generate_event_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"evt_{ts}_{short_uuid}"


@dataclass
class Event:
    """A standardized event flowing through the Grove event bus."""

    type: str  # EventType value
    source: str  # "github" | "lark" | "scheduler" | "internal"
    payload: dict[str, Any]
    member: Member | None = None
    id: str = field(default_factory=_generate_event_id)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core/test_events.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/core/events.py tests/test_core/test_events.py
git commit -m "feat: event types and data models (Event, EventType, Member)"
```

---

### Task 3: File Storage Utilities

**Files:**
- Create: `grove/core/storage.py`
- Test: `tests/test_core/test_storage.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_core/test_storage.py
import json
from pathlib import Path

import pytest

from grove.core.storage import Storage


class TestStorage:
    def test_read_yaml(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        data = storage.read_yaml("team.yml")
        assert data["version"] == 1
        assert len(data["team"]) == 3
        assert data["team"][0]["github"] == "zhangsan"

    def test_read_yaml_missing_file(self, grove_dir: Path):
        storage = Storage(grove_dir)
        with pytest.raises(FileNotFoundError):
            storage.read_yaml("nonexistent.yml")

    def test_write_yaml(self, grove_dir: Path):
        storage = Storage(grove_dir)
        data = {"key": "value", "list": [1, 2, 3]}
        storage.write_yaml("test.yml", data)
        result = storage.read_yaml("test.yml")
        assert result == data

    def test_read_json(self, grove_dir: Path):
        storage = Storage(grove_dir)
        data = {"count": 42, "items": ["a", "b"]}
        (grove_dir / "test.json").write_text(json.dumps(data), encoding="utf-8")
        result = storage.read_json("test.json")
        assert result == data

    def test_write_json(self, grove_dir: Path):
        storage = Storage(grove_dir)
        data = {"count": 42, "items": ["a", "b"]}
        storage.write_json("memory/snapshots/2026-03-21.json", data)
        result = storage.read_json("memory/snapshots/2026-03-21.json")
        assert result == data

    def test_write_json_creates_parent_dirs(self, grove_dir: Path):
        storage = Storage(grove_dir)
        storage.write_json("new/nested/dir/data.json", {"ok": True})
        assert (grove_dir / "new" / "nested" / "dir" / "data.json").exists()

    def test_append_jsonl(self, grove_dir: Path):
        storage = Storage(grove_dir)
        storage.append_jsonl("logs/events.jsonl", {"event": "a"})
        storage.append_jsonl("logs/events.jsonl", {"event": "b"})
        lines = (grove_dir / "logs" / "events.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"event": "a"}
        assert json.loads(lines[1]) == {"event": "b"}

    def test_exists(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        assert storage.exists("team.yml") is True
        assert storage.exists("nonexistent.yml") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement storage.py**

```python
# grove/core/storage.py
"""File storage utilities for reading/writing .grove/ directory."""

import json
from pathlib import Path
from typing import Any

import yaml


class Storage:
    """Read and write YAML/JSON files under a .grove/ directory."""

    def __init__(self, grove_dir: str | Path):
        self.root = Path(grove_dir)

    def _resolve(self, relative_path: str) -> Path:
        return self.root / relative_path

    def read_yaml(self, relative_path: str) -> dict[str, Any]:
        path = self._resolve(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found")
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def write_yaml(self, relative_path: str, data: dict[str, Any]) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def read_json(self, relative_path: str) -> dict[str, Any]:
        path = self._resolve(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, relative_path: str, data: dict[str, Any]) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def append_jsonl(self, relative_path: str, data: dict[str, Any]) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).exists()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core/test_storage.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/core/storage.py tests/test_core/test_storage.py
git commit -m "feat: file storage utilities for .grove/ directory"
```

---

### Task 4: Member Resolver

**Files:**
- Create: `grove/core/member_resolver.py`
- Test: `tests/test_core/test_member_resolver.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_core/test_member_resolver.py
from pathlib import Path

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core/test_member_resolver.py -v`
Expected: FAIL

- [ ] **Step 3: Implement member_resolver.py**

```python
# grove/core/member_resolver.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core/test_member_resolver.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/core/member_resolver.py tests/test_core/test_member_resolver.py
git commit -m "feat: member resolver — lookup team members by GitHub/Lark ID"
```

---

### Task 5: Event Bus

**Files:**
- Create: `grove/core/event_bus.py`
- Test: `tests/test_core/test_event_bus.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_core/test_event_bus.py
import asyncio
import logging

import pytest

from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType


class TestEventBus:
    @pytest.fixture
    def bus(self):
        return EventBus()

    async def test_subscribe_and_dispatch(self, bus: EventBus):
        received = []

        class TestModule:
            @subscribe(EventType.PR_OPENED)
            async def on_pr(self, event: Event):
                received.append(event)

        module = TestModule()
        bus.register(module)

        event = Event(type=EventType.PR_OPENED, source="github", payload={"pr": 1})
        await bus.dispatch(event)

        assert len(received) == 1
        assert received[0].payload == {"pr": 1}

    async def test_dispatch_to_multiple_subscribers(self, bus: EventBus):
        results = {"a": [], "b": []}

        class ModuleA:
            @subscribe(EventType.PR_MERGED)
            async def handle(self, event: Event):
                results["a"].append(event)

        class ModuleB:
            @subscribe(EventType.PR_MERGED)
            async def handle(self, event: Event):
                results["b"].append(event)

        bus.register(ModuleA())
        bus.register(ModuleB())

        event = Event(type=EventType.PR_MERGED, source="github", payload={})
        await bus.dispatch(event)

        assert len(results["a"]) == 1
        assert len(results["b"]) == 1

    async def test_no_cross_dispatch(self, bus: EventBus):
        received = []

        class TestModule:
            @subscribe(EventType.PR_OPENED)
            async def on_pr(self, event: Event):
                received.append(event)

        bus.register(TestModule())

        # Dispatch a different event type
        event = Event(type=EventType.ISSUE_OPENED, source="github", payload={})
        await bus.dispatch(event)

        assert len(received) == 0

    async def test_handler_error_does_not_block_others(self, bus: EventBus, caplog):
        results = []

        class BadModule:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event: Event):
                raise ValueError("boom")

        class GoodModule:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event: Event):
                results.append("ok")

        bus.register(BadModule())
        bus.register(GoodModule())

        event = Event(type=EventType.PR_OPENED, source="github", payload={})
        with caplog.at_level(logging.ERROR):
            await bus.dispatch(event)

        assert len(results) == 1
        assert "boom" in caplog.text

    async def test_multiple_subscriptions_on_same_module(self, bus: EventBus):
        received = []

        class MultiModule:
            @subscribe(EventType.PR_OPENED)
            async def on_pr(self, event: Event):
                received.append("pr")

            @subscribe(EventType.ISSUE_OPENED)
            async def on_issue(self, event: Event):
                received.append("issue")

        bus.register(MultiModule())

        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        await bus.dispatch(Event(type=EventType.ISSUE_OPENED, source="github", payload={}))

        assert received == ["pr", "issue"]

    async def test_emit_internal_event(self, bus: EventBus):
        """Modules can emit internal events via the bus."""
        received = []

        class Producer:
            def __init__(self, bus: EventBus):
                self.bus = bus

            @subscribe(EventType.LARK_MESSAGE)
            async def on_message(self, event: Event):
                await self.bus.dispatch(
                    Event(
                        type=EventType.INTERNAL_NEW_REQUIREMENT,
                        source="internal",
                        payload={"text": event.payload["text"]},
                        member=event.member,
                    )
                )

        class Consumer:
            @subscribe(EventType.INTERNAL_NEW_REQUIREMENT)
            async def on_requirement(self, event: Event):
                received.append(event.payload["text"])

        bus.register(Producer(bus))
        bus.register(Consumer())

        await bus.dispatch(
            Event(type=EventType.LARK_MESSAGE, source="lark", payload={"text": "新需求"})
        )

        assert received == ["新需求"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core/test_event_bus.py -v`
Expected: FAIL

- [ ] **Step 3: Implement event_bus.py**

```python
# grove/core/event_bus.py
"""Event bus with declarative @subscribe decorator and async dispatch."""

import logging
from collections import defaultdict
from typing import Any, Callable

from grove.core.events import Event

logger = logging.getLogger(__name__)

# Marker attribute name for the subscribe decorator
_SUBSCRIBE_ATTR = "_grove_subscriptions"


def subscribe(event_type: str) -> Callable:
    """Decorator to mark a method as an event handler.

    Usage:
        @subscribe(EventType.PR_OPENED)
        async def on_pr_opened(self, event: Event):
            ...
    """

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, _SUBSCRIBE_ATTR):
            setattr(func, _SUBSCRIBE_ATTR, [])
        getattr(func, _SUBSCRIBE_ATTR).append(event_type)
        return func

    return decorator


class EventBus:
    """Central event dispatcher. Modules register themselves; the bus routes events."""

    def __init__(self):
        # event_type -> list of bound async handler methods
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def register(self, module: Any) -> None:
        """Scan a module instance for @subscribe-decorated methods and register them."""
        for attr_name in dir(module):
            method = getattr(module, attr_name, None)
            if method is None or not callable(method):
                continue
            event_types = getattr(method, _SUBSCRIBE_ATTR, None)
            if event_types:
                for event_type in event_types:
                    self._handlers[event_type].append(method)
                    logger.info(
                        "Registered %s.%s for event '%s'",
                        type(module).__name__,
                        attr_name,
                        event_type,
                    )

    async def dispatch(self, event: Event) -> None:
        """Dispatch an event to all registered handlers. Errors are logged, not raised."""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Handler %s.%s failed for event %s",
                    type(handler.__self__).__name__ if hasattr(handler, "__self__") else "?",
                    handler.__name__,
                    event.id,
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core/test_event_bus.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/core/event_bus.py tests/test_core/test_event_bus.py
git commit -m "feat: event bus with @subscribe decorator and error-isolated dispatch"
```

---

### Task 6: Configuration Loading

**Files:**
- Create: `grove/config.py`
- Test: (covered by conftest.py fixture — add a quick config test)

- [ ] **Step 1: Write failing test**

```python
# tests/test_core/test_config.py
from pathlib import Path

import pytest

from grove.config import GroveConfig, load_config


class TestConfig:
    def test_load_config(self, grove_dir: Path, sample_config_yml: Path):
        config = load_config(grove_dir)
        assert config.project.name == "Test Project"
        assert config.project.repo == "testorg/testrepo"
        assert config.lark.app_id == "test_app_id"
        assert config.github.app_id == "12345"
        assert config.llm.model == "claude-sonnet-4-6"
        assert config.persona.name == "Grove"
        assert config.work_hours.timezone == "Asia/Shanghai"
        assert config.schedules.daily_report == "09:00"
        assert config.doc_sync.auto_update_level == "moderate"

    def test_load_config_missing_file(self, grove_dir: Path):
        with pytest.raises(FileNotFoundError):
            load_config(grove_dir)

    def test_config_env_var_resolution(self, grove_dir: Path, monkeypatch):
        """Config values with ${VAR} syntax should resolve from env."""
        monkeypatch.setenv("LARK_APP_ID", "env_resolved_id")
        config_file = grove_dir / "config.yml"
        config_file.write_text(
            """\
version: 1
project:
  name: "Test"
  repo: "org/repo"
  language: "zh-CN"
lark:
  app_id: "${LARK_APP_ID}"
  app_secret: "secret"
  chat_id: "oc_test"
  space_id: "spc_test"
github:
  app_id: "123"
  private_key_path: "/tmp/key.pem"
  installation_id: "456"
  webhook_secret: "ws"
llm:
  api_key: "key"
  model: "claude-sonnet-4-6"
persona:
  name: "Grove"
  tone: "professional"
  reminder_intensity: 3
  proactive_messaging: true
work_hours:
  start: "09:00"
  end: "18:00"
  timezone: "Asia/Shanghai"
  workdays: [1,2,3,4,5]
schedules:
  daily_report: "09:00"
  doc_drift_check: "09:00"
doc_sync:
  auto_update_level: "moderate"
  github_docs_path: "docs/prd/"
""",
            encoding="utf-8",
        )
        config = load_config(grove_dir)
        assert config.lark.app_id == "env_resolved_id"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core/test_config.py -v`
Expected: FAIL

- [ ] **Step 3: Implement config.py**

```python
# grove/config.py
"""Load and validate .grove/config.yml with env var resolution."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class ProjectConfig(BaseModel):
    name: str
    repo: str
    language: str = "zh-CN"


class LarkConfig(BaseModel):
    app_id: str
    app_secret: str
    chat_id: str
    space_id: str


class GitHubConfig(BaseModel):
    app_id: str
    private_key_path: str
    installation_id: str
    webhook_secret: str = ""


class LLMConfig(BaseModel):
    api_key: str
    model: str = "claude-sonnet-4-6"


class PersonaConfig(BaseModel):
    name: str = "Grove"
    tone: str = "专业但不刻板"
    reminder_intensity: int = 3
    proactive_messaging: bool = True


class WorkHoursConfig(BaseModel):
    start: str = "09:00"
    end: str = "18:00"
    timezone: str = "Asia/Shanghai"
    workdays: list[int] = [1, 2, 3, 4, 5]


class SchedulesConfig(BaseModel):
    daily_report: str = "09:00"
    doc_drift_check: str = "09:00"


class DocSyncConfig(BaseModel):
    auto_update_level: str = "moderate"
    github_docs_path: str = "docs/prd/"


class GroveConfig(BaseModel):
    version: int = 1
    project: ProjectConfig
    lark: LarkConfig
    github: GitHubConfig
    llm: LLMConfig
    persona: PersonaConfig = PersonaConfig()
    work_hours: WorkHoursConfig = WorkHoursConfig()
    schedules: SchedulesConfig = SchedulesConfig()
    doc_sync: DocSyncConfig = DocSyncConfig()


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve ${VAR} patterns in config values from environment."""
    if isinstance(obj, str):
        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return _ENV_VAR_PATTERN.sub(replacer, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(grove_dir: str | Path) -> GroveConfig:
    """Load and validate config from .grove/config.yml."""
    config_path = Path(grove_dir) / "config.yml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    resolved = _resolve_env_vars(raw)
    return GroveConfig(**resolved)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/config.py tests/test_core/test_config.py
git commit -m "feat: config loading with env var resolution and pydantic validation"
```

---

### Task 7: GitHub Client (Basic)

**Files:**
- Create: `grove/integrations/github/models.py`
- Create: `grove/integrations/github/client.py`
- Test: `tests/test_integrations/test_github_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_integrations/test_github_client.py
import pytest

from grove.integrations.github.client import GitHubClient
from grove.integrations.github.models import IssueData


class TestGitHubClient:
    """Tests use mocked httpx responses — no real GitHub API calls."""

    def test_client_init(self):
        client = GitHubClient(
            app_id="123",
            private_key_path="/tmp/fake.pem",
            installation_id="456",
        )
        assert client.app_id == "123"

    def test_issue_data_model(self):
        issue = IssueData(
            number=42,
            title="Test issue",
            body="Description",
            state="open",
            labels=["bug"],
            assignees=["zhangsan"],
        )
        assert issue.number == 42
        assert issue.title == "Test issue"
        assert "bug" in issue.labels
```

Note: Full integration tests with mocked HTTP responses will be added as we implement more methods. For Phase 1, we validate the client initializes and models work.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_integrations/test_github_client.py -v`
Expected: FAIL

- [ ] **Step 3: Implement models.py**

```python
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
```

- [ ] **Step 4: Implement client.py (basic skeleton)**

```python
# grove/integrations/github/client.py
"""GitHub API client using PyGithub + httpx."""

import logging

from github import Github, GithubIntegration

from grove.integrations.github.models import IssueData, PRData

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API wrapper. Authenticates as a GitHub App."""

    def __init__(self, app_id: str, private_key_path: str, installation_id: str):
        self.app_id = app_id
        self.private_key_path = private_key_path
        self.installation_id = installation_id
        self._github: Github | None = None

    def _get_github(self) -> Github:
        """Lazy-init authenticated Github instance."""
        if self._github is None:
            with open(self.private_key_path) as f:
                private_key = f.read()
            integration = GithubIntegration(
                integration_id=int(self.app_id),
                private_key=private_key,
            )
            installation = integration.get_access_token(int(self.installation_id))
            self._github = Github(installation.token)
        return self._github

    def create_issue(
        self, repo: str, title: str, body: str = "",
        labels: list[str] | None = None, assignee: str | None = None,
    ) -> IssueData:
        gh = self._get_github()
        r = gh.get_repo(repo)
        issue = r.create_issue(
            title=title, body=body,
            labels=labels or [],
            assignee=assignee,
        )
        logger.info("Created issue #%d in %s", issue.number, repo)
        return IssueData(
            number=issue.number,
            title=issue.title,
            body=issue.body or "",
            state=issue.state,
            labels=[l.name for l in issue.labels],
            assignees=[a.login for a in issue.assignees],
        )

    def add_comment(self, repo: str, issue_number: int, body: str) -> None:
        gh = self._get_github()
        r = gh.get_repo(repo)
        issue = r.get_issue(issue_number)
        issue.create_comment(body)
        logger.info("Added comment to #%d in %s", issue_number, repo)

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Get the diff text for a PR."""
        import httpx

        gh = self._get_github()
        r = gh.get_repo(repo)
        pr = r.get_pull(pr_number)
        # Use httpx to get diff with Accept header
        resp = httpx.get(
            pr.url,
            headers={
                "Authorization": f"token {gh._Github__requester.auth.token}",
                "Accept": "application/vnd.github.v3.diff",
            },
        )
        resp.raise_for_status()
        return resp.text

    def list_issues(self, repo: str, state: str = "open", labels: list[str] | None = None) -> list[IssueData]:
        gh = self._get_github()
        r = gh.get_repo(repo)
        issues = r.get_issues(state=state, labels=labels or [])
        return [
            IssueData(
                number=i.number, title=i.title, body=i.body or "",
                state=i.state, labels=[l.name for l in i.labels],
                assignees=[a.login for a in i.assignees],
            )
            for i in issues
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_integrations/test_github_client.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add grove/integrations/github/ tests/test_integrations/test_github_client.py
git commit -m "feat: GitHub client with basic Issues/PR API"
```

---

### Task 8: Lark Client (Basic)

**Files:**
- Create: `grove/integrations/lark/models.py`
- Create: `grove/integrations/lark/client.py`
- Create: `grove/integrations/lark/cards.py`
- Test: `tests/test_integrations/test_lark_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_integrations/test_lark_client.py
import pytest

from grove.integrations.lark.client import LarkClient
from grove.integrations.lark.models import LarkMessage


class TestLarkClient:
    def test_client_init(self):
        client = LarkClient(app_id="test_id", app_secret="test_secret")
        assert client.app_id == "test_id"

    def test_lark_message_model(self):
        msg = LarkMessage(
            message_id="msg_001",
            chat_id="oc_test",
            sender_id="ou_xxx1",
            text="@Grove 加个暗黑模式",
            is_mention=True,
        )
        assert msg.message_id == "msg_001"
        assert msg.is_mention is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_integrations/test_lark_client.py -v`
Expected: FAIL

- [ ] **Step 3: Implement models.py**

```python
# grove/integrations/lark/models.py
"""Lark/Feishu data models."""

from dataclasses import dataclass


@dataclass
class LarkMessage:
    message_id: str
    chat_id: str
    sender_id: str  # Open ID
    text: str
    is_mention: bool = False
    chat_type: str = "group"  # "group" or "p2p"


@dataclass
class LarkDocInfo:
    doc_id: str
    title: str
    space_id: str
```

- [ ] **Step 4: Implement client.py (basic skeleton)**

```python
# grove/integrations/lark/client.py
"""Lark/Feishu API client using lark-oapi SDK."""

import logging

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

logger = logging.getLogger(__name__)


class LarkClient:
    """Lark API wrapper for messaging, docs, and WebSocket."""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._client: lark.Client | None = None

    def _get_client(self) -> lark.Client:
        if self._client is None:
            self._client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .build()
        return self._client

    async def send_text(self, chat_id: str, text: str) -> None:
        """Send a text message to a chat."""
        import json
        client = self._get_client()
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            ).build()
        response = client.im.v1.message.create(request)
        if not response.success():
            logger.error("Failed to send message: %s", response.msg)
            raise RuntimeError(f"Lark API error: {response.code} {response.msg}")
        logger.info("Sent text to chat %s", chat_id)

    async def send_card(self, chat_id: str, card_content: dict) -> None:
        """Send an interactive card message."""
        import json
        client = self._get_client()
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(json.dumps(card_content))
                .build()
            ).build()
        response = client.im.v1.message.create(request)
        if not response.success():
            logger.error("Failed to send card: %s", response.msg)
            raise RuntimeError(f"Lark API error: {response.code} {response.msg}")
        logger.info("Sent card to chat %s", chat_id)

    async def send_private(self, user_id: str, text: str) -> None:
        """Send a private message to a user by Open ID."""
        import json
        client = self._get_client()
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            ).build()
        response = client.im.v1.message.create(request)
        if not response.success():
            logger.error("Failed to send private msg: %s", response.msg)
            raise RuntimeError(f"Lark API error: {response.code} {response.msg}")
```

- [ ] **Step 5: Implement cards.py (basic skeleton)**

```python
# grove/integrations/lark/cards.py
"""Lark interactive message card builders."""


def build_notification_card(title: str, content: str, color: str = "blue") -> dict:
    """Build a simple notification card."""
    return {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": color,
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": content},
            }
        ],
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_integrations/test_lark_client.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add grove/integrations/lark/ tests/test_integrations/test_lark_client.py
git commit -m "feat: Lark client with messaging API and card builder"
```

---

### Task 9: LLM Client

**Files:**
- Create: `grove/integrations/llm/client.py`
- Create: `grove/integrations/llm/prompts.py`
- Test: `tests/test_integrations/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_integrations/test_llm_client.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grove.integrations.llm.client import LLMClient


class TestLLMClient:
    def test_client_init(self):
        client = LLMClient(api_key="test_key", model="claude-sonnet-4-6")
        assert client.model == "claude-sonnet-4-6"
        assert client._semaphore._value == 3  # default concurrency

    def test_client_custom_concurrency(self):
        client = LLMClient(api_key="test_key", model="claude-sonnet-4-6", max_concurrency=5)
        assert client._semaphore._value == 5

    async def test_chat_calls_anthropic(self):
        client = LLMClient(api_key="test_key", model="claude-sonnet-4-6")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        with patch.object(
            client._anthropic.messages, "create",
            new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.chat(
                system_prompt="You are an AI PM.",
                messages=[{"role": "user", "content": "Hello"}],
            )
            assert result == "Hello from Claude"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_integrations/test_llm_client.py -v`
Expected: FAIL

- [ ] **Step 3: Implement client.py**

```python
# grove/integrations/llm/client.py
"""Claude API client with concurrency control and cost logging."""

import asyncio
import logging
import time

import anthropic

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified Claude API client with semaphore-based concurrency control."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", max_concurrency: int = 3):
        self.model = model
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._anthropic = anthropic.AsyncAnthropic(api_key=api_key)
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat request to Claude with concurrency control."""
        async with self._semaphore:
            start = time.monotonic()
            response = await self._anthropic.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            elapsed = time.monotonic() - start

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens

            logger.info(
                "LLM call: %d in / %d out tokens, %.1fs",
                input_tokens, output_tokens, elapsed,
            )
            return response.content[0].text

    @property
    def total_tokens(self) -> dict[str, int]:
        return {
            "input": self._total_input_tokens,
            "output": self._total_output_tokens,
        }
```

- [ ] **Step 4: Implement prompts.py**

```python
# grove/integrations/llm/prompts.py
"""Shared prompt utilities for Grove AI PM."""

SYSTEM_PROMPT_PREFIX = """\
你是 Grove，一个 AI 产品经理，作为团队中的独立成员存在。

你的核心原则：
- 数据驱动，用事实说话
- 建议为主，不做强制决策
- 保护个人隐私，敏感信息私聊
- 承认错误，及时修正
- 尊重每个人的专业判断

你不应该：
- 在群里公开批评某个人的代码质量
- 对比两个成员的工作效率
- 未经确认删除 Issue 或关闭 PR
- 对技术方案做选择（那是开发者的工作）
"""


def build_system_prompt(persona_name: str = "Grove", extra_context: str = "") -> str:
    """Build the full system prompt with optional extra context."""
    prompt = SYSTEM_PROMPT_PREFIX.replace("Grove", persona_name, 1)
    if extra_context:
        prompt += f"\n\n当前上下文：\n{extra_context}"
    return prompt
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_integrations/test_llm_client.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add grove/integrations/llm/ tests/test_integrations/test_llm_client.py
git commit -m "feat: LLM client with semaphore concurrency control"
```

---

### Task 10: Health Check Endpoint

**Files:**
- Create: `grove/ingress/health.py`
- Test: `tests/test_ingress/test_health.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ingress/test_health.py
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from grove.ingress.health import create_health_router, HealthState


class TestHealth:
    def test_health_endpoint_healthy(self):
        app = FastAPI()
        state = HealthState()
        state.lark_ws_connected = True
        state.scheduler_running = True
        state.last_event_processed = datetime.now(timezone.utc)
        app.include_router(create_health_router(state))

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["fastapi"] is True
        assert data["lark_ws_connected"] is True
        assert data["scheduler_running"] is True

    def test_health_endpoint_degraded(self):
        app = FastAPI()
        state = HealthState()
        state.lark_ws_connected = False
        state.scheduler_running = True
        app.include_router(create_health_router(state))

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["lark_ws_connected"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ingress/test_health.py -v`
Expected: FAIL

- [ ] **Step 3: Implement health.py**

```python
# grove/ingress/health.py
"""Health check endpoint for Docker HEALTHCHECK and monitoring."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter


@dataclass
class HealthState:
    """Mutable health state updated by other components."""

    lark_ws_connected: bool = False
    scheduler_running: bool = False
    last_event_processed: datetime | None = None


def create_health_router(state: HealthState) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        is_healthy = state.lark_ws_connected and state.scheduler_running
        return {
            "status": "healthy" if is_healthy else "degraded",
            "fastapi": True,
            "lark_ws_connected": state.lark_ws_connected,
            "scheduler_running": state.scheduler_running,
            "last_event_processed": (
                state.last_event_processed.isoformat() if state.last_event_processed else None
            ),
        }

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ingress/test_health.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/ingress/health.py tests/test_ingress/test_health.py
git commit -m "feat: health check endpoint with lark/scheduler status"
```

---

### Task 11: GitHub Webhook Ingress

**Files:**
- Create: `grove/ingress/github_webhook.py`
- Test: `tests/test_ingress/test_github_webhook.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ingress/test_github_webhook.py
import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from grove.core.events import EventType
from grove.ingress.github_webhook import create_github_webhook_router


class TestGitHubWebhook:
    def _sign(self, payload: bytes, secret: str) -> str:
        mac = hmac.new(secret.encode(), payload, hashlib.sha256)
        return f"sha256={mac.hexdigest()}"

    def _make_app(self):
        app = FastAPI()
        received_events = []

        async def on_event(event):
            received_events.append(event)

        router = create_github_webhook_router(
            webhook_secret="test_secret",
            on_event=on_event,
        )
        app.include_router(router)
        return app, received_events

    def test_valid_signature_accepted(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = json.dumps({
            "action": "opened",
            "issue": {"number": 1, "title": "Test", "body": "", "state": "open",
                       "labels": [], "assignees": [], "user": {"login": "zhangsan"}},
        }).encode()
        sig = self._sign(payload, "test_secret")
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200

    def test_invalid_signature_rejected(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = b'{"action":"opened"}'
        resp = client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 403

    def test_issue_opened_produces_event(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = json.dumps({
            "action": "opened",
            "issue": {"number": 42, "title": "Bug report", "body": "desc", "state": "open",
                       "labels": [{"name": "bug"}], "assignees": [{"login": "zhangsan"}],
                       "user": {"login": "zhangsan"}},
        }).encode()
        sig = self._sign(payload, "test_secret")
        client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )
        assert len(events) == 1
        assert events[0].type == EventType.ISSUE_OPENED
        assert events[0].source == "github"
        assert events[0].payload["issue"]["number"] == 42

    def test_pr_opened_produces_event(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = json.dumps({
            "action": "opened",
            "pull_request": {"number": 10, "title": "Fix", "body": "", "state": "open",
                              "user": {"login": "lisi"}},
        }).encode()
        sig = self._sign(payload, "test_secret")
        client.post(
            "/webhook/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert len(events) == 1
        assert events[0].type == EventType.PR_OPENED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ingress/test_github_webhook.py -v`
Expected: FAIL

- [ ] **Step 3: Implement github_webhook.py**

```python
# grove/ingress/github_webhook.py
"""GitHub webhook receiver with signature verification."""

import hashlib
import hmac
import logging
from typing import Awaitable, Callable

from fastapi import APIRouter, Request, Response

from grove.core.events import Event, EventType

logger = logging.getLogger(__name__)

# Map GitHub event + action to Grove EventType
_EVENT_MAP: dict[tuple[str, str], str] = {
    ("issues", "opened"): EventType.ISSUE_OPENED,
    ("issues", "edited"): EventType.ISSUE_UPDATED,
    ("issues", "closed"): EventType.ISSUE_UPDATED,
    ("issues", "reopened"): EventType.ISSUE_UPDATED,
    ("issues", "labeled"): EventType.ISSUE_LABELED,
    ("issue_comment", "created"): EventType.ISSUE_COMMENTED,
    ("pull_request", "opened"): EventType.PR_OPENED,
    ("pull_request", "closed"): EventType.PR_MERGED,  # check merged flag in handler
    ("pull_request", "review_requested"): EventType.PR_REVIEW_REQUESTED,
}


def _verify_signature(payload: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_github_username(data: dict) -> str | None:
    """Extract the actor's GitHub username from webhook payload."""
    if "sender" in data:
        return data["sender"].get("login")
    if "issue" in data and "user" in data["issue"]:
        return data["issue"]["user"].get("login")
    if "pull_request" in data and "user" in data["pull_request"]:
        return data["pull_request"]["user"].get("login")
    return None


def create_github_webhook_router(
    webhook_secret: str,
    on_event: Callable[[Event], Awaitable[None]],
) -> APIRouter:
    router = APIRouter()

    @router.post("/webhook/github")
    async def handle_webhook(request: Request):
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")

        if not _verify_signature(body, webhook_secret, signature):
            logger.warning("Invalid webhook signature")
            return Response(status_code=403, content="Invalid signature")

        gh_event = request.headers.get("X-GitHub-Event", "")
        data = await request.json()
        action = data.get("action", "")

        event_type = _EVENT_MAP.get((gh_event, action))
        if event_type is None:
            logger.debug("Ignoring GitHub event: %s/%s", gh_event, action)
            return {"status": "ignored"}

        # For PR closed, check if it was merged
        if gh_event == "pull_request" and action == "closed":
            if data.get("pull_request", {}).get("merged"):
                event_type = EventType.PR_MERGED
            else:
                return {"status": "ignored"}  # closed without merge

        event = Event(
            type=event_type,
            source="github",
            payload=data,
        )
        # Note: member resolution happens in the event bus pre-processing,
        # not here. We store the raw github username in payload for lookup.

        await on_event(event)
        return {"status": "ok"}

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ingress/test_github_webhook.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/ingress/github_webhook.py tests/test_ingress/test_github_webhook.py
git commit -m "feat: GitHub webhook ingress with HMAC signature verification"
```

---

### Task 12: Lark WebSocket Ingress

**Files:**
- Create: `grove/ingress/lark_websocket.py`

This task creates the Lark WebSocket client wrapper. Full testing requires a running Lark connection, so we write the code and add a basic structural test.

- [ ] **Step 1: Implement lark_websocket.py**

```python
# grove/ingress/lark_websocket.py
"""Lark WebSocket long-connection client for receiving messages."""

import json
import logging
from typing import Awaitable, Callable

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from grove.core.events import Event, EventType
from grove.integrations.lark.models import LarkMessage

logger = logging.getLogger(__name__)


def _parse_lark_message(data: P2ImMessageReceiveV1) -> LarkMessage | None:
    """Parse a Lark message event into our model."""
    try:
        msg = data.event.message
        sender = data.event.sender
        content = json.loads(msg.content)
        text = content.get("text", "")
        mentions = msg.mentions or []
        is_mention = any(m.name == "Grove" or m.key == "@_all" for m in mentions)
        # Strip mention tags from text
        for m in mentions:
            text = text.replace(f"@_user_{m.id.open_id}", "").strip()
        return LarkMessage(
            message_id=msg.message_id,
            chat_id=msg.chat_id,
            sender_id=sender.sender_id.open_id,
            text=text,
            is_mention=is_mention,
            chat_type=msg.chat_type,
        )
    except Exception:
        logger.exception("Failed to parse Lark message")
        return None


def create_lark_ws_client(
    app_id: str,
    app_secret: str,
    on_event: Callable[[Event], Awaitable[None]],
) -> lark.ws.Client:
    """Create and return a Lark WebSocket client (not started)."""

    def handle_message(data: P2ImMessageReceiveV1):
        import asyncio

        msg = _parse_lark_message(data)
        if msg is None:
            return

        # Only process messages that mention Grove or are private chats
        if not msg.is_mention and msg.chat_type != "p2p":
            return

        event = Event(
            type=EventType.LARK_MESSAGE,
            source="lark",
            payload={
                "message_id": msg.message_id,
                "chat_id": msg.chat_id,
                "sender_id": msg.sender_id,
                "text": msg.text,
                "chat_type": msg.chat_type,
            },
        )

        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(on_event(event))
        else:
            asyncio.run(on_event(event))

    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(handle_message) \
        .build()

    ws_client = lark.ws.Client(
        app_id=app_id,
        app_secret=app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    return ws_client
```

- [ ] **Step 2: Commit**

```bash
git add grove/ingress/lark_websocket.py
git commit -m "feat: Lark WebSocket ingress client for receiving messages"
```

---

### Task 13: APScheduler Setup

**Files:**
- Create: `grove/ingress/scheduler.py`
- Test: `tests/test_ingress/test_scheduler.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingress/test_scheduler.py
from unittest.mock import AsyncMock

import pytest

from grove.core.events import EventType
from grove.ingress.scheduler import create_scheduler


class TestScheduler:
    def test_create_scheduler_registers_daily_report(self):
        on_event = AsyncMock()
        scheduler = create_scheduler(
            daily_report_time="09:00",
            doc_drift_time="09:00",
            timezone="Asia/Shanghai",
            on_event=on_event,
        )
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "daily_report" in job_ids
        assert "doc_drift_check" in job_ids

    def test_scheduler_not_started(self):
        """Scheduler should be created but not started (caller starts it)."""
        on_event = AsyncMock()
        scheduler = create_scheduler(
            daily_report_time="09:00",
            doc_drift_time="09:00",
            timezone="Asia/Shanghai",
            on_event=on_event,
        )
        assert scheduler.running is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ingress/test_scheduler.py -v`
Expected: FAIL

- [ ] **Step 3: Implement scheduler.py**

```python
# grove/ingress/scheduler.py
"""APScheduler setup for cron-based event emission."""

import asyncio
import logging
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from grove.core.events import Event, EventType

logger = logging.getLogger(__name__)


def create_scheduler(
    daily_report_time: str,
    doc_drift_time: str,
    timezone: str,
    on_event: Callable[[Event], Awaitable[None]],
) -> AsyncIOScheduler:
    """Create an AsyncIOScheduler with cron jobs. Does NOT start it."""

    scheduler = AsyncIOScheduler(timezone=timezone)

    report_hour, report_minute = daily_report_time.split(":")
    drift_hour, drift_minute = doc_drift_time.split(":")

    async def emit_daily_report():
        logger.info("Cron: emitting daily_report event")
        await on_event(Event(
            type=EventType.CRON_DAILY_REPORT,
            source="scheduler",
            payload={},
        ))

    async def emit_doc_drift_check():
        logger.info("Cron: emitting doc_drift_check event")
        await on_event(Event(
            type=EventType.CRON_DOC_DRIFT_CHECK,
            source="scheduler",
            payload={},
        ))

    scheduler.add_job(
        emit_daily_report,
        "cron",
        hour=int(report_hour),
        minute=int(report_minute),
        id="daily_report",
    )
    scheduler.add_job(
        emit_doc_drift_check,
        "cron",
        hour=int(drift_hour),
        minute=int(drift_minute),
        id="doc_drift_check",
    )

    return scheduler
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ingress/test_scheduler.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add grove/ingress/scheduler.py tests/test_ingress/test_scheduler.py
git commit -m "feat: APScheduler cron setup for daily report and doc drift check"
```

---

### Task 14: Application Entry Point (main.py)

**Files:**
- Create: `grove/main.py`

This wires everything together: FastAPI app, event bus, integration clients, ingress components.

- [ ] **Step 1: Implement main.py**

```python
# grove/main.py
"""Grove application entry point — wires FastAPI, EventBus, integrations, ingress."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from grove.config import load_config
from grove.core.event_bus import EventBus
from grove.core.events import Event
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.ingress.github_webhook import create_github_webhook_router
from grove.ingress.health import HealthState, create_health_router
from grove.ingress.lark_websocket import create_lark_ws_client
from grove.ingress.scheduler import create_scheduler
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _get_grove_dir() -> Path:
    """Resolve the .grove/ directory path."""
    return Path(os.environ.get("GROVE_DIR", ".grove"))


# Global state
health_state = HealthState()
event_bus = EventBus()


async def handle_event(event: Event) -> None:
    """Central event handler — resolves member, dispatches to bus."""
    health_state.last_event_processed = event.timestamp
    # Member resolution: fill event.member from payload
    if hasattr(app.state, "member_resolver"):
        resolver: MemberResolver = app.state.member_resolver
        github_user = None
        lark_user = None
        if event.source == "github":
            payload = event.payload
            if "sender" in payload:
                github_user = payload["sender"].get("login")
            elif "issue" in payload:
                github_user = payload["issue"].get("user", {}).get("login")
        elif event.source == "lark":
            lark_user = event.payload.get("sender_id")

        if github_user:
            event.member = resolver.by_github(github_user)
        elif lark_user:
            event.member = resolver.by_lark_id(lark_user)

    await event_bus.dispatch(event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    grove_dir = _get_grove_dir()
    logger.info("Starting Grove with .grove/ at %s", grove_dir)

    # Load config
    config = load_config(grove_dir)
    app.state.config = config

    # Storage
    storage = Storage(grove_dir)
    app.state.storage = storage

    # Member resolver
    resolver = MemberResolver(storage)
    app.state.member_resolver = resolver
    logger.info("Loaded %d team members", len(resolver.members))

    # Integration clients
    app.state.github_client = GitHubClient(
        app_id=config.github.app_id,
        private_key_path=config.github.private_key_path,
        installation_id=config.github.installation_id,
    )
    app.state.lark_client = LarkClient(
        app_id=config.lark.app_id,
        app_secret=config.lark.app_secret,
    )
    app.state.llm_client = LLMClient(
        api_key=config.llm.api_key,
        model=config.llm.model,
    )

    # Scheduler
    scheduler = create_scheduler(
        daily_report_time=config.schedules.daily_report,
        doc_drift_time=config.schedules.doc_drift_check,
        timezone=config.work_hours.timezone,
        on_event=handle_event,
    )
    scheduler.start()
    health_state.scheduler_running = True
    logger.info("Scheduler started")

    # Lark WebSocket (run in background)
    lark_ws = create_lark_ws_client(
        app_id=config.lark.app_id,
        app_secret=config.lark.app_secret,
        on_event=handle_event,
    )

    async def start_lark_ws():
        try:
            lark_ws.start()
            health_state.lark_ws_connected = True
            logger.info("Lark WebSocket connected")
        except Exception:
            logger.exception("Failed to start Lark WebSocket")

    lark_task = asyncio.create_task(start_lark_ws())

    logger.info("Grove is ready — %s", config.persona.name)

    yield

    # Shutdown
    scheduler.shutdown()
    health_state.scheduler_running = False
    lark_task.cancel()
    logger.info("Grove shutdown complete")


app = FastAPI(title="Grove — AI Product Manager", lifespan=lifespan)

# Register routes
app.include_router(create_health_router(health_state))
app.include_router(
    create_github_webhook_router(
        webhook_secret=os.environ.get("GITHUB_WEBHOOK_SECRET", ""),
        on_event=handle_event,
    )
)
```

- [ ] **Step 2: Verify app imports cleanly**

Run: `python -c "from grove.main import app; print('OK')"`
Expected: `OK` (may show warnings about missing env vars, that's fine)

- [ ] **Step 3: Commit**

```bash
git add grove/main.py
git commit -m "feat: main.py — wire up FastAPI, event bus, integrations, and ingress"
```

---

### Task 15: Run Full Test Suite

- [ ] **Step 1: Run all tests**

Run: `pytest -v --tb=short`
Expected: All tests pass. If any fail, fix before proceeding.

- [ ] **Step 2: Run linter**

Run: `ruff check grove/ tests/`
Expected: No errors (or fix any that appear).

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve any test/lint issues from full suite run"
```

---

### Task 16: End-to-End Smoke Test

Verify the Phase 1 acceptance criteria manually:

- [ ] **Step 1: Create .grove/ config for local testing**

Copy `.grove/config.example.yml` to `.grove/config.yml` and fill in real credentials (GitHub App, Lark App, Anthropic API key).

- [ ] **Step 2: Start the server**

Run: `uvicorn grove.main:app --port 8000`
Expected: Server starts, logs show "Grove is ready", scheduler starts, Lark WebSocket attempts to connect.

- [ ] **Step 3: Test health endpoint**

Run: `curl http://localhost:8000/health`
Expected: JSON response with status and component health.

- [ ] **Step 4: Test GitHub webhook locally**

Use a tool like `ngrok` or GitHub's webhook testing to send a test issue event to `POST /webhook/github`. Verify:
- Signature is validated
- Event is parsed and dispatched
- Log shows event processing

- [ ] **Step 5: Verify Lark connectivity**

In the Lark test group, @Grove and verify the WebSocket receives the message (check logs).

- [ ] **Step 6: Final commit and tag**

```bash
git add -A
git commit -m "feat: Phase 1 complete — event-driven foundation with dual-platform ingress"
git tag v0.1.0-phase1
```

---

## Phase 1 Completion Criteria

All of the following must be true:
- [ ] All unit tests pass (`pytest -v`)
- [ ] Linting passes (`ruff check`)
- [ ] Health endpoint returns valid JSON
- [ ] GitHub webhook accepts signed requests and produces events
- [ ] Lark WebSocket connects and receives messages
- [ ] Event bus dispatches events to registered handlers
- [ ] Member resolver correctly maps GitHub ↔ Lark identities
- [ ] Docker build succeeds (`docker build -t grove .`)

**Next:** Create Phase 2 plan (PRD Generator + Communication modules).
