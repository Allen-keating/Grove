# tests/test_integrations/test_lark_client.py
import pytest
from grove.integrations.lark.client import LarkClient
from grove.integrations.lark.models import LarkMessage


class TestLarkClient:
    def test_client_init(self):
        client = LarkClient(app_id="test_id", app_secret="test_secret")
        assert client.app_id == "test_id"

    def test_lark_message_model(self):
        msg = LarkMessage(
            message_id="msg_001",
            chat_id="oc_test",
            sender_id="ou_xxx1",
            text="@Grove 加个暗黑模式",
            is_mention=True,
        )
        assert msg.message_id == "msg_001"
        assert msg.is_mention is True
