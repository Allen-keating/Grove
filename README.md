# 🌳 Grove — Your AI Product Manager

> An autonomous AI PM that lives inside your team — owning a GitHub identity, a Lark/Feishu seat, and the full product lifecycle from PRD to release.

---

## What is Grove?

Grove is an open-source AI Product Manager that operates as an independent team member rather than a passive tool. It holds a GitHub App identity and a Lark/Feishu bot account, monitors your repositories and chat channels, and proactively drives product work — writing PRDs, breaking down tasks, reviewing PRs, and keeping documentation in sync.

You onboard Grove the same way you onboard a human teammate: give it access, introduce it to the team, and let it get to work.

---

## Features

Grove ships with 7 modules, all communicating through an internal event bus:

| Module | What it does |
|---|---|
| **PRD Generator** | Guided multi-turn conversation to produce structured PRDs, saved to Lark Docs and GitHub |
| **Task Breakdown** | Decomposes a PRD into GitHub Issues with skill-matched assignments via interactive Lark cards |
| **Daily Report** | Collects commit/PR/milestone data each morning, runs risk analysis, posts standup to Lark and GitHub |
| **PR Review** | Classifies each merged PR against product requirements and flags misaligned changes |
| **Doc Sync** | Detects documentation drift after merges and rewrites stale Lark Docs sections automatically |
| **Communication** | Routes natural-language messages in Lark to the right module via LLM intent parsing |
| **Member Management** | Maintains a live roster of team members with GitHub/Lark IDs, skills, and workload |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose, **or** Python 3.12+
- A GitHub App (see [docs/setup-guide.md](docs/setup-guide.md))
- A Feishu/Lark custom bot app (see [docs/setup-guide.md](docs/setup-guide.md))
- An Anthropic API key

### Install

```bash
git clone https://github.com/your-org/grove.git
cd grove
cp .env.example .env
# Edit .env with your credentials
```

### Deploy with Docker (recommended)

```bash
# Copy and edit config files
mkdir -p .grove
cp docs/examples/config.yml .grove/config.yml
cp docs/examples/team.yml   .grove/team.yml
# Edit both files, then:

docker compose up -d
```

### Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set GROVE_DIR to point at your config directory
export GROVE_DIR=.grove
uvicorn grove.main:app --reload
```

### Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","lark":"connected","scheduler":"running"}
```

---

## Configuration

Grove reads two YAML files from `$GROVE_DIR` (default: `.grove/`):

### `.grove/config.yml`

```yaml
project:
  name: "My Product"
  repo: "org/repo"
  language: "zh-CN"

lark:
  app_id: "${LARK_APP_ID}"
  app_secret: "${LARK_APP_SECRET}"
  chat_id: "oc_xxxx"       # team group chat
  space_id: "spc_xxxx"     # Lark Docs space

github:
  app_id: "${GITHUB_APP_ID}"
  private_key_path: "${GITHUB_PRIVATE_KEY_PATH}"
  installation_id: "${GITHUB_INSTALLATION_ID}"
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"

llm:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4-6"

persona:
  name: "Grove"
  tone: "professional but approachable"
  reminder_intensity: 3     # 1–5
  proactive_messaging: true

work_hours:
  start: "09:00"
  end: "18:00"
  timezone: "Asia/Shanghai"
  workdays: [1, 2, 3, 4, 5]
```

### `.grove/team.yml`

```yaml
members:
  - github_id: "alice"
    lark_id: "ou_xxxx"
    name: "Alice"
    role: "engineer"
    skills: ["backend", "api"]
  - github_id: "bob"
    lark_id: "ou_yyyy"
    name: "Bob"
    role: "lead"
    skills: ["frontend", "ux"]
```

---

## Architecture

Grove is structured in five layers:

```
┌─────────────────────────────────────────────┐
│  Ingress Layer                              │
│  GitHub Webhook · Lark WebSocket · Scheduler│
└────────────────────┬────────────────────────┘
                     │ Events
┌────────────────────▼────────────────────────┐
│  Event Bus  (@subscribe decorator)          │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│  Modules                                    │
│  PRD · Tasks · Report · PR · Docs · Comms  │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│  Integrations                               │
│  GitHub App Client · Lark Client · LLM     │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│  Storage  (.grove/ YAML/JSON files)         │
└─────────────────────────────────────────────┘
```

Events flow from ingress sources into the bus, which fans out to all subscribed module handlers. Modules call integrations (GitHub, Lark, Claude) and write state to the local `.grove/` directory.

---

## Development

```bash
# Run tests
.venv/bin/pytest -v --tb=short

# Lint
.venv/bin/ruff check grove/ tests/

# Run with live reload
uvicorn grove.main:app --reload
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, code standards, and module authoring guide.

---

## License

[MIT](LICENSE)
