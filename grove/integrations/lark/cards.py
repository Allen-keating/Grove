# grove/integrations/lark/cards.py
"""Lark interactive message card builders."""


def build_task_assignment_card(
    task_title: str, issue_number: int, priority: str,
    estimated_days: int, assignee_name: str, repo: str,
) -> dict:
    issue_url = f"https://github.com/{repo}/issues/{issue_number}"
    return {
        "header": {
            "title": {"tag": "plain_text", "content": "🌳 Grove — 新任务分配"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**任务：** {task_title}\n"
                        f"**优先级：** {priority}\n"
                        f"**关联 Issue：** [#{issue_number}]({issue_url})\n"
                        f"**预估工时：** {estimated_days} 天\n"
                        f"**分配给：** {assignee_name}"
                    ),
                },
            },
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 接受"},
                     "type": "primary", "value": {"action": "accept", "issue_number": issue_number}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "🔄 需要调整"},
                     "value": {"action": "negotiate", "issue_number": issue_number}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 无法承接"},
                     "type": "danger", "value": {"action": "reject", "issue_number": issue_number}},
                ],
            },
        ],
    }


def build_daily_report_card(
    date: str, milestone_summary: list[dict], member_activity: dict[str, int],
    risks: list[dict], suggestions: str,
) -> dict:
    ms_lines = [f"**{ms['title']}** 进度：{ms['progress_pct']}%（{ms['closed']}/{ms['closed'] + ms['open']}）"
                for ms in milestone_summary]
    ms_text = "\n".join(ms_lines) if ms_lines else "暂无里程碑"

    activity_lines = ["| 成员 | 昨日 Commits | 状态 |", "|------|-------------|------|"]
    for member, count in member_activity.items():
        status = "🟢 正常" if count > 0 else "🔴 无活动"
        activity_lines.append(f"| @{member} | {count} | {status} |")
    activity_text = "\n".join(activity_lines)

    risk_lines = [f"{'🔴' if r.get('severity') == 'high' else '🟡'} {r['description']}" for r in risks]
    risk_text = "\n".join(risk_lines) if risk_lines else "✅ 无风险项"

    return {
        "header": {"title": {"tag": "plain_text", "content": f"📋 每日站会报告 — {date}"}, "template": "blue"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**整体进度**\n{ms_text}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**成员动态**\n{activity_text}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**风险项**\n{risk_text}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**建议**\n{suggestions}"}},
        ],
    }


def build_doc_change_card(pr_number, change_description, suggested_update, doc_id):
    return {
        "header": {"title": {"tag": "plain_text", "content": "🌳 Grove — 文档更新确认"}, "template": "orange"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content":
                f"**来源：** PR #{pr_number}\n**变更：** {change_description}\n\n**建议更新：**\n{suggested_update}"}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认更新"},
                 "type": "primary", "value": {"action": "approve_doc_update", "doc_id": doc_id, "pr_number": pr_number}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                 "type": "danger", "value": {"action": "reject_doc_update", "doc_id": doc_id, "pr_number": pr_number}},
            ]},
        ],
    }


def build_notification_card(title, content, color="blue"):
    return {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": color,
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": content}},
        ],
    }


def build_project_overview_card(
    date: str, health: str, milestones: list[dict],
    trends: dict, prd_completion: dict | None,
    risks: list[str], suggestions: str,
) -> dict:
    ms_lines = [
        f"**{ms['title']}** {'█' * (ms['progress_pct'] // 10)}{'░' * (10 - ms['progress_pct'] // 10)} "
        f"{ms['progress_pct']}% ({ms['closed']}/{ms['closed'] + ms['open']})"
        for ms in milestones
    ]
    ms_text = "\n".join(ms_lines) if ms_lines else "暂无里程碑"

    trend_text = (
        f"完成 Issues: {trends.get('closed_issues', 0)}\n"
        f"合并 PR: {trends.get('merged_prs', 0)}\n"
        f"新增 Issues: {trends.get('new_issues', 0)}"
    )

    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**健康度：** {health}"}},
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**📌 里程碑**\n{ms_text}"}},
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**📈 本周趋势（7 天）**\n{trend_text}"}},
    ]

    if prd_completion:
        prd_text = (
            f"✅ 已完成 {prd_completion.get('done', 0)}\n"
            f"🔄 进行中 {prd_completion.get('in_progress', 0)}\n"
            f"⬚ 未开始 {prd_completion.get('not_started', 0)}"
        )
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**📋 PRD 完成度**\n{prd_text}"}})

    risk_text = "\n".join(f"⚠️ {r}" for r in risks) if risks else "✅ 无风险"
    elements.append({"tag": "hr"})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**风险**\n{risk_text}"}})
    elements.append({"tag": "hr"})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**💡 建议**\n{suggestions}"}})

    return {
        "header": {"title": {"tag": "plain_text", "content": f"📊 项目进度总览 — {date}"}, "template": "purple"},
        "elements": elements,
    }


def build_dispatch_summary_card(date: str, member_tasks: list[dict]) -> dict:
    lines = []
    for mt in member_tasks:
        status = "✅" if mt.get("confirmed") else "⏰ 未确认"
        lines.append(f"**👤 {mt['name']}** {status}")
        for t in mt.get("tasks", []):
            priority_icon = "🔴" if t["priority"] == "P0" else "🟡" if t["priority"] == "P1" else "🔵"
            lines.append(f"  · {priority_icon} #{t['issue_number']} {t['title']}")
        lines.append("")

    return {
        "header": {"title": {"tag": "plain_text", "content": f"🌳 今日团队任务 — {date}"}, "template": "green"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}},
        ],
    }


def build_baseline_merge_card(topic: str, summary: str, prd_path: str) -> dict:
    return {
        "header": {"title": {"tag": "plain_text", "content": "🌳 Grove — 基线合并确认"}, "template": "green"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content":
                f"**功能：** {topic}\n**摘要：** {summary}\n**PRD：** {prd_path}"}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 合并到基线"},
                 "type": "primary", "value": {"action": "confirm_baseline_merge", "topic": topic, "prd_path": prd_path}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 暂不合并"},
                 "value": {"action": "skip_baseline_merge", "topic": topic}},
            ]},
        ],
    }


def build_feature_status_card(pr_number: int, feature_name: str, suggested_status: str, reason: str) -> dict:
    status_text = "已完成" if suggested_status == "completed" else "进行中"
    return {
        "header": {"title": {"tag": "plain_text", "content": "🌳 Grove — 功能状态确认"}, "template": "orange"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content":
                f"**PR #{pr_number}** 可能{'完成' if suggested_status == 'completed' else '涉及'}了「{feature_name}」\n"
                f"**建议状态：** {status_text}\n**理由：** {reason}"}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认"},
                 "type": "primary", "value": {"action": "confirm_feature_status", "feature_name": feature_name,
                                               "status": suggested_status, "pr_number": pr_number}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 不相关"},
                 "type": "danger", "value": {"action": "reject_feature_status", "feature_name": feature_name,
                                              "pr_number": pr_number}},
            ]},
        ],
    }
