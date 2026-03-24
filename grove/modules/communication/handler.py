# grove/modules/communication/handler.py
"""Communication module — the hub for all natural language interactions."""
import logging
from datetime import datetime, timezone
from grove.config import GroveConfig
from grove.core.storage import Storage
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.communication.intent_parser import Intent, IntentParser
from grove.modules.communication.prompts import RESPONSE_PROMPT

logger = logging.getLogger(__name__)

class CommunicationModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, registry=None, storage: Storage | None = None):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self.registry = registry
        self._storage = storage
        self._intent_parser = IntentParser(llm=llm)

    @subscribe(EventType.LARK_MESSAGE)
    async def on_lark_message(self, event: Event) -> None:
        if event.member is None:
            logger.debug("Ignoring message from unknown member")
            return

        text = event.payload.get("text", "")
        chat_id = event.payload.get("chat_id", "")

        # Build context for intent parser
        context = {"chat_type": event.payload.get("chat_type", "group")}
        if self._storage and event.member:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            dispatch_path = f"memory/dispatch/{today}/{event.member.github}.json"
            if self._storage.exists(dispatch_path):
                try:
                    session = self._storage.read_json(dispatch_path)
                    context["has_active_dispatch"] = session.get("status") != "confirmed"
                except Exception:
                    context["has_active_dispatch"] = False

        parsed = await self._intent_parser.parse(text, event.member, context=context)
        logger.info("Intent: %s (%.2f) from %s: '%s'",
                    parsed.intent, parsed.confidence, event.member.name, text[:50])

        if parsed.intent == Intent.NEW_REQUIREMENT:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_NEW_REQUIREMENT, source="internal",
                payload={"topic": parsed.topic, "original_text": text, "chat_id": chat_id},
                member=event.member,
            ))
        elif parsed.intent == Intent.QUERY_PROGRESS:
            await self._handle_progress_query(event, chat_id)
        elif parsed.intent == Intent.GENERAL_CHAT:
            await self._handle_general_chat(event, text, chat_id)
        elif parsed.intent == Intent.TOGGLE_MODULE:
            await self._handle_toggle_module(event, parsed, chat_id)
        elif parsed.intent == Intent.QUERY_MODULE_STATUS:
            await self._handle_module_status(event, chat_id)
        elif parsed.intent == Intent.CONTINUE_CONVERSATION:
            await self.bus.dispatch(Event(
                type=EventType.LARK_MESSAGE, source="internal",
                payload={**event.payload, "intent": "continue_conversation"},
                member=event.member,
            ))
        elif parsed.intent == Intent.SCAN_PROJECT:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_SCAN_PROJECT, source="internal",
                payload={"chat_id": chat_id}, member=event.member,
            ))
        elif parsed.intent == Intent.QUERY_PROJECT_OVERVIEW:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_PROJECT_OVERVIEW, source="internal",
                payload={"chat_id": chat_id}, member=event.member,
            ))
        elif parsed.intent == Intent.DISPATCH_NEGOTIATE:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_DISPATCH_NEGOTIATE, source="internal",
                payload={"text": text, "chat_id": chat_id,
                         "sender_id": event.payload.get("sender_id", "")},
                member=event.member,
            ))
        elif parsed.intent == Intent.REORGANIZE_BASELINE:
            await self.bus.dispatch(Event(
                type=EventType.INTERNAL_REORGANIZE_BASELINE, source="internal",
                payload={"chat_id": chat_id}, member=event.member,
            ))
        else:
            await self.lark.send_text(chat_id,
                f"收到，{event.member.name}。不过我不太确定你需要什么，能再说具体一点吗？")

    @subscribe(EventType.ISSUE_COMMENTED)
    async def on_issue_commented(self, event: Event) -> None:
        if event.member is None:
            return
        comment_body = event.payload.get("comment", {}).get("body", "")
        if "@grove-pm" not in comment_body.lower() and "@grove" not in comment_body.lower():
            return
        logger.info("GitHub comment from %s: %s", event.member.name, comment_body[:50])

    async def _handle_progress_query(self, event: Event, chat_id: str) -> None:
        system_prompt = RESPONSE_PROMPT.format(
            member_name=event.member.name, member_role=event.member.role,
            member_authority=event.member.authority)
        response = await self.llm.chat(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": f"{event.member.name}问：{event.payload.get('text', '')}"}])
        await self.lark.send_text(chat_id, response)

    async def _handle_general_chat(self, event: Event, text: str, chat_id: str) -> None:
        system_prompt = RESPONSE_PROMPT.format(
            member_name=event.member.name, member_role=event.member.role,
            member_authority=event.member.authority)
        response = await self.llm.chat(system_prompt=system_prompt,
                                       messages=[{"role": "user", "content": text}])
        await self.lark.send_text(chat_id, response)

    async def _handle_toggle_module(self, event, parsed, chat_id):
        if self.registry is None:
            await self.lark.send_text(chat_id, "模块管理功能未启用。")
            return
        if event.member.authority != "owner":
            await self.lark.send_text(chat_id,
                f"{event.member.name}，模块开关需要 owner 权限。")
            return
        topic = parsed.topic
        if ":" not in topic:
            await self.lark.send_text(chat_id, "无法识别模块名，请说具体一点。")
            return
        action, module_name = topic.split(":", 1)
        if module_name not in self.registry.names:
            await self.lark.send_text(chat_id, f"未知模块：{module_name}")
            return
        MODULE_DISPLAY = {
            "communication": "交互沟通", "prd_generator": "PRD 生成",
            "task_breakdown": "任务拆解", "daily_report": "每日巡检",
            "pr_review": "PR 审查", "doc_sync": "文档同步", "member": "成员管理",
            "project_scanner": "项目扫描", "project_overview": "项目总览",
            "morning_dispatch": "每日任务", "prd_baseline": "PRD 基线",
        }
        display = MODULE_DISPLAY.get(module_name, module_name)
        if action == "enable":
            changed = await self.registry.enable(module_name)
            msg = f"已开启「{display}」模块。" if changed else f"「{display}」模块已经是开启状态。"
        elif action == "disable":
            changed = await self.registry.disable(module_name)
            msg = f"已关闭「{display}」模块。" if changed else f"「{display}」模块已经是关闭状态。"
        else:
            msg = '无法识别操作，请说"开启"或"关闭"。'
        await self.lark.send_text(chat_id, msg)

    async def _handle_module_status(self, event, chat_id):
        if self.registry is None:
            await self.lark.send_text(chat_id, "模块管理功能未启用。")
            return
        MODULE_DISPLAY = {
            "communication": "交互沟通", "prd_generator": "PRD 生成",
            "task_breakdown": "任务拆解", "daily_report": "每日巡检",
            "pr_review": "PR 审查", "doc_sync": "文档同步", "member": "成员管理",
            "project_scanner": "项目扫描", "project_overview": "项目总览",
            "morning_dispatch": "每日任务", "prd_baseline": "PRD 基线",
        }
        status = self.registry.get_status()
        lines = ["📋 **模块状态**\n"]
        for m in status:
            icon = "🟢" if m["enabled"] else "🔴"
            display = MODULE_DISPLAY.get(m["name"], m["name"])
            lines.append(f"{icon} {display}")
        await self.lark.send_text(chat_id, "\n".join(lines))
