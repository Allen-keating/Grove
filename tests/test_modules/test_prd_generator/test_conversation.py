# tests/test_modules/test_prd_generator/test_conversation.py
import json
from pathlib import Path
import pytest
from grove.modules.prd_generator.conversation import ConversationManager, Conversation
from grove.core.storage import Storage


class TestConversation:
    def test_create_conversation(self):
        conv = Conversation(id="conv_001", chat_id="oc_test",
                           initiator_github="zhangsan", topic="暗黑模式")
        assert conv.id == "conv_001"
        assert conv.state == "questioning"
        assert conv.messages == []
        assert conv.answers == {}

    def test_add_message(self):
        conv = Conversation(id="conv_001", chat_id="oc_test",
                           initiator_github="zhangsan", topic="暗黑模式")
        conv.add_message("user", "我想加个暗黑模式")
        conv.add_message("assistant", "好的，目标用户是谁？")
        assert len(conv.messages) == 2
        assert conv.messages[0]["role"] == "user"


class TestConversationManager:
    @pytest.fixture
    def manager(self, grove_dir: Path):
        storage = Storage(grove_dir)
        return ConversationManager(storage)

    def test_create_and_get(self, manager):
        conv = manager.create(chat_id="oc_test", initiator_github="zhangsan", topic="暗黑模式")
        assert conv.id.startswith("conv_")
        retrieved = manager.get(conv.id)
        assert retrieved is not None
        assert retrieved.topic == "暗黑模式"

    def test_get_nonexistent(self, manager):
        assert manager.get("conv_nonexistent") is None

    def test_get_active_for_chat(self, manager):
        conv = manager.create(chat_id="oc_test", initiator_github="zhangsan", topic="暗黑模式")
        active = manager.get_active_for_chat("oc_test")
        assert active is not None
        assert active.id == conv.id

    def test_no_active_when_completed(self, manager):
        conv = manager.create(chat_id="oc_test", initiator_github="zhangsan", topic="暗黑模式")
        conv.state = "completed"
        manager.save(conv)
        assert manager.get_active_for_chat("oc_test") is None

    def test_save_persists_to_disk(self, manager, grove_dir: Path):
        conv = manager.create(chat_id="oc_test", initiator_github="zhangsan", topic="暗黑模式")
        conv.add_message("user", "hello")
        manager.save(conv)
        path = grove_dir / "memory" / "conversations" / f"{conv.id}.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["topic"] == "暗黑模式"
        assert len(data["messages"]) == 1
