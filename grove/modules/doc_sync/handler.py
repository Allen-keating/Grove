# grove/modules/doc_sync/handler.py
"""Document sync module — keep PRD in sync with code changes."""
import logging
from grove.core.event_bus import subscribe
from grove.core.events import Event, EventType
from grove.modules.doc_sync.diff_classifier import DiffClassifier
from grove.modules.doc_sync.doc_updater import DocUpdater

logger = logging.getLogger(__name__)

class DocSyncModule:
    def __init__(self, bus, llm, lark, github, config, storage):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self._storage = storage
        self._classifier = DiffClassifier(llm=llm)
        self._updater = DocUpdater(llm=llm, lark=lark, config=config)

    @subscribe(EventType.PR_MERGED)
    async def on_pr_merged(self, event: Event) -> None:
        pr_data = event.payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        pr_title = pr_data.get("title", "")
        repo = event.payload.get("repository", {}).get("full_name", self.config.project.repo)
        logger.info("Checking PR #%s for doc sync: %s", pr_number, pr_title)
        try:
            diff = await self.github.get_pr_diff(repo, pr_number)
        except Exception:
            logger.exception("Failed to get diff for PR #%s", pr_number)
            return
        classification = await self._classifier.classify(diff, f"PR #{pr_number}: {pr_title}")
        if not classification.is_product_change:
            logger.info("PR #%s: no product-level changes", pr_number)
            return
        logger.info("PR #%s: product change (%s) — %s", pr_number, classification.severity, classification.description)
        doc_id = self._resolve_doc_id()
        if doc_id:
            await self._updater.apply(classification, pr_number, doc_id)
        else:
            logger.warning("No Lark doc_id found in sync-state, skipping Lark update for PR #%s", pr_number)
        self._record_sync(pr_number, classification)

    @subscribe(EventType.CRON_DOC_DRIFT_CHECK)
    async def on_doc_drift_check(self, event: Event) -> None:
        logger.info("Running document drift check...")
        sync_state = self._get_sync_state()
        if not sync_state.get("pending"):
            logger.info("No pending doc syncs")
            return
        report = "📄 **文档同步状态**\n\n"
        for item in sync_state["pending"]:
            report += f"- ⚠️ PR #{item['pr_number']}: {item['description']}（待确认）\n"
        await self.lark.send_text(self.config.lark.chat_id, report)

    def _record_sync(self, pr_number, classification):
        try:
            state = self._get_sync_state()
            if classification.severity in ("medium", "large"):
                state.setdefault("pending", []).append({
                    "pr_number": pr_number, "description": classification.description,
                    "severity": classification.severity})
            else:
                state.setdefault("synced", []).append({
                    "pr_number": pr_number, "description": classification.description})
            self._storage.write_yaml("docs-sync/sync-state.yml", state)
        except Exception:
            logger.exception("Failed to record sync state")

    def _resolve_doc_id(self) -> str | None:
        """Look up the first available PRD doc_id from sync-state."""
        state = self._get_sync_state()
        doc_ids = state.get("doc_ids", {})
        return next(iter(doc_ids.values()), None) if doc_ids else None

    def _get_sync_state(self):
        try:
            return self._storage.read_yaml("docs-sync/sync-state.yml")
        except FileNotFoundError:
            return {"synced": [], "pending": []}
