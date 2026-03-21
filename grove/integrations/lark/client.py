# grove/integrations/lark/client.py
"""Lark/Feishu API client using lark-oapi SDK."""
import asyncio
import json
import logging
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def markdown_to_lark_content(markdown: str) -> str:
    """Convert Markdown to a simplified Lark document content JSON string."""
    import json as _json
    lines = markdown.strip().split("\n")
    blocks = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            blocks.append({"tag": "heading1", "content": stripped[2:]})
        elif stripped.startswith("## "):
            blocks.append({"tag": "heading2", "content": stripped[3:]})
        elif stripped.startswith("### "):
            blocks.append({"tag": "heading3", "content": stripped[4:]})
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append({"tag": "bullet", "content": stripped[2:]})
        else:
            blocks.append({"tag": "paragraph", "content": stripped})
    return _json.dumps(blocks, ensure_ascii=False)


def lark_content_to_markdown(doc_data: dict) -> str:
    """Convert Lark document block structure to Markdown."""
    lines = []
    for block in doc_data.get("blocks", []):
        block_type = block.get("block_type")
        if block_type == 3:
            elements = block.get("heading1", {}).get("elements", [])
            text = "".join(e.get("text_run", {}).get("content", "") for e in elements)
            lines.append(f"# {text}")
        elif block_type == 4:
            elements = block.get("heading2", {}).get("elements", [])
            text = "".join(e.get("text_run", {}).get("content", "") for e in elements)
            lines.append(f"## {text}")
        elif block_type == 5:
            elements = block.get("heading3", {}).get("elements", [])
            text = "".join(e.get("text_run", {}).get("content", "") for e in elements)
            lines.append(f"### {text}")
        elif block_type == 2:
            elements = block.get("text", {}).get("elements", [])
            text = "".join(e.get("text_run", {}).get("content", "") for e in elements)
            lines.append(text)
        elif block_type == 14:
            elements = block.get("bullet", {}).get("elements", [])
            text = "".join(e.get("text_run", {}).get("content", "") for e in elements)
            lines.append(f"- {text}")
    return "\n\n".join(lines)


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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def create_doc(self, space_id: str, title: str, markdown_content: str) -> str:
        """Create a new doc in a Lark wiki space. Returns the document ID."""
        from lark_oapi.api.docx.v1 import CreateDocumentRequest, CreateDocumentRequestBody
        def _create():
            client = self._get_client()
            request = CreateDocumentRequest.builder() \
                .request_body(
                    CreateDocumentRequestBody.builder()
                    .title(title)
                    .folder_token(space_id)
                    .build()
                ).build()
            response = client.docx.v1.document.create(request)
            if not response.success():
                raise RuntimeError(f"Lark create doc error: {response.code} {response.msg}")
            return response.data.document.document_id
        doc_id = await asyncio.to_thread(_create)
        logger.info("Created Lark doc '%s' (id=%s)", title, doc_id)
        return doc_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def read_doc(self, doc_id: str) -> str:
        """Read a Lark document and return its content as Markdown."""
        from lark_oapi.api.docx.v1 import ListDocumentBlockRequest
        def _read():
            client = self._get_client()
            request = ListDocumentBlockRequest.builder() \
                .document_id(doc_id) \
                .build()
            response = client.docx.v1.document_block.list(request)
            if not response.success():
                raise RuntimeError(f"Lark read doc error: {response.code} {response.msg}")
            blocks_data = {
                "blocks": [
                    {"block_type": b.block_type, **{k: v for k, v in b.__dict__.items() if v is not None and k != "block_type"}}
                    for b in (response.data.items or [])
                ]
            }
            return lark_content_to_markdown(blocks_data)
        return await asyncio.to_thread(_read)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    async def update_doc(self, doc_id: str, markdown_content: str) -> None:
        """Update a Lark document (simplified — logs for MVP)."""
        logger.info("update_doc called for %s (content length: %d)", doc_id, len(markdown_content))
