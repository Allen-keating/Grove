"""APScheduler setup for cron-based event emission."""
import logging
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from grove.core.events import Event, EventType

logger = logging.getLogger(__name__)


def create_scheduler(
    daily_report_time: str,
    doc_drift_time: str,
    timezone: str,
    on_event: Callable[[Event], Awaitable[None]],
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone)

    report_hour, report_minute = daily_report_time.split(":")
    drift_hour, drift_minute = doc_drift_time.split(":")

    async def emit_daily_report():
        logger.info("Cron: emitting daily_report event")
        await on_event(Event(type=EventType.CRON_DAILY_REPORT, source="scheduler", payload={}))

    async def emit_doc_drift_check():
        logger.info("Cron: emitting doc_drift_check event")
        await on_event(Event(type=EventType.CRON_DOC_DRIFT_CHECK, source="scheduler", payload={}))

    scheduler.add_job(
        emit_daily_report,
        "cron",
        hour=int(report_hour),
        minute=int(report_minute),
        id="daily_report",
    )
    scheduler.add_job(
        emit_doc_drift_check,
        "cron",
        hour=int(drift_hour),
        minute=int(drift_minute),
        id="doc_drift_check",
    )
    return scheduler
