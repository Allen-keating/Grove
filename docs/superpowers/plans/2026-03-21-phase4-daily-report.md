# Phase 4: 每日巡检与站会报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every morning at 09:00, Grove automatically collects project activity data (commits, PRs, Issues), analyzes progress vs milestones, detects risks, generates a report, pushes it to Lark as a rich card, and archives it as a GitHub Issue.

**Architecture:** New `daily_report/` module subscribes to `cron.daily_report` events (already emitted by APScheduler from Phase 1). It has three stages: (1) `collectors.py` gathers raw data from GitHub API, (2) `analyzer.py` computes progress, detects risks, and checks alignment, (3) `handler.py` orchestrates the flow and uses LLM to polish the report into natural language before sending to Lark and GitHub.

**Tech Stack:** Existing Grove infrastructure. GitHub API for data collection (`list_recent_commits`, `list_open_prs` — new methods). Lark cards for report display. LLM for report polishing.

**Spec:** `docs/superpowers/specs/2026-03-21-grove-architecture-design.md` (Sections 4.1, 8 Phase 4)

**Scope:** Phase 4 only (weeks 7-8). Depends on Phases 1-3.

**Verification criteria (from spec):**
- 每天 09:00 飞书群自动收到报告
- 报告包含成员动态、进度、风险项、建议
- 同时创建 GitHub Issue 归档
- 风险项自动 @相关人

---

## File Structure

```
grove/
├── integrations/github/
│   └── client.py                              # MODIFY: add list_recent_commits, list_open_prs
│
├── integrations/lark/
│   └── cards.py                               # MODIFY: add build_daily_report_card
│
├── modules/daily_report/
│   ├── __init__.py
│   ├── collectors.py                          # Data collection from GitHub API
│   ├── analyzer.py                            # Progress analysis + risk detection
│   ├── prompts.py                             # Prompt for LLM report polishing
│   └── handler.py                             # Event handler: cron.daily_report
│
├── main.py                                    # MODIFY: register daily_report module
│
└── tests/test_modules/test_daily_report/
    ├── __init__.py
    ├── test_collectors.py
    ├── test_analyzer.py
    └── test_handler.py
```

---

### Task 1: GitHub Client — Commit and PR Data Methods

**Files:**
- Modify: `grove/integrations/github/client.py`
- Modify: `grove/integrations/github/models.py`

- [ ] **Step 1: Add CommitData import and new methods to models/client**

Add to `grove/integrations/github/models.py` (already has `CommitData` from Phase 1 — verify it exists, add `PRData` if missing):

Verify existing models have `CommitData` and `PRData`. They should from Phase 1.

Add these methods to `grove/integrations/github/client.py`:

```python
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_recent_commits(self, repo: str, since: str, author: str | None = None) -> list:
        """List commits since a datetime string. Returns list of dicts."""
        from datetime import datetime
        gh = self._get_github()
        r = gh.get_repo(repo)
        kwargs = {"since": datetime.fromisoformat(since)}
        if author:
            kwargs["author"] = author
        commits = r.get_commits(**kwargs)
        return [
            {
                "sha": c.sha[:7],
                "message": c.commit.message.split("\n")[0],
                "author": c.commit.author.name,
                "date": c.commit.author.date.isoformat(),
            }
            for c in commits[:50]  # cap to avoid huge results
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_open_prs(self, repo: str) -> list:
        """List open PRs. Returns list of dicts."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        prs = r.get_pulls(state="open")
        return [
            {
                "number": pr.number,
                "title": pr.title,
                "author": pr.user.login,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "review_requested": bool(list(pr.get_review_requests()[0])),
            }
            for pr in prs[:20]
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_milestones(self, repo: str) -> list:
        """List open milestones. Returns list of dicts."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        milestones = r.get_milestones(state="open")
        return [
            {
                "number": m.number,
                "title": m.title,
                "due_on": m.due_on.isoformat() if m.due_on else None,
                "open_issues": m.open_issues,
                "closed_issues": m.closed_issues,
            }
            for m in milestones
        ]
```

- [ ] **Step 2: Commit**

```bash
git add grove/integrations/github/client.py
git commit -m "feat: GitHub client list_recent_commits, list_open_prs, list_milestones"
```

---

### Task 2: Data Collectors

**Files:**
- Create: `grove/modules/daily_report/__init__.py`
- Create: `grove/modules/daily_report/collectors.py`
- Test: `tests/test_modules/test_daily_report/test_collectors.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_daily_report/test_collectors.py
from unittest.mock import MagicMock
import pytest
from grove.modules.daily_report.collectors import DailyDataCollector


class TestDailyDataCollector:
    @pytest.fixture
    def collector(self):
        github = MagicMock()
        github.list_recent_commits = MagicMock(return_value=[
            {"sha": "abc1234", "message": "fix login", "author": "zhangsan", "date": "2026-03-21T10:00:00"},
            {"sha": "def5678", "message": "add API", "author": "lisi", "date": "2026-03-21T11:00:00"},
            {"sha": "ghi9012", "message": "add API v2", "author": "lisi", "date": "2026-03-21T12:00:00"},
        ])
        github.list_open_prs = MagicMock(return_value=[
            {"number": 45, "title": "Login UI", "author": "zhangsan",
             "created_at": "2026-03-20T10:00:00", "updated_at": "2026-03-20T10:00:00",
             "review_requested": True},
        ])
        github.list_issues = MagicMock(return_value=[
            MagicMock(number=23, title="Login page", state="open", labels=["frontend"],
                     assignees=["zhangsan"]),
        ])
        github.list_milestones = MagicMock(return_value=[
            {"number": 1, "title": "MVP v1.0", "due_on": "2026-04-01T00:00:00",
             "open_issues": 6, "closed_issues": 12},
        ])
        return DailyDataCollector(github=github, repo="org/repo")

    def test_collect_commits_per_member(self, collector):
        data = collector.collect()
        assert "commits_by_member" in data
        assert data["commits_by_member"]["lisi"] == 2
        assert data["commits_by_member"]["zhangsan"] == 1

    def test_collect_open_prs(self, collector):
        data = collector.collect()
        assert len(data["open_prs"]) == 1
        assert data["open_prs"][0]["number"] == 45

    def test_collect_milestones(self, collector):
        data = collector.collect()
        assert len(data["milestones"]) == 1
        assert data["milestones"][0]["title"] == "MVP v1.0"

    def test_collect_total_commits(self, collector):
        data = collector.collect()
        assert data["total_commits"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_daily_report/test_collectors.py -v`

- [ ] **Step 3: Implement collectors.py**

```python
# grove/modules/daily_report/collectors.py
"""Data collection from GitHub for daily reports."""

import logging
from datetime import datetime, timedelta, timezone

from grove.integrations.github.client import GitHubClient

logger = logging.getLogger(__name__)


class DailyDataCollector:
    """Collect project activity data from GitHub for the last 24 hours."""

    def __init__(self, github: GitHubClient, repo: str):
        self.github = github
        self.repo = repo

    def collect(self) -> dict:
        """Collect all data needed for a daily report."""
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        # Commits
        commits = self.github.list_recent_commits(self.repo, since=since)
        commits_by_member: dict[str, int] = {}
        for c in commits:
            author = c["author"]
            commits_by_member[author] = commits_by_member.get(author, 0) + 1

        # Open PRs
        open_prs = self.github.list_open_prs(self.repo)

        # Open Issues
        issues = self.github.list_issues(self.repo, state="open")

        # Milestones
        milestones = self.github.list_milestones(self.repo)

        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_commits": len(commits),
            "commits": commits,
            "commits_by_member": commits_by_member,
            "open_prs": open_prs,
            "open_issues_count": len(issues),
            "milestones": milestones,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_daily_report/test_collectors.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/daily_report/ tests/test_modules/test_daily_report/
git commit -m "feat: daily report data collectors from GitHub API"
```

---

### Task 3: Progress Analyzer + Risk Detection

**Files:**
- Create: `grove/modules/daily_report/analyzer.py`
- Test: `tests/test_modules/test_daily_report/test_analyzer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_daily_report/test_analyzer.py
import pytest
from grove.modules.daily_report.analyzer import ReportAnalyzer, RiskItem


class TestReportAnalyzer:
    @pytest.fixture
    def sample_data(self):
        return {
            "date": "2026-03-21",
            "total_commits": 10,
            "commits_by_member": {"zhangsan": 3, "lisi": 5, "wangwu": 0, "zhaoliu": 2},
            "open_prs": [
                {"number": 45, "title": "Login UI", "author": "zhangsan",
                 "created_at": "2026-03-19T10:00:00", "updated_at": "2026-03-19T10:00:00",
                 "review_requested": True},
            ],
            "open_issues_count": 18,
            "milestones": [
                {"number": 1, "title": "MVP v1.0", "due_on": "2026-03-26T00:00:00",
                 "open_issues": 6, "closed_issues": 12},
            ],
        }

    def test_detect_inactive_members(self, sample_data):
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        risks = analyzer.analyze(sample_data)
        inactive = [r for r in risks if r.risk_type == "inactive_member"]
        assert len(inactive) == 1
        assert "wangwu" in inactive[0].description

    def test_detect_stale_prs(self, sample_data):
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        risks = analyzer.analyze(sample_data)
        stale = [r for r in risks if r.risk_type == "stale_pr"]
        assert len(stale) == 1
        assert "#45" in stale[0].description

    def test_milestone_progress(self, sample_data):
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        summary = analyzer.get_milestone_summary(sample_data)
        assert len(summary) == 1
        assert summary[0]["progress_pct"] == 67  # 12/(12+6)

    def test_no_risks_when_healthy(self):
        data = {
            "date": "2026-03-21",
            "total_commits": 10,
            "commits_by_member": {"zhangsan": 3, "lisi": 3, "wangwu": 2, "zhaoliu": 2},
            "open_prs": [],
            "open_issues_count": 10,
            "milestones": [],
        }
        analyzer = ReportAnalyzer(team_members=["zhangsan", "lisi", "wangwu", "zhaoliu"])
        risks = analyzer.analyze(data)
        assert len(risks) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_daily_report/test_analyzer.py -v`

- [ ] **Step 3: Implement analyzer.py**

```python
# grove/modules/daily_report/analyzer.py
"""Progress analysis and risk detection for daily reports."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class RiskItem:
    risk_type: str  # inactive_member, stale_pr, milestone_risk
    severity: str  # high, medium, low
    description: str
    mention: str = ""  # GitHub username to @mention


class ReportAnalyzer:
    """Analyze collected data to detect risks and compute progress."""

    def __init__(self, team_members: list[str]):
        self._team_members = team_members

    def analyze(self, data: dict) -> list[RiskItem]:
        """Run all risk detection checks. Returns list of risk items."""
        risks = []
        risks.extend(self._check_inactive_members(data))
        risks.extend(self._check_stale_prs(data))
        risks.extend(self._check_milestone_risks(data))
        return risks

    def _check_inactive_members(self, data: dict) -> list[RiskItem]:
        """Detect members with 0 commits in the last 24h."""
        commits_by_member = data.get("commits_by_member", {})
        risks = []
        for member in self._team_members:
            if commits_by_member.get(member, 0) == 0:
                risks.append(RiskItem(
                    risk_type="inactive_member",
                    severity="medium",
                    description=f"{member} 昨日无 commit 活动",
                    mention=member,
                ))
        return risks

    def _check_stale_prs(self, data: dict) -> list[RiskItem]:
        """Detect PRs open > 48h without review."""
        now = datetime.now(timezone.utc)
        risks = []
        for pr in data.get("open_prs", []):
            created = datetime.fromisoformat(pr["created_at"]).replace(tzinfo=timezone.utc)
            age_hours = (now - created).total_seconds() / 3600
            if age_hours > 48:
                risks.append(RiskItem(
                    risk_type="stale_pr",
                    severity="medium",
                    description=f"PR #{pr['number']}「{pr['title']}」已开放 {int(age_hours)}h 未 review",
                    mention=pr["author"],
                ))
        return risks

    def _check_milestone_risks(self, data: dict) -> list[RiskItem]:
        """Detect milestones approaching deadline with many open issues."""
        now = datetime.now(timezone.utc)
        risks = []
        for ms in data.get("milestones", []):
            if not ms.get("due_on"):
                continue
            due = datetime.fromisoformat(ms["due_on"]).replace(tzinfo=timezone.utc)
            days_left = (due - now).days
            if days_left <= 3 and ms["open_issues"] > 0:
                risks.append(RiskItem(
                    risk_type="milestone_risk",
                    severity="high",
                    description=(
                        f"里程碑「{ms['title']}」还有 {days_left} 天截止，"
                        f"剩余 {ms['open_issues']} 个未完成任务"
                    ),
                ))
        return risks

    def get_milestone_summary(self, data: dict) -> list[dict]:
        """Calculate milestone progress percentages."""
        summaries = []
        for ms in data.get("milestones", []):
            total = ms["open_issues"] + ms["closed_issues"]
            pct = int(ms["closed_issues"] / total * 100) if total > 0 else 0
            summaries.append({
                "title": ms["title"],
                "progress_pct": pct,
                "open": ms["open_issues"],
                "closed": ms["closed_issues"],
                "due_on": ms.get("due_on"),
            })
        return summaries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_daily_report/test_analyzer.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/daily_report/analyzer.py tests/test_modules/test_daily_report/test_analyzer.py
git commit -m "feat: progress analyzer with risk detection (inactive, stale PRs, milestones)"
```

---

### Task 4: Daily Report Card Builder

**Files:**
- Modify: `grove/integrations/lark/cards.py`

- [ ] **Step 1: Add build_daily_report_card**

```python
# Add to grove/integrations/lark/cards.py

def build_daily_report_card(
    date: str,
    milestone_summary: list[dict],
    member_activity: dict[str, int],
    risks: list[dict],
    suggestions: str,
) -> dict:
    """Build a rich daily report card for Lark."""
    # Milestone section
    ms_lines = []
    for ms in milestone_summary:
        ms_lines.append(f"**{ms['title']}** 进度：{ms['progress_pct']}%（{ms['closed']}/{ms['closed'] + ms['open']}）")
    ms_text = "\n".join(ms_lines) if ms_lines else "暂无里程碑"

    # Member activity table
    activity_lines = ["| 成员 | 昨日 Commits | 状态 |", "|------|-------------|------|"]
    for member, count in member_activity.items():
        status = "🟢 正常" if count > 0 else "🔴 无活动"
        activity_lines.append(f"| @{member} | {count} | {status} |")
    activity_text = "\n".join(activity_lines)

    # Risks
    risk_lines = []
    for r in risks:
        icon = "🔴" if r.get("severity") == "high" else "🟡"
        risk_lines.append(f"{icon} {r['description']}")
    risk_text = "\n".join(risk_lines) if risk_lines else "✅ 无风险项"

    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"📋 每日站会报告 — {date}"},
            "template": "blue",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**整体进度**\n{ms_text}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**成员动态**\n{activity_text}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**风险项**\n{risk_text}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**建议**\n{suggestions}"}},
        ],
    }
```

- [ ] **Step 2: Commit**

```bash
git add grove/integrations/lark/cards.py
git commit -m "feat: Lark daily report card builder"
```

---

### Task 5: Report Prompts

**Files:**
- Create: `grove/modules/daily_report/prompts.py`

- [ ] **Step 1: Create prompts.py**

```python
# grove/modules/daily_report/prompts.py
"""Prompt templates for daily report generation."""

REPORT_POLISH_PROMPT = """\
你是 Grove，AI 产品经理。请根据以下原始数据，生成一份简洁的每日站会报告的「建议」部分。

日期: {date}

里程碑进度:
{milestone_summary}

成员活动:
{member_activity}

风险项:
{risks}

请给出 2-3 条简洁的行动建议（每条一句话）。
- 针对风险项提出具体的解决方案
- 建议应该是可执行的（谁做什么）
- 用中文，语气温和但明确
- 只输出建议内容，不要标题或其他格式
"""
```

- [ ] **Step 2: Commit**

```bash
git add grove/modules/daily_report/prompts.py
git commit -m "feat: daily report LLM prompt template"
```

---

### Task 6: Daily Report Handler

**Files:**
- Create: `grove/modules/daily_report/handler.py`
- Test: `tests/test_modules/test_daily_report/test_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_daily_report/test_handler.py
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.modules.daily_report.handler import DailyReportModule


class TestDailyReportModule:
    @pytest.fixture
    def module(self, grove_dir: Path, sample_team_yml: Path):
        bus = EventBus()
        llm = MagicMock()
        llm.chat = AsyncMock(return_value="1. 建议 A\n2. 建议 B")
        lark = MagicMock()
        lark.send_card = AsyncMock()
        lark.send_text = AsyncMock()
        github = MagicMock()
        github.list_recent_commits = MagicMock(return_value=[
            {"sha": "abc", "message": "fix", "author": "zhangsan", "date": "2026-03-21T10:00:00"},
        ])
        github.list_open_prs = MagicMock(return_value=[])
        github.list_issues = MagicMock(return_value=[])
        github.list_milestones = MagicMock(return_value=[])
        github.create_issue = MagicMock(return_value=MagicMock(number=100))
        storage = Storage(grove_dir)
        resolver = MemberResolver(storage)
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"

        module = DailyReportModule(
            bus=bus, llm=llm, lark=lark, github=github,
            config=config, resolver=resolver, storage=storage,
        )
        bus.register(module)
        return module, bus

    async def test_cron_triggers_report(self, module):
        mod, bus = module
        event = Event(type=EventType.CRON_DAILY_REPORT, source="scheduler", payload={})
        await bus.dispatch(event)

        # Should send a card to Lark
        mod.lark.send_card.assert_called_once()
        # Should create a GitHub Issue
        mod.github.create_issue.assert_called_once()
        # Issue should have daily-report label
        call_kwargs = mod.github.create_issue.call_args
        assert "daily-report" in (call_kwargs.kwargs.get("labels") or call_kwargs[1].get("labels", []))

    async def test_saves_snapshot(self, module, grove_dir):
        mod, bus = module
        event = Event(type=EventType.CRON_DAILY_REPORT, source="scheduler", payload={})
        await bus.dispatch(event)

        # Should have saved a snapshot
        snapshots = list((grove_dir / "memory" / "snapshots").glob("*.json"))
        assert len(snapshots) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_daily_report/test_handler.py -v`

- [ ] **Step 3: Implement handler.py**

```python
# grove/modules/daily_report/handler.py
"""Daily report module — collect, analyze, report, archive."""

import logging
from datetime import datetime, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_daily_report_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.daily_report.collectors import DailyDataCollector
from grove.modules.daily_report.analyzer import ReportAnalyzer
from grove.modules.daily_report.prompts import REPORT_POLISH_PROMPT

logger = logging.getLogger(__name__)


class DailyReportModule:
    """Generate and distribute daily standup reports."""

    def __init__(
        self,
        bus: EventBus,
        llm: LLMClient,
        lark: LarkClient,
        github: GitHubClient,
        config: GroveConfig,
        resolver: MemberResolver,
        storage: Storage,
    ):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._collector = DailyDataCollector(github=github, repo=config.project.repo)
        self._analyzer = ReportAnalyzer(
            team_members=[m.github for m in resolver.all() if m.role != "design"]
        )
        self._storage = storage

    @subscribe(EventType.CRON_DAILY_REPORT)
    async def on_daily_report(self, event: Event) -> None:
        """Generate and send the daily standup report."""
        logger.info("Generating daily report...")

        # 1. Collect data
        data = self._collector.collect()

        # 2. Analyze risks
        risks = self._analyzer.analyze(data)
        milestone_summary = self._analyzer.get_milestone_summary(data)

        # 3. Get LLM suggestions
        suggestions = await self._generate_suggestions(data, risks, milestone_summary)

        # 4. Save snapshot
        self._save_snapshot(data, risks)

        # 5. Send Lark card
        card = build_daily_report_card(
            date=data["date"],
            milestone_summary=milestone_summary,
            member_activity=data["commits_by_member"],
            risks=[{"severity": r.severity, "description": r.description} for r in risks],
            suggestions=suggestions,
        )
        await self.lark.send_card(self.config.lark.chat_id, card)

        # 6. Archive as GitHub Issue
        report_body = self._build_github_report(data, risks, milestone_summary, suggestions)
        self.github.create_issue(
            repo=self.config.project.repo,
            title=f"📋 每日站会报告 — {data['date']}",
            body=report_body,
            labels=["daily-report"],
        )

        # 7. Emit risk events for high-severity items
        for risk in risks:
            if risk.severity == "high":
                await self.bus.dispatch(Event(
                    type=EventType.INTERNAL_RISK_DETECTED,
                    source="internal",
                    payload={
                        "risk_type": risk.risk_type,
                        "description": risk.description,
                        "mention": risk.mention,
                    },
                ))

        logger.info("Daily report sent (risks: %d)", len(risks))

    async def _generate_suggestions(self, data, risks, milestone_summary) -> str:
        """Use LLM to generate actionable suggestions."""
        prompt = REPORT_POLISH_PROMPT.format(
            date=data["date"],
            milestone_summary="\n".join(
                f"- {ms['title']}: {ms['progress_pct']}% ({ms['closed']}/{ms['closed']+ms['open']})"
                for ms in milestone_summary
            ) or "暂无里程碑",
            member_activity="\n".join(
                f"- {m}: {c} commits" for m, c in data["commits_by_member"].items()
            ),
            risks="\n".join(f"- [{r.severity}] {r.description}" for r in risks) or "无风险",
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请给出建议。"}],
            max_tokens=512,
        )

    def _save_snapshot(self, data: dict, risks: list) -> None:
        """Save daily data snapshot to .grove/memory/snapshots/."""
        snapshot = {
            **data,
            "risks": [{"type": r.risk_type, "severity": r.severity, "desc": r.description} for r in risks],
        }
        self._storage.write_json(f"memory/snapshots/{data['date']}.json", snapshot)

    def _build_github_report(self, data, risks, milestone_summary, suggestions) -> str:
        """Build Markdown report body for GitHub Issue."""
        lines = [f"# 📋 每日站会报告 — {data['date']}\n"]

        # Milestones
        lines.append("## 整体进度\n")
        for ms in milestone_summary:
            lines.append(f"里程碑「{ms['title']}」进度：{ms['progress_pct']}%（{ms['closed']}/{ms['closed']+ms['open']}）\n")

        # Member activity
        lines.append("## 👥 成员动态\n")
        lines.append("| 成员 | 昨日 Commits | 状态 |")
        lines.append("|------|-------------|------|")
        for member, count in data["commits_by_member"].items():
            status = "🟢 正常" if count > 0 else "🔴 无活动"
            lines.append(f"| @{member} | {count} | {status} |")

        # Risks
        lines.append("\n## ⚠️ 风险项\n")
        if risks:
            for r in risks:
                icon = "🔴" if r.severity == "high" else "🟡"
                lines.append(f"- {icon} {r.description}")
        else:
            lines.append("✅ 无风险项")

        # Suggestions
        lines.append(f"\n## 💡 建议\n\n{suggestions}")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_daily_report/test_handler.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/daily_report/handler.py tests/test_modules/test_daily_report/test_handler.py
git commit -m "feat: daily report handler — collect, analyze, report to Lark + GitHub"
```

---

### Task 7: Module Registration + Full Suite

**Files:**
- Modify: `grove/main.py`

- [ ] **Step 1: Add imports and registration**

Add import at top of `grove/main.py`:
```python
from grove.modules.daily_report.handler import DailyReportModule
```

Inside `lifespan`, after existing module registrations, add:
```python
    # Daily report module
    daily_report = DailyReportModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        resolver=resolver, storage=storage,
    )
    event_bus.register(daily_report)
    logger.info("Registered DailyReportModule")
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "from grove.main import app; print('OK')"`

- [ ] **Step 3: Run full test suite + lint**

Run: `.venv/bin/pytest -v --tb=short`
Run: `.venv/bin/ruff check grove/ tests/`

- [ ] **Step 4: Fix issues and commit**

```bash
git add -A
git commit -m "feat: register daily report module + Phase 4 complete"
```

---

## Phase 4 Completion Criteria

- [ ] `cron.daily_report` event → data collection → risk analysis → LLM suggestions
- [ ] Lark receives a rich report card with milestones, member activity, risks, suggestions
- [ ] GitHub Issue created with `daily-report` label and full Markdown report
- [ ] Daily snapshot saved to `.grove/memory/snapshots/`
- [ ] High-severity risks emit `internal.risk_detected` events
- [ ] All tests pass, lint clean

**Next:** Create Phase 5 plan (PR Review + Document Sync).
