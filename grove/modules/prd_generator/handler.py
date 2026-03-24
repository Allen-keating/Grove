"""PRD Generator module — guided questioning and document generation."""

import logging

from grove.config import GroveConfig
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType
from grove.core.storage import Storage
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.prd_generator.conversation import ConversationManager
from grove.modules.prd_generator.prompts import GUIDED_QUESTION_PROMPT, PRD_GENERATE_PROMPT

logger = logging.getLogger(__name__)


class PRDGeneratorModule:
    def __init__(self, bus: EventBus, llm: LLMClient, lark: LarkClient,
                 github: GitHubClient, config: GroveConfig,
                 conv_manager: ConversationManager, storage: Storage | None = None):
        self.bus = bus
        self.llm = llm
        self.lark = lark
        self.github = github
        self.config = config
        self.conv_manager = conv_manager
        self._storage = storage

    @subscribe(EventType.INTERNAL_NEW_REQUIREMENT)
    async def on_new_requirement(self, event: Event) -> None:
        topic = event.payload.get("topic", "新需求")
        chat_id = event.payload.get("chat_id", "")
        initiator = event.member.github if event.member else "unknown"

        existing = self.conv_manager.get_active_for_chat(chat_id)
        if existing:
            await self.lark.send_text(chat_id,
                f"当前正在进行「{existing.topic}」的 PRD 讨论，请先完成再开始新话题。")
            return

        conv = self.conv_manager.create(chat_id=chat_id, initiator_github=initiator, topic=topic)
        conv.add_message("user", event.payload.get("original_text", topic))

        question = await self._get_next_question(conv)
        conv.add_message("assistant", question)
        self.conv_manager.save(conv)

        await self.lark.send_text(chat_id, f"好的，我来帮你整理「{topic}」的 PRD。\n\n{question}")

    @subscribe(EventType.LARK_MESSAGE)
    async def on_lark_message(self, event: Event) -> None:
        if event.payload.get("intent") != "continue_conversation":
            return
        await self._on_continue_conversation(event)

    async def _on_continue_conversation(self, event: Event) -> None:
        chat_id = event.payload.get("chat_id", "")
        text = event.payload.get("text", "")

        conv = self.conv_manager.get_active_for_chat(chat_id)
        if conv is None:
            return

        conv.add_message("user", text)
        next_question = await self._get_next_question(conv)

        if "READY_TO_GENERATE" in next_question:
            conv.state = "generating"
            self.conv_manager.save(conv)
            await self.lark.send_text(chat_id, "信息收集完毕，正在生成 PRD 文档...")
            await self._generate_prd(conv)
        else:
            conv.add_message("assistant", next_question)
            self.conv_manager.save(conv)
            await self.lark.send_text(chat_id, next_question)

    async def _get_next_question(self, conv) -> str:
        collected = "\n".join(f"- {m['role']}: {m['content']}" for m in conv.messages)
        prompt = GUIDED_QUESTION_PROMPT.format(topic=conv.topic, collected_info=collected)
        return await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请提出下一个问题。"}],
            max_tokens=256,
        )

    async def _generate_prd(self, conv) -> None:
        conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in conv.messages)
        prompt = PRD_GENERATE_PROMPT.format(topic=conv.topic, conversation_text=conversation_text)
        prd_content = await self.llm.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "请生成 PRD 文档。"}],
            max_tokens=4096,
        )

        filename = conv.topic.replace(" ", "-").replace("/", "-")

        try:
            doc_id = await self.lark.create_doc(
                space_id=self.config.lark.space_id,
                title=f"{conv.topic} — PRD",
                markdown_content=prd_content,
            )
            conv.prd_doc_id = doc_id
            self._save_doc_id(f"prd-{filename}.md", doc_id)
        except Exception:
            logger.exception("Failed to create Lark doc")
            doc_id = None

        try:
            github_path = f"{self.config.doc_sync.github_docs_path}prd-{filename}.md"
            await self.github.write_file(self.config.project.repo, github_path, prd_content,
                                         f"docs: add PRD for {conv.topic}")
        except Exception:
            logger.exception("Failed to sync PRD to GitHub")

        conv.state = "completed"
        self.conv_manager.save(conv)

        msg = f"PRD「{conv.topic}」已生成！"
        if doc_id:
            msg += "\n📄 飞书文档已创建"
        msg += "\n📝 GitHub 同步副本已提交\n\n请团队成员审阅并修改。"
        await self.lark.send_text(conv.chat_id, msg)

        await self.bus.dispatch(Event(
            type=EventType.INTERNAL_PRD_FINALIZED, source="internal",
            payload={
                "topic": conv.topic, "prd_doc_id": doc_id,
                "conversation_id": conv.id,
                "github_path": f"{self.config.doc_sync.github_docs_path}prd-{filename}.md",
            },
            member=None,
        ))

    def _save_doc_id(self, filename: str, doc_id: str) -> None:
        """Record the Lark doc_id in sync-state for doc_sync module to use."""
        if not self._storage:
            return
        try:
            sync_state = self._storage.read_yaml("docs-sync/sync-state.yml")
        except FileNotFoundError:
            sync_state = {"synced": [], "pending": []}
        sync_state.setdefault("doc_ids", {})[filename] = doc_id
        self._storage.write_yaml("docs-sync/sync-state.yml", sync_state)
