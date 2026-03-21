# grove/modules/task_breakdown/assigner.py
"""Smart task assignment based on skills and workload."""
import logging
from grove.core.events import Member
from grove.core.member_resolver import MemberResolver
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.decomposer import DecomposedTask

logger = logging.getLogger(__name__)

class TaskAssigner:
    def __init__(self, resolver: MemberResolver, member_module: MemberModule):
        self._resolver = resolver
        self._member_module = member_module

    def suggest(self, task: DecomposedTask) -> Member | None:
        candidates = []
        for member in self._resolver.all():
            if member.role == "design" and "design" not in task.labels:
                continue
            if "design" in task.labels and member.role != "design":
                continue
            skill_match = len(set(member.skills) & set(task.required_skills))
            total_skills = len(task.required_skills) if task.required_skills else 1
            match_ratio = skill_match / total_skills
            load = self._member_module.get_load(member.github)
            score = match_ratio * 10 - load
            candidates.append((member, score, match_ratio))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0]
        if best[2] == 0 and task.required_skills:
            return None
        logger.info("Suggested %s for '%s' (match=%.0f%%, load=%d)",
                    best[0].github, task.title, best[2] * 100,
                    self._member_module.get_load(best[0].github))
        return best[0]
