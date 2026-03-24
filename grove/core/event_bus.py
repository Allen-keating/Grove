"""Event bus with declarative @subscribe decorator and async dispatch."""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from grove.core.events import Event

logger = logging.getLogger(__name__)

_SUBSCRIBE_ATTR = "_grove_subscriptions"


def subscribe(event_type: str) -> Callable:
    """Decorator to mark a method as an event handler."""

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, _SUBSCRIBE_ATTR):
            setattr(func, _SUBSCRIBE_ATTR, [])
        getattr(func, _SUBSCRIBE_ATTR).append(event_type)
        return func

    return decorator


class EventBus:
    """Central event dispatcher. Modules register themselves; the bus routes events."""

    def __init__(self, failed_events_path: Path | None = None):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._module_handlers: dict[str, list[tuple[str, Callable]]] = {}
        self._failed_events_path = failed_events_path

    def register(self, module: Any, name: str | None = None) -> None:
        """Scan a module instance for @subscribe-decorated methods and register them."""
        module_name = name or type(module).__name__
        registered: list[tuple[str, Callable]] = []
        for attr_name in dir(module):
            method = getattr(module, attr_name, None)
            if method is None or not callable(method):
                continue
            event_types = getattr(method, _SUBSCRIBE_ATTR, None)
            if event_types:
                for event_type in event_types:
                    self._handlers[event_type].append(method)
                    registered.append((event_type, method))
                    logger.info(
                        "Registered %s.%s for event '%s'",
                        module_name,
                        attr_name,
                        event_type,
                    )
        self._module_handlers[module_name] = registered

    def unregister(self, name: str) -> bool:
        """Remove all handlers registered under the given module name.

        Returns True if the module was found and removed, False otherwise.
        """
        registered = self._module_handlers.pop(name, None)
        if registered is None:
            return False
        for event_type, method in registered:
            handlers = self._handlers.get(event_type)
            if handlers is not None:
                try:
                    handlers.remove(method)
                except ValueError:
                    pass
        return True

    def _log_failed_event(self, event: Event, handler_name: str, error: str) -> None:
        """Append failed event to .grove/logs/failed-events.jsonl."""
        if self._failed_events_path is None:
            return
        try:
            self._failed_events_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "event_id": event.id,
                "event_type": event.type,
                "handler": handler_name,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(self._failed_events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write failed-event log")

    async def dispatch(self, event: Event) -> None:
        """Dispatch an event to all registered handlers concurrently."""
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            return

        async def _safe_call(handler):
            try:
                await handler(event)
            except Exception as exc:
                handler_name = (
                    f"{type(handler.__self__).__name__}.{handler.__name__}"
                    if hasattr(handler, "__self__")
                    else handler.__name__
                )
                logger.exception("Handler %s failed for event %s", handler_name, event.id)
                self._log_failed_event(event, handler_name, str(exc))

        await asyncio.gather(*(_safe_call(h) for h in handlers))
