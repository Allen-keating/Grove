# Grove 全局架构设计 Spec

**日期：** 2026-03-21
**状态：** Draft
**作者：** Allen + Claude

---

## 1. 概述

### 1.1 产品定位

Grove 是一个以独立团队成员身份存在的 AI 产品经理。它拥有自己的 GitHub 账号（`@grove-pm`）和飞书身份，主动参与项目管理、需求追踪和进度把控。

**核心理念：** 不是"每个人手里的工具"，而是"团队里的第六个人"。

**目标用户：** 5 人左右的小型开发团队，使用 GitHub Issues/Projects 做项目管理，飞书做日常沟通协作。

### 1.2 项目约束

| 约束 | 说明 |
|------|------|
| 开发方式 | 一人开发，Claude 辅助 |
| 首批用户 | 自己团队 dogfooding |
| 开源目标 | 最终开源 |
| 团队规模 | 5 人（前端、后端 x2、全栈、设计） |
| 现有工具 | 已在用 GitHub Issues/Projects + 飞书 |

### 1.3 核心决策一览

| 决策点 | 结论 |
|--------|------|
| 架构模式 | 事件驱动模块化，单进程 |
| 部署方式 | Docker 自部署，自有服务器，长驻 FastAPI 进程 |
| 文档 SSOT | 飞书文档，GitHub 放 Markdown 同步副本 |
| 定时任务 | APScheduler 进程内调度 |
| 数据存储 | 纯文件存储（.grove/ 目录），零数据库 |
| LLM | Claude Sonnet 统一，不分级 |
| 团队画像 | 静态画像（team.yml），动态学习后期 |
| 功能范围 | 7 个模块全包含 |
| 开发周期 | 13 周 6 个 Phase |

---

## 2. 系统架构

### 2.1 五层架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   GitHub         │     │   飞书 / Lark    │     │   定时调度       │
│   Webhook        │     │   WebSocket     │     │   APScheduler   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                        入口层 (Ingress)                          │
│  FastAPI HTTP Server          飞书 WebSocket Client              │
│  - POST /webhook/github      - 长连接接收消息                    │
│  - POST /webhook/lark        - 自动重连                          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     事件总线 (Event Bus)                          │
│  标准化事件格式 + @subscribe 声明式订阅 + 成员预识别               │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     功能模块层 (Modules)                          │
│  PRD 生成 · 任务拆解 · 每日巡检 · PR 审查                        │
│  文档同步 · 交互沟通 · 成员管理                                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     集成层 (Integrations)                         │
│  GitHub Client (PyGithub + httpx)                                │
│  Lark Client (lark-oapi)                                         │
│  LLM Client (anthropic)                                          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     存储层 (Storage)                              │
│  .grove/ 文件存储 · 飞书知识库 (SSOT) · GitHub Issues/PR         │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

- **单进程** — FastAPI + WebSocket + APScheduler 全部在一个进程内，Docker 一包部署
- **事件驱动** — 所有外部输入标准化为事件，模块订阅处理，互不直接调用
- **双平台对等** — GitHub 和飞书是两个平等的输入/输出通道，核心逻辑与平台无关
- **零数据库** — .grove/ 文件存储 + 飞书文档 + GitHub Issues，不引入数据库

---

## 3. 事件总线与模块订阅

### 3.1 事件类型总表

| 来源 | 事件类型 | 触发时机 | 订阅模块 |
|------|---------|---------|---------|
| GitHub | `pr.opened` | 新 PR 提交 | PR 审查, 文档同步 |
| GitHub | `pr.merged` | PR 合并 | 文档同步, 每日巡检 |
| GitHub | `pr.review_requested` | 请求 review | 交互沟通 |
| GitHub | `issue.opened` | 新 Issue 创建 | 任务拆解 |
| GitHub | `issue.updated` | Issue 状态变更 | 每日巡检 |
| GitHub | `issue.commented` | Issue 评论 @grove-pm | 交互沟通 |
| GitHub | `issue.labeled` | Issue 加标签 | 任务拆解 (product-idea) |
| 飞书 | `lark.message` | 群聊/私聊消息 @Grove | 交互沟通, PRD 生成 |
| 飞书 | `lark.card_action` | 消息卡片按钮点击 | 任务拆解, 交互沟通 |
| 飞书 | `lark.doc_updated` | 飞书文档变更 | 文档同步 |
| 定时 | `cron.daily_report` | 每日 09:00 | 每日巡检 |
| 定时 | `cron.doc_drift_check` | 每日 09:00（随巡检） | 文档同步 |
| 内部 | `internal.prd_finalized` | PRD 定稿确认 | 任务拆解 |
| 内部 | `internal.task_assigned` | 任务分配完成 | 交互沟通 (飞书通知) |
| 内部 | `internal.risk_detected` | 风险检测到 | 交互沟通 (飞书预警) |

### 3.2 事件标准格式

```json
{
  "id":        "evt_20260321_abc123",
  "type":      "pr.opened",
  "source":    "github",
  "timestamp": "2026-03-21T10:30:00+08:00",
  "member":    {
    "name": "张三",
    "github": "zhangsan",
    "lark_id": "ou_xxxxxxxx1",
    "role": "frontend"
  },
  "payload":   { ... }
}
```

### 3.3 模块订阅方式

```python
# grove/modules/pr_review/handler.py

from grove.core.event_bus import subscribe, Event

class PRReviewModule:
    def __init__(self, github, lark, llm):
        self.github = github
        self.lark = lark
        self.llm = llm

    @subscribe("pr.opened")
    async def on_pr_opened(self, event: Event):
        # 1. 获取 PR diff
        # 2. 从飞书读取关联 PRD
        # 3. LLM 分析对齐度
        # 4. GitHub 发评论 + 飞书通知
        pass
```

### 3.4 关键设计决策

- **成员识别是事件预处理** — 在事件总线分发前，自动从 team.yml 查询并填充 `member` 字段
- **模块间通过内部事件通信** — 交互沟通模块识别意图后发出 `internal.*` 事件，其他模块订阅处理
- **同一事件可被多模块订阅** — 如 `pr.merged` 同时触发文档同步和每日巡检数据采集
- **异步处理** — 所有 handler 都是 async，不阻塞事件总线

---

## 4. 项目目录结构

```
grove/
├── main.py                          # 入口：启动 FastAPI + WebSocket + Scheduler
├── config.py                        # 全局配置加载（从 .grove/config.yml）
│
├── core/                            # 核心基础设施
│   ├── event_bus.py                 # 事件总线：注册、分发、subscribe 装饰器
│   ├── events.py                    # 事件类型定义（枚举 + dataclass）
│   ├── member_resolver.py           # 成员识别：team.yml 查询 + 事件预处理
│   └── storage.py                   # 文件存储工具（读写 .grove/ 下的 YAML/JSON）
│
├── ingress/                         # 入口层：外部输入 → 标准事件
│   ├── github_webhook.py            # FastAPI 路由：POST /webhook/github
│   ├── lark_websocket.py            # 飞书 WebSocket 长连接客户端
│   └── scheduler.py                 # APScheduler 定时任务注册
│
├── modules/                         # 功能模块（每个独立目录）
│   ├── prd_generator/               # 模块 1：PRD 生成
│   │   ├── __init__.py
│   │   ├── handler.py               # 事件处理
│   │   ├── prompts.py               # LLM prompt 模板
│   │   └── templates/               # PRD Markdown 模板
│   │
│   ├── task_breakdown/              # 模块 2：任务拆解与分配
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── prompts.py
│   │   └── assigner.py              # 智能分配逻辑
│   │
│   ├── daily_report/                # 模块 3：每日巡检
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── prompts.py
│   │   ├── collectors.py            # 数据采集
│   │   └── analyzer.py              # 进度分析 + 风险检测
│   │
│   ├── pr_review/                   # 模块 4：PR 需求对齐审查
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   └── prompts.py
│   │
│   ├── doc_sync/                    # 模块 5：文档反向同步
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── prompts.py
│   │   ├── diff_classifier.py       # 变更分级
│   │   └── doc_updater.py           # 飞书文档更新逻辑
│   │
│   ├── communication/               # 模块 6：交互式沟通
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── prompts.py
│   │   └── intent_parser.py         # 意图识别
│   │
│   └── member/                      # 模块 7：成员管理
│       ├── __init__.py
│       └── handler.py
│
├── integrations/                    # 外部服务封装
│   ├── github/
│   │   ├── client.py                # GitHub API 封装
│   │   └── models.py
│   ├── lark/
│   │   ├── client.py                # 飞书 API 封装
│   │   ├── cards.py                 # 消息卡片模板构建
│   │   └── models.py
│   └── llm/
│       ├── client.py                # Claude API 统一调用
│       └── prompts.py               # 公共 prompt 工具
│
├── templates/                       # 共享模板
│   └── lark_cards/                  # 飞书消息卡片 JSON 模板
│       ├── task_assignment.json
│       ├── change_approval.json
│       └── daily_report.json
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── tests/
    ├── test_core/
    ├── test_modules/
    └── test_integrations/
```

### 4.1 模块职责边界

| 模块 | 职责 | 订阅事件 | 输出 |
|------|------|---------|------|
| **PRD 生成** | 引导提问 → 生成 PRD → 写入飞书文档 + GitHub 副本 | `lark.message`(需求意图), `internal.new_requirement` | 飞书文档, GitHub Markdown, `internal.prd_finalized` |
| **任务拆解** | PRD → Issues → 推荐分配 → 飞书卡片确认 | `internal.prd_finalized`, `lark.card_action`, `issue.labeled` | GitHub Issues, `internal.task_assigned` |
| **每日巡检** | 数据采集 → 进度分析 → 风险检测 → 报告 | `cron.daily_report` | 飞书报告, GitHub Issue, `internal.risk_detected` |
| **PR 审查** | diff vs PRD → 对齐度评估 | `pr.opened` | GitHub PR 评论, 飞书通知 |
| **文档同步** | 代码变更 → 分级 → 更新飞书文档 | `pr.merged`, `cron.doc_drift_check`, `lark.doc_updated` | 飞书文档更新, GitHub 副本同步 |
| **交互沟通** | 意图识别 → 路由 → 个性化回复（枢纽模块） | `lark.message`, `issue.commented`, `internal.*` | 飞书回复, internal 事件 |
| **成员管理** | team.yml 加载 → 成员状态缓存 | `internal.*` | 成员信息查询 |

### 4.2 模块间协作规则

- 不直接 import 其他模块 — 模块间通过事件总线通信
- 共享集成层 — 所有模块通过 `integrations/` 访问 GitHub / 飞书 / LLM
- 共享存储层 — 通过 `core/storage.py` 读写 .grove/ 文件
- 交互沟通是枢纽 — 接收自然语言输入，识别意图后发出 internal 事件给其他模块

---

## 5. 集成层设计

### 5.1 GitHub Client

```python
class GitHubClient:
    """GitHub API 封装，使用 PyGithub + httpx"""

    # Issues
    create_issue(repo, title, body, labels, milestone, assignee)
    update_issue(repo, issue_number, **kwargs)
    list_issues(repo, state, labels, since)
    add_comment(repo, issue_number, body)

    # Pull Requests
    get_pr(repo, pr_number)
    get_pr_diff(repo, pr_number)
    get_pr_files(repo, pr_number)
    add_pr_comment(repo, pr_number, body)
    list_open_prs(repo)

    # Commits
    list_recent_commits(repo, since, author)
    get_commit_diff(repo, sha)

    # Projects
    update_project_item(repo, issue_number, status)

    # Contents
    read_file(repo, path)
    write_file(repo, path, content, message)

    # Milestones
    create_milestone(repo, title, due_on)
    list_milestones(repo)
```

**认证方式：** GitHub App Installation Token（自动刷新）

### 5.2 Lark Client

```python
class LarkClient:
    """飞书 API 封装，使用飞书 OpenAPI SDK (lark-oapi)"""

    # 消息
    send_text(chat_id, text)
    send_card(chat_id, card_content)
    send_rich_text(chat_id, content)
    reply_message(message_id, content)
    send_private(user_id, content)

    # 消息卡片
    build_task_card(task_info)
    build_report_card(report_data)
    build_approval_card(change_info)

    # 文档（飞书知识库）
    create_doc(space_id, title, content)
    update_doc(doc_id, content)
    read_doc(doc_id)
    list_docs(space_id)
    append_doc_block(doc_id, block)

    # 群组
    get_chat_members(chat_id)

    # WebSocket
    start_ws_client(on_message_callback)
```

**认证方式：** App ID + App Secret → tenant_access_token（自动刷新）
**飞书文档格式：** 飞书块级文档结构 ↔ Markdown 双向转换

### 5.3 LLM Client

```python
class LLMClient:
    """Claude API 统一调用层"""

    # 核心方法
    async chat(system_prompt, messages, context=None, max_tokens=4096) -> str

    # 便捷方法
    async analyze_pr(diff, prd_content)
    async generate_prd(conversation, template)
    async breakdown_tasks(prd_content)
    async generate_report(data)
    async classify_change(diff)
    async parse_intent(message, member)
    async translate_to_doc(diff, prd_section)
```

**模型：** claude-sonnet-4-6（统一）
**设计：** 统一 system prompt 前缀（AI PM 人设 + 项目上下文），每个模块的 `prompts.py` 定义具体 prompt 模板，LLM Client 负责拼装。

### 5.4 依赖注入

三个 client 在 `main.py` 启动时创建，注入到每个模块实例，共享连接池和 token 缓存。

---

## 6. 配置与存储

### 6.1 .grove/ 目录结构

```
.grove/
├── config.yml                  # Grove 全局配置
├── team.yml                    # 团队成员配置（静态画像）
│
├── memory/
│   ├── profiles/               # 成员状态缓存（运行时更新）
│   │   ├── zhangsan.yml
│   │   └── ...
│   ├── snapshots/              # 每日进度快照
│   │   └── 2026-03-21.json
│   └── decisions/              # 决策记录
│       └── 2026-03-21-payment-priority.md
│
├── docs-sync/                  # 飞书文档的 Markdown 同步副本
│   ├── prd-用户登录.md
│   ├── prd-支付模块.md
│   └── sync-state.yml          # 同步状态映射
│
└── logs/                       # 运行日志（.gitignore）
    ├── events.log
    └── llm-calls.log
```

### 6.2 config.yml

```yaml
# 基本信息
project:
  name: "My Project"
  repo: "org/repo-name"
  language: "zh-CN"

# 飞书配置
lark:
  app_id: "${LARK_APP_ID}"
  app_secret: "${LARK_APP_SECRET}"
  chat_id: "oc_xxxxxxxx"
  space_id: "spc_xxxxxxxx"

# GitHub 配置
github:
  app_id: "${GITHUB_APP_ID}"
  private_key_path: "${GITHUB_PRIVATE_KEY_PATH}"
  installation_id: "${GITHUB_INSTALLATION_ID}"

# LLM 配置
llm:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4-6"

# AI PM 人设
persona:
  name: "Grove"
  tone: "专业但不刻板"
  reminder_intensity: 3
  proactive_messaging: true

# 工作时间
work_hours:
  start: "09:00"
  end: "18:00"
  timezone: "Asia/Shanghai"
  workdays: [1, 2, 3, 4, 5]

# 定时任务
schedules:
  daily_report: "09:00"
  doc_drift_check: "09:00"

# 文档同步
doc_sync:
  auto_update_level: "moderate"
  github_docs_path: "docs/prd/"
```

### 6.3 team.yml

```yaml
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

  - github: zhaoliu
    lark_id: "ou_xxxxxxxx4"
    name: 赵六
    role: backend
    skills: [python, go, kubernetes]
    authority: member

  - github: sunqi
    lark_id: "ou_xxxxxxxx5"
    name: 孙七
    role: design
    skills: [figma, ui, ux]
    authority: member
```

### 6.4 存储策略

- **Git 跟踪：** config.yml, team.yml, docs-sync/, memory/decisions/
- **.gitignore：** logs/, memory/profiles/（运行时缓存，可从 GitHub API 重建）, memory/snapshots/（可选跟踪）
- **敏感信息：** 全部通过环境变量 `${VAR}` 引用，config.yml 中不存明文密钥

---

## 7. 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.12+ | AI 生态友好 |
| Web 框架 | FastAPI + Uvicorn | 异步高性能，Webhook 接收 |
| 定时调度 | APScheduler | 进程内 cron，零外部依赖 |
| GitHub 集成 | PyGithub + httpx | 官方库 + 灵活 HTTP 客户端 |
| 飞书集成 | lark-oapi | 飞书官方 Python SDK |
| LLM | anthropic | Claude API 官方 SDK |
| 部署 | Docker + docker-compose | 自有服务器，一键部署 |
| 存储 | YAML / JSON 文件 | 零数据库，版本可追溯 |

---

## 8. 开发路线图

### Phase 1：基础骨架（第 1-2 周）

**目标：** 事件驱动架构跑通，双平台能收发消息

- 项目脚手架（pyproject.toml, Docker, 目录结构）
- `core/` 完整实现（event_bus, events, member_resolver, storage）
- `ingress/` 完整实现（github_webhook, lark_websocket, scheduler）
- `integrations/` 基础实现（GitHub Issues 读写、飞书发消息收消息、Claude API 调用）
- `.grove/config.yml` + `team.yml` 模板
- Docker 部署配置

**验证标准：**
- GitHub 创建 Issue → 飞书群收到通知
- 飞书群 @Grove → GitHub 创建 Issue
- 能识别消息来自哪个团队成员

### Phase 2：PRD 生成 + 交互沟通（第 3-4 周）

**目标：** 团队能通过飞书对话生成 PRD，Grove 具备基本对话能力

- `modules/communication/` — 意图识别、对话上下文管理、个性化回复、权限检查
- `modules/prd_generator/` — 引导式提问、PRD 模板 + LLM 生成、飞书文档创建、GitHub 同步副本、文档变更监听
- `integrations/lark/` 增强 — 文档读写、消息卡片构建
- AI PM 人设 prompt 定义

**验证标准：**
- 飞书群 @Grove "我想加个暗黑模式" → 引导提问 → 生成 PRD
- PRD 出现在飞书知识库 + GitHub docs/prd/
- "@Grove 目前进度？" → 基于角色的个性化回复
- 权限控制生效

### Phase 3：任务管理（第 5-6 周）

**目标：** PRD 定稿后自动拆解任务，通过飞书卡片确认分配

- `modules/task_breakdown/` — PRD 拆解、GitHub Issues 创建、智能分配推荐、飞书卡片确认、卡片回调处理
- `integrations/lark/cards.py` 增强 — 任务分配卡片模板
- `integrations/github/` 增强 — Milestones + Projects Board
- `modules/member/` — 当前任务缓存 + 负载统计

**验证标准：**
- PRD 定稿 → 自动创建 GitHub Issues
- 飞书群收到分配卡片 → 点击接受 → Issue 自动 assign
- "@Grove 张三手上有几个任务？" → 准确回答

### Phase 4：每日巡检（第 7-8 周）

**目标：** 每天自动推送项目状态报告 + 风险预警

- `modules/daily_report/` — 数据采集、进度分析、风险检测、报告生成
- 飞书群推送（富文本报告卡片）+ GitHub Issue 归档
- `memory/snapshots/` 每日快照存储
- 定时触发器配置

**验证标准：**
- 每天 09:00 飞书群自动收到报告
- 报告包含成员动态、进度、风险项、建议
- 同时创建 GitHub Issue 归档
- 风险项自动 @相关人

### Phase 5：PR 审查 + 文档同步（第 9-11 周）

**目标：** 代码和文档双向保持一致

- `modules/pr_review/` — diff 摘要、PRD 匹配、对齐度分析、GitHub PR 评论、飞书通知
- `modules/doc_sync/` — 变更分级、飞书文档更新（小改自动/中改确认/大改讨论）、文档漂移检测、sync-state.yml 管理
- `integrations/lark/` 增强 — 文档块级编辑

**验证标准：**
- 新 PR → 自动收到需求对齐评论
- PR 合并后 → 飞书 PRD 自动/半自动更新
- 每日报告包含「文档同步状态」板块

### Phase 6：打磨 + 开源准备（第 12-13 周）

**目标：** 团队实际使用打磨 + 开源发布

- 团队 dogfooding 反馈修复
- AI PM 人设与 prompt 调优
- 错误处理与边界情况完善
- 开源文档（README, CONTRIBUTING, 配置教程, 架构说明）
- 示例配置（.grove/config.example.yml）
- GitHub Actions CI（测试 + lint）
- 首个 Release Tag

**验证标准：**
- 团队实际使用 1-2 周无重大问题
- 新用户能按 README 独立完成部署和配置
- GitHub 首个 release 发布

---

## 9. AI PM 人设与行为规范

### 9.1 基本人设

- **名称：** Grove
- **基调：** 专业但不刻板
- **核心原则：** 数据驱动、建议为主、保护隐私、承认错误、尊重专业判断

### 9.2 沟通规范

- **群聊：** 内容偏概要，不暴露个人细节
- **私聊：** 可讨论个人任务困难、工作负载
- **催进度：** 分三级递进（轻度提醒 → 中度提醒 → 升级至 Lead）
- **出错时：** 坦诚认错，说明修正措施
- **不确定时：** 诚实说"不确定"，@相关人求助

### 9.3 行为禁区

- 不在群里公开批评个人代码质量
- 不对比成员工作效率
- 不未经确认删除 Issue 或关闭 PR
- 不在群里透露私聊内容
- 不给成员打分或排名
- 不在非工作时间催进度
- 不干预技术方案选择

### 9.4 权限体系

- **owner：** 所有权限 + 修改 AI PM 配置 + 调整里程碑 + 覆盖 AI PM 决策
- **lead：** 所有 member 权限 + 审批任务重分配 + 确认 PRD 中/重大变更 + 调整模块优先级
- **member：** 查询进度 + 提出想法 + 接受/拒绝任务 + 请求任务调整（需 lead 审批）+ 编辑飞书 PRD

---

## 10. 成本估算

| 项目 | 预估月费用 | 说明 |
|------|-----------|------|
| Claude API (Sonnet) | $30-80 | 每日巡检 + PR review + 对话交互 |
| 服务器 | 已有 | 自有服务器 |
| GitHub Actions | $0 | CI 用途，免费额度足够 |
| 飞书开放平台 | $0 | 自建应用免费 |
| **总计** | **$30-80/月** | |

---

## 11. 风险与应对

| 风险 | 应对策略 |
|------|---------|
| LLM 幻觉导致错误判断 | 关键操作通过飞书卡片确认，人工兜底 |
| API 成本失控 | 设置月度调用上限，日志记录每次调用成本 |
| 团队不信任 AI PM | 初期以建议为主，逐步建立信任，保持透明 |
| GitHub API 限流 | 请求缓存 + 批处理 |
| 飞书文档↔Markdown 转换有损 | 定义转换规则，关键格式人工校验 |
| 文档自动更新出错 | 分级策略：小改自动（可回滚），中/大改人工确认 |
| 误判代码变更为产品变更 | 初期偏保守，宁可漏报不误报，逐步优化分类 |
