"""Project Scanner module — scan repo, generate reverse PRD + dev status doc."""
import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.analyzer import ProjectAnalyzer
from grove.utils.commit_classifier import classify_commit

logger = logging.getLogger(__name__)


class ProjectScannerModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._analyzer = ProjectAnalyzer(llm)
        self._scan_lock = asyncio.Lock()

    @subscribe(EventType.INTERNAL_SCAN_PROJECT)
    async def on_scan_project(self, event: Event) -> None:
        chat_id = event.payload.get("chat_id", self.config.lark.chat_id)

        if self._scan_lock.locked():
            await self.lark.send_text(chat_id, "扫描正在进行中，请稍候。")
            return

        async with self._scan_lock:
            await self.lark.send_text(chat_id, "正在扫描项目，请稍候...")
            try:
                await self._run_scan(chat_id)
            except Exception:
                logger.exception("Project scan failed")
                await self.lark.send_text(chat_id, "项目扫描失败，请稍后重试。")

    async def _run_scan(self, chat_id: str) -> None:
        repo = self.config.project.repo

        # Step 1: Data collection
        tree = self.github.get_repo_tree(repo)
        readme = self._safe_read_file(repo, "README.md")
        deps = self._collect_dependencies(repo)
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        commits = self.github.list_recent_commits_detailed(repo, since=since, max_commits=500)
        issues = self.github.list_issues(repo, state="all")
        milestones = self.github.list_milestones(repo)

        # Check for empty repo
        if not tree and not commits and not issues:
            await self.lark.send_text(chat_id,
                "项目数据不足，无法生成文档。请至少提交一些代码和 README 后再试。")
            return

        # Format data for LLM
        tree_text = self._format_tree(tree)
        commit_summary = await self._summarize_commits(commits)
        issues_text = "\n".join(f"- #{i.number} {i.title} [{i.state}]" for i in issues[:100])
        milestones_text = "\n".join(
            f"- {m['title']}: {m['closed_issues']}/{m['open_issues'] + m['closed_issues']} "
            f"(due: {m.get('due_on', 'N/A')})"
            for m in milestones
        )

        # Step 2: LLM analysis (sequential — each depends on previous)
        architecture = await self._analyzer.analyze_architecture(tree_text, deps, readme)

        try:
            features = await self._analyzer.analyze_features(
                architecture, tree_text, commit_summary, issues_text)
        except Exception:
            logger.exception("Feature analysis failed")
            await self.lark.send_text(chat_id,
                f"架构分析完成，但功能推导失败。\n\n**架构分析：**\n{architecture}")
            return

        try:
            prd_content = await self._analyzer.generate_reverse_prd(
                architecture, features, milestones_text)
        except Exception:
            logger.exception("PRD generation failed")
            features_text = "\n".join(f"- {f['name']}: {f.get('description', '')}" for f in features)
            await self.lark.send_text(chat_id,
                f"功能推导完成，但 PRD 生成失败。\n\n**已识别功能：**\n{features_text}")
            return

        # Step 3: Generate dev status document
        dev_status = self._build_dev_status(architecture, features, commits, milestones)

        # Step 4: Output documents
        prd_doc_id = None
        try:
            existing_doc_id = self._get_existing_doc_id()
            if existing_doc_id:
                await self.lark.update_doc(existing_doc_id, prd_content)
                prd_doc_id = existing_doc_id
            else:
                prd_doc_id = await self.lark.create_doc(
                    self.config.lark.space_id,
                    f"[{self.config.project.name}] PRD（逆向生成草稿）",
                    prd_content,
                )
                self._save_doc_id(prd_doc_id)
        except Exception:
            logger.exception("Lark doc creation/update failed")

        try:
            self.github.write_file(repo, "docs/prd/project-prd-draft.md", prd_content,
                                   "docs: update reverse-engineered PRD")
            self.github.write_file(repo, "docs/development-status.md", dev_status,
                                   "docs: update development status")
        except Exception:
            logger.exception("GitHub file write failed")

        # Save scan metadata
        self._storage.write_json("memory/project-scan/latest-scan.json", {
            "date": datetime.now(timezone.utc).isoformat(),
            "commit_count": len(commits),
            "issue_count": len(issues),
            "feature_count": len(features),
        })

        # Notify
        msg = "项目扫描完成！已生成两份文档：\n📋 逆向 PRD 草稿（请团队审阅补充）\n📄 开发状态文档"
        if prd_doc_id:
            msg += "\n\n飞书文档已创建"
        await self.lark.send_text(chat_id, msg)

    def _safe_read_file(self, repo: str, path: str) -> str:
        try:
            return self.github.read_file(repo, path)
        except Exception:
            return ""

    def _collect_dependencies(self, repo: str) -> str:
        parts = []
        for dep_file in ["requirements.txt", "package.json", "go.mod", "Cargo.toml"]:
            content = self._safe_read_file(repo, dep_file)
            if content:
                parts.append(f"=== {dep_file} ===\n{content[:1000]}")
        return "\n\n".join(parts) if parts else "No dependency files found."

    def _format_tree(self, tree: list[dict], max_depth: int = 3) -> str:
        lines = []
        for item in tree:
            depth = item["path"].count("/")
            if depth <= max_depth:
                prefix = "  " * depth
                name = item["path"].split("/")[-1]
                icon = "📁" if item["type"] == "tree" else "📄"
                lines.append(f"{prefix}{icon} {name}")
        return "\n".join(lines[:200])

    async def _summarize_commits(self, commits: list[dict]) -> str:
        type_counts: dict[str, int] = Counter()
        for c in commits:
            files = [f["filename"] for f in c.get("files", [])]
            ctype = await classify_commit(c["message"], files, llm=self.llm)
            type_counts[ctype] += 1
        lines = [f"- {ctype}: {count} commits" for ctype, count in type_counts.items()]
        return "\n".join(lines)

    def _build_dev_status(self, architecture: str, features: list[dict],
                          commits: list[dict], milestones: list[dict]) -> str:
        lines = [
            "# 开发状态文档\n",
            f"> 自动生成于 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n",
            "## 技术架构\n", architecture, "\n",
            "## 已实现功能\n",
        ]
        for f in features:
            status_icon = {"completed": "✅", "in_progress": "🔄", "planned": "⬚"}.get(f.get("status"), "❓")
            lines.append(f"- {status_icon} **{f['name']}**: {f.get('description', '')}")
        lines.append(f"\n## 近期开发活动\n\n最近 90 天共 {len(commits)} 次提交。\n")
        if milestones:
            lines.append("## 里程碑\n")
            for m in milestones:
                total = m["open_issues"] + m["closed_issues"]
                pct = round(m["closed_issues"] / total * 100) if total > 0 else 0
                lines.append(f"- **{m['title']}** — {pct}% ({m['closed_issues']}/{total})")
        return "\n".join(lines)

    def _get_existing_doc_id(self) -> str | None:
        try:
            data = self._storage.read_yaml("memory/project-scan/reverse-prd-doc-id.yml")
            return data.get("doc_id")
        except FileNotFoundError:
            return None

    def _save_doc_id(self, doc_id: str) -> None:
        self._storage.write_yaml("memory/project-scan/reverse-prd-doc-id.yml", {"doc_id": doc_id})
