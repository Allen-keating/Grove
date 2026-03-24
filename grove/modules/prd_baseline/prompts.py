"""Prompt templates for PRD baseline management."""

FEATURE_MATCH_PROMPT = """\
你是 Grove，AI 产品经理。分析这个 PR 是否与基线中的某个功能相关。

PR 的 commit messages：
{commits}

基线中未完成的功能：
{pending_features}

每个功能的详细 PRD（如有）：
{feature_prds}

请判断：
1. match_type: 这个 PR 与基线中已有功能相关(existing)？还是一个全新功能(new)？还是不涉及功能变更(none)？
2. 如果 existing 或 new：
   - matched_feature: 功能名
   - status: "in_progress"（部分实现）还是 "completed"（核心需求全覆盖）？
   - reason: 判断理由

输出 JSON 数组（一个 PR 可能涉及多个功能）：
[{{"match_type": "existing"|"new"|"none", "matched_feature": "功能名"|null, "status": "in_progress"|"completed"|null, "confidence": 0.0-1.0, "reason": "理由"}}]

如果不涉及任何功能，返回 [{{"match_type": "none", "matched_feature": null, "status": null, "confidence": 0.0, "reason": "不涉及功能变更"}}]。
不要强行匹配。宁可返回 none 也不要低置信度的猜测。
"""

REORGANIZE_BASELINE_PROMPT = """\
你是 Grove，AI 产品经理。请重新整理以下项目基线文档。

当前基线文档：
{baseline_content}

各功能详细 PRD（如有）：
{feature_prds}

请：
1. 保持文档结构不变（概述、技术架构、功能清单、里程碑、近期开发活动）
2. 功能清单中：合并重复项、修正描述、改善排列顺序（按重要性）
3. 保持 ✅/🔄/⬚ 标记和 PRD 链接
4. 用中文，简洁专业

输出完整的 Markdown 文档。
"""
