# grove/modules/doc_sync/doc_updater.py
import logging
from grove.config import GroveConfig
from grove.integrations.lark.cards import build_doc_change_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.doc_sync.diff_classifier import ChangeClassification
from grove.modules.doc_sync.prompts import DOC_UPDATE_PROMPT

logger = logging.getLogger(__name__)

class DocUpdater:
    def __init__(self, llm: LLMClient, lark: LarkClient, config: GroveConfig):
        self.llm = llm
        self.lark = lark
        self.config = config

    async def apply(self, classification: ChangeClassification, pr_number: int, doc_id: str):
        if not classification.is_product_change:
            return
        severity = classification.severity
        if severity == "small":
            await self._auto_update(classification, pr_number, doc_id)
        elif severity == "medium":
            await self._send_confirmation(classification, pr_number, doc_id)
        elif severity == "large":
            await self._send_discussion(classification, pr_number)

    async def _auto_update(self, classification, pr_number, doc_id):
        update_content = await self._generate_update(classification, doc_id)
        await self.lark.update_doc(doc_id, update_content)
        await self.lark.send_text(self.config.lark.chat_id,
            f"已根据 PR #{pr_number} 自动更新 PRD「{', '.join(classification.affected_prd_sections)}」章节。")

    async def _send_confirmation(self, classification, pr_number, doc_id):
        update_content = await self._generate_update(classification, doc_id)
        card = build_doc_change_card(pr_number=pr_number, change_description=classification.description,
                                      suggested_update=update_content[:500], doc_id=doc_id)
        await self.lark.send_card(self.config.lark.chat_id, card)

    async def _send_discussion(self, classification, pr_number):
        await self.lark.send_text(self.config.lark.chat_id,
            f"PR #{pr_number} 包含重大产品变更：{classification.description}\n\n"
            f"影响章节：{', '.join(classification.affected_prd_sections)}\n\n请团队讨论后确认是否更新 PRD。")

    async def _generate_update(self, classification, doc_id) -> str:
        current_prd = ""
        try:
            current_prd = await self.lark.read_doc(doc_id)
        except Exception:
            pass
        prompt = DOC_UPDATE_PROMPT.format(
            change_description=classification.description,
            affected_sections=", ".join(classification.affected_prd_sections),
            current_prd=current_prd[:4000])
        return await self.llm.chat(system_prompt=prompt,
            messages=[{"role": "user", "content": "请生成更新内容。"}], max_tokens=1024)
