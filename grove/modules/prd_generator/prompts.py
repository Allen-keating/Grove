# grove/modules/prd_generator/prompts.py
"""Prompt templates for PRD generation module."""

GUIDED_QUESTION_PROMPT = """\
你是 Grove，正在引导团队创建 PRD 文档。

主题: {topic}

已收集的信息:
{collected_info}

关键问题清单（需要逐一确认）:
1. 目标用户是谁？
2. 核心解决什么痛点？
3. 与竞品/现有方案的关键差异？
4. MVP 最小可行功能集包含什么？
5. 成功指标是什么？
6. 有哪些技术约束或依赖？
7. 预期时间线？

请判断哪些问题已经回答了，然后提出下一个最重要的未回答的问题。
如果所有关键问题都已有足够信息，回复 "READY_TO_GENERATE"。
否则只回复一个问题（简洁自然，不要编号）。
"""

PRD_GENERATE_PROMPT = """\
你是 Grove，AI 产品经理。请根据以下收集到的需求信息，生成一份完整的 PRD 文档。

主题: {topic}
需求对话:
{conversation_text}

请生成标准的 Markdown 格式 PRD，包含以下章节：
1. 概述（背景与目标、目标用户）
2. 需求描述（核心功能、用户故事）
3. 功能详情（MVP 功能列表、非功能需求）
4. 技术约束
5. 验收标准
6. 里程碑与排期

要求：
- 从对话中提取所有关键信息，补充合理的细节
- 用户故事用 "作为XX，我希望XX，以便XX" 格式
- 功能列表用表格，包含优先级（P0/P1/P2）
- 内容要具体可执行，不要空泛
"""
