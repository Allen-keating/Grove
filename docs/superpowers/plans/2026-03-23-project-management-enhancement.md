# Project Management Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project scanning, management-level reporting, commit monitoring, and daily task dispatch with negotiation to Grove.

**Architecture:** 3 new modules (project_scanner, project_overview, morning_dispatch) + 2 enhancements (daily_report, communication) + GitHub client extension + shared commit classifier utility. All follow existing event-bus module pattern with `@subscribe` decorators.

**Tech Stack:** Python 3.12+, FastAPI, PyGithub, lark-oapi, Anthropic SDK, APScheduler, Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-03-23-project-management-enhancement-design.md`

---

## File Map

### New Files (18)

| File | Responsibility |
|------|---------------|
| `grove/utils/__init__.py` | Package init |
| `grove/utils/commit_classifier.py` | Rule-based + LLM fallback commit classification |
| `grove/modules/project_scanner/__init__.py` | Package init |
| `grove/modules/project_scanner/handler.py` | Scan orchestration: data collection → LLM analysis → doc generation |
| `grove/modules/project_scanner/analyzer.py` | 3-step LLM analysis (architecture, features, PRD) |
| `grove/modules/project_scanner/prompts.py` | Prompt templates for the 3 analysis steps |
| `grove/modules/project_overview/__init__.py` | Package init |
| `grove/modules/project_overview/handler.py` | Overview orchestration: collect → trend → LLM → card |
| `grove/modules/project_overview/collectors.py` | Full-cycle data collection + 7-day trend calculation |
| `grove/modules/project_overview/prompts.py` | Health rating + risk analysis prompt |
| `grove/modules/morning_dispatch/__init__.py` | Package init |
| `grove/modules/morning_dispatch/handler.py` | 3-phase flow: generate → negotiate → announce |
| `grove/modules/morning_dispatch/planner.py` | LLM-based per-member task draft generation |
| `grove/modules/morning_dispatch/negotiator.py` | Parse member replies, update task list |
| `grove/modules/morning_dispatch/prompts.py` | Task planning + negotiation understanding prompts |
| `tests/test_modules/test_project_scanner/__init__.py` | Test package |
| `tests/test_modules/test_project_overview/__init__.py` | Test package |
| `tests/test_modules/test_morning_dispatch/__init__.py` | Test package |

### Modified Files (12)

| File | Changes |
|------|---------|
| `grove/core/events.py:28-35` | +5 EventType values |
| `grove/config.py:51-83` | +DispatchConfig, +SchedulesConfig fields, +ModulesConfig fields, +GroveConfig.dispatch |
| `grove/core/module_registry.py:107-118` | +3 modules in merge_module_state |
| `grove/ingress/scheduler.py:12-45` | Refactor to accept SchedulesConfig |
| `grove/integrations/github/client.py:145-185` | +3 API methods |
| `grove/integrations/lark/cards.py:89-100` | +2 card builders |
| `grove/modules/communication/intent_parser.py:12-52` | +3 intents, +context param |
| `grove/modules/communication/prompts.py:1-30` | +3 intent descriptions |
| `grove/modules/communication/handler.py:15-61` | +3 intent routes, +storage dep |
| `grove/modules/daily_report/collectors.py:1-30` | +commits_by_type via classifier |
| `grove/modules/daily_report/handler.py:33-72` | +commit type in report output + snapshot |
| `grove/main.py:1-197` | +3 module imports, instantiation, registration, scheduler |

---

## Task 1: Events + Config + Registry (Infrastructure Wiring)

**Files:**
- Modify: `grove/core/events.py:28-35`
- Modify: `grove/config.py:51-83`
- Modify: `grove/core/module_registry.py:107-118`
- Test: `tests/test_core/test_config.py`

- [ ] **Step 1: Write test for new EventTypes**

```python
# tests/test_core/test_events.py — append to existing file
def test_new_event_types_exist():
    from grove.core.events import EventType
    assert EventType.INTERNAL_SCAN_PROJECT == "internal.scan_project"
    assert EventType.INTERNAL_PROJECT_OVERVIEW == "internal.project_overview"
    assert EventType.CRON_PROJECT_OVERVIEW == "cron.project_overview"
    assert EventType.CRON_MORNING_DISPATCH == "cron.morning_dispatch"
    assert EventType.INTERNAL_DISPATCH_NEGOTIATE == "internal.dispatch_negotiate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core/test_events.py::test_new_event_types_exist -v`
Expected: FAIL — AttributeError

- [ ] **Step 3: Add 5 new EventTypes to events.py**

In `grove/core/events.py`, after line 35 (`INTERNAL_RISK_DETECTED`), add:

```python
    INTERNAL_SCAN_PROJECT = "internal.scan_project"
    INTERNAL_PROJECT_OVERVIEW = "internal.project_overview"
    CRON_PROJECT_OVERVIEW = "cron.project_overview"
    CRON_MORNING_DISPATCH = "cron.morning_dispatch"
    INTERNAL_DISPATCH_NEGOTIATE = "internal.dispatch_negotiate"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core/test_events.py -v`

- [ ] **Step 5: Write test for new config models**

```python
# tests/test_core/test_config.py — append
def test_dispatch_config_defaults():
    from grove.config import DispatchConfig
    dc = DispatchConfig()
    assert dc.confirm_deadline_minutes == 75
    assert dc.max_negotiate_rounds == 10

def test_schedules_config_new_fields():
    from grove.config import SchedulesConfig
    sc = SchedulesConfig()
    assert sc.project_overview == "10:00"
    assert sc.morning_dispatch == "09:15"

def test_modules_config_new_fields():
    from grove.config import ModulesConfig
    mc = ModulesConfig()
    assert mc.project_scanner is True
    assert mc.project_overview is True
    assert mc.morning_dispatch is True

def test_grove_config_has_dispatch():
    from grove.config import GroveConfig, DispatchConfig
    # Minimal valid config
    gc = GroveConfig(
        project={"name": "t", "repo": "o/r"},
        lark={"app_id": "a", "app_secret": "s", "chat_id": "c", "space_id": "sp"},
        github={"app_id": "1", "private_key_path": "/k", "installation_id": "2"},
        llm={"api_key": "k"},
    )
    assert isinstance(gc.dispatch, DispatchConfig)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_core/test_config.py::test_dispatch_config_defaults -v`

- [ ] **Step 7: Add config models to config.py**

In `grove/config.py`, after `SchedulesConfig` (line 53), add `project_overview` and `morning_dispatch` fields:

```python
class SchedulesConfig(BaseModel):
    daily_report: str = "09:00"
    doc_drift_check: str = "09:00"
    project_overview: str = "10:00"
    morning_dispatch: str = "09:15"
```

After `DocSyncConfig` (line 58), add:

```python
class DispatchConfig(BaseModel):
    confirm_deadline_minutes: int = 75
    max_negotiate_rounds: int = 10
```

In `ModulesConfig`, after `member: bool = True` (line 69), add:

```python
    project_scanner: bool = True
    project_overview: bool = True
    morning_dispatch: bool = True
```

In `GroveConfig`, after `admin_token` (line 83), add:

```python
    dispatch: DispatchConfig = DispatchConfig()
```

- [ ] **Step 8: Run config tests**

Run: `python -m pytest tests/test_core/test_config.py -v`

- [ ] **Step 9: Update merge_module_state in module_registry.py**

In `grove/core/module_registry.py`, in the `merge_module_state` function, add after line 117 (`"member": modules_cfg.member,`):

```python
        "project_scanner": modules_cfg.project_scanner,
        "project_overview": modules_cfg.project_overview,
        "morning_dispatch": modules_cfg.morning_dispatch,
```

- [ ] **Step 10: Run all core tests**

Run: `python -m pytest tests/test_core/ -v`

- [ ] **Step 11: Commit**

```bash
git add grove/core/events.py grove/config.py grove/core/module_registry.py tests/test_core/
git commit -m "feat: add event types, config models, and registry entries for project management"
```

---

## Task 2: Scheduler Refactor

**Files:**
- Modify: `grove/ingress/scheduler.py`
- Modify: `grove/main.py:157-163` (scheduler call site)
- Test: `tests/test_ingress/test_scheduler.py`

- [ ] **Step 1: Write test for new scheduler signature**

```python
# tests/test_ingress/test_scheduler.py — replace or extend existing
import pytest
from unittest.mock import AsyncMock
from grove.config import SchedulesConfig
from grove.ingress.scheduler import create_scheduler

class TestScheduler:
    def test_creates_all_jobs(self):
        schedules = SchedulesConfig(
            daily_report="09:00", doc_drift_check="09:00",
            project_overview="10:00", morning_dispatch="09:15",
        )
        on_event = AsyncMock()
        scheduler = create_scheduler(
            schedules=schedules, timezone="Asia/Shanghai", on_event=on_event,
        )
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "daily_report" in job_ids
        assert "doc_drift_check" in job_ids
        assert "project_overview" in job_ids
        assert "morning_dispatch" in job_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingress/test_scheduler.py::TestScheduler::test_creates_all_jobs -v`

- [ ] **Step 3: Rewrite scheduler.py**

Replace the full content of `grove/ingress/scheduler.py`:

```python
"""APScheduler setup for cron-based event emission."""
import logging
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from grove.config import SchedulesConfig
from grove.core.events import Event, EventType

logger = logging.getLogger(__name__)

_SCHEDULE_MAP = {
    "daily_report": EventType.CRON_DAILY_REPORT,
    "doc_drift_check": EventType.CRON_DOC_DRIFT_CHECK,
    "project_overview": EventType.CRON_PROJECT_OVERVIEW,
    "morning_dispatch": EventType.CRON_MORNING_DISPATCH,
}


def create_scheduler(
    schedules: SchedulesConfig,
    timezone: str,
    on_event: Callable[[Event], Awaitable[None]],
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone)

    for field_name, event_type in _SCHEDULE_MAP.items():
        time_str = getattr(schedules, field_name, None)
        if not time_str:
            continue
        hour, minute = time_str.split(":")

        async def _emit(et=event_type, fn=field_name):
            logger.info("Cron: emitting %s event", fn)
            await on_event(Event(type=et, source="scheduler", payload={}))

        scheduler.add_job(_emit, "cron", hour=int(hour), minute=int(minute), id=field_name)

    return scheduler
```

- [ ] **Step 4: Run scheduler tests**

Run: `python -m pytest tests/test_ingress/test_scheduler.py -v`

- [ ] **Step 5: Update main.py scheduler call site**

In `grove/main.py`, replace lines 158-163:

```python
    # Before:
    scheduler = create_scheduler(
        daily_report_time=config.schedules.daily_report,
        doc_drift_time=config.schedules.doc_drift_check,
        timezone=config.work_hours.timezone,
        on_event=handle_event,
    )

    # After:
    scheduler = create_scheduler(
        schedules=config.schedules,
        timezone=config.work_hours.timezone,
        on_event=handle_event,
    )
```

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `python -m pytest tests/ -v`

- [ ] **Step 7: Commit**

```bash
git add grove/ingress/scheduler.py grove/main.py tests/test_ingress/test_scheduler.py
git commit -m "refactor: scheduler accepts SchedulesConfig with all 4 cron jobs"
```

---

## Task 3: GitHub Client Enhancement (3 New API Methods)

**Files:**
- Modify: `grove/integrations/github/client.py:145-185`
- Test: `tests/test_integrations/test_github_client.py`

- [ ] **Step 1: Write tests for new methods**

```python
# tests/test_integrations/test_github_client.py — append
from unittest.mock import MagicMock, patch

class TestGitHubClientNewMethods:
    def _make_client(self):
        return GitHubClient(app_id="1", private_key_path="/tmp/fake.pem", installation_id="2")

    def test_get_repo_tree(self):
        client = self._make_client()
        mock_tree = MagicMock()
        mock_element = MagicMock()
        mock_element.path = "grove/main.py"
        mock_element.type = "blob"
        mock_element.size = 1234
        mock_tree.tree = [mock_element]

        mock_repo = MagicMock()
        mock_repo.get_git_tree.return_value = mock_tree
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.get_repo_tree("org/repo")
        assert len(result) == 1
        assert result[0]["path"] == "grove/main.py"
        assert result[0]["type"] == "blob"
        mock_repo.get_git_tree.assert_called_once()

    def test_get_commit_detail(self):
        client = self._make_client()
        mock_file = MagicMock()
        mock_file.filename = "main.py"
        mock_file.status = "modified"
        mock_file.additions = 10
        mock_file.deletions = 3
        mock_commit = MagicMock()
        mock_commit.sha = "abc1234567"
        mock_commit.commit.message = "feat: add feature"
        mock_commit.commit.author.name = "alice"
        mock_commit.commit.author.date.isoformat.return_value = "2026-03-23T10:00:00"
        mock_commit.files = [mock_file]

        mock_repo = MagicMock()
        mock_repo.get_commit.return_value = mock_commit
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.get_commit_detail("org/repo", "abc1234567")
        assert result["sha"] == "abc1234"
        assert result["files"][0]["filename"] == "main.py"
        assert result["files"][0]["additions"] == 10

    def test_list_recent_commits_detailed_respects_max(self):
        client = self._make_client()
        # Create 5 mock commits
        mock_commits = []
        for i in range(5):
            mc = MagicMock()
            mc.sha = f"sha{i:07d}"
            mc.commit.message = f"commit {i}"
            mc.commit.author.name = "alice"
            mc.commit.author.date.isoformat.return_value = f"2026-03-23T{i:02d}:00:00"
            mc.files = []
            mock_commits.append(mc)

        mock_repo = MagicMock()
        mock_repo.get_commits.return_value = mock_commits
        mock_repo.get_commit.side_effect = lambda sha: next(c for c in mock_commits if c.sha == sha)
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.list_recent_commits_detailed("org/repo", since="2026-03-22T00:00:00", max_commits=3)
        assert len(result) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_integrations/test_github_client.py::TestGitHubClientNewMethods -v`

- [ ] **Step 3: Implement 3 new methods in client.py**

Append after `list_milestones` method (after line 184) in `grove/integrations/github/client.py`:

```python
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def get_repo_tree(self, repo: str, recursive: bool = True) -> list[dict]:
        """Get the full repository file tree via Git Trees API."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        default_branch = r.default_branch
        tree = r.get_git_tree(default_branch, recursive=recursive)
        IGNORE_PREFIXES = (
            "node_modules/", ".git/", "__pycache__/", "vendor/",
            ".venv/", "venv/", "dist/", "build/", ".tox/",
        )
        return [
            {"path": item.path, "type": item.type, "size": item.size or 0}
            for item in tree.tree
            if not any(item.path.startswith(p) or f"/{p}" in item.path for p in IGNORE_PREFIXES)
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def get_commit_detail(self, repo: str, sha: str) -> dict:
        """Get detailed commit info including per-file changes."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        commit = r.get_commit(sha)
        return {
            "sha": commit.sha[:7],
            "message": commit.commit.message.split("\n")[0],
            "author": commit.commit.author.name,
            "date": commit.commit.author.date.isoformat(),
            "files": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
                for f in (commit.files or [])
            ],
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_recent_commits_detailed(
        self, repo: str, since: str, until: str | None = None, max_commits: int = 200,
    ) -> list[dict]:
        """List recent commits with per-file change details. Caps at max_commits."""
        from datetime import datetime
        gh = self._get_github()
        r = gh.get_repo(repo)
        kwargs = {"since": datetime.fromisoformat(since)}
        if until:
            kwargs["until"] = datetime.fromisoformat(until)
        commits = r.get_commits(**kwargs)
        results = []
        for c in commits[:max_commits]:
            detail = self.get_commit_detail(repo, c.sha)
            results.append(detail)
        return results
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_integrations/test_github_client.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/integrations/github/client.py tests/test_integrations/test_github_client.py
git commit -m "feat: add get_repo_tree, get_commit_detail, list_recent_commits_detailed to GitHub client"
```

---

## Task 4: Commit Classifier Utility

**Files:**
- Create: `grove/utils/__init__.py`
- Create: `grove/utils/commit_classifier.py`
- Test: `tests/test_utils/__init__.py` (new)
- Test: `tests/test_utils/test_commit_classifier.py` (new)

- [ ] **Step 1: Write tests**

```python
# tests/test_utils/__init__.py — empty

# tests/test_utils/test_commit_classifier.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_utils/test_commit_classifier.py -v`

- [ ] **Step 3: Create utils package and classifier**

```python
# grove/utils/__init__.py — empty
```

```python
# grove/utils/commit_classifier.py
"""Shared commit classification: conventional-commit rules + LLM fallback."""
import json
import logging
import re

logger = logging.getLogger(__name__)

_PREFIX_MAP = {
    "feat": "feature",
    "fix": "bugfix",
    "docs": "docs",
    "refactor": "refactor",
    "chore": "chore",
    "test": "chore",
    "ci": "chore",
    "build": "chore",
    "style": "chore",
    "perf": "refactor",
}

_CONVENTIONAL_RE = re.compile(r"^(\w+)(?:\(.+?\))?[!]?:\s")

_CLASSIFY_PROMPT = """\
根据 commit message 和修改的文件列表，判断这个提交的类型。
只返回 JSON：{"type": "feature" | "bugfix" | "refactor" | "docs" | "chore"}
不要其他内容。
"""


def classify_commit_by_rule(message: str) -> str | None:
    """Try to classify using conventional commit prefix. Returns None if no match."""
    match = _CONVENTIONAL_RE.match(message)
    if match:
        prefix = match.group(1).lower()
        return _PREFIX_MAP.get(prefix)
    return None


async def classify_commit(
    message: str, files_changed: list[str], *, llm=None,
) -> str:
    """Classify a commit. Uses rule matching first, LLM fallback if needed."""
    result = classify_commit_by_rule(message)
    if result is not None:
        return result

    if llm is None:
        return "chore"

    try:
        response = await llm.chat(
            system_prompt=_CLASSIFY_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Message: {message}\nFiles: {', '.join(files_changed[:20])}",
            }],
            max_tokens=64,
        )
        data = json.loads(response)
        commit_type = data.get("type", "chore")
        if commit_type in ("feature", "bugfix", "refactor", "docs", "chore"):
            return commit_type
        return "chore"
    except Exception:
        logger.warning("LLM classify_commit failed for: %s", message[:80])
        return "chore"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_utils/ -v`

- [ ] **Step 5: Commit**

```bash
git add grove/utils/ tests/test_utils/
git commit -m "feat: add shared commit classifier utility with rule + LLM fallback"
```

---

## Task 5: Daily Report Enhancement (Commit Classification)

**Files:**
- Modify: `grove/modules/daily_report/collectors.py`
- Modify: `grove/modules/daily_report/handler.py:33-72`
- Test: `tests/test_modules/test_daily_report/test_collectors.py`
- Test: `tests/test_modules/test_daily_report/test_handler.py`

- [ ] **Step 1: Write test for enhanced collector**

```python
# tests/test_modules/test_daily_report/test_collectors.py — append
from unittest.mock import AsyncMock

@pytest.mark.asyncio
class TestDailyDataCollectorEnhanced:
    async def test_collect_with_classification(self):
        github = MagicMock()
        github.list_recent_commits.return_value = [
            {"sha": "abc1234", "message": "feat: add login", "author": "zhangsan", "date": "2026-03-21T10:00:00"},
            {"sha": "def5678", "message": "fix: null check", "author": "lisi", "date": "2026-03-21T11:00:00"},
            {"sha": "ghi9012", "message": "docs: update readme", "author": "lisi", "date": "2026-03-21T12:00:00"},
        ]
        github.list_recent_commits_detailed.return_value = [
            {"sha": "abc1234", "message": "feat: add login", "author": "zhangsan", "date": "2026-03-21T10:00:00", "files": [{"filename": "login.py", "status": "added", "additions": 50, "deletions": 0}]},
            {"sha": "def5678", "message": "fix: null check", "author": "lisi", "date": "2026-03-21T11:00:00", "files": [{"filename": "api.py", "status": "modified", "additions": 2, "deletions": 1}]},
            {"sha": "ghi9012", "message": "docs: update readme", "author": "lisi", "date": "2026-03-21T12:00:00", "files": [{"filename": "README.md", "status": "modified", "additions": 5, "deletions": 2}]},
        ]
        github.list_open_prs.return_value = []
        github.list_issues.return_value = []
        github.list_milestones.return_value = []
        collector = DailyDataCollector(github=github, repo="org/repo")
        llm = AsyncMock()
        data = await collector.collect_with_classification(llm=llm)
        assert data["commits_by_type"]["feature"] == 1
        assert data["commits_by_type"]["bugfix"] == 1
        assert data["commits_by_type"]["docs"] == 1
        # LLM should NOT have been called (all conventional commits)
        llm.chat.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_modules/test_daily_report/test_collectors.py::TestDailyDataCollectorEnhanced -v`

- [ ] **Step 3: Add collect_with_classification to collectors.py**

In `grove/modules/daily_report/collectors.py`, add a new async method after `collect`:

```python
    async def collect_with_classification(self, *, llm=None) -> dict:
        """Collect daily data with commit type classification."""
        from grove.utils.commit_classifier import classify_commit

        data = self.collect()
        detailed = self.github.list_recent_commits_detailed(self.repo, since=(
            datetime.now(timezone.utc) - timedelta(hours=24)).isoformat())

        commits_by_type: dict[str, int] = {}
        commit_details: list[dict] = []
        for c in detailed:
            files = [f["filename"] for f in c.get("files", [])]
            ctype = await classify_commit(c["message"], files, llm=llm)
            commits_by_type[ctype] = commits_by_type.get(ctype, 0) + 1
            commit_details.append({
                "sha": c["sha"], "message": c["message"],
                "author": c["author"], "type": ctype,
                "files_changed_count": len(c.get("files", [])),
            })

        data["commits_by_type"] = commits_by_type
        data["commit_details"] = commit_details
        return data
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_modules/test_daily_report/test_collectors.py -v`

- [ ] **Step 5: Update handler to use new collector method and include type in report**

In `grove/modules/daily_report/handler.py`, modify `on_daily_report`:

Replace `data = self._collector.collect()` (line 36) with:
```python
        data = await self._collector.collect_with_classification(llm=self.llm)
```

In `_build_github_report`, after the member activity table (after line 83), add:

```python
        if data.get("commits_by_type"):
            lines.append("\n## 📊 提交分布\n")
            lines.append("| 类型 | 数量 |")
            lines.append("|------|------|")
            for ctype, count in data["commits_by_type"].items():
                lines.append(f"| {ctype} | {count} |")
```

In `_save_snapshot`, the `{**data, ...}` already spreads all data keys, so `commits_by_type` will be included automatically.

- [ ] **Step 6: Run all daily report tests**

Run: `python -m pytest tests/test_modules/test_daily_report/ -v`

- [ ] **Step 7: Commit**

```bash
git add grove/modules/daily_report/ tests/test_modules/test_daily_report/
git commit -m "feat: enhance daily report with commit type classification"
```

---

## Task 6: Communication Module Enhancement (3 New Intents)

**Files:**
- Modify: `grove/modules/communication/intent_parser.py:12-52`
- Modify: `grove/modules/communication/prompts.py:1-30`
- Modify: `grove/modules/communication/handler.py:15-61`
- Test: `tests/test_modules/test_communication/test_intent_parser.py`
- Test: `tests/test_modules/test_communication/test_handler.py`

- [ ] **Step 1: Add 3 new Intent enum values**

In `grove/modules/communication/intent_parser.py`, add after `QUERY_MODULE_STATUS` (line 21):

```python
    SCAN_PROJECT = "scan_project"
    QUERY_PROJECT_OVERVIEW = "query_project_overview"
    DISPATCH_NEGOTIATE = "dispatch_negotiate"
```

- [ ] **Step 2: Add context parameter to IntentParser.parse**

Replace the `parse` method in `intent_parser.py`:

```python
    async def parse(self, text: str, member: Member, context: dict | None = None) -> ParsedIntent:
        from grove.modules.communication.prompts import INTENT_PARSE_PROMPT
        ctx = context or {}

        # Priority 1: Active dispatch session in private chat
        if ctx.get("has_active_dispatch") and ctx.get("chat_type") == "p2p":
            return ParsedIntent(intent=Intent.DISPATCH_NEGOTIATE, topic=text, confidence=0.95)

        try:
            response = await self.llm.chat(
                system_prompt=INTENT_PARSE_PROMPT,
                messages=[{"role": "user", "content": f"发送者: {member.name} (角色: {member.role})\n消息: {text}"}],
                max_tokens=256,
            )
            data = json.loads(response)
            return ParsedIntent(
                intent=data.get("intent", Intent.UNKNOWN),
                topic=data.get("topic", ""),
                confidence=data.get("confidence", 0.0),
                raw_response=response,
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Intent parse failed: %s", exc)
            return ParsedIntent(intent=Intent.UNKNOWN, raw_response=str(exc))
```

- [ ] **Step 3: Update prompts.py with new intents**

In `grove/modules/communication/prompts.py`, add these lines to `INTENT_PARSE_PROMPT` (after `query_module_status` line 15, before `general_chat`):

```
- scan_project: 请求扫描项目或生成项目文档（如"扫描项目"、"生成项目文档"、"更新项目文档"）
- query_project_overview: 查询项目进度总览（如"项目总览"、"项目进度"、"项目进度报告"）
```

And add module name mappings:

```
- 项目扫描 = project_scanner
- 项目总览 = project_overview
- 每日任务 = morning_dispatch
```

- [ ] **Step 4: Update handler.py with new intent routes and storage dependency**

In `grove/modules/communication/handler.py`:

Add imports:
```python
from datetime import datetime, timezone
from grove.core.storage import Storage
```

Update `__init__` to accept `storage`:
```python
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, registry=None, storage: Storage | None = None):
        ...
        self._storage = storage
```

Update `on_lark_message` to build context and pass it to parse:
```python
    @subscribe(EventType.LARK_MESSAGE)
    async def on_lark_message(self, event: Event) -> None:
        if event.member is None:
            logger.debug("Ignoring message from unknown member")
            return

        text = event.payload.get("text", "")
        chat_id = event.payload.get("chat_id", "")

        # Build context for intent parser
        context = {"chat_type": event.payload.get("chat_type", "group")}
        if self._storage and event.member:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            dispatch_path = f"memory/dispatch/{today}/{event.member.github}.json"
            if self._storage.exists(dispatch_path):
                try:
                    session = self._storage.read_json(dispatch_path)
                    context["has_active_dispatch"] = session.get("status") != "confirmed"
                except Exception:
                    context["has_active_dispatch"] = False

        parsed = await self._intent_parser.parse(text, event.member, context=context)
        logger.info("Intent: %s (%.2f) from %s: '%s'",
                    parsed.intent, parsed.confidence, event.member.name, text[:50])
        ...
```

Add new intent routes in the if-elif chain (after `CONTINUE_CONVERSATION`):

```python
        elif parsed.intent == Intent.SCAN_PROJECT:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_SCAN_PROJECT, source="internal",
                payload={"chat_id": chat_id}, member=event.member,
            ))
        elif parsed.intent == Intent.QUERY_PROJECT_OVERVIEW:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_PROJECT_OVERVIEW, source="internal",
                payload={"chat_id": chat_id}, member=event.member,
            ))
        elif parsed.intent == Intent.DISPATCH_NEGOTIATE:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_DISPATCH_NEGOTIATE, source="internal",
                payload={"text": text, "chat_id": chat_id,
                         "sender_id": event.payload.get("sender_id", "")},
                member=event.member,
            ))
```

Update `MODULE_DISPLAY` dicts (both at lines 104 and 124) to include new modules:
```python
            "project_scanner": "项目扫描", "project_overview": "项目总览",
            "morning_dispatch": "每日任务",
```

- [ ] **Step 5: Update main.py to pass storage to CommunicationModule**

In `grove/main.py`, update the CommunicationModule constructor (line 109-112):

```python
    communication = CommunicationModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, registry=registry,
        storage=storage,
    )
```

- [ ] **Step 6: Run communication tests**

Run: `python -m pytest tests/test_modules/test_communication/ -v`

- [ ] **Step 7: Commit**

```bash
git add grove/modules/communication/ grove/main.py tests/test_modules/test_communication/
git commit -m "feat: add scan_project, query_project_overview, dispatch_negotiate intents"
```

---

## Task 7: Lark Card Builders (Project Overview + Dispatch Summary)

**Files:**
- Modify: `grove/integrations/lark/cards.py`
- Test: `tests/test_integrations/test_lark_cards.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_integrations/test_lark_cards.py — append
from grove.integrations.lark.cards import build_project_overview_card, build_dispatch_summary_card

class TestProjectOverviewCard:
    def test_builds_valid_card(self):
        card = build_project_overview_card(
            date="2026-03-23",
            health="🟢 正常",
            milestones=[{"title": "v1.0", "progress_pct": 80, "open": 2, "closed": 8}],
            trends={"closed_issues": 12, "merged_prs": 8, "new_issues": 5},
            prd_completion={"done": 6, "in_progress": 3, "not_started": 1},
            risks=["v1.0 可能延期"],
            suggestions="建议加速前端开发",
        )
        assert card["header"]["title"]["content"] == "📊 项目进度总览 — 2026-03-23"
        assert len(card["elements"]) > 0

class TestDispatchSummaryCard:
    def test_builds_valid_card(self):
        card = build_dispatch_summary_card(
            date="2026-03-23",
            member_tasks=[
                {"name": "Alice", "tasks": [{"priority": "P0", "issue_number": 201, "title": "API"}], "confirmed": True},
                {"name": "Bob", "tasks": [{"priority": "P1", "issue_number": 202, "title": "UI"}], "confirmed": False},
            ],
        )
        assert card["header"]["title"]["content"] == "🌳 今日团队任务 — 2026-03-23"
        content = card["elements"][0]["text"]["content"]
        assert "Alice" in content
        assert "⏰" in content  # Bob not confirmed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_integrations/test_lark_cards.py::TestProjectOverviewCard -v`

- [ ] **Step 3: Implement card builders**

Append to `grove/integrations/lark/cards.py` after `build_notification_card`:

```python
def build_project_overview_card(
    date: str, health: str, milestones: list[dict],
    trends: dict, prd_completion: dict | None,
    risks: list[str], suggestions: str,
) -> dict:
    ms_lines = [
        f"**{ms['title']}** {'█' * (ms['progress_pct'] // 10)}{'░' * (10 - ms['progress_pct'] // 10)} "
        f"{ms['progress_pct']}% ({ms['closed']}/{ms['closed'] + ms['open']})"
        for ms in milestones
    ]
    ms_text = "\n".join(ms_lines) if ms_lines else "暂无里程碑"

    trend_text = (
        f"完成 Issues: {trends.get('closed_issues', 0)}\n"
        f"合并 PR: {trends.get('merged_prs', 0)}\n"
        f"新增 Issues: {trends.get('new_issues', 0)}"
    )

    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**健康度：** {health}"}},
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**📌 里程碑**\n{ms_text}"}},
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**📈 本周趋势（7 天）**\n{trend_text}"}},
    ]

    if prd_completion:
        prd_text = (
            f"✅ 已完成 {prd_completion.get('done', 0)}\n"
            f"🔄 进行中 {prd_completion.get('in_progress', 0)}\n"
            f"⬚ 未开始 {prd_completion.get('not_started', 0)}"
        )
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**📋 PRD 完成度**\n{prd_text}"}})

    risk_text = "\n".join(f"⚠️ {r}" for r in risks) if risks else "✅ 无风险"
    elements.append({"tag": "hr"})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**风险**\n{risk_text}"}})
    elements.append({"tag": "hr"})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**💡 建议**\n{suggestions}"}})

    return {
        "header": {"title": {"tag": "plain_text", "content": f"📊 项目进度总览 — {date}"}, "template": "purple"},
        "elements": elements,
    }


def build_dispatch_summary_card(date: str, member_tasks: list[dict]) -> dict:
    lines = []
    for mt in member_tasks:
        status = "✅" if mt.get("confirmed") else "⏰ 未确认"
        lines.append(f"**👤 {mt['name']}** {status}")
        for t in mt.get("tasks", []):
            priority_icon = "🔴" if t["priority"] == "P0" else "🟡" if t["priority"] == "P1" else "🔵"
            lines.append(f"  · {priority_icon} #{t['issue_number']} {t['title']}")
        lines.append("")

    return {
        "header": {"title": {"tag": "plain_text", "content": f"🌳 今日团队任务 — {date}"}, "template": "green"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}},
        ],
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_integrations/test_lark_cards.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/integrations/lark/cards.py tests/test_integrations/test_lark_cards.py
git commit -m "feat: add project overview and dispatch summary Lark card builders"
```

---

## Task 8: Project Scanner Module

**Files:**
- Create: `grove/modules/project_scanner/__init__.py`
- Create: `grove/modules/project_scanner/prompts.py`
- Create: `grove/modules/project_scanner/analyzer.py`
- Create: `grove/modules/project_scanner/handler.py`
- Test: `tests/test_modules/test_project_scanner/__init__.py`
- Test: `tests/test_modules/test_project_scanner/test_handler.py`

This is a large task. Implement in sub-steps: prompts → analyzer → handler → tests.

- [ ] **Step 1: Create package init and prompts**

```python
# grove/modules/project_scanner/__init__.py — empty
```

```python
# grove/modules/project_scanner/prompts.py
"""Prompt templates for project scanning and reverse PRD generation."""

ARCHITECTURE_ANALYSIS_PROMPT = """\
你是一位资深架构师。根据以下仓库信息，分析项目的技术架构。

目录结构：
{repo_tree}

依赖文件：
{dependencies}

README：
{readme}

请输出：
1. 技术栈（语言、框架、数据库等）
2. 模块划分（每个主要目录的职责）
3. 层次架构（如 MVC、微服务、事件驱动等）

用中文，简洁专业，不超过 500 字。
"""

FEATURE_ANALYSIS_PROMPT = """\
你是一位产品经理。根据以下信息，逆向推导项目已实现的功能。

技术架构分析：
{architecture}

目录结构：
{repo_tree}

近期 Commit 摘要（按类型聚合）：
{commit_summary}

GitHub Issues 标题列表：
{issues}

请输出 JSON 数组，每个元素为：
{{"name": "功能名", "status": "completed|in_progress|planned", "description": "一句话描述"}}

只输出 JSON，不要其他内容。
"""

REVERSE_PRD_PROMPT = """\
你是一位产品经理。根据以下信息，生成一份项目 PRD 文档。

项目架构：
{architecture}

已实现功能：
{features}

GitHub Milestones：
{milestones}

请生成标准 PRD 格式的 Markdown 文档，包含：
1. 概述（项目背景、目标用户）
2. 已实现功能（按模块分类）
3. 待开发功能（从 Issues 和 Milestones 推断，标注"由 Grove 逆向推导，待团队确认"）
4. 技术架构
5. 里程碑与排期

重要：这是逆向生成的草稿，在文档顶部标注：
> ⚠️ 本文档由 Grove 自动逆向生成，请团队审阅并补充「未来规划」部分。

用中文。
"""
```

- [ ] **Step 2: Create analyzer.py**

```python
# grove/modules/project_scanner/analyzer.py
"""LLM-based project analysis: architecture, features, PRD."""
import json
import logging

from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.prompts import (
    ARCHITECTURE_ANALYSIS_PROMPT,
    FEATURE_ANALYSIS_PROMPT,
    REVERSE_PRD_PROMPT,
)

logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def analyze_architecture(
        self, repo_tree: str, dependencies: str, readme: str,
    ) -> str:
        prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(
            repo_tree=repo_tree[:3000], dependencies=dependencies[:2000], readme=readme[:2000],
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请分析架构。"}],
            max_tokens=1024,
        )

    async def analyze_features(
        self, architecture: str, repo_tree: str,
        commit_summary: str, issues: str,
    ) -> list[dict]:
        prompt = FEATURE_ANALYSIS_PROMPT.format(
            architecture=architecture[:1500], repo_tree=repo_tree[:2000],
            commit_summary=commit_summary[:2000], issues=issues[:2000],
        )
        response = await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请逆向推导功能列表。"}],
            max_tokens=2048,
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Feature analysis returned non-JSON, retrying once")
            response = await self.llm.chat(
                system_prompt=prompt + "\n\n重要：只输出 JSON 数组！",
                messages=[{"role": "user", "content": "请逆向推导功能列表。只输出 JSON。"}],
                max_tokens=2048,
            )
            return json.loads(response)

    async def generate_reverse_prd(
        self, architecture: str, features: list[dict], milestones: str,
    ) -> str:
        features_text = "\n".join(
            f"- {f['name']}（{f['status']}）：{f.get('description', '')}"
            for f in features
        )
        prompt = REVERSE_PRD_PROMPT.format(
            architecture=architecture, features=features_text, milestones=milestones,
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请生成逆向 PRD。"}],
            max_tokens=4096,
        )
```

- [ ] **Step 3: Create handler.py**

```python
# grove/modules/project_scanner/handler.py
"""Project Scanner module — scan repo, generate reverse PRD + dev status doc."""
import asyncio
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.analyzer import ProjectAnalyzer
from grove.utils.commit_classifier import classify_commit

logger = logging.getLogger(__name__)


class ProjectScannerModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._analyzer = ProjectAnalyzer(llm)
        self._scan_lock = asyncio.Lock()

    @subscribe(EventType.INTERNAL_SCAN_PROJECT)
    async def on_scan_project(self, event: Event) -> None:
        chat_id = event.payload.get("chat_id", self.config.lark.chat_id)

        if self._scan_lock.locked():
            await self.lark.send_text(chat_id, "扫描正在进行中，请稍候。")
            return

        async with self._scan_lock:
            await self.lark.send_text(chat_id, "正在扫描项目，请稍候...")
            try:
                await self._run_scan(chat_id)
            except Exception:
                logger.exception("Project scan failed")
                await self.lark.send_text(chat_id, "项目扫描失败，请稍后重试。")

    async def _run_scan(self, chat_id: str) -> None:
        repo = self.config.project.repo

        # Step 1: Parallel data collection
        tree = self.github.get_repo_tree(repo)
        readme = self._safe_read_file(repo, "README.md")
        deps = self._collect_dependencies(repo)
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        commits = self.github.list_recent_commits_detailed(repo, since=since, max_commits=500)
        issues = self.github.list_issues(repo, state="all")
        milestones = self.github.list_milestones(repo)

        # Check for empty repo
        if not tree and not commits and not issues:
            await self.lark.send_text(chat_id,
                "项目数据不足，无法生成文档。请至少提交一些代码和 README 后再试。")
            return

        # Format data for LLM
        tree_text = self._format_tree(tree)
        commit_summary = await self._summarize_commits(commits)
        issues_text = "\n".join(f"- #{i.number} {i.title} [{i.state}]" for i in issues[:100])
        milestones_text = "\n".join(
            f"- {m['title']}: {m['closed_issues']}/{m['open_issues'] + m['closed_issues']} "
            f"(due: {m.get('due_on', 'N/A')})"
            for m in milestones
        )

        # Step 2: LLM analysis (sequential, each depends on previous)
        architecture = await self._analyzer.analyze_architecture(tree_text, deps, readme)

        try:
            features = await self._analyzer.analyze_features(
                architecture, tree_text, commit_summary, issues_text)
        except Exception:
            logger.exception("Feature analysis failed")
            await self.lark.send_text(chat_id,
                f"架构分析完成，但功能推导失败。\n\n**架构分析：**\n{architecture}")
            return

        try:
            prd_content = await self._analyzer.generate_reverse_prd(
                architecture, features, milestones_text)
        except Exception:
            logger.exception("PRD generation failed")
            features_text = "\n".join(f"- {f['name']}: {f.get('description', '')}" for f in features)
            await self.lark.send_text(chat_id,
                f"功能推导完成，但 PRD 生成失败。\n\n**已识别功能：**\n{features_text}")
            return

        # Step 3: Generate dev status document
        dev_status = self._build_dev_status(architecture, features, commits, milestones)

        # Step 4: Output documents
        prd_doc_id = None
        try:
            existing_doc_id = self._get_existing_doc_id()
            if existing_doc_id:
                await self.lark.update_doc(existing_doc_id, prd_content)
                prd_doc_id = existing_doc_id
            else:
                prd_doc_id = await self.lark.create_doc(
                    self.config.lark.space_id,
                    f"[{self.config.project.name}] PRD（逆向生成草稿）",
                    prd_content,
                )
                self._save_doc_id(prd_doc_id)
        except Exception:
            logger.exception("Lark doc creation failed")

        try:
            self.github.write_file(repo, "docs/prd/project-prd-draft.md", prd_content,
                                   "docs: update reverse-engineered PRD")
            self.github.write_file(repo, "docs/development-status.md", dev_status,
                                   "docs: update development status")
        except Exception:
            logger.exception("GitHub file write failed")

        # Save scan metadata
        self._storage.write_json("memory/project-scan/latest-scan.json", {
            "date": datetime.now(timezone.utc).isoformat(),
            "commit_count": len(commits),
            "issue_count": len(issues),
            "feature_count": len(features),
        })

        # Notify
        msg = "项目扫描完成！已生成两份文档：\n📋 逆向 PRD 草稿（请团队审阅补充）\n📄 开发状态文档"
        if prd_doc_id:
            msg += f"\n\n飞书文档已{'更新' if self._get_existing_doc_id() else '创建'}"
        await self.lark.send_text(chat_id, msg)

    def _safe_read_file(self, repo: str, path: str) -> str:
        try:
            return self.github.read_file(repo, path)
        except Exception:
            return ""

    def _collect_dependencies(self, repo: str) -> str:
        parts = []
        for dep_file in ["requirements.txt", "package.json", "go.mod", "Cargo.toml"]:
            content = self._safe_read_file(repo, dep_file)
            if content:
                parts.append(f"=== {dep_file} ===\n{content[:1000]}")
        return "\n\n".join(parts) if parts else "No dependency files found."

    def _format_tree(self, tree: list[dict], max_depth: int = 3) -> str:
        lines = []
        for item in tree:
            depth = item["path"].count("/")
            if depth <= max_depth and item["type"] == "tree":
                lines.append(f"{'  ' * depth}📁 {item['path'].split('/')[-1]}/")
            elif depth <= max_depth and item["type"] == "blob":
                lines.append(f"{'  ' * depth}📄 {item['path'].split('/')[-1]}")
        return "\n".join(lines[:200])

    async def _summarize_commits(self, commits: list[dict]) -> str:
        type_counts: dict[str, int] = Counter()
        for c in commits:
            files = [f["filename"] for f in c.get("files", [])]
            ctype = await classify_commit(c["message"], files, llm=self.llm)
            type_counts[ctype] += 1
        lines = [f"- {ctype}: {count} commits" for ctype, count in type_counts.items()]
        return "\n".join(lines)

    def _build_dev_status(self, architecture: str, features: list[dict],
                          commits: list[dict], milestones: list[dict]) -> str:
        lines = [
            "# 开发状态文档\n",
            f"> 自动生成于 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n",
            "## 技术架构\n", architecture, "\n",
            "## 已实现功能\n",
        ]
        for f in features:
            status_icon = {"completed": "✅", "in_progress": "🔄", "planned": "⬚"}.get(f.get("status"), "❓")
            lines.append(f"- {status_icon} **{f['name']}**: {f.get('description', '')}")
        lines.append(f"\n## 近期开发活动\n\n最近 90 天共 {len(commits)} 次提交。\n")
        if milestones:
            lines.append("## 里程碑\n")
            for m in milestones:
                total = m["open_issues"] + m["closed_issues"]
                pct = round(m["closed_issues"] / total * 100) if total > 0 else 0
                lines.append(f"- **{m['title']}** — {pct}% ({m['closed_issues']}/{total})")
        return "\n".join(lines)

    def _get_existing_doc_id(self) -> str | None:
        try:
            data = self._storage.read_yaml("memory/project-scan/reverse-prd-doc-id.yml")
            return data.get("doc_id")
        except FileNotFoundError:
            return None

    def _save_doc_id(self, doc_id: str) -> None:
        self._storage.write_yaml("memory/project-scan/reverse-prd-doc-id.yml", {"doc_id": doc_id})
```

- [ ] **Step 4: Write tests**

```python
# tests/test_modules/test_project_scanner/__init__.py — empty

# tests/test_modules/test_project_scanner/test_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from grove.modules.project_scanner.handler import ProjectScannerModule

@pytest.fixture
def scanner_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    lark = AsyncMock()
    github = MagicMock()
    config = MagicMock()
    config.project.repo = "org/repo"
    config.project.name = "TestProject"
    config.lark.chat_id = "oc_test"
    config.lark.space_id = "spc_test"
    storage = MagicMock()
    storage.exists.return_value = False
    storage.read_yaml.side_effect = FileNotFoundError
    return ProjectScannerModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config, storage=storage,
    )

class TestProjectScanner:
    @pytest.mark.asyncio
    async def test_empty_repo_sends_message(self, scanner_module):
        scanner_module.github.get_repo_tree.return_value = []
        scanner_module.github.list_recent_commits_detailed.return_value = []
        scanner_module.github.list_issues.return_value = []
        scanner_module.github.list_milestones.return_value = []
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await scanner_module.on_scan_project(event)
        calls = scanner_module.lark.send_text.call_args_list
        assert any("数据不足" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_concurrent_scan_rejected(self, scanner_module):
        """Second scan while first is running should be rejected."""
        import asyncio
        scanner_module.github.get_repo_tree.return_value = [{"path": "main.py", "type": "blob", "size": 100}]
        scanner_module.github.list_recent_commits_detailed.return_value = []
        scanner_module.github.list_issues.return_value = []
        scanner_module.github.list_milestones.return_value = []
        scanner_module.github.read_file.side_effect = Exception("not found")
        scanner_module._analyzer.analyze_architecture = AsyncMock(side_effect=lambda *a: asyncio.sleep(0.1) or "arch")

        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}

        # Acquire lock manually to simulate in-progress scan
        await scanner_module._scan_lock.acquire()
        await scanner_module.on_scan_project(event)
        calls = scanner_module.lark.send_text.call_args_list
        assert any("正在进行中" in str(c) for c in calls)
        scanner_module._scan_lock.release()
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_modules/test_project_scanner/ -v`

- [ ] **Step 6: Commit**

```bash
git add grove/modules/project_scanner/ tests/test_modules/test_project_scanner/
git commit -m "feat: add Project Scanner module with reverse PRD generation"
```

---

## Task 9: Project Overview Report Module

**Files:**
- Create: `grove/modules/project_overview/__init__.py`
- Create: `grove/modules/project_overview/prompts.py`
- Create: `grove/modules/project_overview/collectors.py`
- Create: `grove/modules/project_overview/handler.py`
- Test: `tests/test_modules/test_project_overview/__init__.py`
- Test: `tests/test_modules/test_project_overview/test_handler.py`

- [ ] **Step 1: Create package init and prompts**

```python
# grove/modules/project_overview/__init__.py — empty

# grove/modules/project_overview/prompts.py
"""Prompt templates for project overview report."""

OVERVIEW_ANALYSIS_PROMPT = """\
你是 Grove，AI 产品经理。分析以下项目数据，给出项目健康度评估。

Issues 完成率: {completion_rate}%
本周关闭 Issues: {closed_this_week}
本周新增 Issues: {new_this_week}
里程碑:
{milestones}

PRD 完成度:
{prd_completion}

请输出 JSON：
{{
  "health": "🟢 正常" | "🟡 需关注" | "🔴 风险",
  "risks": ["风险1", "风险2", "风险3"],
  "suggestions": "2-3条建议"
}}
只输出 JSON。
"""
```

- [ ] **Step 2: Create collectors.py**

```python
# grove/modules/project_overview/collectors.py
"""Data collection for project overview reports."""
import logging
from datetime import datetime, timedelta, timezone

from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient

logger = logging.getLogger(__name__)


class OverviewDataCollector:
    def __init__(self, github: GitHubClient, repo: str, storage: Storage):
        self.github = github
        self.repo = repo
        self._storage = storage

    def collect(self) -> dict:
        all_issues = self.github.list_issues(self.repo, state="all")
        open_issues = [i for i in all_issues if i.state == "open"]
        closed_issues = [i for i in all_issues if i.state == "closed"]
        total = len(all_issues)
        completion_rate = round(len(closed_issues) / total * 100) if total > 0 else 0

        since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent_commits = self.github.list_recent_commits_detailed(
            self.repo, since=since_7d, max_commits=200)

        open_prs = self.github.list_open_prs(self.repo)
        milestones = self.github.list_milestones(self.repo)

        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_issues": total,
            "open_issues": len(open_issues),
            "closed_issues": len(closed_issues),
            "completion_rate": completion_rate,
            "recent_commits": recent_commits,
            "open_prs": open_prs,
            "milestones": milestones,
        }

    def load_7day_snapshots(self) -> list[dict]:
        snapshots = []
        for i in range(7):
            date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            try:
                snap = self._storage.read_json(f"memory/snapshots/{date}.json")
                snapshots.append(snap)
            except FileNotFoundError:
                continue
        return snapshots

    def compute_trends(self, snapshots: list[dict]) -> dict:
        if not snapshots:
            return {"closed_issues": 0, "merged_prs": 0, "new_issues": 0}
        total_commits = sum(s.get("total_commits", 0) for s in snapshots)
        return {
            "closed_issues": total_commits,
            "merged_prs": len(snapshots),
            "new_issues": 0,
        }
```

- [ ] **Step 3: Create handler.py**

```python
# grove/modules/project_overview/handler.py
"""Project Overview Report module — management-level project status."""
import json
import logging

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_project_overview_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.project_overview.collectors import OverviewDataCollector
from grove.modules.project_overview.prompts import OVERVIEW_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


class ProjectOverviewModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.config = config
        self._storage = storage
        self._collector = OverviewDataCollector(github, config.project.repo, storage)

    @subscribe(EventType.CRON_PROJECT_OVERVIEW)
    @subscribe(EventType.INTERNAL_PROJECT_OVERVIEW)
    async def on_project_overview(self, event: Event) -> None:
        chat_id = event.payload.get("chat_id", self.config.lark.chat_id)
        logger.info("Generating project overview report...")

        data = self._collector.collect()
        snapshots = self._collector.load_7day_snapshots()
        trends = self._collector.compute_trends(snapshots)

        # PRD completion check
        prd_completion = await self._check_prd_completion(data)

        # LLM analysis
        milestones_text = "\n".join(
            f"- {m['title']}: {m['closed_issues']}/{m['open_issues'] + m['closed_issues']}"
            f" (due: {m.get('due_on', 'N/A')})"
            for m in data["milestones"]
        ) or "暂无"

        prd_text = "未生成逆向 PRD"
        if prd_completion:
            prd_text = (
                f"已完成: {prd_completion.get('done', 0)}, "
                f"进行中: {prd_completion.get('in_progress', 0)}, "
                f"未开始: {prd_completion.get('not_started', 0)}"
            )

        analysis = await self._analyze(data, milestones_text, prd_text)

        # Build milestone summary for card
        ms_summary = [
            {
                "title": m["title"],
                "progress_pct": round(m["closed_issues"] / max(m["open_issues"] + m["closed_issues"], 1) * 100),
                "open": m["open_issues"],
                "closed": m["closed_issues"],
            }
            for m in data["milestones"]
        ]

        # Send card
        card = build_project_overview_card(
            date=data["date"], health=analysis.get("health", "🟡 需关注"),
            milestones=ms_summary, trends=trends,
            prd_completion=prd_completion,
            risks=analysis.get("risks", []),
            suggestions=analysis.get("suggestions", ""),
        )
        await self.lark.send_card(chat_id, card)

        # Create GitHub issue
        report_body = self._build_report_markdown(data, trends, prd_completion, analysis)
        self._collector.github.create_issue(
            repo=self.config.project.repo,
            title=f"📊 项目进度总览 — {data['date']}",
            body=report_body, labels=["project-overview"],
        )

        # Save snapshot
        self._storage.write_json(
            f"memory/snapshots/{data['date']}-overview.json",
            {**data, "trends": trends, "prd_completion": prd_completion, "analysis": analysis},
        )
        logger.info("Project overview report sent")

    async def _check_prd_completion(self, data: dict) -> dict | None:
        try:
            doc_info = self._storage.read_yaml("memory/project-scan/reverse-prd-doc-id.yml")
            doc_id = doc_info.get("doc_id")
            if not doc_id:
                return None
            prd_content = await self.lark.read_doc(doc_id)
            # Simple heuristic: count features mentioned in PRD vs issues
            # A full implementation would parse the PRD and match against issues
            return {"done": data["closed_issues"], "in_progress": data["open_issues"],
                    "not_started": 0}
        except (FileNotFoundError, Exception):
            return None

    async def _analyze(self, data: dict, milestones_text: str, prd_text: str) -> dict:
        prompt = OVERVIEW_ANALYSIS_PROMPT.format(
            completion_rate=data["completion_rate"],
            closed_this_week=len(data.get("recent_commits", [])),
            new_this_week=data["open_issues"],
            milestones=milestones_text,
            prd_completion=prd_text,
        )
        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请分析。"}],
                max_tokens=1024,
            )
            return json.loads(response)
        except Exception:
            logger.warning("Overview analysis LLM call failed")
            return {"health": "🟡 需关注", "risks": [], "suggestions": "LLM 分析失败，请手动检查。"}

    def _build_report_markdown(self, data, trends, prd_completion, analysis) -> str:
        lines = [
            f"# 📊 项目进度总览 — {data['date']}\n",
            f"**健康度：** {analysis.get('health', 'N/A')}\n",
            f"## 概览\n",
            f"- Issues 完成率: {data['completion_rate']}% ({data['closed_issues']}/{data['total_issues']})",
            f"- 开放 Issues: {data['open_issues']}",
            f"- 开放 PRs: {len(data['open_prs'])}\n",
        ]
        if data["milestones"]:
            lines.append("## 里程碑\n")
            for m in data["milestones"]:
                total = m["open_issues"] + m["closed_issues"]
                pct = round(m["closed_issues"] / max(total, 1) * 100)
                lines.append(f"- **{m['title']}** — {pct}% ({m['closed_issues']}/{total})")
        if analysis.get("risks"):
            lines.append("\n## 风险\n")
            for r in analysis["risks"]:
                lines.append(f"- ⚠️ {r}")
        lines.append(f"\n## 建议\n\n{analysis.get('suggestions', '')}")
        return "\n".join(lines)
```

- [ ] **Step 4: Write tests**

```python
# tests/test_modules/test_project_overview/__init__.py — empty

# tests/test_modules/test_project_overview/test_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from grove.modules.project_overview.handler import ProjectOverviewModule

@pytest.fixture
def overview_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    llm.chat.return_value = '{"health": "🟢 正常", "risks": [], "suggestions": "继续保持"}'
    lark = AsyncMock()
    github = MagicMock()
    github.list_issues.return_value = []
    github.list_recent_commits_detailed.return_value = []
    github.list_open_prs.return_value = []
    github.list_milestones.return_value = []
    config = MagicMock()
    config.project.repo = "org/repo"
    config.lark.chat_id = "oc_test"
    storage = MagicMock()
    storage.read_json.side_effect = FileNotFoundError
    storage.read_yaml.side_effect = FileNotFoundError
    return ProjectOverviewModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config, storage=storage,
    )

class TestProjectOverview:
    @pytest.mark.asyncio
    async def test_generates_report(self, overview_module):
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await overview_module.on_project_overview(event)
        overview_module.lark.send_card.assert_called_once()
        overview_module._collector.github.create_issue.assert_called_once()
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_modules/test_project_overview/ -v`

- [ ] **Step 6: Commit**

```bash
git add grove/modules/project_overview/ tests/test_modules/test_project_overview/
git commit -m "feat: add Project Overview Report module with management-level reporting"
```

---

## Task 10: Morning Task Dispatch Module

**Files:**
- Create: `grove/modules/morning_dispatch/__init__.py`
- Create: `grove/modules/morning_dispatch/prompts.py`
- Create: `grove/modules/morning_dispatch/planner.py`
- Create: `grove/modules/morning_dispatch/negotiator.py`
- Create: `grove/modules/morning_dispatch/handler.py`
- Test: `tests/test_modules/test_morning_dispatch/__init__.py`
- Test: `tests/test_modules/test_morning_dispatch/test_handler.py`

This is the most complex module. Build bottom-up: prompts → planner → negotiator → handler.

- [ ] **Step 1: Create package init and prompts**

```python
# grove/modules/morning_dispatch/__init__.py — empty

# grove/modules/morning_dispatch/prompts.py
"""Prompt templates for morning task dispatch."""

TASK_PLAN_PROMPT = """\
你是 Grove，AI 产品经理。为团队成员规划今日工作任务。

成员信息：
- 姓名: {member_name}
- 角色: {member_role}
- 技能: {member_skills}
- 当前负载: {current_load} 个进行中任务

昨日该成员的 commit 记录：
{yesterday_commits}

待办 Issues（按优先级排序）：
{open_issues}

里程碑截止：
{milestones}

请为该成员选择 1-3 个今日应重点推进的任务，输出 JSON：
{{
  "tasks": [
    {{"issue_number": 123, "title": "...", "reason": "选择理由"}}
  ],
  "summary": "一句话总结今日工作重点"
}}
只输出 JSON。
"""

NEGOTIATE_PROMPT = """\
你是 Grove，AI 产品经理。成员正在协商调整今日任务。

当前任务列表：
{current_tasks}

成员消息：
{message}

判断成员的意图并输出 JSON：
{{
  "action": "confirm" | "add" | "remove" | "replace" | "question",
  "issue_number": 123,
  "detail": "说明"
}}
只输出 JSON。
"""
```

- [ ] **Step 2: Create planner.py**

```python
# grove/modules/morning_dispatch/planner.py
"""LLM-based per-member daily task planning."""
import json
import logging

from grove.core.events import Member
from grove.integrations.llm.client import LLMClient
from grove.modules.morning_dispatch.prompts import TASK_PLAN_PROMPT

logger = logging.getLogger(__name__)


class TaskPlanner:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def plan_for_member(
        self, member: Member, current_load: int,
        yesterday_commits: str, open_issues: str, milestones: str,
    ) -> dict:
        prompt = TASK_PLAN_PROMPT.format(
            member_name=member.name, member_role=member.role,
            member_skills=", ".join(member.skills),
            current_load=current_load,
            yesterday_commits=yesterday_commits or "无",
            open_issues=open_issues, milestones=milestones,
        )
        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请规划今日任务。"}],
                max_tokens=1024,
            )
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Task plan LLM returned non-JSON for %s, retrying", member.name)
            try:
                response = await self.llm.chat(
                    system_prompt=prompt + "\n重要：只输出 JSON！",
                    messages=[{"role": "user", "content": "请规划今日任务。只输出 JSON。"}],
                    max_tokens=1024,
                )
                return json.loads(response)
            except Exception:
                logger.exception("Task plan failed for %s", member.name)
                return {"tasks": [], "summary": "任务生成失败"}
        except Exception:
            logger.exception("Task plan failed for %s", member.name)
            return {"tasks": [], "summary": "任务生成失败"}
```

- [ ] **Step 3: Create negotiator.py**

```python
# grove/modules/morning_dispatch/negotiator.py
"""Parse member replies during task negotiation."""
import json
import logging

from grove.integrations.llm.client import LLMClient
from grove.modules.morning_dispatch.prompts import NEGOTIATE_PROMPT

logger = logging.getLogger(__name__)


class TaskNegotiator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def parse_reply(self, current_tasks: list[dict], message: str) -> dict:
        # Quick rule-based check for "confirm"
        clean = message.strip().lower()
        if clean in ("确认", "确定", "ok", "好的", "没问题", "可以"):
            return {"action": "confirm", "issue_number": None, "detail": ""}

        tasks_text = "\n".join(
            f"- #{t['issue_number']} {t['title']}" for t in current_tasks
        )
        prompt = NEGOTIATE_PROMPT.format(current_tasks=tasks_text, message=message)
        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": message}],
                max_tokens=256,
            )
            return json.loads(response)
        except Exception:
            logger.warning("Negotiate parse failed for: %s", message[:80])
            return {"action": "question", "issue_number": None, "detail": message}
```

- [ ] **Step 4: Create handler.py**

```python
# grove/modules/morning_dispatch/handler.py
"""Morning Task Dispatch — generate, negotiate, announce."""
import asyncio
import logging
from datetime import datetime, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_dispatch_summary_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.morning_dispatch.negotiator import TaskNegotiator
from grove.modules.morning_dispatch.planner import TaskPlanner
from grove.modules.member.handler import MemberModule

logger = logging.getLogger(__name__)


class MorningDispatchModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage,
                 resolver: MemberResolver, member_module: MemberModule):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._resolver = resolver
        self._member_module = member_module
        self._planner = TaskPlanner(llm)
        self._negotiator = TaskNegotiator(llm)
        self._announce_lock = asyncio.Lock()
        self._deadline_task: asyncio.Task | None = None

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _session_path(self, date: str, github_username: str) -> str:
        return f"memory/dispatch/{date}/{github_username}.json"

    def _read_session(self, date: str, github_username: str) -> dict | None:
        try:
            return self._storage.read_json(self._session_path(date, github_username))
        except FileNotFoundError:
            return None

    def _write_session(self, date: str, github_username: str, session: dict) -> None:
        self._storage.write_json(self._session_path(date, github_username), session)

    def _already_announced(self, date: str) -> bool:
        try:
            meta = self._storage.read_json(f"memory/dispatch/{date}/_announced.json")
            return meta.get("announced", False)
        except FileNotFoundError:
            return False

    @subscribe(EventType.CRON_MORNING_DISPATCH)
    async def on_morning_dispatch(self, event: Event) -> None:
        logger.info("Morning dispatch triggered")
        date = self._today()
        repo = self.config.project.repo

        # Collect data
        issues = self.github.list_issues(repo, state="open")
        milestones = self.github.list_milestones(repo)

        if not issues:
            await self.lark.send_text(self.config.lark.chat_id,
                "当前无待办任务，今日无需派发。")
            return

        # Load yesterday snapshot for commit history
        from datetime import timedelta
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            snapshot = self._storage.read_json(f"memory/snapshots/{yesterday}.json")
        except FileNotFoundError:
            snapshot = {}

        milestones_text = "\n".join(
            f"- {m['title']}: due {m.get('due_on', 'N/A')}" for m in milestones
        ) or "无"

        issues_text = "\n".join(
            f"- #{i.number} [{', '.join(i.labels)}] {i.title}" for i in issues[:50]
        )

        # Generate plan for each member
        members = self._resolver.all()
        for member in members:
            load = self._member_module.get_load(member.github)
            commits_by_member = snapshot.get("commits_by_member", {})
            member_commits = f"{commits_by_member.get(member.github, 0)} commits yesterday"

            plan = await self._planner.plan_for_member(
                member=member, current_load=load,
                yesterday_commits=member_commits,
                open_issues=issues_text, milestones=milestones_text,
            )

            session = {
                "status": "pending",
                "tasks": plan.get("tasks", []),
                "summary": plan.get("summary", ""),
                "messages": [],
                "confirmed_at": None,
            }
            self._write_session(date, member.github, session)

            # Send private message
            if plan.get("tasks"):
                task_lines = []
                for i, t in enumerate(plan["tasks"], 1):
                    task_lines.append(f"{i}. #{t['issue_number']} {t['title']} — {t.get('reason', '')}")
                msg = (
                    f"早上好 {member.name}！以下是今日建议工作内容：\n\n"
                    + "\n".join(task_lines)
                    + "\n\n如需调整请直接告诉我，或回复「确认」。"
                )
            else:
                msg = (
                    f"早上好 {member.name}！任务生成失败，请手动查看 GitHub Issues。"
                )
            session["status"] = "negotiating"
            self._write_session(date, member.github, session)
            await self.lark.send_private(member.lark_id, msg)

        # Schedule deadline
        delay = self.config.dispatch.confirm_deadline_minutes * 60
        self._deadline_task = asyncio.create_task(self._schedule_deadline(date, delay))
        logger.info("Morning dispatch sent to %d members, deadline in %d min",
                    len(members), self.config.dispatch.confirm_deadline_minutes)

    @subscribe(EventType.INTERNAL_DISPATCH_NEGOTIATE)
    async def on_dispatch_negotiate(self, event: Event) -> None:
        if event.member is None:
            return
        date = self._today()
        session = self._read_session(date, event.member.github)

        if session is None or session.get("status") == "confirmed":
            await self.lark.send_private(event.member.lark_id,
                "今日任务已公示，如需调整请直接在群里沟通。")
            return

        text = event.payload.get("text", "")
        session.setdefault("messages", []).append({"role": "user", "content": text})

        # Check negotiate round limit
        max_rounds = self.config.dispatch.max_negotiate_rounds
        if len(session["messages"]) > max_rounds * 2:
            await self.lark.send_private(event.member.lark_id,
                "协商轮次已达上限，请回复「确认」完成确认。")
            return

        result = await self._negotiator.parse_reply(session.get("tasks", []), text)

        if result["action"] == "confirm":
            session["status"] = "confirmed"
            session["confirmed_at"] = datetime.now(timezone.utc).isoformat()
            self._write_session(date, event.member.github, session)
            await self.lark.send_private(event.member.lark_id, "✅ 今日任务已确认！")
            await self._check_all_confirmed(date)
        elif result["action"] == "remove":
            session["tasks"] = [
                t for t in session["tasks"]
                if t.get("issue_number") != result.get("issue_number")
            ]
            self._write_session(date, event.member.github, session)
            await self._send_updated_tasks(event.member, session)
        elif result["action"] == "add":
            session["tasks"].append({
                "issue_number": result.get("issue_number", 0),
                "title": result.get("detail", ""),
                "reason": "成员手动添加",
            })
            self._write_session(date, event.member.github, session)
            await self._send_updated_tasks(event.member, session)
        else:
            # question or unknown — echo back
            await self.lark.send_private(event.member.lark_id,
                "收到。如需调整任务请告诉我具体操作，或回复「确认」。")
            self._write_session(date, event.member.github, session)

    async def _send_updated_tasks(self, member, session) -> None:
        if not session["tasks"]:
            await self.lark.send_private(member.lark_id,
                "当前任务列表为空。请添加任务或回复「确认」。")
            return
        task_lines = [f"- #{t['issue_number']} {t['title']}" for t in session["tasks"]]
        await self.lark.send_private(member.lark_id,
            "已更新任务列表：\n" + "\n".join(task_lines) + "\n\n回复「确认」完成确认。")

    async def _check_all_confirmed(self, date: str) -> None:
        members = self._resolver.all()
        all_confirmed = True
        for m in members:
            session = self._read_session(date, m.github)
            if session and session.get("status") != "confirmed":
                all_confirmed = False
                break
        if all_confirmed:
            await self._announce_to_group(date, force=False)

    async def _schedule_deadline(self, date: str, delay_seconds: int) -> None:
        await asyncio.sleep(delay_seconds)
        if not self._already_announced(date):
            await self._announce_to_group(date, force=True)

    async def _announce_to_group(self, date: str, force: bool) -> None:
        async with self._announce_lock:
            if self._already_announced(date):
                return

            members = self._resolver.all()
            member_tasks = []
            for m in members:
                session = self._read_session(date, m.github)
                tasks = session.get("tasks", []) if session else []
                confirmed = session.get("status") == "confirmed" if session else False
                task_data = [
                    {"priority": "P0", "issue_number": t.get("issue_number", 0), "title": t.get("title", "")}
                    for t in tasks
                ]
                member_tasks.append({
                    "name": m.name, "tasks": task_data, "confirmed": confirmed,
                })

                # Notify unconfirmed members
                if force and not confirmed:
                    await self.lark.send_private(m.lark_id,
                        "你的今日任务已按建议方案公示，如需调整随时告诉我。")

            card = build_dispatch_summary_card(date=date, member_tasks=member_tasks)
            await self.lark.send_card(self.config.lark.chat_id, card)

            self._storage.write_json(f"memory/dispatch/{date}/_announced.json",
                {"announced": True, "date": datetime.now(timezone.utc).isoformat()})

            if self._deadline_task and not self._deadline_task.done():
                self._deadline_task.cancel()

            logger.info("Morning dispatch announced for %s", date)
```

- [ ] **Step 5: Write tests**

```python
# tests/test_modules/test_morning_dispatch/__init__.py — empty

# tests/test_modules/test_morning_dispatch/test_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from grove.core.events import Event, EventType, Member
from grove.modules.morning_dispatch.handler import MorningDispatchModule

@pytest.fixture
def dispatch_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    llm.chat.return_value = '{"tasks": [{"issue_number": 1, "title": "Task 1", "reason": "P0"}], "summary": "Do task 1"}'
    lark = AsyncMock()
    github = MagicMock()
    github.list_issues.return_value = [
        MagicMock(number=1, title="Task 1", state="open", labels=["P0"], body="", assignees=[]),
    ]
    github.list_milestones.return_value = []
    config = MagicMock()
    config.project.repo = "org/repo"
    config.lark.chat_id = "oc_test"
    config.dispatch.confirm_deadline_minutes = 75
    config.dispatch.max_negotiate_rounds = 10
    storage = MagicMock()
    storage.exists.return_value = False
    storage.read_json.side_effect = FileNotFoundError
    resolver = MagicMock()
    member = Member(name="Alice", github="alice", lark_id="ou_alice", role="backend", skills=["python"])
    resolver.all.return_value = [member]
    member_module = MagicMock()
    member_module.get_load.return_value = 0
    return MorningDispatchModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config,
        storage=storage, resolver=resolver, member_module=member_module,
    )

class TestMorningDispatch:
    @pytest.mark.asyncio
    async def test_no_issues_skips_dispatch(self, dispatch_module):
        dispatch_module.github.list_issues.return_value = []
        event = MagicMock()
        event.payload = {}
        await dispatch_module.on_morning_dispatch(event)
        dispatch_module.lark.send_text.assert_called_once()
        assert "无待办" in dispatch_module.lark.send_text.call_args[0][1]

    @pytest.mark.asyncio
    async def test_sends_private_message_to_members(self, dispatch_module):
        event = MagicMock()
        event.payload = {}
        await dispatch_module.on_morning_dispatch(event)
        dispatch_module.lark.send_private.assert_called()
        msg = dispatch_module.lark.send_private.call_args[0][1]
        assert "早上好" in msg

    @pytest.mark.asyncio
    async def test_confirm_marks_session(self, dispatch_module):
        date = dispatch_module._today()
        # Pre-create a session
        dispatch_module._write_session(date, "alice", {
            "status": "negotiating",
            "tasks": [{"issue_number": 1, "title": "Task 1"}],
            "messages": [],
            "confirmed_at": None,
        })
        # Make read_json return the session
        dispatch_module._storage.read_json.side_effect = None
        dispatch_module._storage.read_json.return_value = {
            "status": "negotiating",
            "tasks": [{"issue_number": 1, "title": "Task 1"}],
            "messages": [],
            "confirmed_at": None,
        }
        member = Member(name="Alice", github="alice", lark_id="ou_alice", role="backend")
        event = MagicMock()
        event.member = member
        event.payload = {"text": "确认", "chat_id": "p2p_chat"}
        await dispatch_module.on_dispatch_negotiate(event)
        # Check that send_private was called with confirmation
        calls = dispatch_module.lark.send_private.call_args_list
        assert any("确认" in str(c) for c in calls)
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_modules/test_morning_dispatch/ -v`

- [ ] **Step 7: Commit**

```bash
git add grove/modules/morning_dispatch/ tests/test_modules/test_morning_dispatch/
git commit -m "feat: add Morning Task Dispatch module with negotiation flow"
```

---

## Task 11: Wire Everything in main.py

**Files:**
- Modify: `grove/main.py`

- [ ] **Step 1: Add imports for new modules**

At the top of `grove/main.py`, after existing module imports (line 32), add:

```python
from grove.modules.project_scanner.handler import ProjectScannerModule
from grove.modules.project_overview.handler import ProjectOverviewModule
from grove.modules.morning_dispatch.handler import MorningDispatchModule
```

- [ ] **Step 2: Instantiate new modules in lifespan**

After `doc_sync` instantiation (around line 135), add:

```python
    project_scanner = ProjectScannerModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )
    project_overview = ProjectOverviewModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )
    morning_dispatch = MorningDispatchModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
        resolver=resolver, member_module=member_module,
    )
```

- [ ] **Step 3: Register new modules with registry**

After `registry.add("doc_sync", ...)` (line 144), add:

```python
    registry.add("project_scanner", project_scanner, enabled=effective_modules["project_scanner"])
    registry.add("project_overview", project_overview, enabled=effective_modules["project_overview"])
    registry.add("morning_dispatch", morning_dispatch, enabled=effective_modules["morning_dispatch"])
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`

- [ ] **Step 5: Run linter**

Run: `python -m ruff check grove/ tests/`

- [ ] **Step 6: Fix any lint issues**

- [ ] **Step 7: Commit**

```bash
git add grove/main.py
git commit -m "feat: wire project_scanner, project_overview, morning_dispatch into main.py"
```

---

## Task 12: Update conftest.py and Integration Test

**Files:**
- Modify: `tests/conftest.py`
- Modify: existing sample config

- [ ] **Step 1: Update sample_config_yml to include new fields**

In `tests/conftest.py`, add to the config YAML string (after `doc_drift_check: "09:00"`):

```yaml
  project_overview: "10:00"
  morning_dispatch: "09:15"

dispatch:
  confirm_deadline_minutes: 75
  max_negotiate_rounds: 10
```

- [ ] **Step 2: Add dispatch directory to grove_dir fixture**

Add after existing mkdir calls:

```python
    (grove / "memory" / "dispatch").mkdir()
    (grove / "memory" / "project-scan").mkdir()
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: update conftest with new config fields and directories"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest tests/ -v --tb=short`

- [ ] **Step 2: Run linter on all code**

Run: `python -m ruff check grove/ tests/ --fix`

- [ ] **Step 3: Verify import chain**

Run: `python -c "from grove.main import app; print('Import OK')"` (will fail if circular imports exist)

- [ ] **Step 4: Fix any remaining issues**

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "fix: resolve remaining lint and test issues from project management enhancement"
```
