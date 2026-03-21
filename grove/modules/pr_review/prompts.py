"""Prompts for PR requirement alignment analysis."""

PR_ALIGNMENT_PROMPT = """\
你是 Grove，AI 产品经理。你正在从产品角度 review 一个 PR，判断代码实现是否与需求文档对齐。

注意：你只做产品层面的 review（需求对齐），不做代码质量 review。

PR 信息：
- PR #{pr_number}: {pr_title}
- 关联 Issue: {related_issues}

代码变更摘要（diff）：
{diff_summary}

需求文档（PRD 相关章节）：
{prd_content}

请分析并输出以下内容（Markdown 格式）：

## 🌳 Grove — 需求对齐检查

### 对齐度评估
（一句话概括）

### ✅ 已覆盖的需求
（列出已实现的需求点）

### ⚠️ 遗漏项
（需求中要求但未实现的，无则写"无"）

### 📌 超出范围
（代码有但需求未提及的，无则写"无"）

### 建议
（如有）
"""

DIFF_SUMMARY_PROMPT = """\
请用简洁的中文总结以下代码变更（diff），重点关注产品功能层面的变化。忽略纯格式、注释、测试文件的变更。

Diff:
{diff}

只输出产品层面的变更摘要，每条一行，用 "- " 开头。
"""
