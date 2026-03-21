# grove/modules/task_breakdown/prompts.py
"""Prompt templates for task decomposition."""

DECOMPOSE_PROMPT = """\
你是 Grove，AI 产品经理。请将以下 PRD 拆解为可执行的开发任务。

PRD 主题: {topic}
PRD 内容:
{prd_content}

以 JSON 格式回复：
{{
  "tasks": [
    {{
      "title": "任务标题",
      "body": "任务描述，包含验收标准",
      "labels": ["角色标签(frontend/backend/fullstack/design)", "优先级(P0/P1/P2)"],
      "estimated_days": 天数,
      "required_skills": ["所需技能"]
    }}
  ]
}}

要求：每个任务1-5天工作量，包含验收标准，标注技能。只回复JSON。
"""
