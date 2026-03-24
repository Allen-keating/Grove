"""Task breakdown module — decompose PRD, create Issues, assign via cards."""
import logging
from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_task_assignment_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.member.handler import MemberModule
from grove.modules.task_breakdown.assigner import TaskAssigner
from grove.modules.task_breakdown.decomposer import TaskDecomposer

logger = logging.getLogger(__name__)

_PENDING_PATH = "memory/task-breakdown/pending-assignments.json"


class TaskBreakdownModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig,
                 member_module: MemberModule, resolver: MemberResolver,
                 storage: Storage | None = None):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._decomposer = TaskDecomposer(llm=llm)
        self._assigner = TaskAssigner(resolver=resolver, member_module=member_module)
        self._pending_assignments: dict[int, dict] = self._load_assignments()

    def _load_assignments(self) -> dict[int, dict]:
        if self._storage is None:
            return {}
        try:
            raw = self._storage.read_json(_PENDING_PATH)
            return {int(k): v for k, v in raw.items()}
        except FileNotFoundError:
            return {}

    def _persist_assignments(self) -> None:
        if self._storage is None:
            return
        self._storage.write_json(
            _PENDING_PATH, {str(k): v for k, v in self._pending_assignments.items()})

    @subscribe(EventType.INTERNAL_PRD_FINALIZED)
    async def on_prd_finalized(self, event: Event) -> None:
        topic = event.payload.get("topic", "")
        prd_doc_id = event.payload.get("prd_doc_id")
        repo = self.config.project.repo

        prd_content = f"PRD: {topic}"
        if prd_doc_id:
            try:
                prd_content = await self.lark.read_doc(prd_doc_id)
            except Exception:
                logger.warning("Could not read PRD doc %s", prd_doc_id)

        await self.lark.send_text(self.config.lark.chat_id,
                                  f"PRD「{topic}」已定稿，正在拆解任务...")

        tasks = await self._decomposer.decompose(topic, prd_content)
        if not tasks:
            await self.lark.send_text(self.config.lark.chat_id, "任务拆解失败，请手动创建 Issues。")
            return

        for task in tasks:
            try:
                issue = await self.github.create_issue(repo=repo, title=task.title,
                                                  body=task.body, labels=task.labels)
                issue_number = issue.number
            except Exception:
                logger.exception("Failed to create issue for '%s'", task.title)
                continue

            suggested = self._assigner.suggest(task)
            if suggested:
                self._pending_assignments[issue_number] = {
                    "assignee_github": suggested.github, "task_title": task.title,
                }
                self._persist_assignments()
                priority = next((lb for lb in task.labels if lb.startswith("P")), "P1")
                card = build_task_assignment_card(
                    task_title=task.title, issue_number=issue_number,
                    priority=priority, estimated_days=task.estimated_days,
                    assignee_name=suggested.name, repo=repo,
                )
                await self.lark.send_card(self.config.lark.chat_id, card)

        await self.lark.send_text(self.config.lark.chat_id,
                                  f"已创建 {len(tasks)} 个 Issues，请在上方卡片中确认任务分配。")

    @subscribe(EventType.LARK_CARD_ACTION)
    async def on_card_action(self, event: Event) -> None:
        action_value = event.payload.get("action", {}).get("value", {})
        action = action_value.get("action")
        issue_number = action_value.get("issue_number")

        if issue_number is None or issue_number not in self._pending_assignments:
            return

        assignment = self._pending_assignments[issue_number]
        repo = self.config.project.repo

        if action == "accept":
            await self.github.update_issue(repo, issue_number, assignee=assignment["assignee_github"])
            await self.lark.send_text(self.config.lark.chat_id,
                f"✅ #{issue_number}「{assignment['task_title']}」已分配给 {assignment['assignee_github']}")
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_TASK_ASSIGNED, source="internal",
                payload={"github_username": assignment["assignee_github"],
                         "issue_number": issue_number, "issue_title": assignment["task_title"]},
            ))
            del self._pending_assignments[issue_number]
            self._persist_assignments()
        elif action == "reject":
            await self.lark.send_text(self.config.lark.chat_id,
                f"#{issue_number}「{assignment['task_title']}」分配已取消，请手动分配。")
            del self._pending_assignments[issue_number]
            self._persist_assignments()
        elif action == "negotiate":
            await self.lark.send_text(self.config.lark.chat_id,
                f"#{issue_number}「{assignment['task_title']}」需要调整，请在群里讨论后手动分配。")
            del self._pending_assignments[issue_number]
            self._persist_assignments()
