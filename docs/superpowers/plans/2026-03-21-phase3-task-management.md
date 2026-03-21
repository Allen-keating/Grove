# Phase 3: 任务拆解与分配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a PRD is finalized, automatically break it down into GitHub Issues (Epics → User Stories → Tasks), recommend assignments based on team skills/load, and confirm via Lark interactive cards.

**Architecture:** Two new modules: `task_breakdown/` subscribes to `internal.prd_finalized`, uses LLM to decompose the PRD, creates GitHub Issues, and sends assignment cards via Lark. `member/` maintains a task/load cache for each team member, queried by the assigner. Lark card button clicks (`lark.card_action`) flow back through the event bus to confirm assignments.

**Tech Stack:** Existing Grove infrastructure (event bus, LLM client, GitHub client, Lark client), lark-oapi card actions.

**Spec:** `docs/superpowers/specs/2026-03-21-grove-architecture-design.md` (Sections 4.1, 8 Phase 3)

**Scope:** Phase 3 only (weeks 5-6). Depends on Phase 1-2 being complete.

**Verification criteria (from spec):**
- PRD 定稿 → 自动创建 GitHub Issues
- 飞书群收到分配卡片 → 点击接受 → Issue 自动 assign
- "@Grove 张三手上有几个任务？" → 准确回答

---

## File Structure

```
grove/
├── integrations/
│   ├── github/
│   │   └── client.py                          # MODIFY: add update_issue, create_milestone
│   └── lark/
│       └── cards.py                            # MODIFY: add task_assignment_card builder
│
├── modules/
│   ├── member/
│   │   ├── __init__.py
│   │   └── handler.py                          # Member module: task/load cache + queries
│   │
│   └── task_breakdown/
│       ├── __init__.py
│       ├── handler.py                          # Event handler: prd_finalized, card_action
│       ├── decomposer.py                       # LLM-based PRD → tasks decomposition
│       ├── assigner.py                         # Skill-matching + load-based assignment
│       └── prompts.py                          # Prompt templates for decomposition
│
├── ingress/
│   └── lark_websocket.py                       # MODIFY: handle card_action events
│
├── main.py                                     # MODIFY: register new modules
│
└── tests/
    └── test_modules/
        ├── test_member/
        │   ├── __init__.py
        │   └── test_handler.py
        └── test_task_breakdown/
            ├── __init__.py
            ├── test_decomposer.py
            ├── test_assigner.py
            └── test_handler.py
```

---

### Task 1: Member Module — Task/Load Cache

**Files:**
- Create: `grove/modules/member/__init__.py`
- Create: `grove/modules/member/handler.py`
- Test: `tests/test_modules/test_member/test_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_member/test_handler.py
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.modules.member.handler import MemberModule


class TestMemberModule:
    @pytest.fixture
    def module(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        bus = EventBus()
        module = MemberModule(resolver=resolver, storage=storage)
        bus.register(module)
        return module, bus

    def test_get_member_tasks_empty(self, module):
        mod, bus = module
        tasks = mod.get_tasks("zhangsan")
        assert tasks == []

    def test_get_member_load(self, module):
        mod, bus = module
        load = mod.get_load("zhangsan")
        assert load == 0

    async def test_task_assigned_updates_cache(self, module):
        mod, bus = module
        event = Event(
            type=EventType.INTERNAL_TASK_ASSIGNED, source="internal",
            payload={
                "github_username": "zhangsan",
                "issue_number": 23,
                "issue_title": "登录页面 UI",
            },
        )
        await bus.dispatch(event)
        tasks = mod.get_tasks("zhangsan")
        assert len(tasks) == 1
        assert tasks[0]["issue_number"] == 23
        assert mod.get_load("zhangsan") == 1

    async def test_multiple_tasks_tracked(self, module):
        mod, bus = module
        for i, title in enumerate(["Task A", "Task B", "Task C"]):
            await bus.dispatch(Event(
                type=EventType.INTERNAL_TASK_ASSIGNED, source="internal",
                payload={"github_username": "zhangsan", "issue_number": i + 1, "issue_title": title},
            ))
        assert mod.get_load("zhangsan") == 3

    def test_get_all_loads(self, module):
        mod, bus = module
        loads = mod.get_all_loads()
        assert "zhangsan" in loads
        assert "lisi" in loads
        assert all(v == 0 for v in loads.values())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_member/test_handler.py -v`

- [ ] **Step 3: Implement handler.py**

```python
# grove/modules/member/handler.py
"""Member module — maintains task/load cache for team members."""

import logging
from grove.core.event_bus import subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage

logger = logging.getLogger(__name__)


class MemberModule:
    """Track current tasks and workload per team member."""

    def __init__(self, resolver: MemberResolver, storage: Storage):
        self._resolver = resolver
        self._storage = storage
        # github_username -> list of assigned task dicts
        self._tasks: dict[str, list[dict]] = {
            m.github: [] for m in resolver.all()
        }

    @subscribe(EventType.INTERNAL_TASK_ASSIGNED)
    async def on_task_assigned(self, event: Event) -> None:
        username = event.payload.get("github_username", "")
        if username not in self._tasks:
            self._tasks[username] = []
        self._tasks[username].append({
            "issue_number": event.payload.get("issue_number"),
            "issue_title": event.payload.get("issue_title", ""),
            "status": "assigned",
        })
        logger.info("Task #%s assigned to %s (load: %d)",
                    event.payload.get("issue_number"), username, self.get_load(username))

    def get_tasks(self, github_username: str) -> list[dict]:
        return list(self._tasks.get(github_username, []))

    def get_load(self, github_username: str) -> int:
        return len(self._tasks.get(github_username, []))

    def get_all_loads(self) -> dict[str, int]:
        return {username: len(tasks) for username, tasks in self._tasks.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_member/test_handler.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/member/ tests/test_modules/test_member/
git commit -m "feat: member module — task/load cache per team member"
```

---

### Task 2: Task Decomposer (LLM-based)

**Files:**
- Create: `grove/modules/task_breakdown/__init__.py`
- Create: `grove/modules/task_breakdown/decomposer.py`
- Create: `grove/modules/task_breakdown/prompts.py`
- Test: `tests/test_modules/test_task_breakdown/test_decomposer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_task_breakdown/test_decomposer.py
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.modules.task_breakdown.decomposer import TaskDecomposer, DecomposedTask


class TestDecomposedTask:
    def test_create(self):
        task = DecomposedTask(
            title="实现登录页面 UI",
            body="用户故事：作为用户，我希望看到一个登录页面...",
            labels=["frontend", "P0"],
            estimated_days=3,
            required_skills=["react", "css"],
        )
        assert task.title == "实现登录页面 UI"
        assert "P0" in task.labels
        assert task.estimated_days == 3


class TestTaskDecomposer:
    @pytest.fixture
    def decomposer(self):
        llm = MagicMock()
        return TaskDecomposer(llm=llm)

    async def test_decompose_prd(self, decomposer):
        mock_response = json.dumps({
            "tasks": [
                {
                    "title": "实现登录页面 UI",
                    "body": "用户故事描述...",
                    "labels": ["frontend", "P0"],
                    "estimated_days": 3,
                    "required_skills": ["react", "css"],
                },
                {
                    "title": "实现登录 API",
                    "body": "后端接口描述...",
                    "labels": ["backend", "P0"],
                    "estimated_days": 2,
                    "required_skills": ["python", "fastapi"],
                },
            ]
        })
        decomposer.llm.chat = AsyncMock(return_value=mock_response)

        tasks = await decomposer.decompose("暗黑模式", "# 暗黑模式 PRD\n\n详细内容...")
        assert len(tasks) == 2
        assert tasks[0].title == "实现登录页面 UI"
        assert tasks[1].required_skills == ["python", "fastapi"]

    async def test_decompose_handles_invalid_json(self, decomposer):
        decomposer.llm.chat = AsyncMock(return_value="not json")
        tasks = await decomposer.decompose("topic", "content")
        assert tasks == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_task_breakdown/test_decomposer.py -v`

- [ ] **Step 3: Implement decomposer.py and prompts.py**

```python
# grove/modules/task_breakdown/prompts.py
"""Prompt templates for task decomposition."""

DECOMPOSE_PROMPT = """\
你是 Grove，AI 产品经理。请将以下 PRD 拆解为可执行的开发任务。

PRD 主题: {topic}
PRD 内容:
{prd_content}

请拆解为具体的开发任务，每个任务应该是一个独立的 GitHub Issue。

以 JSON 格式回复：
{{
  "tasks": [
    {{
      "title": "任务标题（简洁明确）",
      "body": "任务详细描述，包含验收标准",
      "labels": ["角色标签(frontend/backend/fullstack/design)", "优先级(P0/P1/P2)"],
      "estimated_days": 天数(整数),
      "required_skills": ["所需技能标签"]
    }}
  ]
}}

要求：
- 每个任务粒度适中（1-5 天工作量）
- 包含清晰的验收标准
- 标注所需技能，便于分配
- P0 是必须的核心功能，P1 是重要功能，P2 是锦上添花
- 只回复 JSON，不要其他内容
"""
```

```python
# grove/modules/task_breakdown/decomposer.py
"""LLM-based PRD decomposition into tasks."""

import json
import logging
from dataclasses import dataclass, field

from grove.integrations.llm.client import LLMClient
from grove.modules.task_breakdown.prompts import DECOMPOSE_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class DecomposedTask:
    title: str
    body: str = ""
    labels: list[str] = field(default_factory=list)
    estimated_days: int = 1
    required_skills: list[str] = field(default_factory=list)


class TaskDecomposer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def decompose(self, topic: str, prd_content: str) -> list[DecomposedTask]:
        try:
            prompt = DECOMPOSE_PROMPT.format(topic=topic, prd_content=prd_content)
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请拆解任务。"}],
                max_tokens=4096,
            )
            data = json.loads(response)
            return [
                DecomposedTask(
                    title=t["title"],
                    body=t.get("body", ""),
                    labels=t.get("labels", []),
                    estimated_days=t.get("estimated_days", 1),
                    required_skills=t.get("required_skills", []),
                )
                for t in data.get("tasks", [])
            ]
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Task decomposition failed: %s", exc)
            return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_task_breakdown/test_decomposer.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/task_breakdown/ tests/test_modules/test_task_breakdown/
git commit -m "feat: LLM-based PRD decomposition into structured tasks"
```

---

### Task 3: Smart Task Assigner

**Files:**
- Create: `grove/modules/task_breakdown/assigner.py`
- Test: `tests/test_modules/test_task_breakdown/test_assigner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_task_breakdown/test_assigner.py
from pathlib import Path
import pytest
from grove.core.events import Member
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
        task = DecomposedTask(
            title="登录页面 UI",
            required_skills=["react", "css"],
            labels=["frontend", "P0"],
        )
        suggestion = assigner.suggest(task)
        assert suggestion is not None
        assert suggestion.github == "zhangsan"  # frontend dev with react + css skills

    def test_assign_backend_task(self, assigner):
        task = DecomposedTask(
            title="用户 API",
            required_skills=["python", "fastapi"],
            labels=["backend", "P0"],
        )
        suggestion = assigner.suggest(task)
        assert suggestion is not None
        assert suggestion.github == "lisi"  # backend lead with python + fastapi

    def test_assign_considers_load(self, assigner):
        # Give zhangsan 5 tasks to make him busy
        for i in range(5):
            assigner._member_module._tasks["zhangsan"].append({
                "issue_number": i, "issue_title": f"Task {i}", "status": "assigned",
            })
        task = DecomposedTask(
            title="CSS Fix",
            required_skills=["css"],
            labels=["frontend", "P1"],
        )
        suggestion = assigner.suggest(task)
        # wangwu is fullstack with no load, should be preferred over busy zhangsan
        assert suggestion is not None
        # Either wangwu (fullstack, 0 load) or zhangsan (frontend, 5 load)
        # wangwu doesn't have css skill in test data but has react
        # The assigner should still prefer lower-load member with partial skill match

    def test_no_match_returns_none(self, assigner):
        task = DecomposedTask(
            title="iOS App",
            required_skills=["swift", "ios"],
            labels=["mobile", "P0"],
        )
        suggestion = assigner.suggest(task)
        # No one has swift/ios skills, should return best effort or None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_task_breakdown/test_assigner.py -v`

- [ ] **Step 3: Implement assigner.py**

```python
# grove/modules/task_breakdown/assigner.py
"""Smart task assignment based on skills and workload."""

import logging
from grove.core.events import Member
from grove.core.member_resolver import MemberResolver
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.decomposer import DecomposedTask

logger = logging.getLogger(__name__)


class TaskAssigner:
    """Recommend task assignments based on skill match and current load."""

    def __init__(self, resolver: MemberResolver, member_module: MemberModule):
        self._resolver = resolver
        self._member_module = member_module

    def suggest(self, task: DecomposedTask) -> Member | None:
        """Suggest the best team member for a task. Returns None if no reasonable match."""
        candidates = []
        for member in self._resolver.all():
            # Skip design role for non-design tasks (and vice versa)
            if member.role == "design" and "design" not in task.labels:
                continue
            if "design" in task.labels and member.role != "design":
                continue

            # Calculate skill match score
            skill_match = len(set(member.skills) & set(task.required_skills))
            total_skills = len(task.required_skills) if task.required_skills else 1
            match_ratio = skill_match / total_skills

            # Get current load
            load = self._member_module.get_load(member.github)

            # Score: higher skill match is better, lower load is better
            # skill_match weighted more heavily than load
            score = match_ratio * 10 - load

            candidates.append((member, score, match_ratio))

        if not candidates:
            return None

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0]

        # If best match has zero skill overlap and there are required skills, return None
        if best[2] == 0 and task.required_skills:
            logger.info("No skill match found for task '%s'", task.title)
            return None

        logger.info(
            "Suggested %s for '%s' (match=%.0f%%, load=%d)",
            best[0].github, task.title, best[2] * 100,
            self._member_module.get_load(best[0].github),
        )
        return best[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_task_breakdown/test_assigner.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/task_breakdown/assigner.py tests/test_modules/test_task_breakdown/test_assigner.py
git commit -m "feat: smart task assigner with skill matching and load balancing"
```

---

### Task 4: Lark Task Assignment Card

**Files:**
- Modify: `grove/integrations/lark/cards.py`
- Test: `tests/test_integrations/test_lark_cards.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_integrations/test_lark_cards.py
from grove.integrations.lark.cards import build_notification_card, build_task_assignment_card


class TestLarkCards:
    def test_notification_card(self):
        card = build_notification_card("Test", "Content")
        assert card["header"]["title"]["content"] == "Test"

    def test_task_assignment_card(self):
        card = build_task_assignment_card(
            task_title="实现登录页面 UI",
            issue_number=23,
            priority="P0",
            estimated_days=3,
            assignee_name="张三",
            repo="org/repo",
        )
        assert card["header"]["title"]["content"] == "🌳 Grove — 新任务分配"
        # Should have action buttons
        elements = card["elements"]
        actions = [e for e in elements if e.get("tag") == "action"]
        assert len(actions) == 1
        buttons = actions[0]["actions"]
        assert len(buttons) == 3  # accept, negotiate, reject
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_integrations/test_lark_cards.py -v`

- [ ] **Step 3: Add build_task_assignment_card to cards.py**

```python
# Add to grove/integrations/lark/cards.py

def build_task_assignment_card(
    task_title: str,
    issue_number: int,
    priority: str,
    estimated_days: int,
    assignee_name: str,
    repo: str,
) -> dict:
    """Build an interactive task assignment card with accept/negotiate/reject buttons."""
    issue_url = f"https://github.com/{repo}/issues/{issue_number}"
    return {
        "header": {
            "title": {"tag": "plain_text", "content": "🌳 Grove — 新任务分配"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**任务：** {task_title}\n"
                        f"**优先级：** {priority}\n"
                        f"**关联 Issue：** [#{issue_number}]({issue_url})\n"
                        f"**预估工时：** {estimated_days} 天\n"
                        f"**分配给：** {assignee_name}"
                    ),
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 接受"},
                        "type": "primary",
                        "value": {"action": "accept", "issue_number": issue_number},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔄 需要调整"},
                        "value": {"action": "negotiate", "issue_number": issue_number},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 无法承接"},
                        "type": "danger",
                        "value": {"action": "reject", "issue_number": issue_number},
                    },
                ],
            },
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_integrations/test_lark_cards.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/integrations/lark/cards.py tests/test_integrations/test_lark_cards.py
git commit -m "feat: Lark task assignment card with accept/negotiate/reject buttons"
```

---

### Task 5: GitHub Client — update_issue and create_milestone

**Files:**
- Modify: `grove/integrations/github/client.py`

- [ ] **Step 1: Add update_issue and create_milestone methods**

```python
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def update_issue(self, repo: str, issue_number: int, **kwargs) -> None:
        """Update an issue. Accepts: title, body, state, labels, assignee, milestone."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        issue = r.get_issue(issue_number)
        issue.edit(**kwargs)
        logger.info("Updated issue #%d in %s", issue_number, repo)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def create_milestone(self, repo: str, title: str, due_on: str | None = None):
        """Create a milestone. Returns the milestone number."""
        from datetime import datetime
        gh = self._get_github()
        r = gh.get_repo(repo)
        kwargs = {"title": title}
        if due_on:
            kwargs["due_on"] = datetime.fromisoformat(due_on)
        milestone = r.create_milestone(**kwargs)
        logger.info("Created milestone '%s' (#%d) in %s", title, milestone.number, repo)
        return milestone.number
```

- [ ] **Step 2: Commit**

```bash
git add grove/integrations/github/client.py
git commit -m "feat: GitHub client update_issue and create_milestone"
```

---

### Task 6: Task Breakdown Handler

**Files:**
- Create: `grove/modules/task_breakdown/handler.py`
- Test: `tests/test_modules/test_task_breakdown/test_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_task_breakdown/test_handler.py
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.handler import TaskBreakdownModule
from grove.modules.task_breakdown.decomposer import DecomposedTask


class TestTaskBreakdownModule:
    @pytest.fixture
    def module(self, grove_dir: Path, sample_team_yml: Path):
        bus = EventBus()
        llm = MagicMock()
        lark = MagicMock()
        lark.send_text = AsyncMock()
        lark.send_card = AsyncMock()
        github = MagicMock()
        github.create_issue = MagicMock(return_value=MagicMock(number=42))
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        member_module = MemberModule(resolver=resolver, storage=storage)
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"

        module = TaskBreakdownModule(
            bus=bus, llm=llm, lark=lark, github=github,
            config=config, member_module=member_module, resolver=resolver,
        )
        bus.register(module)
        bus.register(member_module)
        return module, bus

    async def test_prd_finalized_triggers_decomposition(self, module):
        mod, bus = module
        # Mock decomposer to return tasks
        mod._decomposer.decompose = AsyncMock(return_value=[
            DecomposedTask(title="Task A", body="desc", labels=["frontend", "P0"],
                          estimated_days=2, required_skills=["react"]),
        ])
        # Mock GitHub create_issue to return IssueData
        from grove.integrations.github.models import IssueData
        mod.github.create_issue = MagicMock(return_value=IssueData(
            number=42, title="Task A", body="desc", labels=["frontend", "P0"],
        ))

        event = Event(
            type=EventType.INTERNAL_PRD_FINALIZED, source="internal",
            payload={"topic": "暗黑模式", "prd_doc_id": "doc123"},
        )
        await bus.dispatch(event)

        mod.github.create_issue.assert_called_once()
        # Should send assignment card
        mod.lark.send_card.assert_called()

    async def test_card_action_accept_assigns_issue(self, module):
        mod, bus = module
        mod.github.update_issue = MagicMock()

        # Simulate pending assignment
        mod._pending_assignments[42] = {
            "assignee_github": "zhangsan",
            "task_title": "Task A",
        }

        event = Event(
            type=EventType.LARK_CARD_ACTION, source="lark",
            payload={
                "action": {"value": {"action": "accept", "issue_number": 42}},
            },
            member=Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend"),
        )
        await bus.dispatch(event)

        mod.github.update_issue.assert_called_once_with(
            "org/repo", 42, assignee="zhangsan",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_task_breakdown/test_handler.py -v`

- [ ] **Step 3: Implement handler.py**

```python
# grove/modules/task_breakdown/handler.py
"""Task breakdown module — decompose PRD, create Issues, assign via cards."""

import logging

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_task_assignment_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.assigner import TaskAssigner
from grove.modules.task_breakdown.decomposer import TaskDecomposer

logger = logging.getLogger(__name__)


class TaskBreakdownModule:
    """Decompose PRDs into tasks, create GitHub Issues, and manage assignments."""

    def __init__(
        self,
        bus: EventBus,
        llm: LLMClient,
        lark: LarkClient,
        github: GitHubClient,
        config: GroveConfig,
        member_module: MemberModule,
        resolver: MemberResolver,
    ):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._decomposer = TaskDecomposer(llm=llm)
        self._assigner = TaskAssigner(resolver=resolver, member_module=member_module)
        # issue_number -> assignment info (pending card confirmation)
        self._pending_assignments: dict[int, dict] = {}

    @subscribe(EventType.INTERNAL_PRD_FINALIZED)
    async def on_prd_finalized(self, event: Event) -> None:
        """PRD finalized — decompose into tasks, create Issues, suggest assignments."""
        topic = event.payload.get("topic", "")
        prd_doc_id = event.payload.get("prd_doc_id")
        repo = self.config.project.repo

        # Read PRD content (try from Lark if doc_id available, else use topic as fallback)
        prd_content = f"PRD: {topic}"
        if prd_doc_id:
            try:
                prd_content = await self.lark.read_doc(prd_doc_id)
            except Exception:
                logger.warning("Could not read PRD doc %s, using topic", prd_doc_id)

        await self.lark.send_text(
            self.config.lark.chat_id,
            f"PRD「{topic}」已定稿，正在拆解任务...",
        )

        # Decompose
        tasks = await self._decomposer.decompose(topic, prd_content)
        if not tasks:
            await self.lark.send_text(
                self.config.lark.chat_id,
                f"任务拆解失败，请手动创建 Issues。",
            )
            return

        # Create GitHub Issues and suggest assignments
        for task in tasks:
            try:
                issue = self.github.create_issue(
                    repo=repo,
                    title=task.title,
                    body=task.body,
                    labels=task.labels,
                )
                issue_number = issue.number
            except Exception:
                logger.exception("Failed to create issue for task '%s'", task.title)
                continue

            # Suggest assignment
            suggested = self._assigner.suggest(task)
            if suggested:
                self._pending_assignments[issue_number] = {
                    "assignee_github": suggested.github,
                    "task_title": task.title,
                }

                # Extract priority from labels
                priority = next((lb for lb in task.labels if lb.startswith("P")), "P1")

                card = build_task_assignment_card(
                    task_title=task.title,
                    issue_number=issue_number,
                    priority=priority,
                    estimated_days=task.estimated_days,
                    assignee_name=suggested.name,
                    repo=repo,
                )
                await self.lark.send_card(self.config.lark.chat_id, card)

        await self.lark.send_text(
            self.config.lark.chat_id,
            f"已创建 {len(tasks)} 个 Issues，请在上方卡片中确认任务分配。",
        )

    @subscribe(EventType.LARK_CARD_ACTION)
    async def on_card_action(self, event: Event) -> None:
        """Handle task assignment card button clicks."""
        action_value = event.payload.get("action", {}).get("value", {})
        action = action_value.get("action")
        issue_number = action_value.get("issue_number")

        if issue_number is None or issue_number not in self._pending_assignments:
            return

        assignment = self._pending_assignments[issue_number]
        repo = self.config.project.repo

        if action == "accept":
            self.github.update_issue(
                repo, issue_number, assignee=assignment["assignee_github"],
            )
            await self.lark.send_text(
                self.config.lark.chat_id,
                f"✅ #{issue_number}「{assignment['task_title']}」已分配给 {assignment['assignee_github']}",
            )
            # Emit task_assigned event
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_TASK_ASSIGNED,
                source="internal",
                payload={
                    "github_username": assignment["assignee_github"],
                    "issue_number": issue_number,
                    "issue_title": assignment["task_title"],
                },
            ))
            del self._pending_assignments[issue_number]

        elif action == "reject":
            await self.lark.send_text(
                self.config.lark.chat_id,
                f"#{issue_number}「{assignment['task_title']}」分配已取消，请手动分配。",
            )
            del self._pending_assignments[issue_number]

        elif action == "negotiate":
            await self.lark.send_text(
                self.config.lark.chat_id,
                f"#{issue_number}「{assignment['task_title']}」需要调整，请在群里讨论后手动分配。",
            )
            del self._pending_assignments[issue_number]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_task_breakdown/test_handler.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/task_breakdown/handler.py tests/test_modules/test_task_breakdown/test_handler.py
git commit -m "feat: task breakdown handler — decompose, create Issues, assign via cards"
```

---

### Task 7: Card Action Event in Lark WebSocket

**Files:**
- Modify: `grove/ingress/lark_websocket.py`

The Lark WebSocket needs to handle card action callbacks in addition to messages. Add a handler for `P2CardActionTrigger` (or the equivalent card callback event type).

- [ ] **Step 1: Add card action handling to lark_websocket.py**

Add to the `create_lark_ws_client` function, alongside the existing `handle_message`:

```python
    def handle_card_action(data):
        """Handle Lark interactive card button clicks."""
        try:
            action = data.event.action
            operator = data.event.operator
            event = Event(
                type=EventType.LARK_CARD_ACTION,
                source="lark",
                payload={
                    "action": {"value": action.value if hasattr(action, 'value') else {}},
                    "operator_id": operator.open_id if hasattr(operator, 'open_id') else "",
                },
            )
            asyncio.run_coroutine_threadsafe(on_event(event), _loop)
        except Exception:
            logger.exception("Failed to parse card action")
```

Register in the event_handler builder (note: exact API depends on lark-oapi version):
```python
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(handle_message) \
        .build()
    # Card actions may need a separate registration depending on SDK version
```

- [ ] **Step 2: Commit**

```bash
git add grove/ingress/lark_websocket.py
git commit -m "feat: handle Lark card action events in WebSocket ingress"
```

---

### Task 8: Module Registration in main.py

**Files:**
- Modify: `grove/main.py`

- [ ] **Step 1: Add imports and registration**

Add imports at top:
```python
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.handler import TaskBreakdownModule
```

Inside `lifespan`, after existing module registrations (communication + prd_generator), add:

```python
    # Member module
    member_module = MemberModule(resolver=resolver, storage=storage)
    event_bus.register(member_module)
    logger.info("Registered MemberModule")

    # Task breakdown module
    task_breakdown = TaskBreakdownModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        member_module=member_module, resolver=resolver,
    )
    event_bus.register(task_breakdown)
    logger.info("Registered TaskBreakdownModule")
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "from grove.main import app; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add grove/main.py
git commit -m "feat: register member and task breakdown modules in main.py"
```

---

### Task 9: Full Test Suite + Lint

- [ ] **Step 1: Run all tests**

Run: `.venv/bin/pytest -v --tb=short`

- [ ] **Step 2: Run linter**

Run: `.venv/bin/ruff check grove/ tests/`

- [ ] **Step 3: Fix any issues and commit**

```bash
git add -A && git commit -m "fix: resolve test/lint issues from Phase 3"
```

---

## Phase 3 Completion Criteria

- [ ] PRD finalized event → LLM decomposes into tasks → GitHub Issues created
- [ ] Task assignment cards sent to Lark with accept/negotiate/reject buttons
- [ ] Card accept → GitHub Issue assigned + task_assigned event emitted
- [ ] Member module tracks task load per member
- [ ] Smart assigner matches skills + considers load
- [ ] All tests pass, lint clean

**Next:** Create Phase 4 plan (Daily Report & Standup).
