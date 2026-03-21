"""Event bus with declarative @subscribe decorator and async dispatch."""

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
        self._failed_events_path = failed_events_path

    def register(self, module: Any) -> None:
        """Scan a module instance for @subscribe-decorated methods and register them."""
        for attr_name in dir(module):
            method = getattr(module, attr_name, None)
            if method is None or not callable(method):
                continue
            event_types = getattr(method, _SUBSCRIBE_ATTR, None)
            if event_types:
                for event_type in event_types:
                    self._handlers[event_type].append(method)
                    logger.info(
                        "Registered %s.%s for event '%s'",
                        type(module).__name__,
                        attr_name,
                        event_type,
                    )

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
        """Dispatch an event to all registered handlers. Errors are logged, not raised."""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
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
