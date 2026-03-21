"""Multi-turn conversation state for PRD guided questioning."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from grove.core.storage import Storage


@dataclass
class Conversation:
    id: str
    chat_id: str
    initiator_github: str
    topic: str
    state: str = "questioning"
    messages: list[dict] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)
    prd_doc_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({
            "role": role, "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def to_dict(self) -> dict:
        return {
            "id": self.id, "chat_id": self.chat_id,
            "initiator_github": self.initiator_github, "topic": self.topic,
            "state": self.state, "messages": self.messages,
            "answers": self.answers, "prd_doc_id": self.prd_doc_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        return cls(
            id=data["id"], chat_id=data["chat_id"],
            initiator_github=data["initiator_github"], topic=data["topic"],
            state=data.get("state", "questioning"), messages=data.get("messages", []),
            answers=data.get("answers", {}), prd_doc_id=data.get("prd_doc_id"),
            created_at=data.get("created_at", ""),
        )


class ConversationManager:
    def __init__(self, storage: Storage):
        self._storage = storage
        self._cache: dict[str, Conversation] = {}
        self._load_all()

    def _conv_path(self, conv_id: str) -> str:
        return f"memory/conversations/{conv_id}.json"

    def _load_all(self) -> None:
        conv_dir = self._storage.root / "memory" / "conversations"
        if not conv_dir.exists():
            return
        for path in conv_dir.glob("conv_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                conv = Conversation.from_dict(data)
                self._cache[conv.id] = conv
            except Exception:
                pass

    def create(self, chat_id: str, initiator_github: str, topic: str) -> Conversation:
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        conv = Conversation(id=conv_id, chat_id=chat_id, initiator_github=initiator_github, topic=topic)
        self._cache[conv_id] = conv
        self.save(conv)
        return conv

    def get(self, conv_id: str) -> Conversation | None:
        return self._cache.get(conv_id)

    def get_active_for_chat(self, chat_id: str) -> Conversation | None:
        for conv in self._cache.values():
            if conv.chat_id == chat_id and conv.state in ("questioning", "generating"):
                return conv
        return None

    def save(self, conv: Conversation) -> None:
        self._cache[conv.id] = conv
        self._storage.write_json(self._conv_path(conv.id), conv.to_dict())
