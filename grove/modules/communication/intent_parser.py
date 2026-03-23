# grove/modules/communication/intent_parser.py
"""LLM-based intent recognition for user messages."""
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from grove.core.events import Member
from grove.integrations.llm.client import LLMClient

logger = logging.getLogger(__name__)

class Intent(StrEnum):
    NEW_REQUIREMENT = "new_requirement"
    QUERY_PROGRESS = "query_progress"
    REQUEST_TASK_CHANGE = "request_task_change"
    REQUEST_BREAKDOWN = "request_breakdown"
    REQUEST_ASSIGNMENT = "request_assignment"
    CONTINUE_CONVERSATION = "continue_conversation"
    GENERAL_CHAT = "general_chat"
    TOGGLE_MODULE = "toggle_module"
    QUERY_MODULE_STATUS = "query_module_status"
    UNKNOWN = "unknown"

@dataclass
class ParsedIntent:
    intent: str
    topic: str = ""
    confidence: float = 0.0
    raw_response: str = ""

class IntentParser:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def parse(self, text: str, member: Member) -> ParsedIntent:
        from grove.modules.communication.prompts import INTENT_PARSE_PROMPT
        try:
            response = await self.llm.chat(
                system_prompt=INTENT_PARSE_PROMPT,
                messages=[{"role": "user", "content": f"发送者: {member.name} (角色: {member.role})\n消息: {text}"}],
                max_tokens=256,
            )
            data = json.loads(response)
            return ParsedIntent(
                intent=data.get("intent", Intent.UNKNOWN),
                topic=data.get("topic", ""),
                confidence=data.get("confidence", 0.0),
                raw_response=response,
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Intent parse failed: %s", exc)
            return ParsedIntent(intent=Intent.UNKNOWN, raw_response=str(exc))
