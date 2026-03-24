# PRD Baseline Merge Design

## Overview

将逆向 PRD 和开发状态文档合并为一份「项目基线文档」，新增 prd_baseline 模块自动管理基线生命周期：新需求合并、功能进度追踪（含新功能自动发现）、基线整理。改造 Project Scanner 支持冷启动确认和关键源码读取。

**变更范围：** 1 个新模块 + 1 个模块改造 + GitHub Client / Lark Cards / Communication 增强

---

## 1. 统一基线文档

### 合并原因

原来 Project Scanner 输出两份文档（逆向 PRD + 开发状态），内容重叠度高（技术架构、已实现功能、里程碑三个章节重复）。合并为一份 `project-baseline.md`。

### 文档格式

```markdown
# [项目名] 项目基线文档

> ⚠️ 本文档由 Grove 自动维护。功能清单部分请通过 Grove 指令修改。

## 概述
（项目背景、目标用户）

## 技术架构
（技术栈、模块划分、层次架构）

## 功能清单

### ✅ 已实现
- ✅ **用户登录** — OAuth2 登录系统 `#PR-12`
- ✅ **数据导出** — 支持 CSV/Excel 导出 `#PR-25`

### 🔄 进行中
- 🔄 **用户反馈系统** — 反馈收集与分析 → [详细 PRD](prd-用户反馈系统.md)

### ⬚ 待开发
- ⬚ **数据分析仪表盘** — 可视化统计 → [详细 PRD](prd-数据分析仪表盘.md)

## 里程碑与排期
（从 GitHub Milestones 生成）

## 近期开发活动
（最近 90 天 commit 统计，每次扫描刷新）
```

### 存储路径

- GitHub: `docs/project-baseline.md`
- 飞书 Wiki: doc_id 存于 `.grove/memory/project-scan/baseline-doc-id.yml`

替代原来的 `project-prd-draft.md` + `development-status.md` + `reverse-prd-doc-id.yml`。

---

## 2. Project Scanner 改造

### 源码读取策略

在 `get_repo_tree` 获取目录树之后，额外读取关键源码文件的前 100 行：

```
筛选规则（从目录树自动识别）：
  1. 入口文件：main.py, app.py, index.ts, mod.rs
  2. 顶层包 __init__.py
  3. 路由/API：**/routes.*, **/urls.*, **/api/ 入口文件, **/router.*
  4. 配置文件：config.*, settings.*, *.config.js/ts
  5. 模块入口：每个一级子目录下的 __init__.py 或 index.*

每个文件只读前 100 行（类定义、函数签名、导入）
总量上限：50 个文件
```

### GitHub Client 新增方法

```python
def read_file_head(self, repo: str, path: str, max_lines: int = 100) -> str:
    """读取文件前 N 行。"""
```

### 功能推导改造

原来的 commit 分析是按类型聚合（feature 4 个、bugfix 2 个）。改为按功能聚类：

LLM 将 commit messages 分组归纳为功能单元，结合关键源码内容判断：
- 有对应代码 + 只有 merged PR → ✅ 已实现
- 有 open PR 涉及 → 🔄 进行中
- 冷启动不产生 ⬚ 待开发

### 冷启动流程

```
"扫描项目"（首次，baseline-confirmed 不存在）
  ↓
数据采集：
  ├── 目录树
  ├── 关键源码（前 100 行，≤50 个文件）
  ├── README + 依赖文件
  ├── commit messages（近 90 天，Claude 写的，质量高）
  ├── Open PRs + Merged PRs 列表
  └── Milestones
  ↓
LLM 分析：
  1. 架构分析（不变）
  2. 功能推导（commit 按功能聚类 + 源码辅助）
  3. 基线文档生成（单份文档）
  ↓
生成基线草稿 → 飞书 Wiki + GitHub
  ↓
发飞书确认卡片：[✅ 确认] [📝 需要调整]
  确认 → latest-scan.json 写入 baseline-confirmed: true
  调整 → 提示在飞书编辑后再确认
```

### 后续扫描 vs 首次扫描

| | 首次（冷启动） | 后续 |
|---|-------------|------|
| 功能来源 | commit + 代码逆向推导 | 基线已有 + 增量 |
| 状态判断 | LLM 从 PR/代码推断 | prd_baseline 模块自动维护 |
| 审阅方式 | 飞书确认卡片 | 无需确认 |
| 兜底对比 | 不需要（首次全量） | 对比推导结果 vs 基线，发现遗漏 |

### 扫描兜底对比

后续"扫描项目"时，在功能推导完成后增加一步：

```
对比 LLM 推导出的功能列表 vs 基线中已有的功能
  ↓ 发现基线中没有的
飞书汇总卡片：
  "扫描发现以下功能未在基线中记录：
   · XX 功能（推测已实现）
   · YY 功能（推测进行中）
   确认添加到基线？"
  [✅ 全部添加] [📝 逐个确认]
```

---

## 3. PRD 基线合并模块（prd_baseline）

新建独立模块，负责基线文档的自动维护。

### 触发点 1：新需求 PRD 合并

```
INTERNAL_PRD_FINALIZED
  ↓ prd_baseline 监听
发飞书确认卡片："是否将「用户反馈系统」合并到项目基线？"
  [✅ 合并] [❌ 暂不合并]
  ↓ 确认（LARK_CARD_ACTION）
结构化追加到基线"⬚ 待开发"章节：
  - ⬚ **用户反馈系统** — 反馈收集与分析 → [详细 PRD](prd-用户反馈系统.md)
同步飞书 Wiki + GitHub
更新 feature-tracking.json
```

### 触发点 2：PR 合并 → 功能状态更新

```
PR_MERGED
  ↓ prd_baseline 监听（与 Doc Sync 独立）
读取基线中 🔄 进行中 + ⬚ 待开发的功能列表
读取 PR 关联的 commit messages
LLM 匹配 → 输出：
  {
    "match_type": "existing" | "new" | "none",
    "matched_feature": "功能名",
    "status": "in_progress" | "completed",
    "confidence": 0.85,
    "reason": "理由"
  }
```

#### 匹配类型

| match_type | 含义 |
|-----------|------|
| `existing` | 匹配到基线中已有的功能 |
| `new` | 全新功能，基线中没有 |
| `none` | 不涉及功能变更（重构、bugfix 等） |

#### 处理规则

| match_type | confidence | status | 基线操作 | 通知方式 |
|-----------|------------|--------|---------|---------|
| existing | > 0.8 | completed | → ✅ | 飞书文字："PR #N 完成了「XX」，已更新基线" |
| existing | > 0.8 | in_progress | ⬚→🔄（首次） | 飞书文字："PR #N 开始了「XX」开发" |
| existing | > 0.8 | in_progress | 🔄 保持 | 不通知（避免频繁打扰） |
| existing | 0.5-0.8 | 任意 | 发卡片确认 | 飞书卡片 [✅ 确认] [❌ 不相关] |
| new | > 0.7 | 任意 | 自动添加到 🔄 | 飞书文字："检测到新功能「XX」" |
| new | 0.5-0.7 | 任意 | 发卡片确认 | 飞书卡片"是否为新功能？" |
| none 或 < 0.5 | — | — | 忽略 | 无 |

#### LLM 匹配 Prompt

```
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

输出 JSON：
{"match_type": "existing"|"new"|"none", "matched_feature": "功能名"|null, "status": "in_progress"|"completed"|null, "confidence": 0.0-1.0, "reason": "理由"}

不要强行匹配。宁可返回 none 也不要低置信度的猜测。
```

### 触发点 3：手动整理

```
飞书 "整理基线"
  ↓ INTERNAL_REORGANIZE_BASELINE
LLM 读取基线全文 + 各功能详细 PRD → 重新整理排版
同步飞书 Wiki + GitHub
```

### 结构化 Markdown 操作

不经过 LLM，直接操作 Markdown 文本：

```python
# baseline_editor.py

def parse_features(baseline_content: str) -> dict[str, list[dict]]:
    """解析基线文档，返回 {"done": [...], "in_progress": [...], "planned": [...]}"""

def append_feature(baseline_content: str, section: str, entry: str) -> str:
    """在指定章节末尾追加条目。section: "done"|"in_progress"|"planned" """

def move_feature(baseline_content: str, feature_name: str, from_section: str, to_section: str) -> str:
    """将功能从一个章节移到另一个，修改前缀标记"""

def format_feature_entry(name: str, description: str, status: str, prd_path: str | None = None, pr_number: int | None = None) -> str:
    """生成标准格式的功能条目"""
```

### 功能状态索引

```
.grove/memory/project-scan/feature-tracking.json
```

```json
{
  "features": {
    "用户反馈系统": {
      "status": "in_progress",
      "prd_path": "prd-用户反馈系统.md",
      "related_prs": [101, 105],
      "added_at": "2026-03-24",
      "updated_at": "2026-03-24"
    }
  }
}
```

基线文档是面向人的 Markdown，此 JSON 是面向程序的快速索引。两者保持同步。

### 与现有模块的关系

```
PRD Generator ──INTERNAL_PRD_FINALIZED──→ prd_baseline（确认 → 追加基线）
PR_MERGED ──→ Doc Sync（更新独立 PRD 文档内容）
          ──→ prd_baseline（匹配功能状态 → 更新基线）
Communication ──"整理基线"──→ prd_baseline（LLM 重排版）
Project Scanner ──扫描后──→ 兜底对比（发现遗漏功能）
```

四个模块独立运行，通过事件总线松耦合。

---

## 4. 事件、配置与接线

### 新增 EventType（1 个）

```python
INTERNAL_REORGANIZE_BASELINE = "internal.reorganize_baseline"
```

其他全部复用已有事件（INTERNAL_PRD_FINALIZED、PR_MERGED、LARK_CARD_ACTION、ISSUE_COMMENTED）。

### Communication 新增意图

```
REORGANIZE_BASELINE — "整理基线" / "重排基线"
```

### 新增飞书卡片（2 个）

```python
build_baseline_merge_card(topic, summary, prd_path)
  # "是否将「XX」合并到项目基线？"
  # [✅ 合并] [❌ 暂不合并]

build_feature_status_card(pr_number, feature_name, suggested_status, reason)
  # "PR #123 可能完成了「XX」，确认吗？"
  # [✅ 确认] [❌ 不相关]
```

### 配置变更

```yaml
modules:
  prd_baseline: true
```

### Pydantic 模型

```python
# ModulesConfig 新增
prd_baseline: bool = True

# merge_module_state 新增
"prd_baseline": modules_cfg.prd_baseline,
```

---

## 5. 文件结构

### 新增文件（7 个）

```
grove/modules/prd_baseline/
  __init__.py
  handler.py           # 主流程：合并确认、PR 匹配、整理
  baseline_editor.py   # 结构化 Markdown 操作
  matcher.py           # LLM 功能匹配（existing/new/none）
  prompts.py           # 匹配 prompt + 整理 prompt

tests/test_modules/test_prd_baseline/
  __init__.py
  test_baseline_editor.py
  test_handler.py
```

### 修改文件（13 个）

```
grove/core/events.py                            # +1 EventType
grove/config.py                                  # +1 模块开关
grove/core/module_registry.py                    # +1 merge_module_state
grove/main.py                                    # 注册 prd_baseline 模块

grove/modules/communication/intent_parser.py     # +1 Intent
grove/modules/communication/prompts.py           # +1 意图描述
grove/modules/communication/handler.py           # +1 路由

grove/integrations/github/client.py              # +read_file_head
grove/integrations/lark/cards.py                 # +2 卡片

grove/modules/project_scanner/handler.py         # 单文档输出 + 首次确认 + 兜底对比
grove/modules/project_scanner/analyzer.py        # commit 聚类 + 源码辅助
grove/modules/project_scanner/prompts.py         # prompt 更新

tests/conftest.py                                # 配置更新
```

---

## 6. 变更总结

| 变更 | 新文件 | 修改文件 | 复杂度 |
|------|--------|----------|--------|
| prd_baseline 模块 | 5 | 0 | 中 |
| 事件 + 配置 + 注册 | 0 | 4 | 低 |
| Communication 增强 | 0 | 3 | 低 |
| GitHub Client + Lark Cards | 0 | 2 | 低 |
| Project Scanner 改造 | 0 | 3 | 中 |
| 测试 | 2 | 1 | — |
| **合计** | **7** | **13** | — |

## 7. 建议实现顺序

1. **事件 + 配置 + 注册** — 基础设施
2. **GitHub Client `read_file_head`** — Project Scanner 依赖
3. **Project Scanner 改造** — 单文档输出 + 源码读取 + 首次确认 + 兜底对比
4. **Lark Cards** — 2 个新卡片
5. **prd_baseline 模块** — 核心（baseline_editor → matcher → handler）
6. **Communication 增强** — "整理基线" 意图
7. **main.py 接线 + 测试**
