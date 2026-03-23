# Project Management Enhancement Design

## Overview

Grove 新增项目管理能力：从 GitHub 仓库扫描生成逆向 PRD 和已开发文档、增强 commit 监控、管理层项目进度报告、每日任务智能派发与协商确认。

**变更范围：** 3 个新模块 + 2 个模块增强 + GitHub Client 扩展

---

## 1. GitHub Client 增强

所有新模块的数据基础层。

### 新增 API 方法

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `get_repo_tree(repo, path="", recursive=True)` | 仓库目录树扫描 | `[{path, type, size}]` |
| `get_commit_detail(repo, sha)` | 单个 commit 详情含文件变更 | `{sha, message, author, date, files: [{filename, status, additions, deletions}]}` |
| `list_recent_commits_detailed(repo, since, until=None)` | 批量 commit 详情 | `[commit_detail]` |
| `classify_commit(message, files_changed)` | commit 分类 | `"feature" \| "bugfix" \| "refactor" \| "docs" \| "chore"` |

### 设计决策

- **Commit 分类优先用规则匹配**：解析 conventional commit 前缀（`feat:`, `fix:`, `docs:`, `refactor:`），无法判断时 fallback 到 LLM（~64 tokens）
- **`get_repo_tree` 使用 Git Trees API**：单次请求获取完整目录树，比逐层 Contents API 高效
- **并发限制**：`list_recent_commits_detailed` 每个 commit 有额外 API 调用，加入 max 5 concurrent 限制

---

## 2. Project Scanner 模块（新模块）

扫描 GitHub 仓库，逆向生成 PRD 草稿 + 综合已开发文档。

### 触发方式

- 飞书命令手动触发："生成项目文档" / "扫描项目" / "更新项目文档"
- Communication 模块识别意图 `SCAN_PROJECT` → 派发 `INTERNAL_SCAN_PROJECT`

### 处理流程

```
on_scan_project(event):

  1. 通知群："正在扫描项目，请稍候..."

  2. 并行数据采集：
     ├── get_repo_tree() → 目录结构、文件类型统计
     ├── read_file(README.md) → 项目描述
     ├── read_file(requirements.txt / package.json / go.mod) → 依赖
     ├── read_file(Dockerfile / docker-compose.yml) → 部署方式
     ├── read_file(.github/workflows/*) → CI/CD 配置
     ├── list_recent_commits_detailed(since=项目首个commit) → 全量 commit 历史
     ├── list_issues(state="all") → 全部 Issues
     └── list_milestones() → 里程碑

  3. LLM 分步分析（避免超 context）：
     a. 架构分析（~1024 tokens）
        输入：目录树 + 依赖文件 + README
        输出：技术栈、模块划分、层次架构描述

     b. 功能逆向推导（~2048 tokens）
        输入：目录树 + commit 历史摘要 + Issues 标题列表
        输出：已实现功能清单、各功能当前状态

     c. PRD 草稿生成（~4096 tokens）
        输入：架构分析结果 + 功能清单 + Issues/Milestones
        输出：标准 PRD 格式（概述、已实现功能、待开发功能、技术架构、里程碑）

  4. 生成两份文档：
     a. 逆向 PRD → 飞书 Wiki + GitHub docs/prd/project-prd-draft.md
     b. 已开发文档（架构+进度+变更记录）→ 飞书 Wiki + GitHub docs/development-status.md

  5. 通知群：文档链接
```

### 存储

```
.grove/memory/project-scan/
  ├── latest-scan.json        # 最近扫描元数据（时间、commit 范围）
  ├── repo-tree.json          # 目录树快照
  └── reverse-prd-doc-id.yml  # 飞书文档 ID，后续更新用
```

### 设计决策

- **LLM 分步调用**：仓库数据量大，分 3 步分析避免超 context window
- **目录树截断**：忽略 `node_modules/`、`.git/`、`__pycache__/`、`vendor/` 等
- **首次 vs 更新**：检查 `reverse-prd-doc-id.yml`，存在则更新飞书文档而非新建
- **标记为草稿**：逆向 PRD 明确标注需团队补充"未来规划"部分

---

## 3. Project Overview Report 模块（新模块）

面向 PM/管理层的宏观项目进度总览，独立于站会报告。

### 触发方式

- 定时：`CRON_PROJECT_OVERVIEW`（默认每天 10:00）
- 手动：飞书命令 "项目总览" / "项目进度报告"，意图 `QUERY_PROJECT_OVERVIEW`

### 与 Daily Report 的数据源对比

| 维度 | 站会报告 | 管理层报告 |
|------|---------|-----------|
| 时间窗口 | 过去 24h | 项目全周期 + 近 7 天趋势 |
| Commits | 按人计数 | 按类型分类 + 7 天趋势 |
| Issues | Open 数量 | 完成率、新增/关闭趋势、优先级分布 |
| PRs | Open 列表 | 合并速度、Review 周转时间 |
| Milestones | 进度% | 进度% + 预计交付偏差 |
| PRD 基线 | 不涉及 | 对比逆向 PRD：✅已完成/🔄进行中/⬚未开始 |
| 风险 | 战术风险 | 项目级风险（延迟、人力瓶颈、技术债） |

### 处理流程

```
on_project_overview(event):

  1. 并行数据采集：
     ├── list_issues(state="all") → 完成率、趋势
     ├── list_recent_commits_detailed(since=7天前) → 分类统计
     ├── list_open_prs() → 存活时间、review 周转
     ├── list_milestones() → 进度 + due_on 偏差
     ├── storage.read("memory/snapshots/") → 7 天快照（趋势对比）
     └── storage.read("project-scan/reverse-prd-doc-id.yml") → 读取逆向 PRD

  2. 如有逆向 PRD：
     → 读取飞书 PRD 文档，提取功能清单
     → 逐项比对 Issues 状态，标注完成度

  3. LLM 分析（~1024 tokens）：
     输出：健康度评级（🟢/🟡/🔴）、关键风险 top 3、行动建议

  4. 输出：
     a. 飞书卡片：健康度 + 里程碑 + 7天趋势 + PRD完成度 + 风险 + 建议
     b. GitHub Issue：标签 ["project-overview"]，Markdown 完整报告

  5. 保存快照：memory/snapshots/{date}-overview.json
```

### 与 Daily Report 的关系

- 完全独立模块，不共享 handler
- 可复用数据：同一天 Daily Report 已存快照则直接读取，避免重复 API 调用
- 不同时间：站会 9:00，管理层 10:00

---

## 4. Daily Report 增强

在现有站会报告中加入 commit 分类汇总。改动较小。

### 变更

```
collectors.py 返回值增加：
  commits_by_type: {feature: 4, bugfix: 2, refactor: 1, docs: 1}
  commit_details: [{sha, message, author, type, files_changed_count}]
```

### 报告输出变化

飞书卡片"成员动态"部分新增一行：

```
提交分布：feature 4 | bugfix 2 | refactor 1 | docs 1
```

GitHub Issue markdown 同步增加对应表格。

### 性能

- 规则匹配零成本，仅 <20% 情况 fallback LLM
- 24h 内通常 <50 个 commit，API 调用可控

---

## 5. Morning Task Dispatch 模块（新模块）

每日任务智能派发，私聊协商确认后群里公示。

### 触发方式

- 定时：`CRON_MORNING_DISPATCH`（默认每天 09:15）
- 配置：`schedules.morning_dispatch: "09:15"`

### 三阶段流程

#### 阶段一：生成草案（自动）

```
on_morning_dispatch(event):

  1. 并行数据采集：
     ├── list_issues(state="open", labels=["P0","P1","P2"]) → 待办池
     ├── storage.read("member-tasks.yml") → 每人当前负载
     ├── storage.read("snapshots/{yesterday}.json") → 昨日进展
     └── list_milestones() → 里程碑截止压力

  2. LLM 生成每人任务草案（~1024 tokens/人）：
     输入：成员信息、昨日 commit、待办池（按优先级排序）、里程碑截止
     输出 JSON：
       {
         "member": "alice",
         "tasks": [
           {"issue_number": 201, "title": "...", "reason": "P0 且匹配 backend 技能"},
           {"issue_number": 205, "title": "...", "reason": "昨日已开始，建议继续"}
         ],
         "summary": "今日建议重点完成..."
       }

  3. 为每个成员创建 dispatch session：
     存储：.grove/memory/dispatch/{date}/{member_github}.json
     状态：pending → negotiating → confirmed
```

#### 阶段二：私聊协商（每人独立对话）

```
给每个成员发私信：
  "早上好 {name}！以下是今日建议工作内容：

   1. 🔴 P0 #201 反馈提交 API — 昨日已开始，建议继续完成核心逻辑
   2. 🟡 P1 #205 标签分类接口 — 匹配你的 backend 技能

   如需调整请直接告诉我，比如：
   · 「去掉 #205，我今天要处理一个线上 bug」
   · 「加上 #210」
   · 「确认」"

成员回复 → Communication 识别 DISPATCH_NEGOTIATE → 路由到本模块：
  1. 读取该成员的 dispatch session
  2. LLM 理解意图（~256 tokens）：确认/增加/减少/替换/提问
  3. 更新任务列表，发送更新版，等待最终确认
  4. 成员说"确认" → session 状态改为 confirmed
```

#### 阶段三：群里公示（全员确认后）

```
全部 confirmed OR 超过截止时间（默认 10:30）时：

  发送团队任务总览卡片：
    每人姓名 + 今日任务列表（优先级标注）
    未确认成员标注 "⏰ 未确认（使用建议方案）"

  超时成员额外私聊提醒
```

### 状态存储

```
.grove/memory/dispatch/{date}/
  ├── alice.json    # {status, tasks, messages, confirmed_at}
  ├── bob.json
  └── carol.json
```

### 设计决策

- **不改 Issue assignee**：每日派发是"今天重点做什么"的建议，不改变 Issue 分配归属
- **超时机制**：避免一人不回复阻塞全团队，超时后使用建议方案公示
- **对话轮数限制**：最多 10 轮协商
- **私聊识别**：通过 `chat_type`（p2p vs group）区分，私聊协商不误路由

---

## 6. Communication 模块增强

### 新增意图

| 意图 | 触发词 | 路由目标 |
|------|--------|---------|
| `SCAN_PROJECT` | "生成项目文档" / "扫描项目" / "更新项目文档" | Project Scanner |
| `QUERY_PROJECT_OVERVIEW` | "项目总览" / "项目进度报告" | Project Overview Report |
| `DISPATCH_NEGOTIATE` | 私聊中的任务协商（dispatch session 存在时） | Morning Task Dispatch |

### 意图解析增强

```
IntentParser.parse(text, member, context):
  新增 context 参数：
    has_active_dispatch: bool
    chat_type: "p2p" | "group"

  路由优先级：
    1. has_active_dispatch=True 且 chat_type="p2p" → DISPATCH_NEGOTIATE
    2. 有活跃 PRD 对话 → CONTINUE_CONVERSATION
    3. 其他正常分类
```

---

## 7. 事件总线 + 配置变更

### 新增 EventType（4 个）

- `INTERNAL_SCAN_PROJECT`
- `CRON_PROJECT_OVERVIEW`
- `CRON_MORNING_DISPATCH`
- `INTERNAL_DISPATCH_NEGOTIATE`

### 新增配置项

```yaml
schedules:
  project_overview: "10:00"
  morning_dispatch: "09:15"

modules:
  project_scanner: true
  project_overview: true
  morning_dispatch: true

dispatch:
  confirm_deadline_minutes: 75    # 超时时间
  max_negotiate_rounds: 10        # 最大协商轮数
```

### 完整事件流

```
飞书 "扫描项目" → SCAN_PROJECT → INTERNAL_SCAN_PROJECT → Project Scanner
                                                          ├→ 逆向 PRD（飞书+GitHub）
                                                          └→ 已开发文档（飞书+GitHub）

每天 09:15 → CRON_MORNING_DISPATCH → Morning Task Dispatch
                                      ├→ 生成草案 → 私聊每人
                                      └→ 全员确认 → 群公示

私聊回复 → DISPATCH_NEGOTIATE → INTERNAL_DISPATCH_NEGOTIATE → Morning Task Dispatch
                                                               └→ 调整/确认

每天 10:00 → CRON_PROJECT_OVERVIEW → Project Overview Report
                                      ├→ 飞书卡片
                                      └→ GitHub Issue
```

---

## 8. 文件结构

### 新增文件（16 个）

```
grove/modules/project_scanner/
  __init__.py
  handler.py          # on_scan_project 主流程
  analyzer.py         # LLM 架构分析、功能推导、PRD 生成
  prompts.py          # 架构分析/功能推导/PRD 草稿 prompt

grove/modules/project_overview/
  __init__.py
  handler.py          # on_project_overview 主流程
  collectors.py       # 全周期数据采集 + 7 天趋势
  prompts.py          # 健康度评级 + 风险分析 prompt

grove/modules/morning_dispatch/
  __init__.py
  handler.py          # 三阶段主流程
  planner.py          # LLM 生成每人任务草案
  negotiator.py       # 对话式任务调整
  prompts.py          # 任务规划/协商理解 prompt

tests/modules/
  test_project_scanner.py
  test_project_overview.py
  test_morning_dispatch.py
```

### 修改文件（10 个）

```
grove/core/events.py                          # +4 事件类型
grove/integrations/github/client.py           # +4 API 方法
grove/integrations/lark/cards.py              # +2 卡片模板
grove/modules/communication/handler.py        # +3 意图路由
grove/modules/communication/intent_parser.py  # parse() 增加 context
grove/modules/communication/prompts.py        # +3 意图描述
grove/modules/daily_report/collectors.py      # +commits_by_type
grove/modules/daily_report/handler.py         # 报告增加分类行
grove/config.py                               # +dispatch 配置、+3 模块、+2 schedule
grove/main.py                                 # 注册 3 新模块 + 2 新 cron
tests/integrations/test_github_client.py      # 追加新方法测试
```

---

## 9. 变更总结

| 变更 | 新文件 | 修改文件 | 复杂度 |
|------|--------|----------|--------|
| GitHub Client 增强 | 0 | 1 | 低 |
| Project Scanner | 4 | 0 | 中 |
| Project Overview Report | 4 | 0 | 中 |
| Daily Report 增强 | 0 | 2 | 低 |
| Morning Task Dispatch | 5 | 0 | 高 |
| Communication 增强 | 0 | 3 | 低 |
| Events + Config + Main | 0 | 3 | 低 |
| 测试 | 3 | 1 | — |
| **合计** | **16** | **10** | — |
