# Contributing to Grove

Thank you for your interest in contributing! This guide covers everything you need to get a working development environment and submit a pull request.

---

## Development Environment Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/grove.git
cd grove
```

### 2. Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install in editable mode with dev dependencies

```bash
pip install -e ".[dev]"
```

### 4. Create a local config directory

```bash
mkdir -p .grove
cp docs/examples/config.yml .grove/config.yml   # edit with your credentials
cp docs/examples/team.yml   .grove/team.yml
```

---

## Code Standards

- **Python version:** 3.12 or higher. Type annotations are required on all public functions.
- **Formatter / linter:** [Ruff](https://docs.astral.sh/ruff/). Run `ruff check grove/ tests/` before every commit. The line length limit is 100 characters.
- **Tests:** Every new module handler, integration method, or utility function must have a corresponding test. Tests live in `tests/` and mirror the `grove/` package structure.
- **Async:** Use `async/await` throughout. Blocking I/O in handlers will stall the event loop.
- **No secrets in source:** All credentials must come from environment variables or the config YAML (which itself reads env vars via `${VAR}` substitution).

### Running checks locally

```bash
# Lint
ruff check grove/ tests/

# Tests
pytest -v --tb=short

# Tests with coverage
pytest --cov=grove --cov-report=term-missing
```

---

## Pull Request Workflow

1. **Fork** the repository and create a feature branch from `main`:

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Write tests first** (or alongside the code). All tests must pass before opening a PR.

3. **Run lint** and fix any issues:

   ```bash
   ruff check grove/ tests/
   ```

4. **Commit** with a conventional commit message:

   ```
   feat: add X
   fix: correct Y
   docs: update Z
   refactor: simplify W
   test: cover V
   ci: adjust U
   ```

5. **Open a PR** against `main`. Fill in the PR template (what changed and why, how to test it).

6. A maintainer will review and merge.

---

## Project Structure

```
grove/
├── main.py                  # FastAPI app factory, wires all layers together
├── config.py                # Pydantic config models, YAML + env var loading
│
├── core/                    # Infrastructure shared across all modules
│   ├── event_bus.py         # EventBus class + @subscribe decorator
│   ├── events.py            # Event dataclass and EventType enum
│   ├── member_resolver.py   # GitHub/Lark ID → Member lookup
│   └── storage.py           # Read/write helpers for .grove/ files
│
├── ingress/                 # External event sources
│   ├── github_webhook.py    # FastAPI router for GitHub webhook POSTs
│   ├── lark_webhook.py      # FastAPI router for Lark HTTP callbacks
│   ├── lark_websocket.py    # Long-lived WebSocket client (Lark events)
│   ├── scheduler.py         # APScheduler cron jobs (daily report, drift check)
│   └── health.py            # /health endpoint
│
├── modules/                 # Business logic — one sub-package per feature
│   ├── communication/       # Intent parsing and message routing
│   ├── daily_report/        # Standup data collection and posting
│   ├── doc_sync/            # Documentation drift detection and rewrite
│   ├── member/              # Team roster and workload tracking
│   ├── pr_review/           # PR alignment analysis
│   ├── prd_generator/       # Multi-turn PRD conversation
│   └── task_breakdown/      # Issue decomposition and assignment
│
├── integrations/            # Third-party API wrappers
│   ├── github/              # PyGithub wrapper (issues, PRs, files)
│   ├── lark/                # Lark OAPI wrapper (messages, docs, cards)
│   └── llm/                 # Anthropic client with concurrency control
│
└── templates/               # Jinja2 / string templates (Lark card JSON)
```

---

## Writing a New Module

Every module follows the same pattern:

### 1. Create the sub-package

```
grove/modules/my_module/
    __init__.py
    handler.py      # subscribes to events, orchestrates logic
    prompts.py      # LLM prompt strings (keep them here, not in handler)
```

### 2. Subscribe to events in `handler.py`

```python
from grove.core.event_bus import subscribe
from grove.core.events import Event

class MyModuleHandler:
    def __init__(self, bus, github, lark, llm, config):
        self.github = github
        self.lark = lark
        self.llm = llm
        self.config = config
        bus.register(self)   # bus discovers all @subscribe methods automatically

    @subscribe("lark.message.received")
    async def on_message(self, event: Event) -> None:
        # handle the event
        ...
```

### 3. Add prompts to `prompts.py`

```python
MY_PROMPT = """
You are Grove, an AI Product Manager.
...
{variable}
"""
```

### 4. Register in `main.py`

```python
from grove.modules.my_module.handler import MyModuleHandler

MyModuleHandler(bus, github_client, lark_client, llm_client, settings)
```

### 5. Write tests

```
tests/test_modules/test_my_module/
    test_handler.py
```

Use `pytest-asyncio` and mock the integration clients. See existing module tests for examples.

---

## Reporting Issues

Open a GitHub Issue describing:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Grove version and Python version
