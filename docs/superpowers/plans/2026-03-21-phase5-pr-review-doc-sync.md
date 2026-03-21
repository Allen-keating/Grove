# Phase 5: PR 审查 + 文档反向同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a PR is opened, automatically review it against PRD requirements and post an alignment assessment. When a PR is merged, detect product-level code changes, classify their severity, and update Lark PRD documents accordingly (auto for small changes, confirm for medium, discuss for large).

**Architecture:** Two new modules: `pr_review/` subscribes to `pr.opened`, fetches the diff + related PRD, uses LLM to assess requirement alignment, and posts a GitHub comment. `doc_sync/` subscribes to `pr.merged` and `cron.doc_drift_check`, classifies changes as product-level vs technical, grades severity (small/medium/large), and updates Lark docs or sends confirmation cards. Both share a `diff_analyzer` utility for extracting product-relevant changes from diffs.

**Tech Stack:** Existing Grove infrastructure. GitHub API (get_pr_diff, add_pr_comment). Lark Docs API (read_doc, update_doc). LLM for alignment analysis and change classification.

**Spec:** `docs/superpowers/specs/2026-03-21-grove-architecture-design.md` (Sections 4.1, 8 Phase 5)

**Scope:** Phase 5 only (weeks 9-11). Depends on Phases 1-4.

**Verification criteria (from spec):**
- 新 PR → 自动收到需求对齐评论
- PR 合并后 → 飞书 PRD 自动/半自动更新
- 每日报告包含「文档同步状态」板块

---

## File Structure

```
grove/
├── modules/
│   ├── pr_review/
│   │   ├── __init__.py
│   │   ├── handler.py                 # Subscribe pr.opened → alignment review
│   │   └── prompts.py                 # Prompts for PR alignment analysis
│   │
│   └── doc_sync/
│       ├── __init__.py
│       ├── handler.py                 # Subscribe pr.merged, cron.doc_drift_check
│       ├── diff_classifier.py         # Classify changes: product vs tech, small/medium/large
│       ├── doc_updater.py             # Update Lark docs based on classification
│       └── prompts.py                 # Prompts for change classification + doc translation
│
├── integrations/lark/
│   └── cards.py                       # MODIFY: add build_doc_change_card
│
├── main.py                            # MODIFY: register new modules
│
└── tests/test_modules/
    ├── test_pr_review/
    │   ├── __init__.py
    │   └── test_handler.py
    └── test_doc_sync/
        ├── __init__.py
        ├── test_diff_classifier.py
        ├── test_doc_updater.py
        └── test_handler.py
```

---

### Task 1: PR Review Prompts

**Files:**
- Create: `grove/modules/pr_review/__init__.py`
- Create: `grove/modules/pr_review/prompts.py`

- [ ] **Step 1: Create prompts.py**

```python
# grove/modules/pr_review/prompts.py
"""Prompts for PR requirement alignment analysis."""

PR_ALIGNMENT_PROMPT = """\
你是 Grove，AI 产品经理。你正在从产品角度 review 一个 PR，判断代码实现是否与需求文档对齐。

注意：你只做产品层面的 review（需求对齐），不做代码质量 review。

PR 信息：
- PR #{pr_number}: {pr_title}
- 关联 Issue: {related_issues}

代码变更摘要（diff）：
{diff_summary}

需求文档（PRD 相关章节）：
{prd_content}

请分析并输出以下内容（Markdown 格式）：

## 🌳 Grove — 需求对齐检查

### 对齐度评估
（代码实现与需求的整体对齐情况，一句话概括）

### ✅ 已覆盖的需求
（列出代码已经实现的需求点）

### ⚠️ 遗漏项
（需求中要求但代码未实现的部分，如果没有则写"无"）

### 📌 超出范围
（代码中有但需求未提及的改动，如果没有则写"无"）

### 建议
（如有，给出具体建议）
"""

DIFF_SUMMARY_PROMPT = """\
请用简洁的中文总结以下代码变更（diff），重点关注产品功能层面的变化：
- 新增了什么功能/接口
- 修改了什么行为
- 删除了什么

忽略纯格式、注释、测试文件的变更。

Diff:
{diff}

只输出产品层面的变更摘要，每条一行，用 "- " 开头。
"""
```

- [ ] **Step 2: Commit**

```bash
git add grove/modules/pr_review/
git commit -m "feat: PR alignment review prompts"
```

---

### Task 2: PR Review Handler

**Files:**
- Create: `grove/modules/pr_review/handler.py`
- Test: `tests/test_modules/test_pr_review/test_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_pr_review/test_handler.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.modules.pr_review.handler import PRReviewModule


class TestPRReviewModule:
    @pytest.fixture
    def module(self):
        bus = EventBus()
        llm = MagicMock()
        llm.chat = AsyncMock(return_value="- 新增了登录页面组件")
        lark = MagicMock()
        lark.send_text = AsyncMock()
        lark.read_doc = AsyncMock(return_value="# 登录模块 PRD\n\n需要实现登录页面...")
        github = MagicMock()
        github.get_pr_diff = MagicMock(return_value="diff --git a/login.py...")
        github.add_pr_comment = MagicMock()
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"
        config.lark.space_id = "spc_test"

        module = PRReviewModule(bus=bus, llm=llm, lark=lark, github=github, config=config)
        bus.register(module)
        return module, bus

    async def test_pr_opened_posts_review_comment(self, module):
        mod, bus = module
        # Second LLM call returns the alignment review
        call_count = 0
        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "- 新增了登录页面组件"
            return "## 🌳 Grove — 需求对齐检查\n\n### 对齐度评估\n代码与需求基本对齐。"

        mod.llm.chat = AsyncMock(side_effect=mock_chat)

        event = Event(
            type=EventType.PR_OPENED, source="github",
            payload={
                "pull_request": {"number": 45, "title": "Add login page", "body": "Fixes #23"},
                "repository": {"full_name": "org/repo"},
            },
            member=Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend"),
        )
        await bus.dispatch(event)

        mod.github.get_pr_diff.assert_called_once()
        mod.github.add_pr_comment.assert_called_once()
        # Comment should contain alignment review
        comment_body = mod.github.add_pr_comment.call_args[1].get("body") or mod.github.add_pr_comment.call_args[0][2]
        assert "Grove" in comment_body

    async def test_pr_without_diff_skips(self, module):
        mod, bus = module
        mod.github.get_pr_diff = MagicMock(side_effect=Exception("API error"))

        event = Event(
            type=EventType.PR_OPENED, source="github",
            payload={
                "pull_request": {"number": 99, "title": "Test", "body": ""},
                "repository": {"full_name": "org/repo"},
            },
        )
        await bus.dispatch(event)
        mod.github.add_pr_comment.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_pr_review/test_handler.py -v`

- [ ] **Step 3: Implement handler.py**

```python
# grove/modules/pr_review/handler.py
"""PR Review module — requirement alignment checking."""

import logging
import re

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.pr_review.prompts import PR_ALIGNMENT_PROMPT, DIFF_SUMMARY_PROMPT

logger = logging.getLogger(__name__)


class PRReviewModule:
    """Review PRs for requirement alignment (product-level, not code quality)."""

    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config

    @subscribe(EventType.PR_OPENED)
    async def on_pr_opened(self, event: Event) -> None:
        pr_data = event.payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        pr_title = pr_data.get("title", "")
        pr_body = pr_data.get("body", "") or ""
        repo = event.payload.get("repository", {}).get("full_name", self.config.project.repo)

        logger.info("Reviewing PR #%s: %s", pr_number, pr_title)

        # 1. Get PR diff
        try:
            diff = self.github.get_pr_diff(repo, pr_number)
        except Exception:
            logger.exception("Failed to get diff for PR #%s", pr_number)
            return

        # 2. Summarize diff (product perspective)
        diff_summary = await self.llm.chat(
            system_prompt=DIFF_SUMMARY_PROMPT.format(diff=diff[:8000]),
            messages=[{"role": "user", "content": "请总结代码变更。"}],
            max_tokens=512,
        )

        # 3. Extract related issue numbers from PR body
        related_issues = re.findall(r"#(\d+)", pr_body)
        related_str = ", ".join(f"#{n}" for n in related_issues) if related_issues else "无关联 Issue"

        # 4. Try to read related PRD content
        prd_content = "未找到关联的 PRD 文档。"
        try:
            # Read from sync copies in .grove/docs-sync/ or Lark
            prd_content = await self.lark.read_doc(self.config.lark.space_id)
        except Exception:
            logger.debug("Could not read PRD for PR #%s", pr_number)

        # 5. LLM alignment analysis
        review = await self.llm.chat(
            system_prompt=PR_ALIGNMENT_PROMPT.format(
                pr_number=pr_number, pr_title=pr_title,
                related_issues=related_str, diff_summary=diff_summary,
                prd_content=prd_content[:4000],
            ),
            messages=[{"role": "user", "content": "请进行需求对齐分析。"}],
            max_tokens=1024,
        )

        # 6. Post comment on PR
        self.github.add_pr_comment(repo, pr_number, review)
        logger.info("Posted alignment review on PR #%s", pr_number)

        # 7. If misalignment detected, notify Lark
        if "⚠️" in review and "无" not in review.split("⚠️")[1][:20]:
            await self.lark.send_text(
                self.config.lark.chat_id,
                f"PR #{pr_number}「{pr_title}」需求对齐检查发现遗漏项，请查看 PR 评论。",
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_pr_review/test_handler.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/pr_review/ tests/test_modules/test_pr_review/
git commit -m "feat: PR review module — requirement alignment analysis"
```

---

### Task 3: Diff Classifier

**Files:**
- Create: `grove/modules/doc_sync/__init__.py`
- Create: `grove/modules/doc_sync/diff_classifier.py`
- Create: `grove/modules/doc_sync/prompts.py`
- Test: `tests/test_modules/test_doc_sync/test_diff_classifier.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_doc_sync/test_diff_classifier.py
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.modules.doc_sync.diff_classifier import DiffClassifier, ChangeClassification


class TestChangeClassification:
    def test_create(self):
        c = ChangeClassification(
            is_product_change=True, severity="medium",
            description="新增了微信支付渠道",
            affected_prd_sections=["支付模块"],
        )
        assert c.is_product_change is True
        assert c.severity == "medium"


class TestDiffClassifier:
    @pytest.fixture
    def classifier(self):
        return DiffClassifier(llm=MagicMock())

    async def test_classify_product_change(self, classifier):
        classifier.llm.chat = AsyncMock(return_value=json.dumps({
            "is_product_change": True, "severity": "medium",
            "description": "新增微信支付渠道",
            "affected_prd_sections": ["支付模块"],
        }))
        result = await classifier.classify("diff content here", "PR #45: Add wechat pay")
        assert result.is_product_change is True
        assert result.severity == "medium"

    async def test_classify_tech_refactor(self, classifier):
        classifier.llm.chat = AsyncMock(return_value=json.dumps({
            "is_product_change": False, "severity": "none",
            "description": "纯技术重构",
            "affected_prd_sections": [],
        }))
        result = await classifier.classify("refactor diff", "PR #46: Refactor auth service")
        assert result.is_product_change is False

    async def test_classify_handles_error(self, classifier):
        classifier.llm.chat = AsyncMock(return_value="not json")
        result = await classifier.classify("diff", "PR")
        assert result.is_product_change is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_doc_sync/test_diff_classifier.py -v`

- [ ] **Step 3: Implement diff_classifier.py and prompts.py**

```python
# grove/modules/doc_sync/prompts.py
"""Prompts for document sync change classification and translation."""

CLASSIFY_CHANGE_PROMPT = """\
你是 Grove，AI 产品经理。分析以下代码变更，判断是否为产品级变更。

PR 标题: {pr_title}
代码变更:
{diff}

请判断：
1. 是否是产品级变更（影响用户可见的功能/行为）？还是纯技术重构（不影响产品行为）？
2. 如果是产品级变更，严重程度是什么？
   - small: 参数调整、文案修改等
   - medium: 新增字段、流程微调
   - large: 新功能、架构调整
3. 影响了 PRD 的哪些章节？

以 JSON 格式回复：
{{"is_product_change": true/false, "severity": "none/small/medium/large",
  "description": "变更描述（产品语言）", "affected_prd_sections": ["章节名"]}}

过滤规则（以下变更不算产品级变更）：
- 测试文件（tests/）
- CI/CD 配置（.github/）
- 代码风格/格式化
- 内部重构（接口不变）
- 注释/文档修改

只回复 JSON。
"""

DOC_UPDATE_PROMPT = """\
你是 Grove，AI 产品经理。请根据以下代码变更，用产品语言描述需要更新到 PRD 中的内容。

代码变更描述: {change_description}
影响的 PRD 章节: {affected_sections}
当前 PRD 内容:
{current_prd}

请输出需要添加或修改的 PRD 内容（Markdown 格式）。
- 用产品语言，不要技术术语
- 标注来源 PR 编号
- 简洁明了
"""
```

```python
# grove/modules/doc_sync/diff_classifier.py
"""Classify code changes as product-level vs technical."""

import json
import logging
from dataclasses import dataclass, field

from grove.integrations.llm.client import LLMClient
from grove.modules.doc_sync.prompts import CLASSIFY_CHANGE_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ChangeClassification:
    is_product_change: bool
    severity: str = "none"  # none, small, medium, large
    description: str = ""
    affected_prd_sections: list[str] = field(default_factory=list)


class DiffClassifier:
    """Classify PR diffs as product-level or technical changes."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def classify(self, diff: str, pr_title: str) -> ChangeClassification:
        try:
            prompt = CLASSIFY_CHANGE_PROMPT.format(pr_title=pr_title, diff=diff[:6000])
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请分类此变更。"}],
                max_tokens=512,
            )
            data = json.loads(response)
            return ChangeClassification(
                is_product_change=data.get("is_product_change", False),
                severity=data.get("severity", "none"),
                description=data.get("description", ""),
                affected_prd_sections=data.get("affected_prd_sections", []),
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Diff classification failed: %s", exc)
            return ChangeClassification(is_product_change=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_doc_sync/test_diff_classifier.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/doc_sync/ tests/test_modules/test_doc_sync/
git commit -m "feat: diff classifier — product vs technical change detection"
```

---

### Task 4: Doc Updater

**Files:**
- Create: `grove/modules/doc_sync/doc_updater.py`
- Modify: `grove/integrations/lark/cards.py` — add `build_doc_change_card`
- Test: `tests/test_modules/test_doc_sync/test_doc_updater.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_doc_sync/test_doc_updater.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.modules.doc_sync.doc_updater import DocUpdater
from grove.modules.doc_sync.diff_classifier import ChangeClassification


class TestDocUpdater:
    @pytest.fixture
    def updater(self):
        llm = MagicMock()
        llm.chat = AsyncMock(return_value="更新后的 PRD 内容...")
        lark = MagicMock()
        lark.update_doc = AsyncMock()
        lark.send_text = AsyncMock()
        lark.send_card = AsyncMock()
        lark.read_doc = AsyncMock(return_value="# 当前 PRD\n\n内容...")
        config = MagicMock()
        config.lark.chat_id = "oc_test"
        config.lark.space_id = "spc_test"
        config.doc_sync.auto_update_level = "moderate"
        return DocUpdater(llm=llm, lark=lark, config=config)

    async def test_small_change_auto_updates(self, updater):
        classification = ChangeClassification(
            is_product_change=True, severity="small",
            description="修改超时从30s到60s", affected_prd_sections=["技术约束"])
        await updater.apply(classification, pr_number=45, doc_id="doc123")
        updater.lark.update_doc.assert_called_once()
        updater.lark.send_text.assert_called_once()

    async def test_medium_change_sends_confirmation(self, updater):
        classification = ChangeClassification(
            is_product_change=True, severity="medium",
            description="新增微信支付渠道", affected_prd_sections=["支付模块"])
        await updater.apply(classification, pr_number=45, doc_id="doc123")
        updater.lark.send_card.assert_called_once()
        updater.lark.update_doc.assert_not_called()

    async def test_large_change_sends_discussion(self, updater):
        classification = ChangeClassification(
            is_product_change=True, severity="large",
            description="新增暗黑模式功能", affected_prd_sections=["功能模块"])
        await updater.apply(classification, pr_number=45, doc_id="doc123")
        updater.lark.send_text.assert_called_once()
        assert "讨论" in updater.lark.send_text.call_args[0][1] or "讨论" in str(updater.lark.send_text.call_args)

    async def test_non_product_change_skips(self, updater):
        classification = ChangeClassification(is_product_change=False)
        await updater.apply(classification, pr_number=45, doc_id="doc123")
        updater.lark.update_doc.assert_not_called()
        updater.lark.send_card.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_doc_sync/test_doc_updater.py -v`

- [ ] **Step 3: Implement doc_updater.py + add card to cards.py**

Add to `grove/integrations/lark/cards.py`:

```python
def build_doc_change_card(
    pr_number: int, change_description: str,
    suggested_update: str, doc_id: str,
) -> dict:
    """Build a card for confirming medium-severity doc changes."""
    return {
        "header": {
            "title": {"tag": "plain_text", "content": "🌳 Grove — 文档更新确认"},
            "template": "orange",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**来源：** PR #{pr_number}\n"
                        f"**变更：** {change_description}\n\n"
                        f"**建议更新内容：**\n{suggested_update}"
                    ),
                },
            },
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认更新"},
                     "type": "primary",
                     "value": {"action": "approve_doc_update", "doc_id": doc_id, "pr_number": pr_number}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                     "type": "danger",
                     "value": {"action": "reject_doc_update", "doc_id": doc_id, "pr_number": pr_number}},
                ],
            },
        ],
    }
```

```python
# grove/modules/doc_sync/doc_updater.py
"""Apply document updates based on change classification."""

import logging

from grove.config import GroveConfig
from grove.integrations.lark.cards import build_doc_change_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.doc_sync.diff_classifier import ChangeClassification
from grove.modules.doc_sync.prompts import DOC_UPDATE_PROMPT

logger = logging.getLogger(__name__)


class DocUpdater:
    """Apply document updates based on change severity level."""

    def __init__(self, llm: LLMClient, lark: LarkClient, config: GroveConfig):
        self.llm = llm
        self.lark = lark
        self.config = config

    async def apply(
        self, classification: ChangeClassification,
        pr_number: int, doc_id: str,
    ) -> None:
        if not classification.is_product_change:
            logger.debug("PR #%d: non-product change, skipping doc update", pr_number)
            return

        severity = classification.severity

        if severity == "small":
            await self._auto_update(classification, pr_number, doc_id)
        elif severity == "medium":
            await self._send_confirmation(classification, pr_number, doc_id)
        elif severity == "large":
            await self._send_discussion(classification, pr_number)

    async def _auto_update(self, classification, pr_number, doc_id):
        """Small changes: auto-update the doc and notify."""
        update_content = await self._generate_update(classification, doc_id)
        await self.lark.update_doc(doc_id, update_content)
        await self.lark.send_text(
            self.config.lark.chat_id,
            f"已根据 PR #{pr_number} 自动更新 PRD「{', '.join(classification.affected_prd_sections)}」章节。",
        )

    async def _send_confirmation(self, classification, pr_number, doc_id):
        """Medium changes: send a confirmation card."""
        update_content = await self._generate_update(classification, doc_id)
        card = build_doc_change_card(
            pr_number=pr_number,
            change_description=classification.description,
            suggested_update=update_content[:500],
            doc_id=doc_id,
        )
        await self.lark.send_card(self.config.lark.chat_id, card)

    async def _send_discussion(self, classification, pr_number):
        """Large changes: send a discussion message."""
        await self.lark.send_text(
            self.config.lark.chat_id,
            f"PR #{pr_number} 包含重大产品变更：{classification.description}\n\n"
            f"影响章节：{', '.join(classification.affected_prd_sections)}\n\n"
            f"请团队讨论后确认是否更新 PRD。",
        )

    async def _generate_update(self, classification, doc_id) -> str:
        """Use LLM to generate the doc update content."""
        current_prd = ""
        try:
            current_prd = await self.lark.read_doc(doc_id)
        except Exception:
            pass
        prompt = DOC_UPDATE_PROMPT.format(
            change_description=classification.description,
            affected_sections=", ".join(classification.affected_prd_sections),
            current_prd=current_prd[:4000],
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请生成更新内容。"}],
            max_tokens=1024,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_doc_sync/test_doc_updater.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/doc_sync/doc_updater.py grove/integrations/lark/cards.py tests/test_modules/test_doc_sync/
git commit -m "feat: doc updater with severity-based update strategy"
```

---

### Task 5: Doc Sync Handler

**Files:**
- Create: `grove/modules/doc_sync/handler.py`
- Test: `tests/test_modules/test_doc_sync/test_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modules/test_doc_sync/test_handler.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from grove.core.event_bus import EventBus
from grove.core.events import Event, EventType, Member
from grove.core.storage import Storage
from grove.modules.doc_sync.handler import DocSyncModule
from pathlib import Path


class TestDocSyncModule:
    @pytest.fixture
    def module(self, grove_dir: Path):
        bus = EventBus()
        llm = MagicMock()
        import json
        llm.chat = AsyncMock(return_value=json.dumps({
            "is_product_change": True, "severity": "small",
            "description": "修改超时配置", "affected_prd_sections": ["技术约束"],
        }))
        lark = MagicMock()
        lark.send_text = AsyncMock()
        lark.update_doc = AsyncMock()
        lark.read_doc = AsyncMock(return_value="PRD content")
        github = MagicMock()
        github.get_pr_diff = MagicMock(return_value="diff content")
        storage = Storage(grove_dir)
        config = MagicMock()
        config.project.repo = "org/repo"
        config.lark.chat_id = "oc_test"
        config.lark.space_id = "spc_test"
        config.doc_sync.auto_update_level = "moderate"

        module = DocSyncModule(bus=bus, llm=llm, lark=lark, github=github,
                                config=config, storage=storage)
        bus.register(module)
        return module, bus

    async def test_pr_merged_triggers_classification(self, module):
        mod, bus = module
        event = Event(
            type=EventType.PR_MERGED, source="github",
            payload={
                "pull_request": {"number": 45, "title": "Fix timeout", "merged": True},
                "repository": {"full_name": "org/repo"},
            },
        )
        await bus.dispatch(event)
        mod.github.get_pr_diff.assert_called_once()
        # Should have called LLM for classification
        mod.llm.chat.assert_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modules/test_doc_sync/test_handler.py -v`

- [ ] **Step 3: Implement handler.py**

```python
# grove/modules/doc_sync/handler.py
"""Document sync module — keep PRD in sync with code changes."""

import logging

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.doc_sync.diff_classifier import DiffClassifier
from grove.modules.doc_sync.doc_updater import DocUpdater

logger = logging.getLogger(__name__)


class DocSyncModule:
    """Keep Lark PRD documents in sync with code changes."""

    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._classifier = DiffClassifier(llm=llm)
        self._updater = DocUpdater(llm=llm, lark=lark, config=config)

    @subscribe(EventType.PR_MERGED)
    async def on_pr_merged(self, event: Event) -> None:
        """When a PR is merged, classify changes and update docs if needed."""
        pr_data = event.payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        pr_title = pr_data.get("title", "")
        repo = event.payload.get("repository", {}).get("full_name", self.config.project.repo)

        logger.info("Checking PR #%s for doc sync: %s", pr_number, pr_title)

        # Get diff
        try:
            diff = self.github.get_pr_diff(repo, pr_number)
        except Exception:
            logger.exception("Failed to get diff for PR #%s", pr_number)
            return

        # Classify
        classification = await self._classifier.classify(diff, f"PR #{pr_number}: {pr_title}")

        if not classification.is_product_change:
            logger.info("PR #%s: no product-level changes, skipping doc sync", pr_number)
            return

        logger.info("PR #%s: product change detected (%s) — %s",
                    pr_number, classification.severity, classification.description)

        # Update docs based on severity
        # Use space_id as doc_id placeholder — in production this would map to specific doc
        await self._updater.apply(classification, pr_number, self.config.lark.space_id)

        # Record in sync state
        self._record_sync(pr_number, classification)

    @subscribe(EventType.CRON_DOC_DRIFT_CHECK)
    async def on_doc_drift_check(self, event: Event) -> None:
        """Periodic check for document drift (runs with daily report)."""
        logger.info("Running document drift check...")
        # Read sync state to find recent unsynced PRs
        sync_state = self._get_sync_state()
        if not sync_state.get("pending"):
            logger.info("No pending doc syncs")
            return
        # Report pending items
        pending = sync_state["pending"]
        report = "📄 **文档同步状态**\n\n"
        for item in pending:
            report += f"- ⚠️ PR #{item['pr_number']}: {item['description']}（待确认）\n"
        await self.lark.send_text(self.config.lark.chat_id, report)

    def _record_sync(self, pr_number: int, classification) -> None:
        """Record sync activity to .grove/docs-sync/sync-state.yml."""
        try:
            state = self._get_sync_state()
            if classification.severity in ("medium", "large"):
                state.setdefault("pending", []).append({
                    "pr_number": pr_number,
                    "description": classification.description,
                    "severity": classification.severity,
                })
            else:
                state.setdefault("synced", []).append({
                    "pr_number": pr_number,
                    "description": classification.description,
                })
            self._storage.write_yaml("docs-sync/sync-state.yml", state)
        except Exception:
            logger.exception("Failed to record sync state")

    def _get_sync_state(self) -> dict:
        try:
            return self._storage.read_yaml("docs-sync/sync-state.yml")
        except FileNotFoundError:
            return {"synced": [], "pending": []}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_doc_sync/test_handler.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/modules/doc_sync/handler.py tests/test_modules/test_doc_sync/test_handler.py
git commit -m "feat: doc sync handler — classify merged PRs and update Lark docs"
```

---

### Task 6: Module Registration + Full Suite

**Files:**
- Modify: `grove/main.py`

- [ ] **Step 1: Add imports and registration**

Add imports at top of `grove/main.py`:
```python
from grove.modules.pr_review.handler import PRReviewModule
from grove.modules.doc_sync.handler import DocSyncModule
```

Inside `lifespan`, after existing module registrations, add:
```python
    # PR Review module
    pr_review = PRReviewModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
    )
    event_bus.register(pr_review)
    logger.info("Registered PRReviewModule")

    # Doc Sync module
    doc_sync = DocSyncModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )
    event_bus.register(doc_sync)
    logger.info("Registered DocSyncModule")
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "from grove.main import app; print('OK')"`

- [ ] **Step 3: Run full test suite + lint**

Run: `.venv/bin/pytest -v --tb=short`
Run: `.venv/bin/ruff check grove/ tests/`

- [ ] **Step 4: Fix issues and commit**

```bash
git add -A
git commit -m "feat: register PR review and doc sync modules + Phase 5 complete"
```

---

## Phase 5 Completion Criteria

- [ ] PR opened → diff summarized → alignment analysis → GitHub PR comment posted
- [ ] PR merged → diff classified (product vs tech) → severity graded (small/medium/large)
- [ ] Small changes → Lark doc auto-updated + notification
- [ ] Medium changes → confirmation card sent
- [ ] Large changes → discussion message sent
- [ ] Doc drift check runs daily, reports pending syncs
- [ ] Sync state tracked in `.grove/docs-sync/sync-state.yml`
- [ ] All tests pass, lint clean

**Next:** Create Phase 6 plan (Polish + Open Source Preparation).
