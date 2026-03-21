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
