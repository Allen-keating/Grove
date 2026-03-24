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


def _markdown_to_sdk_blocks(markdown: str) -> list:
    """Convert markdown text to a list of Lark SDK Block objects for document creation."""
    from lark_oapi.api.docx.v1 import Block, Text, TextElement, TextRun

    def _make_text(content: str):
        return Text.builder() \
            .elements([
                TextElement.builder()
                .text_run(TextRun.builder().content(content).build())
                .build()
            ]).build()

    blocks = []
    for line in markdown.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            blocks.append(Block.builder().block_type(5).heading3(_make_text(stripped[4:])).build())
        elif stripped.startswith("## "):
            blocks.append(Block.builder().block_type(4).heading2(_make_text(stripped[3:])).build())
        elif stripped.startswith("# "):
            blocks.append(Block.builder().block_type(3).heading1(_make_text(stripped[2:])).build())
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(Block.builder().block_type(14).bullet(_make_text(stripped[2:])).build())
        else:
            blocks.append(Block.builder().block_type(2).text(_make_text(stripped)).build())
    return blocks


def _markdown_to_json_blocks(markdown: str) -> list[dict]:
    """Convert markdown to Lark block dicts for the HTTP API."""
    def _text_block(content: str) -> dict:
        return {"block_type": 2, "text": {"elements": [{"text_run": {"content": content}}]}}

    blocks = []
    for line in markdown.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": stripped[4:]}}]}})
        elif stripped.startswith("## "):
            blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": stripped[3:]}}]}})
        elif stripped.startswith("# "):
            blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": stripped[2:]}}]}})
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(_text_block(f"• {stripped[2:]}"))
        else:
            blocks.append(_text_block(stripped))
    return blocks


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
                .domain(lark.LARK_DOMAIN) \
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
        """Create a new doc in a Lark wiki space. Returns the obj_token.

        space_id can be either numeric or the wiki token from the URL.
        """
        from lark_oapi.api.wiki.v2 import CreateSpaceNodeRequest, GetNodeSpaceRequest, Node

        def _create():
            client = self._get_client()
            # Resolve numeric space_id from wiki token if needed
            numeric_id = space_id
            if not space_id.isdigit():
                req = GetNodeSpaceRequest.builder().token(space_id).build()
                resp = client.wiki.v2.space.get_node(req)
                if resp.success():
                    numeric_id = str(resp.data.node.space_id)
                else:
                    raise RuntimeError(f"Lark resolve space_id error: {resp.code} {resp.msg}")

            node = Node.builder().obj_type("docx").node_type("origin").title(title).build()
            request = CreateSpaceNodeRequest.builder() \
                .space_id(numeric_id) \
                .request_body(node) \
                .build()
            response = client.wiki.v2.space_node.create(request)
            if not response.success():
                raise RuntimeError(f"Lark create wiki doc error: {response.code} {response.msg}")
            return response.data.node.obj_token

        doc_id = await asyncio.to_thread(_create)
        logger.info("Created Lark wiki doc '%s' (id=%s)", title, doc_id)
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
        """Update a Lark document by replacing all content blocks via HTTP API."""
        import httpx as _httpx

        def _get_token():
            resp = _httpx.post(
                f"{lark.LARK_DOMAIN}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            return resp.json()["tenant_access_token"]

        def _update():
            token = _get_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            base = lark.LARK_DOMAIN

            # Step 1: List blocks to find page block and child count
            resp = _httpx.get(f"{base}/open-apis/docx/v1/documents/{doc_id}/blocks", headers=headers)
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"Lark list blocks error: {data['code']} {data['msg']}")
            blocks = data["data"]["items"]
            if not blocks:
                logger.warning("No blocks in doc %s", doc_id)
                return
            page_id = blocks[0]["block_id"]
            children = blocks[0].get("children", [])

            # Step 2: Delete existing children
            if children:
                resp = _httpx.request(
                    "DELETE",
                    f"{base}/open-apis/docx/v1/documents/{doc_id}/blocks/{page_id}/children/batch_delete",
                    headers=headers,
                    json={"start_index": 0, "end_index": len(children)},
                )
                if resp.json()["code"] != 0:
                    raise RuntimeError(f"Lark delete blocks error: {resp.json()}")

            # Step 3: Create new blocks from markdown
            new_blocks = _markdown_to_json_blocks(markdown_content)
            if new_blocks:
                resp = _httpx.post(
                    f"{base}/open-apis/docx/v1/documents/{doc_id}/blocks/{page_id}/children",
                    headers=headers,
                    json={"children": new_blocks, "index": 0},
                )
                if resp.json()["code"] != 0:
                    raise RuntimeError(f"Lark create blocks error: {resp.json()}")

        await asyncio.to_thread(_update)
        logger.info("Updated Lark doc %s", doc_id)
