# tests/test_modules/test_communication/test_intent_data.py
"""
Large-scale parametrized test data for the intent matching system.

Coverage:
- Rule-matched intents (toggle_module, query_module_status, scan_project,
  query_project_overview) — LLM must NOT be called
- Negation cases — must fall through to LLM
- LLM fallback cases — must call LLM
- LLM intent clamping — LLM returns rule-only intent, expect UNKNOWN
- Edge cases
"""

from unittest.mock import AsyncMock
import pytest
from grove.core.events import Member
from grove.modules.communication.intent_parser import IntentParser, Intent


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def member():
    return Member(name="测试员", github="tester", lark_id="ou_test", role="backend")


@pytest.fixture
def parser():
    """Fresh IntentParser with AsyncMock LLM for every test case."""
    llm = AsyncMock()
    return IntentParser(llm=llm)


# ---------------------------------------------------------------------------
# toggle_module — rule path, LLM must NOT be called
# ---------------------------------------------------------------------------

# Format: (text, expected_topic)
TOGGLE_MODULE_CASES = [
    # Standard "action + module" order
    ("关闭 PR 审查", "disable:pr_review"),
    ("开启每日巡检", "enable:daily_report"),
    ("启用任务拆解", "enable:task_breakdown"),
    ("禁用文档同步", "disable:doc_sync"),
    ("停用成员管理", "disable:member"),
    ("打开prd生成", "enable:prd_generator"),
    ("启用项目扫描", "enable:project_scanner"),
    ("关闭每日任务", "disable:morning_dispatch"),
    ("开启沟通", "enable:communication"),
    ("禁用巡检", "disable:daily_report"),
    ("停用拆解", "disable:task_breakdown"),
    # Inverted order "module + action"
    ("把文档同步关闭", "disable:doc_sync"),
    ("帮我把任务拆解开启", "enable:task_breakdown"),
    ("将pr审查禁用", "disable:pr_review"),
    ("把每日巡检停用", "disable:daily_report"),
    ("把项目扫描启用", "enable:project_scanner"),
    # With filler words before the action+module pair
    ("帮我开启项目扫描", "enable:project_scanner"),
    ("请帮我关闭pr审查", "disable:pr_review"),
    ("麻烦你启用文档同步", "enable:doc_sync"),
    # All six action words, one each
    ("开启成员管理", "enable:member"),
    ("关闭成员管理", "disable:member"),
    ("启用每日任务", "enable:morning_dispatch"),
    ("禁用prd生成", "disable:prd_generator"),
    ("打开每日巡检", "enable:daily_report"),
    ("停用项目扫描", "disable:project_scanner"),
    # Alias variants
    ("开启pr 审查", "enable:pr_review"),          # space inside alias
    ("关闭prd", "disable:prd_generator"),          # short alias
    ("启用交互沟通", "enable:communication"),
    ("禁用沟通", "disable:communication"),
]


@pytest.mark.parametrize("text,expected_topic", TOGGLE_MODULE_CASES)
@pytest.mark.asyncio
async def test_toggle_module_rule_match(text, expected_topic, member):
    """toggle_module must be resolved by rule — LLM must not be called."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse(text, member)
    assert result.intent == Intent.TOGGLE_MODULE, (
        f"Expected TOGGLE_MODULE for '{text}', got {result.intent}"
    )
    assert result.topic == expected_topic, (
        f"Expected topic '{expected_topic}' for '{text}', got '{result.topic}'"
    )
    assert result.confidence == 1.0
    llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# query_module_status — rule path
# ---------------------------------------------------------------------------

QUERY_MODULE_STATUS_CASES = [
    "模块状态",
    "哪些功能开着",
    "哪些功能开着？",
    "看看功能列表",
    "模块列表",
    "现在模块状态怎么样",
    "给我看一下模块列表",
    "哪些功能是开启的",
    "当前功能列表是什么",
    "显示模块状态",
]


@pytest.mark.parametrize("text", QUERY_MODULE_STATUS_CASES)
@pytest.mark.asyncio
async def test_query_module_status_rule_match(text, member):
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse(text, member)
    assert result.intent == Intent.QUERY_MODULE_STATUS, (
        f"Expected QUERY_MODULE_STATUS for '{text}', got {result.intent}"
    )
    llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# scan_project — rule path
# ---------------------------------------------------------------------------

SCAN_PROJECT_CASES = [
    "扫描项目",
    "请扫描项目",
    "帮我扫描项目",
    "生成项目文档",
    "帮我更新项目文档",
    "更新项目文档",
    "重新生成项目文档",
    "请帮我扫描项目",
    "扫描项目，更新一下文档",
]


@pytest.mark.parametrize("text", SCAN_PROJECT_CASES)
@pytest.mark.asyncio
async def test_scan_project_rule_match(text, member):
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse(text, member)
    assert result.intent == Intent.SCAN_PROJECT, (
        f"Expected SCAN_PROJECT for '{text}', got {result.intent}"
    )
    llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# query_project_overview — rule path
# ---------------------------------------------------------------------------

QUERY_PROJECT_OVERVIEW_CASES = [
    "项目总览",
    "项目进度报告",
    "看看项目概况",
    "项目概况是什么",
    "给我项目总览",
    "显示项目总览",
    "我想看项目进度报告",
    "查看项目概况",
    "帮我生成项目进度报告",
]


@pytest.mark.parametrize("text", QUERY_PROJECT_OVERVIEW_CASES)
@pytest.mark.asyncio
async def test_query_project_overview_rule_match(text, member):
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse(text, member)
    assert result.intent == Intent.QUERY_PROJECT_OVERVIEW, (
        f"Expected QUERY_PROJECT_OVERVIEW for '{text}', got {result.intent}"
    )
    llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# Negation cases — must fall through to LLM, NOT match rules
# ---------------------------------------------------------------------------

# Format: (text, llm_returns_intent)
NEGATION_CASES = [
    ("我不想扫描项目", "general_chat"),
    ("不要关闭 PR 审查", "general_chat"),
    ("别开启每日巡检", "general_chat"),
    ("不需要项目总览", "general_chat"),
    ("取消扫描项目", "general_chat"),
    ("不用生成项目文档", "general_chat"),
    ("没必要更新项目文档", "general_chat"),
    ("不要启用文档同步", "general_chat"),
    ("不想开启任务拆解", "general_chat"),
    ("别禁用成员管理了", "general_chat"),
    ("取消关闭prd生成", "general_chat"),
    ("不需要模块状态", "general_chat"),
]


@pytest.mark.parametrize("text,llm_intent", NEGATION_CASES)
@pytest.mark.asyncio
async def test_negation_falls_through_to_llm(text, llm_intent, member):
    """Negation should skip rules and call LLM exactly once."""
    llm = AsyncMock()
    llm.chat.return_value = f'{{"intent": "{llm_intent}", "topic": "", "confidence": 0.7}}'
    p = IntentParser(llm=llm)
    result = await p.parse(text, member)
    # Result comes from LLM
    assert result.intent == llm_intent, (
        f"Expected LLM intent '{llm_intent}' for negation '{text}', got {result.intent}"
    )
    llm.chat.assert_called_once()


# ---------------------------------------------------------------------------
# LLM fallback cases — no rule matches, LLM must be called exactly once
# ---------------------------------------------------------------------------

# Format: (text, llm_returns_intent)
LLM_FALLBACK_CASES = [
    ("我想加个暗黑模式", "new_requirement"),
    ("能不能做个导出功能", "new_requirement"),
    ("目前进度怎么样", "query_progress"),
    ("张三手上几个任务", "query_progress"),
    ("整体进度如何", "query_progress"),
    ("这个任务能延期吗", "request_task_change"),
    ("我想换个任务做", "request_task_change"),
    ("帮我拆一下这个需求", "request_breakdown"),
    ("把这个分给李四", "request_assignment"),
    ("今天天气不错", "general_chat"),
    ("你好", "general_chat"),
    ("上次说的需求还在吗", "continue_conversation"),
    ("刚才那个功能再说一下", "continue_conversation"),
    ("sprint 还有几天结束", "query_progress"),
    ("能帮我看下 #205 这个 PR 吗", "general_chat"),
]


@pytest.mark.parametrize("text,llm_intent", LLM_FALLBACK_CASES)
@pytest.mark.asyncio
async def test_llm_fallback(text, llm_intent, member):
    """Messages with no rule match must call LLM exactly once."""
    llm = AsyncMock()
    llm.chat.return_value = f'{{"intent": "{llm_intent}", "topic": "", "confidence": 0.85}}'
    p = IntentParser(llm=llm)
    result = await p.parse(text, member)
    assert result.intent == llm_intent, (
        f"Expected '{llm_intent}' from LLM for '{text}', got {result.intent}"
    )
    llm.chat.assert_called_once()


# ---------------------------------------------------------------------------
# LLM intent clamping — LLM returns a rule-only intent → must clamp to UNKNOWN
# ---------------------------------------------------------------------------

# Format: (text, llm_raw_response)
LLM_CLAMP_CASES = [
    (
        "间接提到了模块开关",
        '{"intent": "toggle_module", "topic": "disable:pr_review", "confidence": 0.8}',
    ),
    (
        "顺便问下扫描的事",
        '{"intent": "scan_project", "topic": "", "confidence": 0.7}',
    ),
    (
        "想看看模块的情况",
        '{"intent": "query_module_status", "topic": "", "confidence": 0.75}',
    ),
    (
        "项目整体状况",
        '{"intent": "query_project_overview", "topic": "", "confidence": 0.6}',
    ),
    (
        "随便说说",
        '{"intent": "dispatch_negotiate", "topic": "", "confidence": 0.5}',
    ),
]


@pytest.mark.parametrize("text,llm_raw", LLM_CLAMP_CASES)
@pytest.mark.asyncio
async def test_llm_returns_rule_intent_clamped_to_unknown(text, llm_raw, member):
    """LLM returning a rule-only intent must be clamped to UNKNOWN."""
    llm = AsyncMock()
    llm.chat.return_value = llm_raw
    p = IntentParser(llm=llm)
    result = await p.parse(text, member)
    assert result.intent == Intent.UNKNOWN, (
        f"Expected UNKNOWN (clamped) for '{text}', got {result.intent}"
    )
    llm.chat.assert_called_once()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_string(member):
    """Empty string should fall through to LLM."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.5}'
    p = IntentParser(llm=llm)
    result = await p.parse("", member)
    llm.chat.assert_called_once()
    assert result.intent == Intent.GENERAL_CHAT


@pytest.mark.asyncio
async def test_very_long_string(member):
    """Very long message should fall through to LLM without error."""
    long_text = "帮我看一下 " * 200 + "目前进度怎么样"
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "query_progress", "topic": "", "confidence": 0.9}'
    p = IntentParser(llm=llm)
    result = await p.parse(long_text, member)
    llm.chat.assert_called_once()
    assert result.intent == Intent.QUERY_PROGRESS


@pytest.mark.asyncio
async def test_mixed_chinese_english_rule(member):
    """Mixed Chinese/English toggle command should still rule-match."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse("请关闭 PR 审查 module", member)
    assert result.intent == Intent.TOGGLE_MODULE
    assert result.topic == "disable:pr_review"
    llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_mixed_chinese_english_llm(member):
    """Mixed Chinese/English non-command should fall through to LLM."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.7}'
    p = IntentParser(llm=llm)
    await p.parse("let me know about the project status", member)
    llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_punctuation_only(member):
    """Punctuation-only string should fall through to LLM."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.5}'
    p = IntentParser(llm=llm)
    result = await p.parse("???!!!", member)
    llm.chat.assert_called_once()
    assert result.intent == Intent.GENERAL_CHAT


@pytest.mark.asyncio
async def test_whitespace_only(member):
    """Whitespace-only string should fall through to LLM."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.5}'
    p = IntentParser(llm=llm)
    await p.parse("   ", member)
    llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_looks_like_toggle_but_unknown_module(member):
    """Action word + unknown module name should fall through to LLM."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.7}'
    p = IntentParser(llm=llm)
    result = await p.parse("关闭不存在的模块", member)
    llm.chat.assert_called_once()
    assert result.intent == Intent.GENERAL_CHAT


@pytest.mark.asyncio
async def test_looks_like_toggle_but_action_word_only(member):
    """Action word alone (no module) should fall through to LLM."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.6}'
    p = IntentParser(llm=llm)
    await p.parse("关闭", member)
    llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_looks_like_scan_but_negated(member):
    """Negation prefix before scan keyword must bypass rule."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.7}'
    p = IntentParser(llm=llm)
    await p.parse("不用扫描项目", member)
    llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_llm_json_parse_error_returns_unknown(member):
    """LLM returning invalid JSON should return UNKNOWN without raising."""
    llm = AsyncMock()
    llm.chat.return_value = "这不是 JSON"
    p = IntentParser(llm=llm)
    result = await p.parse("随便说点什么", member)
    assert result.intent == Intent.UNKNOWN
    llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_negotiate_context_no_llm(member):
    """Active dispatch + p2p chat must resolve to DISPATCH_NEGOTIATE without LLM."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    context = {"has_active_dispatch": True, "chat_type": "p2p"}
    result = await p.parse("好的，没问题", member, context=context)
    assert result.intent == Intent.DISPATCH_NEGOTIATE
    assert result.confidence == 0.95
    llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_negotiate_group_chat_uses_llm(member):
    """Active dispatch but group chat must fall through to LLM."""
    llm = AsyncMock()
    llm.chat.return_value = '{"intent": "general_chat", "topic": "", "confidence": 0.8}'
    p = IntentParser(llm=llm)
    context = {"has_active_dispatch": True, "chat_type": "group"}
    result = await p.parse("没问题", member, context=context)
    assert result.intent == Intent.GENERAL_CHAT
    llm.chat.assert_called_once()


@pytest.mark.asyncio
async def test_keyword_with_surrounding_text_still_matches_scan(member):
    """Keyword embedded in longer text should still trigger rule match."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse("麻烦帮忙扫描项目一下谢谢", member)
    assert result.intent == Intent.SCAN_PROJECT
    llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_keyword_with_surrounding_text_still_matches_overview(member):
    """项目总览 embedded in sentence should still trigger rule match."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse("能给我看一下项目总览吗", member)
    assert result.intent == Intent.QUERY_PROJECT_OVERVIEW
    llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_scan_keyword_in_module_status_message(member):
    """模块列表 should match QUERY_MODULE_STATUS, not SCAN_PROJECT."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse("给我看下模块列表", member)
    assert result.intent == Intent.QUERY_MODULE_STATUS
    llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# Confidence and topic field checks for rule-matched intents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rule_match_confidence_is_1(member):
    """All rule-matched intents must return confidence == 1.0."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    for text, _ in TOGGLE_MODULE_CASES[:5]:
        result = await p.parse(text, member)
        assert result.confidence == 1.0, f"confidence should be 1.0 for '{text}'"


@pytest.mark.asyncio
async def test_scan_project_has_no_topic(member):
    """SCAN_PROJECT rule match should return empty topic."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse("扫描项目", member)
    assert result.intent == Intent.SCAN_PROJECT
    assert result.topic == ""


@pytest.mark.asyncio
async def test_query_module_status_has_no_topic(member):
    """QUERY_MODULE_STATUS rule match should return empty topic."""
    llm = AsyncMock()
    p = IntentParser(llm=llm)
    result = await p.parse("模块状态", member)
    assert result.intent == Intent.QUERY_MODULE_STATUS
    assert result.topic == ""
