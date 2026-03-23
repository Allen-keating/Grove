"""LLM-based project analysis: architecture, features, PRD."""
import json
import logging

from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.prompts import (
    ARCHITECTURE_ANALYSIS_PROMPT,
    FEATURE_ANALYSIS_PROMPT,
    REVERSE_PRD_PROMPT,
)

logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def analyze_architecture(
        self, repo_tree: str, dependencies: str, readme: str,
    ) -> str:
        prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(
            repo_tree=repo_tree[:3000], dependencies=dependencies[:2000], readme=readme[:2000],
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请分析架构。"}],
            max_tokens=1024,
        )

    async def analyze_features(
        self, architecture: str, repo_tree: str,
        commit_summary: str, issues: str,
    ) -> list[dict]:
        prompt = FEATURE_ANALYSIS_PROMPT.format(
            architecture=architecture[:1500], repo_tree=repo_tree[:2000],
            commit_summary=commit_summary[:2000], issues=issues[:2000],
        )
        response = await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请逆向推导功能列表。"}],
            max_tokens=2048,
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Feature analysis returned non-JSON, retrying once")
            response = await self.llm.chat(
                system_prompt=prompt + "\n\n重要：只输出 JSON 数组！",
                messages=[{"role": "user", "content": "请逆向推导功能列表。只输出 JSON。"}],
                max_tokens=2048,
            )
            return json.loads(response)

    async def generate_reverse_prd(
        self, architecture: str, features: list[dict], milestones: str,
    ) -> str:
        features_text = "\n".join(
            f"- {f['name']}（{f['status']}）：{f.get('description', '')}"
            for f in features
        )
        prompt = REVERSE_PRD_PROMPT.format(
            architecture=architecture, features=features_text, milestones=milestones,
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请生成逆向 PRD。"}],
            max_tokens=4096,
        )
