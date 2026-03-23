from datetime import datetime

from grove.core.events import Event, EventType, Member


class TestEventType:
    def test_github_event_types_exist(self):
        assert EventType.PR_OPENED == "pr.opened"
        assert EventType.PR_MERGED == "pr.merged"
        assert EventType.ISSUE_OPENED == "issue.opened"
        assert EventType.ISSUE_UPDATED == "issue.updated"
        assert EventType.ISSUE_COMMENTED == "issue.commented"
        assert EventType.ISSUE_LABELED == "issue.labeled"

    def test_lark_event_types_exist(self):
        assert EventType.LARK_MESSAGE == "lark.message"
        assert EventType.LARK_CARD_ACTION == "lark.card_action"
        assert EventType.LARK_DOC_UPDATED == "lark.doc_updated"

    def test_cron_event_types_exist(self):
        assert EventType.CRON_DAILY_REPORT == "cron.daily_report"
        assert EventType.CRON_DOC_DRIFT_CHECK == "cron.doc_drift_check"

    def test_internal_event_types_exist(self):
        assert EventType.INTERNAL_NEW_REQUIREMENT == "internal.new_requirement"
        assert EventType.INTERNAL_PRD_FINALIZED == "internal.prd_finalized"
        assert EventType.INTERNAL_TASK_ASSIGNED == "internal.task_assigned"
        assert EventType.INTERNAL_RISK_DETECTED == "internal.risk_detected"


class TestMember:
    def test_create_member(self):
        m = Member(name="张三", github="zhangsan", lark_id="ou_xxx1", role="frontend")
        assert m.name == "张三"
        assert m.github == "zhangsan"
        assert m.lark_id == "ou_xxx1"
        assert m.role == "frontend"

    def test_member_optional_fields(self):
        m = Member(name="张三", github="zhangsan", lark_id="ou_xxx1", role="frontend")
        assert m.skills == []
        assert m.authority == "member"


class TestEvent:
    def test_create_event(self):
        event = Event(
            type=EventType.PR_OPENED,
            source="github",
            payload={"pr_number": 42},
        )
        assert event.type == "pr.opened"
        assert event.source == "github"
        assert event.payload == {"pr_number": 42}
        assert event.member is None
        assert event.id.startswith("evt_")

    def test_event_auto_generates_id_and_timestamp(self):
        e1 = Event(type=EventType.PR_OPENED, source="github", payload={})
        e2 = Event(type=EventType.PR_OPENED, source="github", payload={})
        assert e1.id != e2.id
        assert isinstance(e1.timestamp, datetime)

    def test_event_with_member(self):
        member = Member(name="张三", github="zhangsan", lark_id="ou_xxx1", role="frontend")
        event = Event(
            type=EventType.LARK_MESSAGE,
            source="lark",
            payload={"text": "hello"},
            member=member,
        )
        assert event.member.name == "张三"


def test_new_event_types_exist():
    from grove.core.events import EventType
    assert EventType.INTERNAL_SCAN_PROJECT == "internal.scan_project"
    assert EventType.INTERNAL_PROJECT_OVERVIEW == "internal.project_overview"
    assert EventType.CRON_PROJECT_OVERVIEW == "cron.project_overview"
    assert EventType.CRON_MORNING_DISPATCH == "cron.morning_dispatch"
    assert EventType.INTERNAL_DISPATCH_NEGOTIATE == "internal.dispatch_negotiate"
