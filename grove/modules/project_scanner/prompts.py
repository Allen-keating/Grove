"""Prompt templates for project scanning and baseline generation."""

ARCHITECTURE_ANALYSIS_PROMPT = """\
你是一位资深架构师。根据以下仓库信息，分析项目的技术架构。

目录结构：
{repo_tree}

关键源码（入口文件、模块入口的前 100 行）：
{source_snippets}

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

COMMIT_CLUSTER_PROMPT = """\
你是一位产品经理。将以下 commit messages 按功能分组归纳。

Commit messages：
{commits}

请将这些 commit 按功能单元分组，输出 JSON 数组：
[{{"feature": "功能名称", "commits": ["sha1", "sha2"], "description": "一句话功能描述"}}]

规则：
- 同一个功能的 commit 归为一组
- 纯重构(refactor)、纯测试(test)、纯 CI(ci) 的 commit 归入 "工程维护" 组
- 功能名称要简洁有意义
- 只输出 JSON，不要其他内容
"""

BASELINE_GENERATE_PROMPT = """\
你是一位产品经理。根据以下信息，生成项目基线文档。

项目名称：{project_name}
技术架构：
{architecture}

已识别功能（带状态）：
{features}

GitHub Milestones：
{milestones}

近期开发活动摘要：
{activity_summary}

请生成 Markdown 文档，严格遵循以下结构：

# {project_name} 项目基线文档

> ⚠️ 本文档由 Grove 自动维护。功能清单部分请通过 Grove 指令修改。

## 概述
（从架构和功能推断项目背景和目标用户）

## 技术架构
（直接使用上面的架构分析）

## 功能清单

### ✅ 已实现
（每行格式：- ✅ **功能名** — 描述）

### 🔄 进行中
（每行格式：- 🔄 **功能名** — 描述）

### ⬚ 待开发
（冷启动时此节为空）

## 里程碑与排期
（从 Milestones 生成）

## 近期开发活动
（commit 统计摘要）

用中文。
"""
