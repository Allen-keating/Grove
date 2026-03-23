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
