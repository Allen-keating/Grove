"""PRD Baseline module — manage baseline lifecycle."""
import logging
from datetime import datetime, timezone

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.cards import build_baseline_merge_card, build_feature_status_card
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.prd_baseline.baseline_editor import (
    append_feature, format_feature_entry, parse_features,
)
from grove.modules.prd_baseline.matcher import FeatureMatcher
from grove.modules.prd_baseline.prompts import REORGANIZE_BASELINE_PROMPT

logger = logging.getLogger(__name__)

_OWN_ACTIONS = frozenset({
    "confirm_baseline_merge", "skip_baseline_merge",
    "confirm_feature_status", "reject_feature_status",
    "confirm_scan_gap",
})

_TRACKING_PATH = "memory/project-scan/feature-tracking.json"
_BASELINE_DOC_PATH = "memory/project-scan/baseline-doc-id.yml"


class PRDBaselineModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig, storage: Storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._matcher = FeatureMatcher(llm)

    # -- Trigger 1: New PRD finalized → send merge confirmation card --

    @subscribe(EventType.INTERNAL_PRD_FINALIZED)
    async def on_prd_finalized(self, event: Event) -> None:
        topic = event.payload.get("topic", "")
        github_path = event.payload.get("github_path", "")
        if not topic:
            return

        # Read first paragraph as summary
        summary = topic
        if github_path:
            try:
                content = await self.github.read_file(self.config.project.repo, github_path)
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
                        summary = stripped[:100]
                        break
            except Exception:
                pass

        prd_filename = github_path.split("/")[-1] if github_path else f"prd-{topic}.md"
        card = build_baseline_merge_card(topic=topic, summary=summary, prd_path=prd_filename)
        await self.lark.send_card(self.config.lark.chat_id, card)
        logger.info("Sent baseline merge card for '%s'", topic)

    # -- Trigger 2: PR merged → feature matching --

    @subscribe(EventType.PR_MERGED)
    async def on_pr_merged(self, event: Event) -> None:
        pr_data = event.payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        repo = event.payload.get("repository", {}).get("full_name", self.config.project.repo)
        if not pr_number:
            return

        # Load tracking data
        tracking = self._load_tracking()
        pending = [
            {"name": name, "status": info["status"], "description": info.get("description", "")}
            for name, info in tracking.get("features", {}).items()
            if info["status"] in ("in_progress", "planned")
        ]

        # Get PR commits
        try:
            commits = await self.github.get_pr_commits(repo, pr_number)
        except Exception:
            logger.warning("Failed to get commits for PR #%s", pr_number)
            return

        if not commits:
            return

        # LLM matching
        matches = await self._matcher.match_pr(commits, pending)

        for match in matches:
            if match.match_type == "none" or match.confidence < 0.5:
                continue
            await self._handle_match(match, pr_number, tracking)

    async def _handle_match(self, match, pr_number: int, tracking: dict) -> None:
        feature_name = match.matched_feature or ""
        chat_id = self.config.lark.chat_id

        if match.match_type == "existing":
            if match.confidence > 0.8:
                # Auto-update
                self._update_feature_status(tracking, feature_name, match.status, pr_number)
                if match.status == "completed":
                    await self.lark.send_text(chat_id,
                        f"PR #{pr_number} 完成了「{feature_name}」，已更新基线。")
                elif tracking["features"].get(feature_name, {}).get("status") == "planned":
                    await self.lark.send_text(chat_id,
                        f"PR #{pr_number} 开始了「{feature_name}」开发，已更新基线。")
                # in_progress → in_progress: no notification
                await self._sync_baseline()
            else:
                # Send confirmation card
                card = build_feature_status_card(
                    pr_number=pr_number, feature_name=feature_name,
                    suggested_status=match.status or "in_progress", reason=match.reason,
                )
                await self.lark.send_card(chat_id, card)

        elif match.match_type == "new":
            if match.confidence > 0.7:
                # Auto-add new feature
                self._add_feature(tracking, feature_name,
                                  status=match.status or "in_progress", pr_number=pr_number)
                await self.lark.send_text(chat_id,
                    f"检测到新功能「{feature_name}」（来自 PR #{pr_number}），已添加到基线。")
                await self._sync_baseline()
            else:
                card = build_feature_status_card(
                    pr_number=pr_number, feature_name=feature_name,
                    suggested_status="in_progress", reason=f"新功能：{match.reason}",
                )
                await self.lark.send_card(chat_id, card)

    # -- Trigger: Card actions --

    @subscribe(EventType.LARK_CARD_ACTION)
    async def on_card_action(self, event: Event) -> None:
        action_data = event.payload.get("action", {}).get("value", {})
        action = action_data.get("action", "")
        if action not in _OWN_ACTIONS:
            return

        tracking = self._load_tracking()
        chat_id = self.config.lark.chat_id

        if action == "confirm_baseline_merge":
            topic = action_data.get("topic", "")
            prd_path = action_data.get("prd_path", "")
            self._add_feature(tracking, topic, status="planned", prd_path=prd_path)
            await self._sync_baseline()
            await self.lark.send_text(chat_id, f"「{topic}」已添加到基线待开发列表。")

        elif action == "skip_baseline_merge":
            topic = action_data.get("topic", "")
            await self.lark.send_text(chat_id, f"已跳过「{topic}」的基线合并。")

        elif action == "confirm_feature_status":
            feature_name = action_data.get("feature_name", "")
            status = action_data.get("status", "in_progress")
            pr_number = action_data.get("pr_number")
            self._update_feature_status(tracking, feature_name, status, pr_number)
            await self._sync_baseline()
            await self.lark.send_text(chat_id, f"「{feature_name}」状态已更新。")

        elif action == "reject_feature_status":
            await self.lark.send_text(chat_id, "已忽略该功能关联。")

        elif action == "confirm_scan_gap":
            features = action_data.get("features", [])
            for f in features:
                self._add_feature(tracking, f["name"], status=f.get("status", "done"))
            await self._sync_baseline()
            await self.lark.send_text(chat_id, f"已将 {len(features)} 个功能添加到基线。")

    # -- Trigger 3: Reorganize baseline --

    @subscribe(EventType.INTERNAL_REORGANIZE_BASELINE)
    async def on_reorganize(self, event: Event) -> None:
        chat_id = event.payload.get("chat_id", self.config.lark.chat_id)
        await self.lark.send_text(chat_id, "正在整理基线文档...")

        baseline = await self._read_baseline_from_github()
        if not baseline:
            await self.lark.send_text(chat_id, "未找到基线文档，请先运行「扫描项目」。")
            return

        prompt = REORGANIZE_BASELINE_PROMPT.format(
            baseline_content=baseline, feature_prds="",
        )
        try:
            new_content = await self.llm.chat(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "请整理基线文档。"}],
                max_tokens=4096,
            )
        except Exception:
            await self.lark.send_text(chat_id, "基线整理失败，请稍后重试。")
            return

        # Update tracking from reorganized content
        features = parse_features(new_content)
        tracking = {"features": {}}
        for status_key, feat_list in features.items():
            for f in feat_list:
                tracking["features"][f["name"]] = {
                    "status": status_key,
                    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                }
        self._save_tracking(tracking)

        # Sync
        await self._write_baseline_to_github(new_content)
        await self._update_lark_doc(new_content)
        await self.lark.send_text(chat_id, "基线文档已整理完成。")

    # -- Internal helpers --

    def _load_tracking(self) -> dict:
        try:
            return self._storage.read_json(_TRACKING_PATH)
        except FileNotFoundError:
            return {"features": {}}

    def _save_tracking(self, tracking: dict) -> None:
        self._storage.write_json(_TRACKING_PATH, tracking)

    def _add_feature(self, tracking: dict, name: str, status: str = "planned",
                     prd_path: str | None = None, pr_number: int | None = None) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tracking.setdefault("features", {})[name] = {
            "status": status,
            "prd_path": prd_path,
            "related_prs": [pr_number] if pr_number else [],
            "added_at": now,
            "updated_at": now,
        }
        self._save_tracking(tracking)

    def _update_feature_status(self, tracking: dict, name: str, status: str | None,
                                pr_number: int | None = None) -> None:
        features = tracking.setdefault("features", {})
        if name not in features:
            features[name] = {"status": "planned", "related_prs": [],
                               "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
        if status:
            features[name]["status"] = status
        if pr_number:
            features[name].setdefault("related_prs", []).append(pr_number)
        features[name]["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._save_tracking(tracking)

    async def _read_baseline_from_github(self) -> str | None:
        try:
            return await self.github.read_file(self.config.project.repo, "docs/project-baseline.md")
        except Exception:
            return None

    async def _write_baseline_to_github(self, content: str) -> None:
        try:
            await self.github.write_file(
                self.config.project.repo, "docs/project-baseline.md",
                content, "docs: update project baseline",
            )
        except Exception:
            logger.exception("Failed to write baseline to GitHub")

    async def _update_lark_doc(self, content: str) -> None:
        try:
            doc_info = self._storage.read_yaml(_BASELINE_DOC_PATH)
            doc_id = doc_info.get("doc_id")
            if doc_id:
                await self.lark.update_doc(doc_id, content)
        except (FileNotFoundError, Exception):
            logger.warning("Failed to update Lark baseline doc")

    async def _sync_baseline(self) -> None:
        """Regenerate baseline Markdown from tracking data and sync."""
        baseline = await self._read_baseline_from_github()
        if not baseline:
            return
        tracking = self._load_tracking()
        for name, info in tracking.get("features", {}).items():
            status = info.get("status", "planned")
            status_map = {"done": "done", "in_progress": "in_progress",
                          "planned": "planned", "completed": "done"}
            section = status_map.get(status, "planned")

            # Check if feature already exists in baseline
            features = parse_features(baseline)
            all_names = [f["name"] for fl in features.values() for f in fl]
            if name not in all_names:
                entry = format_feature_entry(
                    name=name, description=info.get("description", ""),
                    status=section, prd_path=info.get("prd_path"),
                )
                baseline = append_feature(baseline, section, entry)

        await self._write_baseline_to_github(baseline)
        await self._update_lark_doc(baseline)
