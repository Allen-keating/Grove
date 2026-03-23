"""Shared commit classification: conventional-commit rules + LLM fallback."""
import json
import logging
import re

logger = logging.getLogger(__name__)

_PREFIX_MAP = {
    "feat": "feature",
    "fix": "bugfix",
    "docs": "docs",
    "refactor": "refactor",
    "chore": "chore",
    "test": "chore",
    "ci": "chore",
    "build": "chore",
    "style": "chore",
    "perf": "refactor",
}

_CONVENTIONAL_RE = re.compile(r"^(\w+)(?:\(.+?\))?[!]?:\s")

_CLASSIFY_PROMPT = """\
根据 commit message 和修改的文件列表，判断这个提交的类型。
只返回 JSON：{"type": "feature" | "bugfix" | "refactor" | "docs" | "chore"}
不要其他内容。
"""


def classify_commit_by_rule(message: str) -> str | None:
    """Try to classify using conventional commit prefix. Returns None if no match."""
    match = _CONVENTIONAL_RE.match(message)
    if match:
        prefix = match.group(1).lower()
        return _PREFIX_MAP.get(prefix)
    return None


async def classify_commit(
    message: str, files_changed: list[str], *, llm=None,
) -> str:
    """Classify a commit. Uses rule matching first, LLM fallback if needed."""
    result = classify_commit_by_rule(message)
    if result is not None:
        return result

    if llm is None:
        return "chore"

    try:
        response = await llm.chat(
            system_prompt=_CLASSIFY_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Message: {message}\nFiles: {', '.join(files_changed[:20])}",
            }],
            max_tokens=64,
        )
        data = json.loads(response)
        commit_type = data.get("type", "chore")
        if commit_type in ("feature", "bugfix", "refactor", "docs", "chore"):
            return commit_type
        return "chore"
    except Exception:
        logger.warning("LLM classify_commit failed for: %s", message[:80])
        return "chore"
