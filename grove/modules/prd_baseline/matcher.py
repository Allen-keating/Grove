"""LLM-based feature matching: map PRs to baseline features."""
import json
import logging
from dataclasses import dataclass

from grove.integrations.llm.client import LLMClient
from grove.modules.prd_baseline.prompts import FEATURE_MATCH_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class FeatureMatch:
    match_type: str  # "existing" | "new" | "none"
    matched_feature: str | None
    status: str | None  # "in_progress" | "completed"
    confidence: float
    reason: str


class FeatureMatcher:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def match_pr(
        self, commits: list[dict], pending_features: list[dict],
        feature_prds: str = "",
    ) -> list[FeatureMatch]:
        commits_text = "\n".join(
            f"- {c['sha']} {c['message']}" for c in commits
        )
        features_text = "\n".join(
            f"- {f['name']}（{f.get('status', 'unknown')}）：{f.get('description', '')}"
            for f in pending_features
        ) or "（无）"

        prompt = FEATURE_MATCH_PROMPT.format(
            commits=commits_text,
            pending_features=features_text,
            feature_prds=feature_prds[:3000] or "（无）",
        )

        try:
            response = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请分析。"}],
                max_tokens=1024,
            )
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]
            return [
                FeatureMatch(
                    match_type=item.get("match_type", "none"),
                    matched_feature=item.get("matched_feature"),
                    status=item.get("status"),
                    confidence=item.get("confidence", 0.0),
                    reason=item.get("reason", ""),
                )
                for item in data
            ]
        except Exception:
            logger.warning("Feature matching LLM call failed")
            return [FeatureMatch(match_type="none", matched_feature=None,
                                  status=None, confidence=0.0, reason="LLM failure")]
