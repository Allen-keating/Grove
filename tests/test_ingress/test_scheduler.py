import pytest
from unittest.mock import AsyncMock
from grove.config import SchedulesConfig
from grove.ingress.scheduler import create_scheduler

class TestScheduler:
    def test_creates_all_jobs(self):
        schedules = SchedulesConfig(
            daily_report="09:00", doc_drift_check="09:00",
            project_overview="10:00", morning_dispatch="09:15",
        )
        on_event = AsyncMock()
        scheduler = create_scheduler(
            schedules=schedules, timezone="Asia/Shanghai", on_event=on_event,
        )
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "daily_report" in job_ids
        assert "doc_drift_check" in job_ids
        assert "project_overview" in job_ids
        assert "morning_dispatch" in job_ids
        assert len(job_ids) == 4
