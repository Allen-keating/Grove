"""Prompt templates for project scanning and reverse PRD generation."""

ARCHITECTURE_ANALYSIS_PROMPT = """\
你是一位资深架构师。根据以下仓库信息，分析项目的技术架构。

目录结构：
{repo_tree}

依赖文件：
{dependencies}

README：
{readme}

请输出：
1. 技术栈（语言、框架、数据库等）
2. 模块划分（每个主要目录的职责）
3. 层次架构（如 MVC、微服务、事件驱动等）

用中文，简洁专业，不超过 500 字。
"""

FEATURE_ANALYSIS_PROMPT = """\
你是一位产品经理。根据以下信息，逆向推导项目已实现的功能。

技术架构分析：
{architecture}

目录结构：
{repo_tree}

近期 Commit 摘要（按类型聚合）：
{commit_summary}

GitHub Issues 标题列表：
{issues}

请输出 JSON 数组，每个元素为：
{{"name": "功能名", "status": "completed|in_progress|planned", "description": "一句话描述"}}

只输出 JSON，不要其他内容。
"""

REVERSE_PRD_PROMPT = """\
你是一位产品经理。根据以下信息，生成一份项目 PRD 文档。

项目架构：
{architecture}

已实现功能：
{features}

GitHub Milestones：
{milestones}

请生成标准 PRD 格式的 Markdown 文档，包含：
1. 概述（项目背景、目标用户）
2. 已实现功能（按模块分类）
3. 待开发功能（从 Issues 和 Milestones 推断，标注"由 Grove 逆向推导，待团队确认"）
4. 技术架构
5. 里程碑与排期

重要：这是逆向生成的草稿，在文档顶部标注：
> ⚠️ 本文档由 Grove 自动逆向生成，请团队审阅并补充「未来规划」部分。

用中文。
"""
