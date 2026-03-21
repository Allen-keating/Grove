# grove/modules/doc_sync/prompts.py
CLASSIFY_CHANGE_PROMPT = """\
你是 Grove，AI 产品经理。分析代码变更，判断是否为产品级变更。

PR 标题: {pr_title}
代码变更:
{diff}

判断：1) 产品级变更还是纯技术重构？2) 严重程度(none/small/medium/large)？3) 影响PRD哪些章节？

过滤：测试文件、CI配置、代码风格、内部重构不算产品变更。

JSON回复：{{"is_product_change": true/false, "severity": "none/small/medium/large",
  "description": "描述", "affected_prd_sections": ["章节"]}}
只回复JSON。
"""

DOC_UPDATE_PROMPT = """\
你是 Grove，AI 产品经理。根据代码变更生成PRD更新内容。

变更: {change_description}
影响章节: {affected_sections}
当前PRD:
{current_prd}

输出需要更新的Markdown内容，用产品语言，标注来源PR。
"""
