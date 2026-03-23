"""APScheduler setup for cron-based event emission."""
import logging
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from grove.config import SchedulesConfig
from grove.core.events import Event, EventType

logger = logging.getLogger(__name__)

_SCHEDULE_MAP = {
    "daily_report": EventType.CRON_DAILY_REPORT,
    "doc_drift_check": EventType.CRON_DOC_DRIFT_CHECK,
    "project_overview": EventType.CRON_PROJECT_OVERVIEW,
    "morning_dispatch": EventType.CRON_MORNING_DISPATCH,
}


def create_scheduler(
    schedules: SchedulesConfig,
    timezone: str,
    on_event: Callable[[Event], Awaitable[None]],
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone)

    for field_name, event_type in _SCHEDULE_MAP.items():
        time_str = getattr(schedules, field_name, None)
        if not time_str:
            continue
        hour, minute = time_str.split(":")

        async def _emit(et=event_type, fn=field_name):
            logger.info("Cron: emitting %s event", fn)
            await on_event(Event(type=et, source="scheduler", payload={}))

        scheduler.add_job(_emit, "cron", hour=int(hour), minute=int(minute), id=field_name)

    return scheduler
