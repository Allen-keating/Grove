# PRD Baseline Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge reverse PRD + dev status into a unified baseline document, add prd_baseline module for lifecycle management (merge confirmation, PR feature matching, reorganization), and overhaul Project Scanner for source code reading and cold start confirmation.

**Architecture:** New `prd_baseline` module subscribes to `INTERNAL_PRD_FINALIZED`, `PR_MERGED`, `LARK_CARD_ACTION`, and `INTERNAL_REORGANIZE_BASELINE`. Project Scanner is refactored to output a single `project-baseline.md` with commit clustering and source code reading. `feature-tracking.json` is the programmatic source of truth; Markdown is regenerated from it.

**Tech Stack:** Python 3.12+, FastAPI, PyGithub, lark-oapi, Anthropic SDK, pytest

**Spec:** `docs/superpowers/specs/2026-03-24-prd-baseline-merge-design.md`

---

## File Map

### New Files (8)

| File | Responsibility |
|------|---------------|
| `grove/modules/prd_baseline/__init__.py` | Package init |
| `grove/modules/prd_baseline/prompts.py` | LLM prompts for feature matching + baseline reorganization |
| `grove/modules/prd_baseline/baseline_editor.py` | Deterministic Markdown operations: parse, append, move features |
| `grove/modules/prd_baseline/matcher.py` | LLM-based PR→feature matching (existing/new/none) |
| `grove/modules/prd_baseline/handler.py` | Event handlers: PRD merge confirm, PR match, card actions, reorg |
| `tests/test_modules/test_prd_baseline/__init__.py` | Test package |
| `tests/test_modules/test_prd_baseline/test_baseline_editor.py` | Pure Markdown operation tests |
| `tests/test_modules/test_prd_baseline/test_handler.py` | Event flow tests |

### Modified Files (14)

| File | Changes |
|------|---------|
| `grove/core/events.py:40` | +1 EventType: INTERNAL_REORGANIZE_BASELINE |
| `grove/config.py:79` | +1 ModulesConfig field: prd_baseline |
| `grove/core/module_registry.py:120` | +1 merge_module_state entry |
| `grove/integrations/github/client.py` | +2 methods: read_file_head, get_pr_commits |
| `grove/integrations/lark/cards.py` | +2 card builders |
| `grove/modules/communication/intent_parser.py:31` | +1 Intent, +1 keyword rule, +1 MODULE_ALIAS |
| `grove/modules/communication/handler.py:90` | +1 intent route |
| `grove/modules/prd_generator/handler.py:128` | +github_path in INTERNAL_PRD_FINALIZED payload |
| `grove/modules/project_scanner/prompts.py` | Replace feature prompt with clustering prompt; add baseline gen prompt |
| `grove/modules/project_scanner/analyzer.py` | Replace analyze_features with cluster_features; replace generate_reverse_prd with generate_baseline |
| `grove/modules/project_scanner/handler.py` | Single doc output, source code reading, cold start confirm, gap detection, migration |
| `grove/main.py:35,152,164` | +import, +instantiate, +register prd_baseline |
| `tests/conftest.py` | +prd_baseline module config |
| `grove/modules/communication/prompts.py` | No changes needed (rule-matched intents don't appear in LLM prompt) |

---

## Task 1: Events + Config + Registry

**Files:**
- Modify: `grove/core/events.py:40`
- Modify: `grove/config.py:79`
- Modify: `grove/core/module_registry.py:120`

- [ ] **Step 1: Add INTERNAL_REORGANIZE_BASELINE to events.py**

After line 40 (`INTERNAL_DISPATCH_NEGOTIATE`), add:

```python
    INTERNAL_REORGANIZE_BASELINE = "internal.reorganize_baseline"
```

- [ ] **Step 2: Add prd_baseline to ModulesConfig**

In `grove/config.py`, after `morning_dispatch: bool = True` (line 79), add:

```python
    prd_baseline: bool = True
```

- [ ] **Step 3: Add to merge_module_state**

In `grove/core/module_registry.py`, after `"morning_dispatch"` entry (line 120), add:

```python
        "prd_baseline": modules_cfg.prd_baseline,
```

- [ ] **Step 4: Write tests and verify**

Append to `tests/test_core/test_events.py`:
```python
def test_reorganize_baseline_event():
    from grove.core.events import EventType
    assert EventType.INTERNAL_REORGANIZE_BASELINE == "internal.reorganize_baseline"
```

Append to `tests/test_core/test_config.py`:
```python
def test_modules_config_has_prd_baseline():
    from grove.config import ModulesConfig
    mc = ModulesConfig()
    assert mc.prd_baseline is True
```

Run: `./.venv/bin/pytest tests/test_core/ -v`

- [ ] **Step 5: Commit**

```bash
git add grove/core/events.py grove/config.py grove/core/module_registry.py tests/test_core/
git commit -m "feat: add INTERNAL_REORGANIZE_BASELINE event and prd_baseline config"
```

---

## Task 2: GitHub Client — read_file_head + get_pr_commits

**Files:**
- Modify: `grove/integrations/github/client.py`
- Test: `tests/test_integrations/test_github_client.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_integrations/test_github_client.py`:

```python
class TestGitHubClientBaselineMethods:
    def _make_client(self):
        return GitHubClient(app_id="1", private_key_path="/tmp/fake.pem", installation_id="2")

    def test_read_file_head_truncates(self):
        client = self._make_client()
        mock_repo = MagicMock()
        mock_content = MagicMock()
        mock_content.decoded_content = b"line1\nline2\nline3\nline4\nline5"
        mock_repo.get_contents.return_value = mock_content
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.read_file_head("org/repo", "main.py", max_lines=3)
        assert result == "line1\nline2\nline3"

    def test_get_pr_commits(self):
        client = self._make_client()
        mock_commit = MagicMock()
        mock_commit.sha = "abc1234567"
        mock_commit.commit.message = "feat: add login\n\nDetailed description"
        mock_commit.commit.author.name = "alice"
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [mock_commit]
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.get_pr_commits("org/repo", 42)
        assert len(result) == 1
        assert result[0]["sha"] == "abc1234"
        assert result[0]["message"] == "feat: add login"
        assert result[0]["author"] == "alice"
```

- [ ] **Step 2: Implement methods**

Append to `grove/integrations/github/client.py` after the last method:

```python
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def read_file_head(self, repo: str, path: str, max_lines: int = 100) -> str:
        """Read the first N lines of a file. Downloads full file, truncates locally."""
        content = self.read_file(repo, path)
        lines = content.split("\n")
        return "\n".join(lines[:max_lines])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def get_pr_commits(self, repo: str, pr_number: int) -> list[dict]:
        """Get all commits associated with a PR."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        pr = r.get_pull(pr_number)
        return [
            {
                "sha": c.sha[:7],
                "message": c.commit.message.split("\n")[0],
                "author": c.commit.author.name,
            }
            for c in pr.get_commits()
        ]
```

- [ ] **Step 3: Run tests**

Run: `./.venv/bin/pytest tests/test_integrations/test_github_client.py -v`

- [ ] **Step 4: Commit**

```bash
git add grove/integrations/github/client.py tests/test_integrations/test_github_client.py
git commit -m "feat: add read_file_head and get_pr_commits to GitHub client"
```

---

## Task 3: Lark Card Builders

**Files:**
- Modify: `grove/integrations/lark/cards.py`
- Test: `tests/test_integrations/test_lark_cards.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_integrations/test_lark_cards.py`:

```python
from grove.integrations.lark.cards import build_baseline_merge_card, build_feature_status_card

class TestBaselineMergeCard:
    def test_builds_valid_card(self):
        card = build_baseline_merge_card(
            topic="用户反馈系统", summary="反馈收集与分析", prd_path="prd-用户反馈系统.md",
        )
        assert "基线合并" in card["header"]["title"]["content"]
        actions = [e for e in card["elements"] if e.get("tag") == "action"]
        assert len(actions) == 1
        buttons = actions[0]["actions"]
        assert buttons[0]["value"]["action"] == "confirm_baseline_merge"
        assert buttons[1]["value"]["action"] == "skip_baseline_merge"

class TestFeatureStatusCard:
    def test_builds_valid_card(self):
        card = build_feature_status_card(
            pr_number=123, feature_name="用户反馈系统",
            suggested_status="completed", reason="核心 API 已实现",
        )
        assert "#123" in card["elements"][0]["text"]["content"]
        actions = [e for e in card["elements"] if e.get("tag") == "action"]
        buttons = actions[0]["actions"]
        assert buttons[0]["value"]["action"] == "confirm_feature_status"
```

- [ ] **Step 2: Implement card builders**

Append to `grove/integrations/lark/cards.py`:

```python
def build_baseline_merge_card(topic: str, summary: str, prd_path: str) -> dict:
    return {
        "header": {"title": {"tag": "plain_text", "content": "🌳 Grove — 基线合并确认"}, "template": "green"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content":
                f"**功能：** {topic}\n**摘要：** {summary}\n**PRD：** {prd_path}"}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 合并到基线"},
                 "type": "primary", "value": {"action": "confirm_baseline_merge", "topic": topic, "prd_path": prd_path}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 暂不合并"},
                 "value": {"action": "skip_baseline_merge", "topic": topic}},
            ]},
        ],
    }


def build_feature_status_card(pr_number: int, feature_name: str, suggested_status: str, reason: str) -> dict:
    status_text = "已完成" if suggested_status == "completed" else "进行中"
    return {
        "header": {"title": {"tag": "plain_text", "content": "🌳 Grove — 功能状态确认"}, "template": "orange"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content":
                f"**PR #{pr_number}** 可能{'完成' if suggested_status == 'completed' else '涉及'}了「{feature_name}」\n"
                f"**建议状态：** {status_text}\n**理由：** {reason}"}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认"},
                 "type": "primary", "value": {"action": "confirm_feature_status", "feature_name": feature_name,
                                               "status": suggested_status, "pr_number": pr_number}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 不相关"},
                 "type": "danger", "value": {"action": "reject_feature_status", "feature_name": feature_name,
                                              "pr_number": pr_number}},
            ]},
        ],
    }
```

- [ ] **Step 3: Run tests**

Run: `./.venv/bin/pytest tests/test_integrations/test_lark_cards.py -v`

- [ ] **Step 4: Commit**

```bash
git add grove/integrations/lark/cards.py tests/test_integrations/test_lark_cards.py
git commit -m "feat: add baseline merge and feature status Lark card builders"
```

---

## Task 4: PRD Generator Payload Extension

**Files:**
- Modify: `grove/modules/prd_generator/handler.py:126-130`

- [ ] **Step 1: Add github_path to INTERNAL_PRD_FINALIZED payload**

In `grove/modules/prd_generator/handler.py`, replace the dispatch block at lines 126-130:

```python
        await self.bus.dispatch(Event(
            type=EventType.INTERNAL_PRD_FINALIZED, source="internal",
            payload={"topic": conv.topic, "prd_doc_id": doc_id, "conversation_id": conv.id},
            member=None,
        ))
```

With:

```python
        await self.bus.dispatch(Event(
            type=EventType.INTERNAL_PRD_FINALIZED, source="internal",
            payload={
                "topic": conv.topic, "prd_doc_id": doc_id,
                "conversation_id": conv.id,
                "github_path": f"{self.config.doc_sync.github_docs_path}prd-{filename}.md",
            },
            member=None,
        ))
```

Note: `filename` is already defined at line 96 as `conv.topic.replace(" ", "-").replace("/", "-")`.

- [ ] **Step 2: Run existing PRD generator tests**

Run: `./.venv/bin/pytest tests/test_modules/test_prd_generator/ -v`

- [ ] **Step 3: Commit**

```bash
git add grove/modules/prd_generator/handler.py
git commit -m "feat: add github_path to INTERNAL_PRD_FINALIZED payload"
```

---

## Task 5: prd_baseline Module — baseline_editor.py

**Files:**
- Create: `grove/modules/prd_baseline/__init__.py`
- Create: `grove/modules/prd_baseline/baseline_editor.py`
- Test: `tests/test_modules/test_prd_baseline/__init__.py`
- Test: `tests/test_modules/test_prd_baseline/test_baseline_editor.py`

This is the deterministic Markdown parsing/editing core. No LLM, no mocks needed.

- [ ] **Step 1: Write comprehensive tests**

```python
# tests/test_modules/test_prd_baseline/__init__.py — empty

# tests/test_modules/test_prd_baseline/test_baseline_editor.py
from grove.modules.prd_baseline.baseline_editor import (
    parse_features, append_feature, move_feature, format_feature_entry,
)

SAMPLE_BASELINE = """\
# TestProject 项目基线文档

## 功能清单

### ✅ 已实现
- ✅ **用户登录** — OAuth2 登录 `#PR-12`

### 🔄 进行中
- 🔄 **数据导出** — CSV 导出 → [详细 PRD](prd-数据导出.md)

### ⬚ 待开发
- ⬚ **仪表盘** — 数据可视化 → [详细 PRD](prd-仪表盘.md)

## 里程碑
"""


class TestParseFeatures:
    def test_parses_all_sections(self):
        result = parse_features(SAMPLE_BASELINE)
        assert len(result["done"]) == 1
        assert result["done"][0]["name"] == "用户登录"
        assert len(result["in_progress"]) == 1
        assert result["in_progress"][0]["name"] == "数据导出"
        assert len(result["planned"]) == 1
        assert result["planned"][0]["name"] == "仪表盘"

    def test_empty_sections(self):
        content = "# Doc\n\n## 功能清单\n\n### ✅ 已实现\n\n### 🔄 进行中\n\n### ⬚ 待开发\n"
        result = parse_features(content)
        assert result == {"done": [], "in_progress": [], "planned": []}


class TestAppendFeature:
    def test_append_to_planned(self):
        entry = format_feature_entry("反馈系统", "用户反馈", "planned", prd_path="prd-反馈系统.md")
        result = append_feature(SAMPLE_BASELINE, "planned", entry)
        assert "反馈系统" in result
        # Should appear after existing planned item
        assert result.index("反馈系统") > result.index("仪表盘")

    def test_append_to_empty_section(self):
        content = "# Doc\n\n## 功能清单\n\n### ✅ 已实现\n\n### 🔄 进行中\n\n### ⬚ 待开发\n\n## 里程碑\n"
        entry = format_feature_entry("新功能", "描述", "planned")
        result = append_feature(content, "planned", entry)
        assert "新功能" in result


class TestMoveFeature:
    def test_move_planned_to_in_progress(self):
        result = move_feature(SAMPLE_BASELINE, "仪表盘", "planned", "in_progress")
        features = parse_features(result)
        assert any(f["name"] == "仪表盘" for f in features["in_progress"])
        assert not any(f["name"] == "仪表盘" for f in features["planned"])

    def test_move_in_progress_to_done(self):
        result = move_feature(SAMPLE_BASELINE, "数据导出", "in_progress", "done")
        features = parse_features(result)
        assert any(f["name"] == "数据导出" for f in features["done"])
        assert not any(f["name"] == "数据导出" for f in features["in_progress"])

    def test_move_nonexistent_returns_unchanged(self):
        result = move_feature(SAMPLE_BASELINE, "不存在", "planned", "done")
        assert result == SAMPLE_BASELINE


class TestFormatFeatureEntry:
    def test_planned_with_prd(self):
        entry = format_feature_entry("反馈系统", "反馈收集", "planned", prd_path="prd-反馈系统.md")
        assert entry == "- ⬚ **反馈系统** — 反馈收集 → [详细 PRD](prd-反馈系统.md)"

    def test_done_with_pr(self):
        entry = format_feature_entry("登录", "OAuth 登录", "done", pr_number=42)
        assert entry == "- ✅ **登录** — OAuth 登录 `#PR-42`"

    def test_in_progress_minimal(self):
        entry = format_feature_entry("搜索", "全文搜索", "in_progress")
        assert entry == "- 🔄 **搜索** — 全文搜索"
```

- [ ] **Step 2: Implement baseline_editor.py**

```python
# grove/modules/prd_baseline/__init__.py — empty

# grove/modules/prd_baseline/baseline_editor.py
"""Deterministic Markdown operations for the project baseline document."""
import re

_STATUS_ICONS = {"done": "✅", "in_progress": "🔄", "planned": "⬚"}
_SECTION_HEADERS = {
    "done": "### ✅ 已实现",
    "in_progress": "### 🔄 进行中",
    "planned": "### ⬚ 待开发",
}
_FEATURE_RE = re.compile(
    r"^- [✅🔄⬚] \*\*(.+?)\*\* — (.+)$"
)


def parse_features(baseline_content: str) -> dict[str, list[dict]]:
    """Parse the feature list sections from baseline Markdown."""
    result: dict[str, list[dict]] = {"done": [], "in_progress": [], "planned": []}
    current_section: str | None = None

    for line in baseline_content.split("\n"):
        stripped = line.strip()
        if stripped == _SECTION_HEADERS["done"]:
            current_section = "done"
        elif stripped == _SECTION_HEADERS["in_progress"]:
            current_section = "in_progress"
        elif stripped == _SECTION_HEADERS["planned"]:
            current_section = "planned"
        elif stripped.startswith("## ") or stripped.startswith("### "):
            current_section = None
        elif current_section and (m := _FEATURE_RE.match(stripped)):
            result[current_section].append({
                "name": m.group(1),
                "description": m.group(2),
                "raw_line": stripped,
            })

    return result


def format_feature_entry(
    name: str, description: str, status: str,
    prd_path: str | None = None, pr_number: int | None = None,
) -> str:
    """Generate a standard-format feature entry line."""
    icon = _STATUS_ICONS.get(status, "❓")
    entry = f"- {icon} **{name}** — {description}"
    if prd_path:
        entry += f" → [详细 PRD]({prd_path})"
    elif pr_number:
        entry += f" `#PR-{pr_number}`"
    return entry


def append_feature(baseline_content: str, section: str, entry: str) -> str:
    """Append a feature entry to the end of a section."""
    header = _SECTION_HEADERS.get(section)
    if not header:
        return baseline_content

    lines = baseline_content.split("\n")
    result = []
    found_section = False
    inserted = False

    for i, line in enumerate(lines):
        result.append(line)
        if line.strip() == header:
            found_section = True
            continue
        if found_section and not inserted:
            # Find the end of this section (next heading or blank line before heading)
            is_next_heading = (
                i + 1 < len(lines) and
                (lines[i + 1].strip().startswith("### ") or lines[i + 1].strip().startswith("## "))
            )
            is_last_content = not line.strip() and is_next_heading
            is_end_of_items = line.strip() and not line.strip().startswith("- ")

            if is_last_content or is_next_heading:
                result.insert(len(result) - 1 if is_last_content else len(result), entry)
                inserted = True

    if found_section and not inserted:
        # Section was at the end of file or had no items
        result.append(entry)

    return "\n".join(result)


def move_feature(
    baseline_content: str, feature_name: str,
    from_section: str, to_section: str,
) -> str:
    """Move a feature from one section to another, updating the status icon."""
    features = parse_features(baseline_content)
    source_features = features.get(from_section, [])
    match = next((f for f in source_features if f["name"] == feature_name), None)
    if not match:
        return baseline_content

    # Remove from source
    content = baseline_content.replace(match["raw_line"] + "\n", "")
    content = content.replace(match["raw_line"], "")  # handle last line without newline

    # Build new entry with updated icon
    new_entry = format_feature_entry(
        name=match["name"],
        description=match["description"].split(" → ")[0].split(" `")[0],
        status=to_section,
    )

    # Append to target
    return append_feature(content, to_section, new_entry)
```

- [ ] **Step 3: Run tests**

Run: `./.venv/bin/pytest tests/test_modules/test_prd_baseline/test_baseline_editor.py -v`

- [ ] **Step 4: Commit**

```bash
git add grove/modules/prd_baseline/ tests/test_modules/test_prd_baseline/
git commit -m "feat: add baseline_editor with parse, append, move, format operations"
```

---

## Task 6: prd_baseline Module — matcher.py + prompts.py

**Files:**
- Create: `grove/modules/prd_baseline/prompts.py`
- Create: `grove/modules/prd_baseline/matcher.py`

- [ ] **Step 1: Create prompts.py**

```python
# grove/modules/prd_baseline/prompts.py
"""Prompt templates for PRD baseline management."""

FEATURE_MATCH_PROMPT = """\
你是 Grove，AI 产品经理。分析这个 PR 是否与基线中的某个功能相关。

PR 的 commit messages：
{commits}

基线中未完成的功能：
{pending_features}

每个功能的详细 PRD（如有）：
{feature_prds}

请判断：
1. match_type: 这个 PR 与基线中已有功能相关(existing)？还是一个全新功能(new)？还是不涉及功能变更(none)？
2. 如果 existing 或 new：
   - matched_feature: 功能名
   - status: "in_progress"（部分实现）还是 "completed"（核心需求全覆盖）？
   - reason: 判断理由

输出 JSON 数组（一个 PR 可能涉及多个功能）：
[{{"match_type": "existing"|"new"|"none", "matched_feature": "功能名"|null, "status": "in_progress"|"completed"|null, "confidence": 0.0-1.0, "reason": "理由"}}]

如果不涉及任何功能，返回 [{{"match_type": "none", "matched_feature": null, "status": null, "confidence": 0.0, "reason": "不涉及功能变更"}}]。
不要强行匹配。宁可返回 none 也不要低置信度的猜测。
"""

REORGANIZE_BASELINE_PROMPT = """\
你是 Grove，AI 产品经理。请重新整理以下项目基线文档。

当前基线文档：
{baseline_content}

各功能详细 PRD（如有）：
{feature_prds}

请：
1. 保持文档结构不变（概述、技术架构、功能清单、里程碑、近期开发活动）
2. 功能清单中：合并重复项、修正描述、改善排列顺序（按重要性）
3. 保持 ✅/🔄/⬚ 标记和 PRD 链接
4. 用中文，简洁专业

输出完整的 Markdown 文档。
"""
```

- [ ] **Step 2: Create matcher.py**

```python
# grove/modules/prd_baseline/matcher.py
"""LLM-based feature matching: map PRs to baseline features."""
import json
import logging
from dataclasses import dataclass

from grove.integrations.llm.client import LLMClient
from grove.modules.prd_baseline.prompts import FEATURE_MATCH_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class FeatureMatch:
    match_type: str  # "existing" | "new" | "none"
    matched_feature: str | None
    status: str | None  # "in_progress" | "completed"
    confidence: float
    reason: str


class FeatureMatcher:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def match_pr(
        self, commits: list[dict], pending_features: list[dict],
        feature_prds: str = "",
    ) -> list[FeatureMatch]:
        commits_text = "\n".join(
            f"- {c['sha']} {c['message']}" for c in commits
        )
        features_text = "\n".join(
            f"- {f['name']}（{f.get('status', 'unknown')}）：{f.get('description', '')}"
            for f in pending_features
        ) or "（无）"

        prompt = FEATURE_MATCH_PROMPT.format(
            commits=commits_text,
            pending_features=features_text,
            feature_prds=feature_prds[:3000] or "（无）",
        )

        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请分析。"}],
                max_tokens=1024,
            )
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]
            return [
                FeatureMatch(
                    match_type=item.get("match_type", "none"),
                    matched_feature=item.get("matched_feature"),
                    status=item.get("status"),
                    confidence=item.get("confidence", 0.0),
                    reason=item.get("reason", ""),
                )
                for item in data
            ]
        except Exception:
            logger.warning("Feature matching LLM call failed")
            return [FeatureMatch(match_type="none", matched_feature=None,
                                  status=None, confidence=0.0, reason="LLM failure")]
```

- [ ] **Step 3: Run import check**

Run: `./.venv/bin/python -c "from grove.modules.prd_baseline.matcher import FeatureMatcher; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add grove/modules/prd_baseline/prompts.py grove/modules/prd_baseline/matcher.py
git commit -m "feat: add feature matcher and prompts for baseline management"
```

---

## Task 7: prd_baseline Module — handler.py

**Files:**
- Create: `grove/modules/prd_baseline/handler.py`
- Test: `tests/test_modules/test_prd_baseline/test_handler.py`

- [ ] **Step 1: Create handler.py**

```python
# grove/modules/prd_baseline/handler.py
"""PRD Baseline module — manage baseline lifecycle."""
import logging
from datetime import datetime, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_baseline_merge_card, build_feature_status_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.prd_baseline.baseline_editor import (
    append_feature, format_feature_entry, move_feature, parse_features,
)
from grove.modules.prd_baseline.matcher import FeatureMatcher
from grove.modules.prd_baseline.prompts import REORGANIZE_BASELINE_PROMPT

logger = logging.getLogger(__name__)

_OWN_ACTIONS = frozenset({
    "confirm_baseline_merge", "skip_baseline_merge",
    "confirm_feature_status", "reject_feature_status",
    "confirm_scan_gap",
})

_TRACKING_PATH = "memory/project-scan/feature-tracking.json"
_BASELINE_DOC_PATH = "memory/project-scan/baseline-doc-id.yml"


class PRDBaselineModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._matcher = FeatureMatcher(llm)

    # -- Trigger 1: New PRD finalized → send merge confirmation card --

    @subscribe(EventType.INTERNAL_PRD_FINALIZED)
    async def on_prd_finalized(self, event: Event) -> None:
        topic = event.payload.get("topic", "")
        github_path = event.payload.get("github_path", "")
        if not topic:
            return

        # Read first paragraph as summary
        summary = topic
        if github_path:
            try:
                content = self.github.read_file(self.config.project.repo, github_path)
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
                        summary = stripped[:100]
                        break
            except Exception:
                pass

        prd_filename = github_path.split("/")[-1] if github_path else f"prd-{topic}.md"
        card = build_baseline_merge_card(topic=topic, summary=summary, prd_path=prd_filename)
        await self.lark.send_card(self.config.lark.chat_id, card)
        logger.info("Sent baseline merge card for '%s'", topic)

    # -- Trigger 2: PR merged → feature matching --

    @subscribe(EventType.PR_MERGED)
    async def on_pr_merged(self, event: Event) -> None:
        pr_data = event.payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        repo = event.payload.get("repository", {}).get("full_name", self.config.project.repo)
        if not pr_number:
            return

        # Load tracking data
        tracking = self._load_tracking()
        pending = [
            {"name": name, "status": info["status"], "description": info.get("description", "")}
            for name, info in tracking.get("features", {}).items()
            if info["status"] in ("in_progress", "planned")
        ]

        # Get PR commits
        try:
            commits = self.github.get_pr_commits(repo, pr_number)
        except Exception:
            logger.warning("Failed to get commits for PR #%s", pr_number)
            return

        if not commits:
            return

        # LLM matching
        matches = await self._matcher.match_pr(commits, pending)

        for match in matches:
            if match.match_type == "none" or match.confidence < 0.5:
                continue
            await self._handle_match(match, pr_number, tracking)

    async def _handle_match(self, match, pr_number: int, tracking: dict) -> None:
        feature_name = match.matched_feature or ""
        chat_id = self.config.lark.chat_id

        if match.match_type == "existing":
            if match.confidence > 0.8:
                # Auto-update
                self._update_feature_status(tracking, feature_name, match.status, pr_number)
                if match.status == "completed":
                    await self.lark.send_text(chat_id,
                        f"PR #{pr_number} 完成了「{feature_name}」，已更新基线。")
                elif tracking["features"].get(feature_name, {}).get("status") == "planned":
                    await self.lark.send_text(chat_id,
                        f"PR #{pr_number} 开始了「{feature_name}」开发，已更新基线。")
                # in_progress → in_progress: no notification
                await self._sync_baseline()
            else:
                # Send confirmation card
                card = build_feature_status_card(
                    pr_number=pr_number, feature_name=feature_name,
                    suggested_status=match.status or "in_progress", reason=match.reason,
                )
                await self.lark.send_card(chat_id, card)

        elif match.match_type == "new":
            if match.confidence > 0.7:
                # Auto-add new feature
                self._add_feature(tracking, feature_name,
                                  status=match.status or "in_progress", pr_number=pr_number)
                await self.lark.send_text(chat_id,
                    f"检测到新功能「{feature_name}」（来自 PR #{pr_number}），已添加到基线。")
                await self._sync_baseline()
            else:
                card = build_feature_status_card(
                    pr_number=pr_number, feature_name=feature_name,
                    suggested_status="in_progress", reason=f"新功能：{match.reason}",
                )
                await self.lark.send_card(chat_id, card)

    # -- Trigger: Card actions --

    @subscribe(EventType.LARK_CARD_ACTION)
    async def on_card_action(self, event: Event) -> None:
        action_data = event.payload.get("action", {}).get("value", {})
        action = action_data.get("action", "")
        if action not in _OWN_ACTIONS:
            return

        tracking = self._load_tracking()
        chat_id = self.config.lark.chat_id

        if action == "confirm_baseline_merge":
            topic = action_data.get("topic", "")
            prd_path = action_data.get("prd_path", "")
            self._add_feature(tracking, topic, status="planned", prd_path=prd_path)
            await self._sync_baseline()
            await self.lark.send_text(chat_id, f"「{topic}」已添加到基线待开发列表。")

        elif action == "skip_baseline_merge":
            topic = action_data.get("topic", "")
            await self.lark.send_text(chat_id, f"已跳过「{topic}」的基线合并。")

        elif action == "confirm_feature_status":
            feature_name = action_data.get("feature_name", "")
            status = action_data.get("status", "in_progress")
            pr_number = action_data.get("pr_number")
            self._update_feature_status(tracking, feature_name, status, pr_number)
            await self._sync_baseline()
            await self.lark.send_text(chat_id, f"「{feature_name}」状态已更新。")

        elif action == "reject_feature_status":
            await self.lark.send_text(chat_id, "已忽略该功能关联。")

        elif action == "confirm_scan_gap":
            # Bulk add features from scan gap detection
            features = action_data.get("features", [])
            for f in features:
                self._add_feature(tracking, f["name"], status=f.get("status", "done"))
            await self._sync_baseline()
            await self.lark.send_text(chat_id, f"已将 {len(features)} 个功能添加到基线。")

    # -- Trigger 3: Reorganize baseline --

    @subscribe(EventType.INTERNAL_REORGANIZE_BASELINE)
    async def on_reorganize(self, event: Event) -> None:
        chat_id = event.payload.get("chat_id", self.config.lark.chat_id)
        await self.lark.send_text(chat_id, "正在整理基线文档...")

        baseline = self._read_baseline_from_github()
        if not baseline:
            await self.lark.send_text(chat_id, "未找到基线文档，请先运行「扫描项目」。")
            return

        prompt = REORGANIZE_BASELINE_PROMPT.format(
            baseline_content=baseline, feature_prds="",
        )
        try:
            new_content = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请整理基线文档。"}],
                max_tokens=4096,
            )
        except Exception:
            await self.lark.send_text(chat_id, "基线整理失败，请稍后重试。")
            return

        # Update tracking from reorganized content
        features = parse_features(new_content)
        tracking = {"features": {}}
        for status_key, feat_list in features.items():
            for f in feat_list:
                tracking["features"][f["name"]] = {
                    "status": status_key,
                    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                }
        self._save_tracking(tracking)

        # Sync
        self._write_baseline_to_github(new_content)
        await self._update_lark_doc(new_content)
        await self.lark.send_text(chat_id, "基线文档已整理完成。")

    # -- Internal helpers --

    def _load_tracking(self) -> dict:
        try:
            return self._storage.read_json(_TRACKING_PATH)
        except FileNotFoundError:
            return {"features": {}}

    def _save_tracking(self, tracking: dict) -> None:
        self._storage.write_json(_TRACKING_PATH, tracking)

    def _add_feature(self, tracking: dict, name: str, status: str = "planned",
                     prd_path: str | None = None, pr_number: int | None = None) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tracking.setdefault("features", {})[name] = {
            "status": status,
            "prd_path": prd_path,
            "related_prs": [pr_number] if pr_number else [],
            "added_at": now,
            "updated_at": now,
        }
        self._save_tracking(tracking)

    def _update_feature_status(self, tracking: dict, name: str, status: str | None,
                                pr_number: int | None = None) -> None:
        features = tracking.setdefault("features", {})
        if name not in features:
            features[name] = {"status": "planned", "related_prs": [],
                               "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
        if status:
            features[name]["status"] = status
        if pr_number:
            features[name].setdefault("related_prs", []).append(pr_number)
        features[name]["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._save_tracking(tracking)

    def _read_baseline_from_github(self) -> str | None:
        try:
            return self.github.read_file(self.config.project.repo, "docs/project-baseline.md")
        except Exception:
            return None

    def _write_baseline_to_github(self, content: str) -> None:
        try:
            self.github.write_file(
                self.config.project.repo, "docs/project-baseline.md",
                content, "docs: update project baseline",
            )
        except Exception:
            logger.exception("Failed to write baseline to GitHub")

    async def _update_lark_doc(self, content: str) -> None:
        try:
            doc_info = self._storage.read_yaml(_BASELINE_DOC_PATH)
            doc_id = doc_info.get("doc_id")
            if doc_id:
                await self.lark.update_doc(doc_id, content)
        except (FileNotFoundError, Exception):
            logger.warning("Failed to update Lark baseline doc")

    async def _sync_baseline(self) -> None:
        """Regenerate baseline Markdown from tracking data and sync."""
        baseline = self._read_baseline_from_github()
        if not baseline:
            return
        tracking = self._load_tracking()
        for name, info in tracking.get("features", {}).items():
            status = info.get("status", "planned")
            status_map = {"done": "done", "in_progress": "in_progress",
                          "planned": "planned", "completed": "done"}
            section = status_map.get(status, "planned")

            # Check if feature already exists in baseline
            features = parse_features(baseline)
            all_names = [f["name"] for fl in features.values() for f in fl]
            if name not in all_names:
                entry = format_feature_entry(
                    name=name, description=info.get("description", ""),
                    status=section, prd_path=info.get("prd_path"),
                )
                baseline = append_feature(baseline, section, entry)

        self._write_baseline_to_github(baseline)
        await self._update_lark_doc(baseline)
```

- [ ] **Step 2: Write handler tests**

```python
# tests/test_modules/test_prd_baseline/test_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from grove.modules.prd_baseline.handler import PRDBaselineModule


@pytest.fixture
def baseline_module():
    bus = MagicMock()
    bus.dispatch = AsyncMock()
    llm = AsyncMock()
    lark = AsyncMock()
    github = MagicMock()
    config = MagicMock()
    config.project.repo = "org/repo"
    config.lark.chat_id = "oc_test"
    config.lark.space_id = "spc_test"
    config.doc_sync.github_docs_path = "docs/prd/"
    storage = MagicMock()
    storage.read_json.side_effect = FileNotFoundError
    storage.read_yaml.side_effect = FileNotFoundError
    return PRDBaselineModule(
        bus=bus, llm=llm, lark=lark, github=github, config=config, storage=storage,
    )


class TestPRDFinalized:
    @pytest.mark.asyncio
    async def test_sends_merge_card(self, baseline_module):
        event = MagicMock()
        event.payload = {"topic": "用户反馈", "github_path": "docs/prd/prd-用户反馈.md"}
        baseline_module.github.read_file.return_value = "# 用户反馈\n\n反馈收集系统"
        await baseline_module.on_prd_finalized(event)
        baseline_module.lark.send_card.assert_called_once()


class TestCardAction:
    @pytest.mark.asyncio
    async def test_confirm_merge_adds_to_tracking(self, baseline_module):
        baseline_module._storage.read_json.side_effect = None
        baseline_module._storage.read_json.return_value = {"features": {}}
        baseline_module.github.read_file.return_value = "# Baseline\n\n## 功能清单\n\n### ⬚ 待开发\n\n## 里程碑\n"
        baseline_module._storage.read_yaml.side_effect = FileNotFoundError
        event = MagicMock()
        event.payload = {"action": {"value": {
            "action": "confirm_baseline_merge", "topic": "反馈系统", "prd_path": "prd-反馈系统.md",
        }}}
        await baseline_module.on_card_action(event)
        baseline_module._storage.write_json.assert_called()
        baseline_module.lark.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_ignores_unknown_actions(self, baseline_module):
        event = MagicMock()
        event.payload = {"action": {"value": {"action": "accept"}}}
        await baseline_module.on_card_action(event)
        baseline_module.lark.send_text.assert_not_called()


class TestReorganize:
    @pytest.mark.asyncio
    async def test_reorganize_calls_llm(self, baseline_module):
        baseline_module.github.read_file.return_value = "# Baseline\n\n## 功能清单\n"
        baseline_module.llm.chat.return_value = "# Baseline\n\n## 功能清单\n\n### ✅ 已实现\n\n### 🔄 进行中\n\n### ⬚ 待开发\n"
        baseline_module._storage.read_yaml.side_effect = FileNotFoundError
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await baseline_module.on_reorganize(event)
        baseline_module.llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_reorganize_no_baseline(self, baseline_module):
        baseline_module.github.read_file.side_effect = Exception("not found")
        event = MagicMock()
        event.payload = {"chat_id": "oc_test"}
        await baseline_module.on_reorganize(event)
        assert any("未找到" in str(c) for c in baseline_module.lark.send_text.call_args_list)
```

- [ ] **Step 3: Run tests**

Run: `./.venv/bin/pytest tests/test_modules/test_prd_baseline/ -v`

- [ ] **Step 4: Commit**

```bash
git add grove/modules/prd_baseline/handler.py tests/test_modules/test_prd_baseline/test_handler.py
git commit -m "feat: add prd_baseline handler with merge confirmation, PR matching, and reorg"
```

---

## Task 8: Project Scanner Overhaul

**Files:**
- Modify: `grove/modules/project_scanner/prompts.py`
- Modify: `grove/modules/project_scanner/analyzer.py`
- Modify: `grove/modules/project_scanner/handler.py`

This is the largest task. Read all 3 files first, then rewrite.

- [ ] **Step 1: Rewrite prompts.py**

Replace full content of `grove/modules/project_scanner/prompts.py`:

```python
"""Prompt templates for project scanning and baseline generation."""

ARCHITECTURE_ANALYSIS_PROMPT = """\
你是一位资深架构师。根据以下仓库信息，分析项目的技术架构。

目录结构：
{repo_tree}

关键源码（入口文件、模块入口的前 100 行）：
{source_snippets}

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

COMMIT_CLUSTER_PROMPT = """\
你是一位产品经理。将以下 commit messages 按功能分组归纳。

Commit messages：
{commits}

请将这些 commit 按功能单元分组，输出 JSON 数组：
[{{"feature": "功能名称", "commits": ["sha1", "sha2"], "description": "一句话功能描述"}}]

规则：
- 同一个功能的 commit 归为一组
- 纯重构(refactor)、纯测试(test)、纯 CI(ci) 的 commit 归入 "工程维护" 组
- 功能名称要简洁有意义
- 只输出 JSON，不要其他内容
"""

BASELINE_GENERATE_PROMPT = """\
你是一位产品经理。根据以下信息，生成项目基线文档。

项目名称：{project_name}
技术架构：
{architecture}

已识别功能（带状态）：
{features}

GitHub Milestones：
{milestones}

近期开发活动摘要：
{activity_summary}

请生成 Markdown 文档，严格遵循以下结构：

# {project_name} 项目基线文档

> ⚠️ 本文档由 Grove 自动维护。功能清单部分请通过 Grove 指令修改。

## 概述
（从架构和功能推断项目背景和目标用户）

## 技术架构
（直接使用上面的架构分析）

## 功能清单

### ✅ 已实现
（每行格式：- ✅ **功能名** — 描述）

### 🔄 进行中
（每行格式：- 🔄 **功能名** — 描述）

### ⬚ 待开发
（冷启动时此节为空）

## 里程碑与排期
（从 Milestones 生成）

## 近期开发活动
（commit 统计摘要）

用中文。
"""
```

- [ ] **Step 2: Rewrite analyzer.py**

Replace full content of `grove/modules/project_scanner/analyzer.py`:

```python
"""LLM-based project analysis: architecture, feature clustering, baseline generation."""
import json
import logging

from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.prompts import (
    ARCHITECTURE_ANALYSIS_PROMPT,
    COMMIT_CLUSTER_PROMPT,
    BASELINE_GENERATE_PROMPT,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 80


class ProjectAnalyzer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def analyze_architecture(
        self, repo_tree: str, source_snippets: str,
        dependencies: str, readme: str,
    ) -> str:
        prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(
            repo_tree=repo_tree[:3000],
            source_snippets=source_snippets[:4000],
            dependencies=dependencies[:2000],
            readme=readme[:2000],
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请分析架构。"}],
            max_tokens=1024,
        )

    async def cluster_features(self, commits: list[dict]) -> list[dict]:
        """Cluster commits into feature groups. Batches large lists."""
        if not commits:
            return []

        all_clusters: list[dict] = []
        for i in range(0, len(commits), _BATCH_SIZE):
            batch = commits[i:i + _BATCH_SIZE]
            commits_text = "\n".join(f"- {c['sha']} {c['message']}" for c in batch)
            prompt = COMMIT_CLUSTER_PROMPT.format(commits=commits_text)
            try:
                response = await self.llm.chat(
                    system_prompt=prompt,
                    messages=[{"role": "user", "content": "请分组。"}],
                    max_tokens=2048,
                )
                clusters = json.loads(response)
                if isinstance(clusters, list):
                    all_clusters.extend(clusters)
            except Exception:
                logger.warning("Commit clustering failed for batch %d", i // _BATCH_SIZE)

        # Merge clusters with same feature name
        merged: dict[str, dict] = {}
        for c in all_clusters:
            name = c.get("feature", "未分类")
            if name in merged:
                merged[name]["commits"].extend(c.get("commits", []))
            else:
                merged[name] = {
                    "feature": name,
                    "commits": c.get("commits", []),
                    "description": c.get("description", ""),
                }
        return list(merged.values())

    async def generate_baseline(
        self, project_name: str, architecture: str,
        features: list[dict], milestones: str, activity_summary: str,
    ) -> str:
        features_text = "\n".join(
            f"- {f.get('status_icon', '✅')} **{f['name']}** — {f.get('description', '')}"
            for f in features
        )
        prompt = BASELINE_GENERATE_PROMPT.format(
            project_name=project_name,
            architecture=architecture,
            features=features_text,
            milestones=milestones,
            activity_summary=activity_summary,
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请生成基线文档。"}],
            max_tokens=4096,
        )
```

- [ ] **Step 3: Rewrite handler.py**

Replace full content of `grove/modules/project_scanner/handler.py`:

```python
"""Project Scanner module — scan repo, generate unified baseline document."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.analyzer import ProjectAnalyzer

logger = logging.getLogger(__name__)

_KEY_FILE_PATTERNS = (
    "main.py", "app.py", "index.ts", "index.js", "mod.rs",
    "routes.py", "urls.py", "router.py", "router.ts",
    "config.py", "settings.py",
)
_MAX_KEY_FILES = 50
_MAX_FILE_SIZE = 50_000  # 50KB


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

    @subscribe(EventType.LARK_CARD_ACTION)
    async def on_card_action(self, event: Event) -> None:
        action_data = event.payload.get("action", {}).get("value", {})
        action = action_data.get("action", "")
        if action == "confirm_cold_start":
            self._storage.write_yaml("memory/project-scan/baseline-confirmed.yml",
                {"confirmed": True, "date": datetime.now(timezone.utc).isoformat()})
            await self.lark.send_text(self.config.lark.chat_id, "基线文档已确认生效！")
        elif action == "adjust_cold_start":
            await self.lark.send_text(self.config.lark.chat_id,
                "请在飞书文档中编辑后，再次发送「扫描项目」确认。")

    async def _run_scan(self, chat_id: str) -> None:
        repo = self.config.project.repo
        is_cold_start = not self._is_baseline_confirmed()

        # Data collection
        tree = self.github.get_repo_tree(repo)
        readme = self._safe_read_file(repo, "README.md")
        deps = self._collect_dependencies(repo)
        source_snippets = self._read_key_sources(repo, tree)
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        commits = self.github.list_recent_commits_detailed(repo, since=since, max_commits=500)
        milestones = self.github.list_milestones(repo)
        open_prs = self.github.list_open_prs(repo)

        if not tree and not commits:
            await self.lark.send_text(chat_id,
                "项目数据不足，无法生成文档。请至少提交一些代码和 README 后再试。")
            return

        # LLM analysis
        tree_text = self._format_tree(tree)
        architecture = await self._analyzer.analyze_architecture(
            tree_text, source_snippets, deps, readme)
        clusters = await self._analyzer.cluster_features(commits)

        # Determine feature status
        open_pr_texts = " ".join(pr.get("title", "") for pr in open_prs)
        features = []
        for cluster in clusters:
            if cluster["feature"] == "工程维护":
                continue
            is_in_progress = any(
                cluster["feature"].lower() in open_pr_texts.lower()
                for _ in [None]
            ) if open_pr_texts else False
            status = "in_progress" if is_in_progress else "completed"
            icon = "🔄" if is_in_progress else "✅"
            features.append({
                "name": cluster["feature"],
                "description": cluster.get("description", ""),
                "status": status,
                "status_icon": icon,
            })

        milestones_text = "\n".join(
            f"- {m['title']}: {m['closed_issues']}/{m['open_issues'] + m['closed_issues']} "
            f"(due: {m.get('due_on', 'N/A')})" for m in milestones
        ) or "暂无"

        activity = f"最近 90 天共 {len(commits)} 次提交，涉及 {len(clusters)} 个功能模块。"

        baseline_content = await self._analyzer.generate_baseline(
            self.config.project.name, architecture, features, milestones_text, activity,
        )

        # Save feature tracking
        tracking = {"features": {}}
        for f in features:
            tracking["features"][f["name"]] = {
                "status": f["status"],
                "description": f["description"],
                "related_prs": [],
                "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        self._storage.write_json("memory/project-scan/feature-tracking.json", tracking)

        # Output: single baseline document
        doc_id = await self._output_baseline(baseline_content)

        # Save metadata
        self._storage.write_json("memory/project-scan/latest-scan.json", {
            "date": datetime.now(timezone.utc).isoformat(),
            "commit_count": len(commits),
            "feature_count": len(features),
        })

        # Migration: clean up old files
        self._migrate_old_files(repo)

        if is_cold_start:
            # Send confirmation card
            from grove.integrations.lark.cards import build_notification_card
            card = build_notification_card(
                "🌳 Grove — 基线文档确认",
                f"项目基线文档已生成（{len(features)} 个功能）。请审阅后确认。",
                color="green",
            )
            # Manually add action buttons
            card["elements"].append({
                "tag": "action", "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认"},
                     "type": "primary", "value": {"action": "confirm_cold_start"}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "📝 需要调整"},
                     "value": {"action": "adjust_cold_start"}},
                ],
            })
            await self.lark.send_card(chat_id, card)
        else:
            await self.lark.send_text(chat_id,
                f"项目扫描完成！基线文档已更新（{len(features)} 个功能）。")

    async def _output_baseline(self, content: str) -> str | None:
        repo = self.config.project.repo
        doc_id = None

        # Try to reuse existing doc (migration-aware)
        existing_id = self._get_baseline_doc_id()
        try:
            if existing_id:
                await self.lark.update_doc(existing_id, content)
                doc_id = existing_id
            else:
                doc_id = await self.lark.create_doc(
                    self.config.lark.space_id,
                    f"[{self.config.project.name}] 项目基线文档",
                    content,
                )
                self._storage.write_yaml("memory/project-scan/baseline-doc-id.yml", {"doc_id": doc_id})
        except Exception:
            logger.exception("Lark baseline doc failed")

        try:
            self.github.write_file(repo, "docs/project-baseline.md", content,
                                   "docs: update project baseline")
        except Exception:
            logger.exception("GitHub baseline write failed")

        return doc_id

    def _get_baseline_doc_id(self) -> str | None:
        """Get doc_id, with migration fallback to old path."""
        for path in ["memory/project-scan/baseline-doc-id.yml",
                      "memory/project-scan/reverse-prd-doc-id.yml"]:
            try:
                data = self._storage.read_yaml(path)
                return data.get("doc_id")
            except FileNotFoundError:
                continue
        return None

    def _is_baseline_confirmed(self) -> bool:
        try:
            data = self._storage.read_yaml("memory/project-scan/baseline-confirmed.yml")
            return data.get("confirmed", False)
        except FileNotFoundError:
            return False

    def _migrate_old_files(self, repo: str) -> None:
        """Clean up old dual-document files."""
        for old_path in ["docs/prd/project-prd-draft.md", "docs/development-status.md"]:
            try:
                self.github.read_file(repo, old_path)
                self.github.write_file(repo, old_path,
                    "本文档已合并到 docs/project-baseline.md，请查看新文档。",
                    f"docs: deprecate {old_path} in favor of project-baseline.md")
            except Exception:
                pass

        # Rename storage file
        old_storage = self._storage.root / "memory" / "project-scan" / "reverse-prd-doc-id.yml"
        new_storage = self._storage.root / "memory" / "project-scan" / "baseline-doc-id.yml"
        if old_storage.exists() and not new_storage.exists():
            old_storage.rename(new_storage)

    def _read_key_sources(self, repo: str, tree: list[dict]) -> str:
        """Read first 100 lines of key source files."""
        candidates = []
        for item in tree:
            if item["type"] != "blob" or item.get("size", 0) > _MAX_FILE_SIZE:
                continue
            filename = item["path"].split("/")[-1]
            depth = item["path"].count("/")
            # Match key file patterns
            if filename in _KEY_FILE_PATTERNS:
                candidates.append(item["path"])
            elif filename == "__init__.py" and depth <= 1:
                candidates.append(item["path"])
            elif filename.startswith("index.") and depth <= 1:
                candidates.append(item["path"])

        snippets = []
        for path in candidates[:_MAX_KEY_FILES]:
            try:
                content = self.github.read_file_head(repo, path, max_lines=100)
                snippets.append(f"=== {path} ===\n{content}")
            except Exception:
                continue
        return "\n\n".join(snippets)

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
            if depth <= max_depth:
                prefix = "  " * depth
                name = item["path"].split("/")[-1]
                icon = "📁" if item["type"] == "tree" else "📄"
                lines.append(f"{prefix}{icon} {name}")
        return "\n".join(lines[:200])
```

- [ ] **Step 4: Update scanner tests**

Read and update `tests/test_modules/test_project_scanner/test_handler.py` — the `test_scan_calls_analyzer` test needs updating since `analyze_features` is now `cluster_features` and `generate_reverse_prd` is now `generate_baseline`. Also fix the mock setup.

- [ ] **Step 5: Run tests**

Run: `./.venv/bin/pytest tests/test_modules/test_project_scanner/ -v`

Then full: `./.venv/bin/pytest tests/ -v --tb=short`

- [ ] **Step 6: Commit**

```bash
git add grove/modules/project_scanner/ tests/test_modules/test_project_scanner/
git commit -m "refactor: overhaul Project Scanner for unified baseline, source reading, cold start"
```

---

## Task 9: Communication Enhancement — REORGANIZE_BASELINE Intent

**Files:**
- Modify: `grove/modules/communication/intent_parser.py:79`
- Modify: `grove/modules/communication/handler.py:90-91`

- [ ] **Step 1: Add keyword rule and intent**

In `grove/modules/communication/intent_parser.py`:

a) Add to `Intent` enum (after `DISPATCH_NEGOTIATE`, line 33):
```python
    REORGANIZE_BASELINE = "reorganize_baseline"
```

b) Add to `MODULE_ALIASES` (after `"每日任务": "morning_dispatch"`, line 58):
```python
    "基线管理": "prd_baseline", "prd基线": "prd_baseline",
```

c) Add to `_KEYWORD_RULES` (after the project overview entry, line 80):
```python
    (["整理基线", "重排基线", "基线整理"], Intent.REORGANIZE_BASELINE),
```

- [ ] **Step 2: Add route in handler.py**

In `grove/modules/communication/handler.py`, before the `else:` clause (line 91), add:

```python
        elif parsed.intent == Intent.REORGANIZE_BASELINE:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_REORGANIZE_BASELINE, source="internal",
                payload={"chat_id": chat_id}, member=event.member,
            ))
```

Also add `"prd_baseline": "PRD 基线"` to both `MODULE_DISPLAY` dicts (lines 141 and 163).

- [ ] **Step 3: Run tests**

Run: `./.venv/bin/pytest tests/test_modules/test_communication/ -v`

- [ ] **Step 4: Commit**

```bash
git add grove/modules/communication/
git commit -m "feat: add reorganize_baseline intent and prd_baseline module display"
```

---

## Task 10: Wire prd_baseline in main.py + conftest

**Files:**
- Modify: `grove/main.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add import to main.py**

After line 35 (`from grove.modules.morning_dispatch.handler import MorningDispatchModule`), add:

```python
from grove.modules.prd_baseline.handler import PRDBaselineModule
```

- [ ] **Step 2: Instantiate prd_baseline**

After `morning_dispatch` instantiation (line 152), add:

```python
    prd_baseline = PRDBaselineModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )
```

- [ ] **Step 3: Register with registry**

After `morning_dispatch` registration (line 164), add:

```python
    registry.add("prd_baseline", prd_baseline, enabled=effective_modules["prd_baseline"])
```

- [ ] **Step 4: Update conftest.py**

Add `prd_baseline: true` to the modules section in `sample_config_yml`.

- [ ] **Step 5: Run full test suite**

Run: `./.venv/bin/pytest tests/ -v --tb=short`

- [ ] **Step 6: Run lint**

Run: `./.venv/bin/ruff check grove/ tests/`

- [ ] **Step 7: Commit**

```bash
git add grove/main.py tests/conftest.py
git commit -m "feat: wire prd_baseline module into main.py"
```

---

## Task 11: Final Verification

- [ ] **Step 1: Full test suite**

Run: `./.venv/bin/pytest tests/ -v --tb=short`

- [ ] **Step 2: Lint**

Run: `./.venv/bin/ruff check grove/ tests/ --fix`

- [ ] **Step 3: Import check**

Run: `./.venv/bin/python -c "from grove.main import app; print('Import OK')"`

- [ ] **Step 4: Fix any issues and commit**

```bash
git add -A
git commit -m "fix: resolve remaining lint and test issues from baseline merge"
```
