"""Project Scanner module — scan repo, generate unified baseline document."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.project_scanner.analyzer import ProjectAnalyzer

logger = logging.getLogger(__name__)

_KEY_FILE_PATTERNS = (
    "main.py", "app.py", "index.ts", "index.js", "mod.rs",
    "routes.py", "urls.py", "router.py", "router.ts",
    "config.py", "settings.py",
)
_MAX_KEY_FILES = 50
_MAX_FILE_SIZE = 50_000  # 50KB


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

    @subscribe(EventType.LARK_CARD_ACTION)
    async def on_card_action(self, event: Event) -> None:
        action_data = event.payload.get("action", {}).get("value", {})
        action = action_data.get("action", "")
        if action == "confirm_cold_start":
            self._storage.write_yaml("memory/project-scan/baseline-confirmed.yml",
                {"confirmed": True, "date": datetime.now(timezone.utc).isoformat()})
            await self.lark.send_text(self.config.lark.chat_id, "基线文档已确认生效！")
        elif action == "adjust_cold_start":
            await self.lark.send_text(self.config.lark.chat_id,
                "请在飞书文档中编辑后，再次发送「扫描项目」确认。")

    async def _run_scan(self, chat_id: str) -> None:
        repo = self.config.project.repo
        is_cold_start = not self._is_baseline_confirmed()

        # Data collection
        tree = await self.github.get_repo_tree(repo)
        readme = await self._safe_read_file(repo, "README.md")
        deps = await self._collect_dependencies(repo)
        source_snippets = await self._read_key_sources(repo, tree)
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        commits = await self.github.list_recent_commits_detailed(repo, since=since, max_commits=500)
        milestones = await self.github.list_milestones(repo)
        open_prs = await self.github.list_open_prs(repo)

        if not tree and not commits:
            await self.lark.send_text(chat_id,
                "项目数据不足，无法生成文档。请至少提交一些代码和 README 后再试。")
            return

        # LLM analysis
        tree_text = self._format_tree(tree)
        architecture = await self._analyzer.analyze_architecture(
            tree_text, source_snippets, deps, readme)
        clusters = await self._analyzer.cluster_features(commits)

        # Determine feature status
        open_pr_texts = " ".join(pr.get("title", "") for pr in open_prs)
        features = []
        for cluster in clusters:
            if cluster["feature"] == "工程维护":
                continue
            is_in_progress = bool(open_pr_texts) and cluster["feature"].lower() in open_pr_texts.lower()
            status = "in_progress" if is_in_progress else "completed"
            icon = "🔄" if is_in_progress else "✅"
            features.append({
                "name": cluster["feature"],
                "description": cluster.get("description", ""),
                "status": status,
                "status_icon": icon,
            })

        milestones_text = "\n".join(
            f"- {m['title']}: {m['closed_issues']}/{m['open_issues'] + m['closed_issues']} "
            f"(due: {m.get('due_on', 'N/A')})" for m in milestones
        ) or "暂无"

        activity = f"最近 90 天共 {len(commits)} 次提交，涉及 {len(clusters)} 个功能模块。"

        baseline_content = await self._analyzer.generate_baseline(
            self.config.project.name, architecture, features, milestones_text, activity,
        )

        # Save feature tracking
        tracking = {"features": {}}
        for f in features:
            tracking["features"][f["name"]] = {
                "status": f["status"],
                "description": f["description"],
                "related_prs": [],
                "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        self._storage.write_json("memory/project-scan/feature-tracking.json", tracking)

        # Output: single baseline document
        await self._output_baseline(baseline_content)

        # Save metadata
        self._storage.write_json("memory/project-scan/latest-scan.json", {
            "date": datetime.now(timezone.utc).isoformat(),
            "commit_count": len(commits),
            "feature_count": len(features),
        })

        # Migration: clean up old files
        await self._migrate_old_files(repo)

        if is_cold_start:
            from grove.integrations.lark.cards import build_notification_card
            card = build_notification_card(
                "🌳 Grove — 基线文档确认",
                f"项目基线文档已生成（{len(features)} 个功能）。请审阅后确认。",
                color="green",
            )
            card["elements"].append({
                "tag": "action", "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认"},
                     "type": "primary", "value": {"action": "confirm_cold_start"}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "📝 需要调整"},
                     "value": {"action": "adjust_cold_start"}},
                ],
            })
            await self.lark.send_card(chat_id, card)
        else:
            await self.lark.send_text(chat_id,
                f"项目扫描完成！基线文档已更新（{len(features)} 个功能）。")

    async def _output_baseline(self, content: str) -> str | None:
        repo = self.config.project.repo
        doc_id = None

        existing_id = self._get_baseline_doc_id()
        try:
            if existing_id:
                await self.lark.update_doc(existing_id, content)
                doc_id = existing_id
            else:
                doc_id = await self.lark.create_doc(
                    self.config.lark.space_id,
                    f"[{self.config.project.name}] 项目基线文档",
                    content,
                )
                self._storage.write_yaml("memory/project-scan/baseline-doc-id.yml", {"doc_id": doc_id})
        except Exception:
            logger.exception("Lark baseline doc failed")

        try:
            await self.github.write_file(repo, "docs/project-baseline.md", content,
                                   "docs: update project baseline")
        except Exception:
            logger.exception("GitHub baseline write failed")

        return doc_id

    def _get_baseline_doc_id(self) -> str | None:
        for path in ["memory/project-scan/baseline-doc-id.yml",
                      "memory/project-scan/reverse-prd-doc-id.yml"]:
            try:
                data = self._storage.read_yaml(path)
                return data.get("doc_id")
            except FileNotFoundError:
                continue
        return None

    def _is_baseline_confirmed(self) -> bool:
        try:
            data = self._storage.read_yaml("memory/project-scan/baseline-confirmed.yml")
            return data.get("confirmed", False)
        except FileNotFoundError:
            return False

    async def _migrate_old_files(self, repo: str) -> None:
        for old_path in ["docs/prd/project-prd-draft.md", "docs/development-status.md"]:
            try:
                await self.github.read_file(repo, old_path)
                await self.github.write_file(repo, old_path,
                    "本文档已合并到 docs/project-baseline.md，请查看新文档。",
                    f"docs: deprecate {old_path} in favor of project-baseline.md")
            except Exception:
                pass

        old_storage = self._storage.root / "memory" / "project-scan" / "reverse-prd-doc-id.yml"
        new_storage = self._storage.root / "memory" / "project-scan" / "baseline-doc-id.yml"
        if old_storage.exists() and not new_storage.exists():
            old_storage.rename(new_storage)

    async def _read_key_sources(self, repo: str, tree: list[dict]) -> str:
        candidates = []
        for item in tree:
            if item["type"] != "blob" or item.get("size", 0) > _MAX_FILE_SIZE:
                continue
            filename = item["path"].split("/")[-1]
            depth = item["path"].count("/")
            if filename in _KEY_FILE_PATTERNS:
                candidates.append(item["path"])
            elif filename == "__init__.py" and depth <= 1:
                candidates.append(item["path"])
            elif filename.startswith("index.") and depth <= 1:
                candidates.append(item["path"])

        snippets = []
        for path in candidates[:_MAX_KEY_FILES]:
            try:
                content = await self.github.read_file_head(repo, path, max_lines=100)
                snippets.append(f"=== {path} ===\n{content}")
            except Exception:
                continue
        return "\n\n".join(snippets)

    async def _safe_read_file(self, repo: str, path: str) -> str:
        try:
            return await self.github.read_file(repo, path)
        except Exception:
            return ""

    async def _collect_dependencies(self, repo: str) -> str:
        parts = []
        for dep_file in ["requirements.txt", "package.json", "go.mod", "Cargo.toml"]:
            content = await self._safe_read_file(repo, dep_file)
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
