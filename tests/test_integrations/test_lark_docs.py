# tests/test_integrations/test_lark_docs.py
from grove.integrations.lark.client import LarkClient


class TestLarkDocAPIs:
    def test_client_has_doc_methods(self):
        client = LarkClient(app_id="test", app_secret="test")
        assert hasattr(client, "create_doc")
        assert hasattr(client, "read_doc")
        assert hasattr(client, "update_doc")

    def test_markdown_to_lark_blocks_basic(self):
        from grove.integrations.lark.client import markdown_to_lark_content
        result = markdown_to_lark_content("# Hello\n\nThis is a paragraph.")
        assert isinstance(result, str)

    def test_markdown_to_sdk_blocks(self):
        from grove.integrations.lark.client import _markdown_to_sdk_blocks
        blocks = _markdown_to_sdk_blocks("# Title\n\nSome text\n\n- Bullet item\n\n## Subtitle")
        assert len(blocks) == 4
        assert blocks[0].block_type == 3   # heading1
        assert blocks[1].block_type == 2   # text
        assert blocks[2].block_type == 14  # bullet
        assert blocks[3].block_type == 4   # heading2

    def test_markdown_to_sdk_blocks_empty(self):
        from grove.integrations.lark.client import _markdown_to_sdk_blocks
        blocks = _markdown_to_sdk_blocks("")
        assert blocks == []

    def test_lark_content_to_markdown_basic(self):
        from grove.integrations.lark.client import lark_content_to_markdown
        lark_blocks = {
            "document": {"document_id": "doc1"},
            "blocks": [
                {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Title"}}]}},
                {"block_type": 2, "text": {"elements": [{"text_run": {"content": "Paragraph text"}}]}},
            ]
        }
        result = lark_content_to_markdown(lark_blocks)
        assert "Title" in result
        assert "Paragraph text" in result
