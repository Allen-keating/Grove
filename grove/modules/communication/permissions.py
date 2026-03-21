"""Authority-based permission checking for Grove actions."""
from enum import StrEnum
from grove.core.events import Member


class Action(StrEnum):
    QUERY_PROGRESS = "query_progress"
    PROPOSE_IDEA = "propose_idea"
    REQUEST_TASK_CHANGE = "request_task_change"
    ACCEPT_TASK = "accept_task"
    APPROVE_CHANGE = "approve_change"
    ADJUST_PRIORITY = "adjust_priority"
    MODIFY_CONFIG = "modify_config"
    ADJUST_MILESTONE = "adjust_milestone"


_PERMISSIONS: dict[Action, str] = {
    Action.QUERY_PROGRESS: "member",
    Action.PROPOSE_IDEA: "member",
    Action.REQUEST_TASK_CHANGE: "member",
    Action.ACCEPT_TASK: "member",
    Action.APPROVE_CHANGE: "lead",
    Action.ADJUST_PRIORITY: "lead",
    Action.MODIFY_CONFIG: "owner",
    Action.ADJUST_MILESTONE: "owner",
}

_AUTHORITY_LEVELS = {"member": 0, "lead": 1, "owner": 2}


def check_permission(member: Member, action: Action) -> bool:
    required = _PERMISSIONS.get(action, "owner")
    member_level = _AUTHORITY_LEVELS.get(member.authority, 0)
    required_level = _AUTHORITY_LEVELS.get(required, 0)
    return member_level >= required_level
