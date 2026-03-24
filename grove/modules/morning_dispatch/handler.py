"""Morning Task Dispatch — generate, negotiate, announce."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_dispatch_summary_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.morning_dispatch.negotiator import TaskNegotiator
from grove.modules.morning_dispatch.planner import TaskPlanner
from grove.modules.member.handler import MemberModule

logger = logging.getLogger(__name__)


class MorningDispatchModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage,
                 resolver: MemberResolver, member_module: MemberModule):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._resolver = resolver
        self._member_module = member_module
        self._planner = TaskPlanner(llm)
        self._negotiator = TaskNegotiator(llm)
        self._announce_lock = asyncio.Lock()
        self._deadline_task: asyncio.Task | None = None

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _session_path(self, date: str, github_username: str) -> str:
        return f"memory/dispatch/{date}/{github_username}.json"

    def _read_session(self, date: str, github_username: str) -> dict | None:
        try:
            return self._storage.read_json(self._session_path(date, github_username))
        except FileNotFoundError:
            return None

    def _write_session(self, date: str, github_username: str, session: dict) -> None:
        self._storage.write_json(self._session_path(date, github_username), session)

    def _already_announced(self, date: str) -> bool:
        try:
            meta = self._storage.read_json(f"memory/dispatch/{date}/_announced.json")
            return meta.get("announced", False)
        except FileNotFoundError:
            return False

    @subscribe(EventType.CRON_MORNING_DISPATCH)
    async def on_morning_dispatch(self, event: Event) -> None:
        logger.info("Morning dispatch triggered")
        date = self._today()
        repo = self.config.project.repo

        # Collect data
        issues = await self.github.list_issues(repo, state="open")
        milestones = await self.github.list_milestones(repo)

        if not issues:
            await self.lark.send_text(self.config.lark.chat_id,
                "当前无待办任务，今日无需派发。")
            return

        # Load yesterday snapshot for commit history
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            snapshot = self._storage.read_json(f"memory/snapshots/{yesterday}.json")
        except FileNotFoundError:
            snapshot = {}

        milestones_text = "\n".join(
            f"- {m['title']}: due {m.get('due_on', 'N/A')}" for m in milestones
        ) or "无"

        issues_text = "\n".join(
            f"- #{i.number} [{', '.join(i.labels)}] {i.title}" for i in issues[:50]
        )

        # Generate plan for each member
        members = self._resolver.all()
        for member in members:
            load = self._member_module.get_load(member.github)
            commits_by_member = snapshot.get("commits_by_member", {})
            member_commits = f"{commits_by_member.get(member.github, 0)} commits yesterday"

            plan = await self._planner.plan_for_member(
                member=member, current_load=load,
                yesterday_commits=member_commits,
                open_issues=issues_text, milestones=milestones_text,
            )

            session = {
                "status": "negotiating",
                "tasks": plan.get("tasks", []),
                "summary": plan.get("summary", ""),
                "messages": [],
                "confirmed_at": None,
            }
            self._write_session(date, member.github, session)

            # Send private message
            if plan.get("tasks"):
                task_lines = []
                for idx, t in enumerate(plan["tasks"], 1):
                    task_lines.append(f"{idx}. #{t['issue_number']} {t['title']} — {t.get('reason', '')}")
                msg = (
                    f"早上好 {member.name}！以下是今日建议工作内容：\n\n"
                    + "\n".join(task_lines)
                    + "\n\n如需调整请直接告诉我，或回复「确认」。"
                )
            else:
                msg = f"早上好 {member.name}！任务生成失败，请手动查看 GitHub Issues。"
            await self.lark.send_private(member.lark_id, msg)

        # Schedule deadline
        delay = self.config.dispatch.confirm_deadline_minutes * 60
        self._deadline_task = asyncio.create_task(self._schedule_deadline(date, delay))
        logger.info("Morning dispatch sent to %d members, deadline in %d min",
                    len(members), self.config.dispatch.confirm_deadline_minutes)

    @subscribe(EventType.INTERNAL_DISPATCH_NEGOTIATE)
    async def on_dispatch_negotiate(self, event: Event) -> None:
        if event.member is None:
            return
        date = self._today()
        session = self._read_session(date, event.member.github)

        if session is None or session.get("status") == "confirmed":
            await self.lark.send_private(event.member.lark_id,
                "今日任务已公示，如需调整请直接在群里沟通。")
            return

        text = event.payload.get("text", "")
        session.setdefault("messages", []).append({"role": "user", "content": text})

        # Check negotiate round limit
        max_rounds = self.config.dispatch.max_negotiate_rounds
        if len(session["messages"]) > max_rounds * 2:
            await self.lark.send_private(event.member.lark_id,
                "协商轮次已达上限，请回复「确认」完成确认。")
            return

        result = await self._negotiator.parse_reply(session.get("tasks", []), text)

        if result["action"] == "confirm":
            session["status"] = "confirmed"
            session["confirmed_at"] = datetime.now(timezone.utc).isoformat()
            self._write_session(date, event.member.github, session)
            await self.lark.send_private(event.member.lark_id, "✅ 今日任务已确认！")
            await self._check_all_confirmed(date)
        elif result["action"] == "remove":
            session["tasks"] = [
                t for t in session["tasks"]
                if t.get("issue_number") != result.get("issue_number")
            ]
            self._write_session(date, event.member.github, session)
            await self._send_updated_tasks(event.member, session)
        elif result["action"] == "add":
            session["tasks"].append({
                "issue_number": result.get("issue_number", 0),
                "title": result.get("detail", ""),
                "reason": "成员手动添加",
            })
            self._write_session(date, event.member.github, session)
            await self._send_updated_tasks(event.member, session)
        else:
            await self.lark.send_private(event.member.lark_id,
                "收到。如需调整任务请告诉我具体操作，或回复「确认」。")
            self._write_session(date, event.member.github, session)

    async def _send_updated_tasks(self, member, session) -> None:
        if not session["tasks"]:
            await self.lark.send_private(member.lark_id,
                "当前任务列表为空。请添加任务或回复「确认」。")
            return
        task_lines = [f"- #{t['issue_number']} {t['title']}" for t in session["tasks"]]
        await self.lark.send_private(member.lark_id,
            "已更新任务列表：\n" + "\n".join(task_lines) + "\n\n回复「确认」完成确认。")

    async def _check_all_confirmed(self, date: str) -> None:
        members = self._resolver.all()
        all_confirmed = True
        for m in members:
            session = self._read_session(date, m.github)
            if session and session.get("status") != "confirmed":
                all_confirmed = False
                break
        if all_confirmed:
            await self._announce_to_group(date, force=False)

    async def _schedule_deadline(self, date: str, delay_seconds: int) -> None:
        await asyncio.sleep(delay_seconds)
        if not self._already_announced(date):
            await self._announce_to_group(date, force=True)

    async def _announce_to_group(self, date: str, force: bool) -> None:
        async with self._announce_lock:
            if self._already_announced(date):
                return

            members = self._resolver.all()
            member_tasks = []
            for m in members:
                session = self._read_session(date, m.github)
                tasks = session.get("tasks", []) if session else []
                confirmed = session.get("status") == "confirmed" if session else False
                task_data = [
                    {"priority": "P0", "issue_number": t.get("issue_number", 0), "title": t.get("title", "")}
                    for t in tasks
                ]
                member_tasks.append({
                    "name": m.name, "tasks": task_data, "confirmed": confirmed,
                })

                if force and not confirmed:
                    await self.lark.send_private(m.lark_id,
                        "你的今日任务已按建议方案公示，如需调整随时告诉我。")

            card = build_dispatch_summary_card(date=date, member_tasks=member_tasks)
            await self.lark.send_card(self.config.lark.chat_id, card)

            self._storage.write_json(f"memory/dispatch/{date}/_announced.json",
                {"announced": True, "date": datetime.now(timezone.utc).isoformat()})

            if self._deadline_task and not self._deadline_task.done():
                self._deadline_task.cancel()

            logger.info("Morning dispatch announced for %s", date)
