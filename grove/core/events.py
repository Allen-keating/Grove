"""Event types and data models for the Grove event bus."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from dataclasses import dataclass, field
from typing import Any


class EventType(StrEnum):
    """All event types in the Grove system."""

    # GitHub events
    PR_OPENED = "pr.opened"
    PR_MERGED = "pr.merged"
    PR_REVIEW_REQUESTED = "pr.review_requested"
    ISSUE_OPENED = "issue.opened"
    ISSUE_UPDATED = "issue.updated"
    ISSUE_COMMENTED = "issue.commented"
    ISSUE_LABELED = "issue.labeled"

    # Lark events
    LARK_MESSAGE = "lark.message"
    LARK_CARD_ACTION = "lark.card_action"
    LARK_DOC_UPDATED = "lark.doc_updated"

    # Cron events
    CRON_DAILY_REPORT = "cron.daily_report"
    CRON_DOC_DRIFT_CHECK = "cron.doc_drift_check"

    # Internal events (module-to-module)
    INTERNAL_NEW_REQUIREMENT = "internal.new_requirement"
    INTERNAL_PRD_FINALIZED = "internal.prd_finalized"
    INTERNAL_TASK_ASSIGNED = "internal.task_assigned"
    INTERNAL_RISK_DETECTED = "internal.risk_detected"
    INTERNAL_SCAN_PROJECT = "internal.scan_project"
    INTERNAL_PROJECT_OVERVIEW = "internal.project_overview"
    CRON_PROJECT_OVERVIEW = "cron.project_overview"
    CRON_MORNING_DISPATCH = "cron.morning_dispatch"
    INTERNAL_DISPATCH_NEGOTIATE = "internal.dispatch_negotiate"


@dataclass
class Member:
    """A team member resolved from team.yml."""

    name: str
    github: str
    lark_id: str
    role: str
    skills: list[str] = field(default_factory=list)
    authority: str = "member"


def _generate_event_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"evt_{ts}_{short_uuid}"


@dataclass
class Event:
    """A standardized event flowing through the Grove event bus."""

    type: str  # EventType value
    source: str  # "github" | "lark" | "scheduler" | "internal"
    payload: dict[str, Any]
    member: Member | None = None
    id: str = field(default_factory=_generate_event_id)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
