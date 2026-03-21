# grove/modules/communication/handler.py
"""Communication module — the hub for all natural language interactions."""
import logging
from grove.config import GroveConfig
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
                 github: GitHubClient, config: GroveConfig):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._intent_parser = IntentParser(llm=llm)

    @subscribe(EventType.LARK_MESSAGE)
    async def on_lark_message(self, event: Event) -> None:
        if event.member is None:
            logger.debug("Ignoring message from unknown member")
            return

        text = event.payload.get("text", "")
        chat_id = event.payload.get("chat_id", "")
        parsed = await self._intent_parser.parse(text, event.member)
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
        elif parsed.intent == Intent.CONTINUE_CONVERSATION:
            await self.bus.dispatch(Event(
                type=EventType.LARK_MESSAGE, source="internal",
                payload={**event.payload, "intent": "continue_conversation"},
                member=event.member,
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
