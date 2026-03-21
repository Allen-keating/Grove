# Phase 6: 打磨 + 开源准备 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare Grove for open source release — documentation, CI pipeline, error handling improvements, and first release tag.

**Architecture:** No new modules. This phase adds project-level files (README, CONTRIBUTING, setup guide), GitHub Actions CI, and polishes existing code.

**Tech Stack:** GitHub Actions, existing Grove codebase.

**Scope:** Phase 6 (weeks 12-13). Final phase.

**Verification criteria (from spec):**
- 新用户能按 README 独立完成部署和配置
- GitHub Actions CI 通过（测试 + lint）
- GitHub 首个 release 发布

---

## File Structure

```
grove/
├── README.md                          # Project overview + quick start
├── CONTRIBUTING.md                    # Contribution guide
├── docs/
│   └── setup-guide.md                 # Detailed setup tutorial
├── .github/
│   └── workflows/
│       └── ci.yml                     # GitHub Actions: test + lint
├── .grove/
│   ├── config.example.yml             # Already exists — verify complete
│   └── team.example.yml               # Already exists — verify complete
└── .env.example                       # Environment variable template
```

---

### Task 1: README.md

**Files:** Create `README.md`

- [ ] **Step 1: Write README**

```markdown
# 🌳 Grove — Your AI Product Manager

> Grove /ɡroʊv/ — 果林。产品从一颗种子成长为一棵大树，Grove 是照料这片林子的人。

Grove 是一个以独立团队成员身份存在的 AI 产品经理。它拥有自己的 GitHub 账号和飞书身份，主动参与项目管理、需求追踪和进度把控。

**核心理念：** 不是"每个人手里的工具"，而是"团队里的第六个人"。

## 功能

- **PRD 生成** — 在飞书群对话中引导团队创建产品需求文档，自动写入飞书知识库 + GitHub 同步
- **任务拆解** — PRD 定稿后自动拆解为 GitHub Issues，智能推荐分配，飞书卡片确认
- **每日巡检** — 每天自动采集项目数据，分析进度，检测风险，推送飞书报告 + GitHub 归档
- **PR 审查** — 新 PR 自动进行产品层面的需求对齐检查（非代码质量 review）
- **文档同步** — 代码变更后自动检测产品影响，分级更新飞书 PRD 文档
- **智能沟通** — 意图识别、个性化回复、权限控制，像真人 PM 一样交流
- **成员管理** — 团队画像、任务负载追踪、技能匹配分配

## 快速开始

### 前置条件

- Python 3.12+
- Docker（可选，推荐）
- GitHub App（[创建教程](docs/setup-guide.md#github-app)）
- 飞书自建应用（[创建教程](docs/setup-guide.md#飞书应用)）
- Anthropic API Key

### 安装

```bash
git clone https://github.com/your-org/grove.git
cd grove
cp .grove/config.example.yml .grove/config.yml
cp .grove/team.example.yml .grove/team.yml
cp .env.example .env
# 编辑配置文件，填入你的凭证
```

### Docker 部署（推荐）

```bash
docker-compose up -d
```

### 本地开发

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn grove.main:app --port 8000
```

### 验证

```bash
curl http://localhost:8000/health
```

## 配置

详见 [Setup Guide](docs/setup-guide.md)。

核心配置文件：
- `.grove/config.yml` — Grove 全局配置（飞书/GitHub/LLM 凭证、人设、工作时间）
- `.grove/team.yml` — 团队成员信息（GitHub ↔ 飞书 ID 映射、角色、技能、权限）

## 架构

```
入口层 → 事件总线 → 功能模块 → 集成层 → 存储层
```

- **事件驱动** — GitHub Webhook + 飞书 WebSocket + 定时任务 → 标准化事件 → 模块订阅处理
- **双平台** — GitHub（代码管理）+ 飞书（日常沟通）并行
- **单进程** — FastAPI + WebSocket + APScheduler，Docker 一包部署

详见 [Architecture Doc](docs/superpowers/specs/2026-03-21-grove-architecture-design.md)。

## 开发

```bash
# 运行测试
pytest -v

# 代码检查
ruff check grove/ tests/
```

## 许可证

MIT License

## 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)。
```

- [ ] **Step 2: Commit**

```bash
git add README.md && git commit -m "docs: add README with project overview and quick start guide"
```

---

### Task 2: CONTRIBUTING.md + Setup Guide

**Files:** Create `CONTRIBUTING.md`, `docs/setup-guide.md`

- [ ] **Step 1: Write CONTRIBUTING.md**

```markdown
# Contributing to Grove

感谢你对 Grove 的关注！

## 开发环境

```bash
git clone https://github.com/your-org/grove.git
cd grove
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 代码规范

- Python 3.12+
- 使用 ruff 进行代码检查：`ruff check grove/ tests/`
- 所有代码需要有测试覆盖

## 提交流程

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 编写代码和测试
4. 确保测试通过：`pytest -v`
5. 确保 lint 通过：`ruff check grove/ tests/`
6. 提交 PR

## 项目结构

```
grove/
├── core/           # 核心基础设施（事件总线、存储、成员识别）
├── ingress/        # 入口层（Webhook、WebSocket、定时任务）
├── integrations/   # 外部服务封装（GitHub、飞书、LLM）
├── modules/        # 功能模块（每个模块独立目录）
└── main.py         # 应用入口
```

## 模块开发

每个功能模块是一个独立目录，包含：
- `handler.py` — 事件处理（通过 `@subscribe` 装饰器订阅事件）
- `prompts.py` — LLM 提示词模板
- 模块间通过事件总线通信，不直接 import 其他模块
```

- [ ] **Step 2: Write docs/setup-guide.md**

```markdown
# Grove 配置教程

## GitHub App

1. 前往 GitHub → Settings → Developer settings → GitHub Apps → New GitHub App
2. 配置：
   - Name: `grove-pm`
   - Homepage URL: 你的服务器地址
   - Webhook URL: `https://your-server/webhook/github`
   - Webhook secret: 生成一个随机字符串
   - Permissions:
     - Issues: Read & write
     - Pull requests: Read & write
     - Contents: Read & write
     - Projects: Read & write
   - Subscribe to events: Issues, Pull request, Issue comment
3. 安装到你的仓库
4. 记录 App ID、Installation ID，下载 Private Key

## 飞书应用

1. 前往 [飞书开放平台](https://open.feishu.cn/) → 创建企业自建应用
2. 配置：
   - 添加机器人能力
   - 添加消息与群组权限（im:message, im:chat）
   - 添加云文档权限（docx:document）
   - 配置事件订阅 → WebSocket 模式
3. 将 Bot 添加到项目群
4. 记录 App ID 和 App Secret

## 环境变量

创建 `.env` 文件：

```env
LARK_APP_ID=your_lark_app_id
LARK_APP_SECRET=your_lark_app_secret
GITHUB_APP_ID=your_github_app_id
GITHUB_PRIVATE_KEY_PATH=/path/to/private-key.pem
GITHUB_INSTALLATION_ID=your_installation_id
GITHUB_WEBHOOK_SECRET=your_webhook_secret
ANTHROPIC_API_KEY=your_anthropic_api_key
```

## 配置文件

编辑 `.grove/config.yml`（参考 `.grove/config.example.yml`）和 `.grove/team.yml`（参考 `.grove/team.example.yml`）。

## 启动

```bash
docker-compose up -d
curl http://localhost:8000/health
```

在飞书群 @Grove 测试是否响应。
```

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md docs/setup-guide.md && git commit -m "docs: add CONTRIBUTING guide and setup tutorial"
```

---

### Task 3: .env.example + GitHub Actions CI

**Files:** Create `.env.example`, `.github/workflows/ci.yml`

- [ ] **Step 1: Create .env.example**

```env
# Grove Environment Variables
LARK_APP_ID=
LARK_APP_SECRET=
GITHUB_APP_ID=
GITHUB_PRIVATE_KEY_PATH=
GITHUB_INSTALLATION_ID=
GITHUB_WEBHOOK_SECRET=
ANTHROPIC_API_KEY=
```

- [ ] **Step 2: Create CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check grove/ tests/

      - name: Test
        run: pytest -v --tb=short
```

- [ ] **Step 3: Update .gitignore**

Add `.env` to `.gitignore` (if not already there).

- [ ] **Step 4: Commit**

```bash
git add .env.example .github/workflows/ci.yml .gitignore && git commit -m "ci: add GitHub Actions workflow + .env.example"
```

---

### Task 4: Final Polish + Release Tag

- [ ] **Step 1: Run full test suite + lint**

```bash
.venv/bin/pytest -v --tb=short
.venv/bin/ruff check grove/ tests/
```

- [ ] **Step 2: Verify Docker build**

```bash
docker build -t grove .
```

- [ ] **Step 3: Fix any issues**

- [ ] **Step 4: Create release commit and tag**

```bash
git add -A
git commit -m "release: Grove v0.1.0 — AI Product Manager MVP"
git tag -a v0.1.0 -m "Grove v0.1.0 — First release with all 7 modules"
```

---

## Phase 6 Completion Criteria

- [ ] README.md with overview, quick start, architecture summary
- [ ] CONTRIBUTING.md with dev setup and code standards
- [ ] docs/setup-guide.md with GitHub App + 飞书应用配置教程
- [ ] .env.example with all required env vars
- [ ] GitHub Actions CI (test + lint on Python 3.12/3.13)
- [ ] Docker build succeeds
- [ ] All tests pass, lint clean
- [ ] v0.1.0 release tag created
