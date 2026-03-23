"""Prompt templates for project overview report."""

OVERVIEW_ANALYSIS_PROMPT = """\
你是 Grove，AI 产品经理。分析以下项目数据，给出项目健康度评估。

Issues 完成率: {completion_rate}%
本周关闭 Issues: {closed_this_week}
本周新增 Issues: {new_this_week}
里程碑:
{milestones}

PRD 完成度:
{prd_completion}

请输出 JSON：
{{
  "health": "🟢 正常" | "🟡 需关注" | "🔴 风险",
  "risks": ["风险1", "风险2", "风险3"],
  "suggestions": "2-3条建议"
}}
只输出 JSON。
"""
