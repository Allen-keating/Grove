# grove/integrations/lark/cards.py
"""Lark interactive message card builders."""


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
