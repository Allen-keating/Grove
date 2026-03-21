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
