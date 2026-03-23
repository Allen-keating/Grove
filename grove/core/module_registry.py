"""Registry for managing module lifecycle and hot-toggle."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any


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
