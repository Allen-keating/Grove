# grove/integrations/lark/client.py
"""Lark/Feishu API client using lark-oapi SDK."""
import asyncio
import json
import logging
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LarkClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._client: lark.Client | None = None

    def _get_client(self) -> lark.Client:
        if self._client is None:
            self._client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .build()
        return self._client

    def _send_message_sync(self, receive_id_type, receive_id, msg_type, content):
        """Synchronous message send — called via asyncio.to_thread."""
        client = self._get_client()
        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            ).build()
        response = client.im.v1.message.create(request)
        if not response.success():
            raise RuntimeError(f"Lark API error: {response.code} {response.msg}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def send_text(self, chat_id, text):
        await asyncio.to_thread(
            self._send_message_sync, "chat_id", chat_id, "text",
            json.dumps({"text": text}),
        )
        logger.info("Sent text to chat %s", chat_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def send_card(self, chat_id, card_content):
        await asyncio.to_thread(
            self._send_message_sync, "chat_id", chat_id, "interactive",
            json.dumps(card_content),
        )
        logger.info("Sent card to chat %s", chat_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def send_private(self, user_id, text):
        await asyncio.to_thread(
            self._send_message_sync, "open_id", user_id, "text",
            json.dumps({"text": text}),
        )
        logger.info("Sent private msg to %s", user_id)
