"""Member module — maintains task/load cache for team members."""
import logging
from grove.core.event_bus import subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage

logger = logging.getLogger(__name__)

class MemberModule:
    _TASKS_PATH = "memory/profiles/member-tasks.yml"

    def __init__(self, resolver: MemberResolver, storage: Storage):
        self._resolver = resolver
        self._storage = storage
        self._tasks: dict[str, list[dict]] = {m.github: [] for m in resolver.all()}
        self._load_tasks()

    def _load_tasks(self) -> None:
        try:
            saved = self._storage.read_yaml(self._TASKS_PATH)
            for username, tasks in saved.items():
                if username in self._tasks:
                    self._tasks[username] = tasks
        except FileNotFoundError:
            pass

    def _persist_tasks(self) -> None:
        self._storage.write_yaml(self._TASKS_PATH, self._tasks)

    @subscribe(EventType.INTERNAL_TASK_ASSIGNED)
    async def on_task_assigned(self, event: Event) -> None:
        username = event.payload.get("github_username", "")
        if username not in self._tasks:
            self._tasks[username] = []
        self._tasks[username].append({
            "issue_number": event.payload.get("issue_number"),
            "issue_title": event.payload.get("issue_title", ""),
            "status": "assigned",
        })
        self._persist_tasks()
        logger.info("Task #%s assigned to %s (load: %d)",
                    event.payload.get("issue_number"), username, self.get_load(username))

    def get_tasks(self, github_username: str) -> list[dict]:
        return list(self._tasks.get(github_username, []))

    def get_load(self, github_username: str) -> int:
        return len(self._tasks.get(github_username, []))

    def get_all_loads(self) -> dict[str, int]:
        return {username: len(tasks) for username, tasks in self._tasks.items()}
