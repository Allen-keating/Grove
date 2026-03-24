"""LLM-based project analysis: architecture, feature clustering, baseline generation."""
import json
import logging

from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.prompts import (
    ARCHITECTURE_ANALYSIS_PROMPT,
    COMMIT_CLUSTER_PROMPT,
    BASELINE_GENERATE_PROMPT,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 80


class ProjectAnalyzer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def analyze_architecture(
        self, repo_tree: str, source_snippets: str,
        dependencies: str, readme: str,
    ) -> str:
        prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(
            repo_tree=repo_tree[:3000],
            source_snippets=source_snippets[:4000],
            dependencies=dependencies[:2000],
            readme=readme[:2000],
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请分析架构。"}],
            max_tokens=1024,
        )

    async def cluster_features(self, commits: list[dict]) -> list[dict]:
        """Cluster commits into feature groups. Batches large lists."""
        if not commits:
            return []

        all_clusters: list[dict] = []
        for i in range(0, len(commits), _BATCH_SIZE):
            batch = commits[i:i + _BATCH_SIZE]
            commits_text = "\n".join(f"- {c['sha']} {c['message']}" for c in batch)
            prompt = COMMIT_CLUSTER_PROMPT.format(commits=commits_text)
            try:
                response = await self.llm.chat(
                    system_prompt=prompt,
                    messages=[{"role": "user", "content": "请分组。"}],
                    max_tokens=2048,
                )
                clusters = json.loads(response)
                if isinstance(clusters, list):
                    all_clusters.extend(clusters)
            except Exception:
                logger.warning("Commit clustering failed for batch %d", i // _BATCH_SIZE)

        # Merge clusters with same feature name
        merged: dict[str, dict] = {}
        for c in all_clusters:
            name = c.get("feature", "未分类")
            if name in merged:
                merged[name]["commits"].extend(c.get("commits", []))
            else:
                merged[name] = {
                    "feature": name,
                    "commits": c.get("commits", []),
                    "description": c.get("description", ""),
                }
        return list(merged.values())

    async def generate_baseline(
        self, project_name: str, architecture: str,
        features: list[dict], milestones: str, activity_summary: str,
    ) -> str:
        features_text = "\n".join(
            f"- {f.get('status_icon', '✅')} **{f['name']}** — {f.get('description', '')}"
            for f in features
        )
        prompt = BASELINE_GENERATE_PROMPT.format(
            project_name=project_name,
            architecture=architecture,
            features=features_text,
            milestones=milestones,
            activity_summary=activity_summary,
        )
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请生成基线文档。"}],
            max_tokens=4096,
        )
