# grove/modules/doc_sync/diff_classifier.py
import json
import logging
from dataclasses import dataclass, field
from grove.integrations.llm.client import LLMClient
from grove.modules.doc_sync.prompts import CLASSIFY_CHANGE_PROMPT

logger = logging.getLogger(__name__)

@dataclass
class ChangeClassification:
    is_product_change: bool
    severity: str = "none"
    description: str = ""
    affected_prd_sections: list[str] = field(default_factory=list)

class DiffClassifier:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def classify(self, diff: str, pr_title: str) -> ChangeClassification:
        try:
            prompt = CLASSIFY_CHANGE_PROMPT.format(pr_title=pr_title, diff=diff[:6000])
            response = await self.llm.chat(system_prompt=prompt,
                messages=[{"role": "user", "content": "请分类此变更。"}], max_tokens=512)
            data = json.loads(response)
            return ChangeClassification(
                is_product_change=data.get("is_product_change", False),
                severity=data.get("severity", "none"),
                description=data.get("description", ""),
                affected_prd_sections=data.get("affected_prd_sections", []))
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Diff classification failed: %s", exc)
            return ChangeClassification(is_product_change=False)
