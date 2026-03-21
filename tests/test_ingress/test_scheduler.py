from unittest.mock import AsyncMock


from grove.ingress.scheduler import create_scheduler


class TestScheduler:
    def test_create_scheduler_registers_daily_report(self):
        on_event = AsyncMock()
        scheduler = create_scheduler(
            daily_report_time="09:00",
            doc_drift_time="09:00",
            timezone="Asia/Shanghai",
            on_event=on_event,
        )
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "daily_report" in job_ids
        assert "doc_drift_check" in job_ids

    def test_scheduler_not_started(self):
        on_event = AsyncMock()
        scheduler = create_scheduler(
            daily_report_time="09:00",
            doc_drift_time="09:00",
            timezone="Asia/Shanghai",
            on_event=on_event,
        )
        assert scheduler.running is False
