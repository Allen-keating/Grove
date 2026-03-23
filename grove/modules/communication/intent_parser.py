# grove/modules/communication/intent_parser.py
"""Intent recognition: rule-based fast path + LLM fallback."""
import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from grove.core.events import Member
from grove.integrations.llm.client import LLMClient

logger = logging.getLogger(__name__)


# -- Intent types --
# Intents are split into two groups:
# - RULE_INTENTS: matched by keyword/regex, never sent to LLM
# - LLM_INTENTS: require semantic understanding, handled by LLM

class Intent(StrEnum):
    # LLM-classified intents
    NEW_REQUIREMENT = "new_requirement"
    QUERY_PROGRESS = "query_progress"
    REQUEST_TASK_CHANGE = "request_task_change"
    REQUEST_BREAKDOWN = "request_breakdown"
    REQUEST_ASSIGNMENT = "request_assignment"
    CONTINUE_CONVERSATION = "continue_conversation"
    GENERAL_CHAT = "general_chat"
    # Rule-matched intents (not in LLM prompt)
    TOGGLE_MODULE = "toggle_module"
    QUERY_MODULE_STATUS = "query_module_status"
    SCAN_PROJECT = "scan_project"
    QUERY_PROJECT_OVERVIEW = "query_project_overview"
    DISPATCH_NEGOTIATE = "dispatch_negotiate"
    # Fallback
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    intent: str
    topic: str = ""
    confidence: float = 0.0
    raw_response: str = ""


# -- Rule-based matching infrastructure --

MODULE_ALIASES: dict[str, str] = {
    "交互沟通": "communication", "沟通": "communication",
    "prd 生成": "prd_generator", "prd生成": "prd_generator", "prd": "prd_generator",
    "任务拆解": "task_breakdown", "拆解": "task_breakdown",
    "每日巡检": "daily_report", "巡检": "daily_report",
    "pr 审查": "pr_review", "pr审查": "pr_review",
    "文档同步": "doc_sync",
    "成员管理": "member",
    "项目扫描": "project_scanner",
    "项目总览": "project_overview",
    "每日任务": "morning_dispatch",
}

_TOGGLE_ACTION_MAP: dict[str, str] = {
    "开启": "enable", "启用": "enable", "打开": "enable",
    "关闭": "disable", "禁用": "disable", "停用": "disable",
}

_ACTION_WORDS = "|".join(re.escape(w) for w in _TOGGLE_ACTION_MAP)
_MODULE_NAMES = "|".join(re.escape(w) for w in sorted(MODULE_ALIASES, key=len, reverse=True))

# Match both "关闭 PR 审查" and "把 PR 审查关闭" / "帮我把巡检开启"
_TOGGLE_PATTERNS = [
    re.compile(rf"({_ACTION_WORDS})\s*({_MODULE_NAMES})"),       # action + module
    re.compile(rf"({_MODULE_NAMES})\s*({_ACTION_WORDS})"),       # module + action
]

_NEGATION_RE = re.compile(r"不要|不想|别|不用|不需要|没必要|取消")

_KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["模块状态", "哪些功能", "功能列表", "模块列表"], Intent.QUERY_MODULE_STATUS),
    (["扫描项目", "生成项目文档", "更新项目文档"], Intent.SCAN_PROJECT),
    (["项目总览", "项目进度报告", "项目概况"], Intent.QUERY_PROJECT_OVERVIEW),
]

# LLM should only return these intents; anything else is clamped to UNKNOWN
_LLM_VALID_INTENTS = frozenset({
    Intent.NEW_REQUIREMENT, Intent.QUERY_PROGRESS,
    Intent.REQUEST_TASK_CHANGE, Intent.REQUEST_BREAKDOWN,
    Intent.REQUEST_ASSIGNMENT, Intent.CONTINUE_CONVERSATION,
    Intent.GENERAL_CHAT,
})


class IntentParser:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def _try_rule_match(self, text: str, context: dict) -> ParsedIntent | None:
        """Attempt to match intent via rules. Returns None if no rule matches."""
        # Rule 1: Active dispatch session in private chat
        if context.get("has_active_dispatch") and context.get("chat_type") == "p2p":
            return ParsedIntent(intent=Intent.DISPATCH_NEGOTIATE, topic=text, confidence=0.95)

        normalized = text.strip().lower()

        # Skip rule matching if text contains negation — let LLM handle nuance
        if _NEGATION_RE.search(normalized):
            return None

        # Rule 2: Keyword matching
        for keywords, intent in _KEYWORD_RULES:
            if any(kw in normalized for kw in keywords):
                return ParsedIntent(intent=intent, confidence=1.0)

        # Rule 3: Toggle module — supports "关闭 PR 审查" and "把 PR 审查关闭"
        for pattern in _TOGGLE_PATTERNS:
            m = pattern.search(normalized)
            if m:
                g1, g2 = m.group(1), m.group(2)
                # Determine which group is the action and which is the module
                if g1 in _TOGGLE_ACTION_MAP:
                    action_zh, module_text = g1, g2
                else:
                    module_text, action_zh = g1, g2
                module_key = MODULE_ALIASES.get(module_text)
                if module_key:
                    action = _TOGGLE_ACTION_MAP[action_zh]
                    return ParsedIntent(
                        intent=Intent.TOGGLE_MODULE,
                        topic=f"{action}:{module_key}",
                        confidence=1.0,
                    )

        return None

    async def parse(self, text: str, member: Member, context: dict | None = None) -> ParsedIntent:
        ctx = context or {}

        # Fast path: rule-based matching
        rule_match = self._try_rule_match(text, ctx)
        if rule_match:
            logger.debug("Rule match: %s for '%s'", rule_match.intent, text[:30])
            return rule_match

        # Fallback: LLM intent classification
        from grove.modules.communication.prompts import INTENT_PARSE_PROMPT
        try:
            response = await self.llm.chat(
                system_prompt=INTENT_PARSE_PROMPT,
                messages=[{"role": "user", "content": f"发送者: {member.name} (角色: {member.role})\n消息: {text}"}],
                max_tokens=256,
            )
            data = json.loads(response)
            intent = data.get("intent", Intent.UNKNOWN)
            # Clamp unexpected intents to UNKNOWN
            if intent not in _LLM_VALID_INTENTS:
                logger.debug("LLM returned non-LLM intent '%s', clamping to UNKNOWN", intent)
                intent = Intent.UNKNOWN
            return ParsedIntent(
                intent=intent,
                topic=data.get("topic", ""),
                confidence=data.get("confidence", 0.0),
                raw_response=response,
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Intent parse failed: %s", exc)
            return ParsedIntent(intent=Intent.UNKNOWN, raw_response=str(exc))
