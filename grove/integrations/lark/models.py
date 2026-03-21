# grove/integrations/lark/models.py
"""Lark/Feishu data models."""
from dataclasses import dataclass


@dataclass
class LarkMessage:
    message_id: str
    chat_id: str
    sender_id: str
    text: str
    is_mention: bool = False
    chat_type: str = "group"


@dataclass
class LarkDocInfo:
    doc_id: str
    title: str
    space_id: str
