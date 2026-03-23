# 模块热开关（Hot-Toggle）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add runtime module enable/disable via HTTP Admin API and Lark commands, with state persisted to `.grove/runtime/modules-state.yml`.

**Architecture:** EventBus gains `unregister()`. New `ModuleRegistry` orchestrates module lifecycle. Admin API provides HTTP endpoints. Communication module handles Lark toggle commands. All modules are always instantiated; toggle only controls event subscription.

**Tech Stack:** Existing Grove (FastAPI, event bus, Lark client), asyncio.Lock for concurrency.

**Spec:** `docs/superpowers/specs/2026-03-23-hot-toggle-design.md`

---

## File Structure

```
grove/
├── core/
│   ├── event_bus.py                     # MODIFY: +name param, +_module_handlers, +unregister()
│   └── module_registry.py               # NEW: ModuleRegistry + merge_module_state()
├── ingress/
│   └── admin.py                         # NEW: Admin API router
├── config.py                            # MODIFY: +admin_token
├── main.py                              # MODIFY: use registry, mount admin router
├── modules/communication/
│   ├── intent_parser.py                 # MODIFY: +TOGGLE_MODULE, +QUERY_MODULE_STATUS
│   ├── handler.py                       # MODIFY: +toggle/status handlers
│   └── prompts.py                       # MODIFY: +toggle intent in prompt
└── tests/
    ├── test_core/
    │   ├── test_event_bus.py            # MODIFY: +unregister tests
    │   └── test_module_registry.py      # NEW
    └── test_ingress/
        └── test_admin.py               # NEW
```

---

### Task 1: EventBus — name param + unregister()

**Files:**
- Modify: `grove/core/event_bus.py`
- Modify: `tests/test_core/test_event_bus.py`

- [ ] **Step 1: Write failing tests for unregister**

Add to `tests/test_core/test_event_bus.py`:

```python
class TestEventBusUnregister:
    @pytest.fixture
    def bus(self):
        return EventBus()

    async def test_register_with_name(self, bus):
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event): pass
        bus.register(Mod(), name="test_mod")
        assert "test_mod" in bus._module_handlers

    async def test_unregister_removes_handlers(self, bus):
        received = []
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event):
                received.append(event)
        bus.register(Mod(), name="my_mod")
        bus.unregister("my_mod")
        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        assert len(received) == 0

    async def test_unregister_unknown_returns_false(self, bus):
        assert bus.unregister("nonexistent") is False

    async def test_unregister_returns_true(self, bus):
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event): pass
        bus.register(Mod(), name="my_mod")
        assert bus.unregister("my_mod") is True

    async def test_register_without_name_uses_classname(self, bus):
        class MyModule:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event): pass
        bus.register(MyModule())
        assert "MyModule" in bus._module_handlers

    async def test_re_register_after_unregister(self, bus):
        received = []
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event):
                received.append(event)
        mod = Mod()
        bus.register(mod, name="my_mod")
        bus.unregister("my_mod")
        bus.register(mod, name="my_mod")
        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        assert len(received) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_core/test_event_bus.py::TestEventBusUnregister -v`

- [ ] **Step 3: Implement changes to event_bus.py**

Replace the `register` method and add `unregister`. The full updated `EventBus` class:

```python
class EventBus:
    """Central event dispatcher. Modules register themselves; the bus routes events."""

    def __init__(self, failed_events_path: Path | None = None):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._module_handlers: dict[str, list[tuple[str, Callable]]] = {}
        self._failed_events_path = failed_events_path

    def register(self, module: Any, name: str | None = None) -> None:
        """Scan a module instance for @subscribe-decorated methods and register them."""
        module_name = name or type(module).__name__
        handlers_for_module: list[tuple[str, Callable]] = []
        for attr_name in dir(module):
            method = getattr(module, attr_name, None)
            if method is None or not callable(method):
                continue
            event_types = getattr(method, _SUBSCRIBE_ATTR, None)
            if event_types:
                for event_type in event_types:
                    self._handlers[event_type].append(method)
                    handlers_for_module.append((event_type, method))
                    logger.info(
                        "Registered %s.%s for event '%s'",
                        module_name, attr_name, event_type,
                    )
        self._module_handlers[module_name] = handlers_for_module

    def unregister(self, name: str) -> bool:
        """Remove all handlers for a named module. Returns True if module was found."""
        handlers = self._module_handlers.pop(name, None)
        if handlers is None:
            return False
        for event_type, method in handlers:
            try:
                self._handlers[event_type].remove(method)
            except ValueError:
                pass
        logger.info("Unregistered all handlers for module '%s'", name)
        return True

    # _log_failed_event and dispatch remain unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_core/test_event_bus.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/core/event_bus.py tests/test_core/test_event_bus.py
git commit -m "feat: EventBus name param + unregister() for hot-toggle support"
```

---

### Task 2: ModuleRegistry + merge_module_state

**Files:**
- Create: `grove/core/module_registry.py`
- Test: `tests/test_core/test_module_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_core/test_module_registry.py
import asyncio
from pathlib import Path
import pytest
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.core.module_registry import ModuleRegistry, merge_module_state
from grove.config import ModulesConfig


class TestModuleRegistry:
    @pytest.fixture
    def registry(self, grove_dir: Path):
        bus = EventBus()
        storage = Storage(grove_dir)
        return ModuleRegistry(bus=bus, storage=storage), bus

    async def test_add_enabled_registers_handlers(self, registry):
        reg, bus = registry
        received = []
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event):
                received.append(event)
        reg.add("test_mod", Mod(), enabled=True)
        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        assert len(received) == 1

    async def test_add_disabled_does_not_register(self, registry):
        reg, bus = registry
        received = []
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event):
                received.append(event)
        reg.add("test_mod", Mod(), enabled=False)
        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        assert len(received) == 0

    async def test_disable_removes_handlers(self, registry):
        reg, bus = registry
        received = []
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event):
                received.append(event)
        reg.add("test_mod", Mod(), enabled=True)
        result = await reg.disable("test_mod")
        assert result is True
        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        assert len(received) == 0

    async def test_enable_re_registers_handlers(self, registry):
        reg, bus = registry
        received = []
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event):
                received.append(event)
        reg.add("test_mod", Mod(), enabled=True)
        await reg.disable("test_mod")
        await reg.enable("test_mod")
        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        assert len(received) == 1

    async def test_disable_already_disabled_returns_false(self, registry):
        reg, bus = registry
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event): pass
        reg.add("test_mod", Mod(), enabled=False)
        result = await reg.disable("test_mod")
        assert result is False

    async def test_enable_already_enabled_returns_false(self, registry):
        reg, bus = registry
        class Mod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event): pass
        reg.add("test_mod", Mod(), enabled=True)
        result = await reg.enable("test_mod")
        assert result is False

    def test_get_status(self, registry):
        reg, bus = registry
        class ModA:
            pass
        class ModB:
            pass
        reg.add("mod_a", ModA(), enabled=True)
        reg.add("mod_b", ModB(), enabled=False)
        status = reg.get_status()
        assert len(status) == 2
        names = {s["name"] for s in status}
        assert names == {"mod_a", "mod_b"}

    async def test_disable_persists_to_runtime_state(self, registry, grove_dir):
        reg, bus = registry
        class Mod:
            pass
        reg.add("pr_review", Mod(), enabled=True)
        await reg.disable("pr_review")
        state_path = grove_dir / "runtime" / "modules-state.yml"
        assert state_path.exists()


class TestMergeModuleState:
    def test_merge_defaults(self, grove_dir: Path):
        storage = Storage(grove_dir)
        cfg = ModulesConfig()
        result = merge_module_state(cfg, storage)
        assert result["communication"] is True
        assert result["pr_review"] is True

    def test_merge_with_runtime_override(self, grove_dir: Path):
        storage = Storage(grove_dir)
        # Write runtime state
        (grove_dir / "runtime").mkdir(exist_ok=True)
        import yaml
        (grove_dir / "runtime" / "modules-state.yml").write_text(
            yaml.dump({"modules": {"pr_review": False}}), encoding="utf-8")
        cfg = ModulesConfig()
        result = merge_module_state(cfg, storage)
        assert result["pr_review"] is False
        assert result["communication"] is True  # unaffected

    def test_merge_ignores_unknown_keys(self, grove_dir: Path):
        storage = Storage(grove_dir)
        (grove_dir / "runtime").mkdir(exist_ok=True)
        import yaml
        (grove_dir / "runtime" / "modules-state.yml").write_text(
            yaml.dump({"modules": {"nonexistent": True}}), encoding="utf-8")
        cfg = ModulesConfig()
        result = merge_module_state(cfg, storage)
        assert "nonexistent" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_core/test_module_registry.py -v`

- [ ] **Step 3: Implement module_registry.py**

```python
# grove/core/module_registry.py
"""Registry for managing module lifecycle and hot-toggle."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import yaml

from grove.config import ModulesConfig
from grove.core.event_bus import EventBus
from grove.core.storage import Storage

logger = logging.getLogger(__name__)


@dataclass
class ModuleEntry:
    name: str
    instance: Any
    enabled: bool


class ModuleRegistry:
    """Track module instances, manage enable/disable with EventBus, persist state."""

    def __init__(self, bus: EventBus, storage: Storage):
        self._bus = bus
        self._storage = storage
        self._modules: dict[str, ModuleEntry] = {}
        self._lock = asyncio.Lock()

    def add(self, name: str, instance: Any, enabled: bool = True) -> None:
        self._modules[name] = ModuleEntry(name=name, instance=instance, enabled=enabled)
        if enabled:
            self._bus.register(instance, name=name)
            logger.info("Module '%s' added and enabled", name)
        else:
            logger.info("Module '%s' added but disabled", name)

    async def enable(self, name: str) -> bool:
        """Enable a module. Returns True if state changed, False if already enabled."""
        async with self._lock:
            entry = self._modules.get(name)
            if entry is None:
                return False
            if entry.enabled:
                return False
            self._bus.register(entry.instance, name=name)
            entry.enabled = True
            self._persist_state()
            logger.info("Module '%s' enabled", name)
            if name == "member":
                tb = self._modules.get("task_breakdown")
                if tb and tb.enabled:
                    logger.warning(
                        "Re-enabled 'member' — task assignment load data may be stale"
                    )
            return True

    async def disable(self, name: str) -> bool:
        """Disable a module. Returns True if state changed, False if already disabled."""
        async with self._lock:
            entry = self._modules.get(name)
            if entry is None:
                return False
            if not entry.enabled:
                return False
            self._bus.unregister(name)
            entry.enabled = False
            self._persist_state()
            logger.info("Module '%s' disabled", name)
            if name == "member":
                tb = self._modules.get("task_breakdown")
                if tb and tb.enabled:
                    logger.warning(
                        "Disabled 'member' while 'task_breakdown' is enabled — "
                        "task assignment load data will become stale"
                    )
            if name == "communication":
                logger.warning(
                    "Disabled 'communication' — Lark command channel is now inoperable, "
                    "use Admin API to re-enable"
                )
            return True

    def get_status(self) -> list[dict[str, Any]]:
        return [
            {"name": e.name, "enabled": e.enabled, "type": type(e.instance).__name__}
            for e in self._modules.values()
        ]

    def get(self, name: str) -> ModuleEntry | None:
        return self._modules.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._modules.keys())

    def _persist_state(self) -> None:
        """Write current enabled/disabled state to .grove/runtime/modules-state.yml."""
        state = {
            "modules": {name: entry.enabled for name, entry in self._modules.items()}
        }
        self._storage.write_yaml("runtime/modules-state.yml", state)


def merge_module_state(modules_cfg: ModulesConfig, storage: Storage) -> dict[str, bool]:
    """Merge config.yml modules with runtime state. Runtime values take priority."""
    # Start with config defaults
    result = {
        "communication": modules_cfg.communication,
        "prd_generator": modules_cfg.prd_generator,
        "task_breakdown": modules_cfg.task_breakdown,
        "daily_report": modules_cfg.daily_report,
        "pr_review": modules_cfg.pr_review,
        "doc_sync": modules_cfg.doc_sync,
        "member": modules_cfg.member,
    }

    # Override with runtime state if it exists
    try:
        runtime = storage.read_yaml("runtime/modules-state.yml")
        for key, value in runtime.get("modules", {}).items():
            if key in result:
                result[key] = bool(value)
            else:
                logger.warning("Unknown module '%s' in runtime state, ignoring", key)
    except FileNotFoundError:
        pass

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_core/test_module_registry.py -v`

- [ ] **Step 5: Commit**

```bash
git add grove/core/module_registry.py tests/test_core/test_module_registry.py
git commit -m "feat: ModuleRegistry with hot-toggle, persistence, and state merge"
```

---

### Task 3: Admin API Router

**Files:**
- Create: `grove/ingress/admin.py`
- Modify: `grove/config.py`
- Test: `tests/test_ingress/test_admin.py`

- [ ] **Step 1: Add admin_token to config**

Add to `grove/config.py` in `GroveConfig`:

```python
    admin_token: str = ""  # Empty = admin endpoints not mounted
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_ingress/test_admin.py
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from grove.ingress.admin import create_admin_router
from grove.core.module_registry import ModuleRegistry
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import EventType
from grove.core.storage import Storage
from pathlib import Path


class TestAdminAPI:
    @pytest.fixture
    def app(self, grove_dir: Path):
        bus = EventBus()
        storage = Storage(grove_dir)
        registry = ModuleRegistry(bus=bus, storage=storage)

        class DummyMod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event): pass

        registry.add("pr_review", DummyMod(), enabled=True)
        registry.add("doc_sync", DummyMod(), enabled=False)

        app = FastAPI()
        app.include_router(create_admin_router(registry, admin_token="test_token"))
        return app

    def test_list_modules(self, app):
        client = TestClient(app)
        resp = client.get("/admin/modules", headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        modules = resp.json()["modules"]
        names = {m["name"] for m in modules}
        assert "pr_review" in names
        assert "doc_sync" in names

    def test_disable_module(self, app):
        client = TestClient(app)
        resp = client.post("/admin/modules/pr_review/disable",
                          headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_enable_module(self, app):
        client = TestClient(app)
        resp = client.post("/admin/modules/doc_sync/enable",
                          headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_unknown_module_404(self, app):
        client = TestClient(app)
        resp = client.post("/admin/modules/nonexistent/disable",
                          headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 404

    def test_no_auth_401(self, app):
        client = TestClient(app)
        resp = client.get("/admin/modules")
        assert resp.status_code == 401

    def test_wrong_token_401(self, app):
        client = TestClient(app)
        resp = client.get("/admin/modules", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ingress/test_admin.py -v`

- [ ] **Step 4: Implement admin.py**

```python
# grove/ingress/admin.py
"""Admin API for runtime module management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from grove.core.module_registry import ModuleRegistry

logger = logging.getLogger(__name__)


def create_admin_router(registry: ModuleRegistry, admin_token: str) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin"])

    async def verify_token(authorization: Optional[str] = Header(None)):
        if not authorization or authorization != f"Bearer {admin_token}":
            raise HTTPException(status_code=401, detail="Invalid or missing admin token")

    @router.get("/modules", dependencies=[Depends(verify_token)])
    async def list_modules():
        return {"modules": registry.get_status()}

    @router.post("/modules/{name}/enable", dependencies=[Depends(verify_token)])
    async def enable_module(name: str):
        if name not in registry.names:
            raise HTTPException(status_code=404, detail=f"Unknown module: {name}")
        changed = await registry.enable(name)
        entry = registry.get(name)
        return {"name": name, "enabled": entry.enabled, "changed": changed}

    @router.post("/modules/{name}/disable", dependencies=[Depends(verify_token)])
    async def disable_module(name: str):
        if name not in registry.names:
            raise HTTPException(status_code=404, detail=f"Unknown module: {name}")
        changed = await registry.disable(name)
        entry = registry.get(name)
        return {"name": name, "enabled": entry.enabled, "changed": changed}

    return router
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ingress/test_admin.py -v`

- [ ] **Step 6: Commit**

```bash
git add grove/ingress/admin.py grove/config.py tests/test_ingress/test_admin.py
git commit -m "feat: Admin API with bearer token auth for module hot-toggle"
```

---

### Task 4: Lark Toggle Commands

**Files:**
- Modify: `grove/modules/communication/intent_parser.py`
- Modify: `grove/modules/communication/prompts.py`
- Modify: `grove/modules/communication/handler.py`
- Test: `tests/test_modules/test_communication/test_handler.py` (add tests)

- [ ] **Step 1: Add new intents to intent_parser.py**

Add to the `Intent` enum:

```python
    TOGGLE_MODULE = "toggle_module"
    QUERY_MODULE_STATUS = "query_module_status"
```

- [ ] **Step 2: Update prompts.py**

Replace `INTENT_PARSE_PROMPT` with version that includes toggle intents:

```python
INTENT_PARSE_PROMPT = """\
你是 Grove 的意图识别引擎。分析用户消息，判断其意图。

可能的意图：
- new_requirement: 提出新需求或产品想法
- query_progress: 询问项目进度或任务状态
- request_task_change: 请求调整任务
- request_breakdown: 请求拆解需求
- request_assignment: 请求任务分配
- continue_conversation: 在已有对话中的后续回复
- toggle_module: 开启或关闭某个功能模块（如"关闭 PR 审查"、"开启每日巡检"）
- query_module_status: 查询模块状态（如"模块状态"、"哪些功能开着"）
- general_chat: 普通闲聊或不相关消息

模块名映射（用于 toggle_module）：
- 交互沟通 = communication
- PRD 生成 = prd_generator
- 任务拆解 = task_breakdown
- 每日巡检 = daily_report
- PR 审查 = pr_review
- 文档同步 = doc_sync
- 成员管理 = member

以 JSON 格式回复：{"intent": "...", "topic": "...", "confidence": 0.0-1.0}
- 对于 toggle_module，topic 格式为 "enable:模块key" 或 "disable:模块key"，如 "disable:pr_review"
只回复 JSON，不要其他内容。
"""
```

- [ ] **Step 3: Add toggle handling to handler.py**

The `CommunicationModule.__init__` needs to accept `registry` parameter. Add toggle handling in `on_lark_message`:

```python
# Updated __init__:
def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
             github: GitHubClient, config: GroveConfig,
             registry=None):
    self.bus = bus
    self.llm = llm
    self.lark = lark
    self.github = github
    self.config = config
    self.registry = registry  # ModuleRegistry, None if not available
    self._intent_parser = IntentParser(llm=llm)
```

Add in the intent routing (after existing elif blocks, before the else):

```python
        elif parsed.intent == Intent.TOGGLE_MODULE:
            await self._handle_toggle_module(event, parsed, chat_id)
        elif parsed.intent == Intent.QUERY_MODULE_STATUS:
            await self._handle_module_status(event, chat_id)
```

Add the handler methods:

```python
    async def _handle_toggle_module(self, event: Event, parsed, chat_id: str) -> None:
        if self.registry is None:
            await self.lark.send_text(chat_id, "模块管理功能未启用。")
            return
        if event.member.authority != "owner":
            await self.lark.send_text(chat_id,
                f"{event.member.name}，模块开关需要 owner 权限。")
            return
        # Parse "enable:pr_review" or "disable:pr_review" from topic
        topic = parsed.topic
        if ":" not in topic:
            await self.lark.send_text(chat_id, "无法识别模块名，请说具体一点。")
            return
        action, module_name = topic.split(":", 1)
        if module_name not in self.registry.names:
            await self.lark.send_text(chat_id, f"未知模块：{module_name}")
            return
        MODULE_DISPLAY = {
            "communication": "交互沟通", "prd_generator": "PRD 生成",
            "task_breakdown": "任务拆解", "daily_report": "每日巡检",
            "pr_review": "PR 审查", "doc_sync": "文档同步", "member": "成员管理",
        }
        display = MODULE_DISPLAY.get(module_name, module_name)
        if action == "enable":
            changed = await self.registry.enable(module_name)
            msg = f"已开启「{display}」模块。" if changed else f"「{display}」模块已经是开启状态。"
        elif action == "disable":
            changed = await self.registry.disable(module_name)
            msg = f"已关闭「{display}」模块。" if changed else f"「{display}」模块已经是关闭状态。"
        else:
            msg = "无法识别操作，请说"开启"或"关闭"。"
        await self.lark.send_text(chat_id, msg)

    async def _handle_module_status(self, event: Event, chat_id: str) -> None:
        if self.registry is None:
            await self.lark.send_text(chat_id, "模块管理功能未启用。")
            return
        MODULE_DISPLAY = {
            "communication": "交互沟通", "prd_generator": "PRD 生成",
            "task_breakdown": "任务拆解", "daily_report": "每日巡检",
            "pr_review": "PR 审查", "doc_sync": "文档同步", "member": "成员管理",
        }
        status = self.registry.get_status()
        lines = ["📋 **模块状态**\n"]
        for m in status:
            icon = "🟢" if m["enabled"] else "🔴"
            display = MODULE_DISPLAY.get(m["name"], m["name"])
            lines.append(f"{icon} {display}")
        await self.lark.send_text(chat_id, "\n".join(lines))
```

- [ ] **Step 4: Write tests for toggle**

Add to `tests/test_modules/test_communication/test_handler.py`:

```python
class TestCommunicationToggle:
    @pytest.fixture
    def module_with_registry(self, grove_dir: Path):
        from grove.core.module_registry import ModuleRegistry
        from grove.core.storage import Storage
        bus = EventBus()
        llm = MagicMock()
        lark = MagicMock()
        lark.send_text = AsyncMock()
        github = MagicMock()
        config = MagicMock()
        config.lark.chat_id = "oc_test"
        storage = Storage(grove_dir)
        registry = ModuleRegistry(bus=bus, storage=storage)

        class DummyMod:
            pass
        registry.add("pr_review", DummyMod(), enabled=True)

        module = CommunicationModule(
            bus=bus, llm=llm, lark=lark, github=github,
            config=config, registry=registry,
        )
        bus.register(module)
        return module, bus, registry

    async def test_toggle_disable_by_owner(self, module_with_registry):
        mod, bus, registry = module_with_registry
        mod._intent_parser.parse = AsyncMock(
            return_value=ParsedIntent(intent=Intent.TOGGLE_MODULE, topic="disable:pr_review", confidence=0.95))
        member = Member(name="Allen", github="allen", lark_id="ou_xxx", role="fullstack", authority="owner")
        event = Event(type=EventType.LARK_MESSAGE, source="lark",
                     payload={"text": "关闭 PR 审查", "chat_id": "oc_test"},
                     member=member)
        await bus.dispatch(event)
        mod.lark.send_text.assert_called_once()
        assert "已关闭" in mod.lark.send_text.call_args[0][1]

    async def test_toggle_rejected_for_member(self, module_with_registry):
        mod, bus, registry = module_with_registry
        mod._intent_parser.parse = AsyncMock(
            return_value=ParsedIntent(intent=Intent.TOGGLE_MODULE, topic="disable:pr_review", confidence=0.95))
        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx", role="frontend", authority="member")
        event = Event(type=EventType.LARK_MESSAGE, source="lark",
                     payload={"text": "关闭 PR 审查", "chat_id": "oc_test"},
                     member=member)
        await bus.dispatch(event)
        assert "owner 权限" in mod.lark.send_text.call_args[0][1]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modules/test_communication/ -v`

- [ ] **Step 6: Commit**

```bash
git add grove/modules/communication/ tests/test_modules/test_communication/
git commit -m "feat: Lark toggle commands — enable/disable modules via chat"
```

---

### Task 5: Wire Up main.py + .gitignore

**Files:**
- Modify: `grove/main.py`
- Modify: `.gitignore`

- [ ] **Step 1: Update main.py**

Add imports at top:
```python
from grove.core.module_registry import ModuleRegistry, merge_module_state
from grove.ingress.admin import create_admin_router
```

Replace the module registration block in `lifespan` with:

```python
    # Merge config + runtime state
    effective_modules = merge_module_state(config.modules, storage)

    # Module registry
    registry = ModuleRegistry(bus=event_bus, storage=storage)
    app.state.module_registry = registry

    # Conversation manager
    conv_manager = ConversationManager(storage)

    # Always instantiate all modules
    member_module = MemberModule(resolver=resolver, storage=storage)
    communication = CommunicationModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, registry=registry,
    )
    prd_generator = PRDGeneratorModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, conv_manager=conv_manager,
    )
    task_breakdown = TaskBreakdownModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        member_module=member_module, resolver=resolver,
    )
    daily_report = DailyReportModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        resolver=resolver, storage=storage,
    )
    pr_review = PRReviewModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
    )
    doc_sync = DocSyncModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )

    # Register via registry (respects merged state)
    registry.add("communication", communication, enabled=effective_modules["communication"])
    registry.add("prd_generator", prd_generator, enabled=effective_modules["prd_generator"])
    registry.add("member", member_module, enabled=effective_modules["member"])
    registry.add("task_breakdown", task_breakdown, enabled=effective_modules["task_breakdown"])
    registry.add("daily_report", daily_report, enabled=effective_modules["daily_report"])
    registry.add("pr_review", pr_review, enabled=effective_modules["pr_review"])
    registry.add("doc_sync", doc_sync, enabled=effective_modules["doc_sync"])

    # Admin API (only if token configured)
    if config.admin_token:
        app.include_router(create_admin_router(registry, config.admin_token))
        logger.info("Admin API enabled at /admin/modules")
```

- [ ] **Step 2: Add .grove/runtime/ to .gitignore**

Append: `.grove/runtime/`

- [ ] **Step 3: Verify import**

Run: `.venv/bin/python -c "from grove.main import app; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add grove/main.py .gitignore
git commit -m "feat: wire ModuleRegistry + admin router into main.py"
```

---

### Task 6: Full Test Suite + Lint

- [ ] **Step 1: Run all tests**

Run: `.venv/bin/pytest -v --tb=short`

- [ ] **Step 2: Run linter**

Run: `.venv/bin/ruff check grove/ tests/`

- [ ] **Step 3: Fix any issues and commit**

```bash
git add -A && git commit -m "fix: resolve test/lint issues from hot-toggle feature"
```

---

## Completion Criteria

- [ ] EventBus supports `register(module, name)` and `unregister(name)`
- [ ] ModuleRegistry tracks instances, enables/disables via EventBus
- [ ] `merge_module_state` merges config.yml + runtime state
- [ ] Admin API: GET/POST with bearer token auth
- [ ] Lark commands: "@Grove 关闭 PR 审查" (owner only)
- [ ] Runtime state persisted to `.grove/runtime/modules-state.yml`
- [ ] All tests pass, lint clean
