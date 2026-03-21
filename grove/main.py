"""Grove application entry point — wires FastAPI, EventBus, integrations, ingress."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from grove.config import load_config
from grove.core.event_bus import EventBus
from grove.core.events import Event
from grove.core.member_resolver import MemberResolver
from grove.core.storage import Storage
from grove.ingress.github_webhook import create_github_webhook_router
from grove.ingress.health import HealthState, create_health_router
from grove.ingress.lark_webhook import create_lark_webhook_router
from grove.ingress.lark_websocket import create_lark_ws_client
from grove.ingress.scheduler import create_scheduler
from grove.integrations.github.client import GitHubClient
from grove.integrations.lark.client import LarkClient
from grove.integrations.llm.client import LLMClient
from grove.modules.communication.handler import CommunicationModule
from grove.modules.member.handler import MemberModule
from grove.modules.prd_generator.handler import PRDGeneratorModule
from grove.modules.prd_generator.conversation import ConversationManager
from grove.modules.task_breakdown.handler import TaskBreakdownModule
from grove.modules.daily_report.handler import DailyReportModule
from grove.modules.pr_review.handler import PRReviewModule
from grove.modules.doc_sync.handler import DocSyncModule

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _get_grove_dir() -> Path:
    return Path(os.environ.get("GROVE_DIR", ".grove"))


health_state = HealthState()
_grove_dir = _get_grove_dir()
event_bus = EventBus(failed_events_path=_grove_dir / "logs" / "failed-events.jsonl")
_member_resolver: MemberResolver | None = None


async def handle_event(event: Event) -> None:
    health_state.last_event_processed = event.timestamp
    if _member_resolver is not None:
        github_user = None
        lark_user = None
        if event.source == "github":
            payload = event.payload
            if "sender" in payload:
                github_user = payload["sender"].get("login")
            elif "issue" in payload:
                github_user = payload["issue"].get("user", {}).get("login")
        elif event.source == "lark":
            lark_user = event.payload.get("sender_id")
        if github_user:
            event.member = _member_resolver.by_github(github_user)
        elif lark_user:
            event.member = _member_resolver.by_lark_id(lark_user)
    await event_bus.dispatch(event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _member_resolver
    grove_dir = _get_grove_dir()
    logger.info("Starting Grove with .grove/ at %s", grove_dir)

    config = load_config(grove_dir)
    app.state.config = config

    storage = Storage(grove_dir)
    app.state.storage = storage

    resolver = MemberResolver(storage)
    _member_resolver = resolver
    app.state.member_resolver = resolver
    logger.info("Loaded %d team members", len(resolver.members))

    app.state.github_client = GitHubClient(
        app_id=config.github.app_id,
        private_key_path=config.github.private_key_path,
        installation_id=config.github.installation_id,
    )
    app.state.lark_client = LarkClient(
        app_id=config.lark.app_id, app_secret=config.lark.app_secret,
    )
    app.state.llm_client = LLMClient(
        api_key=config.llm.api_key, model=config.llm.model,
    )

    # Conversation manager
    conv_manager = ConversationManager(storage)

    # Register modules
    communication = CommunicationModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
    )
    event_bus.register(communication)
    logger.info("Registered CommunicationModule")

    prd_generator = PRDGeneratorModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, conv_manager=conv_manager,
    )
    event_bus.register(prd_generator)
    logger.info("Registered PRDGeneratorModule")

    # Member module
    member_module = MemberModule(resolver=resolver, storage=storage)
    event_bus.register(member_module)
    logger.info("Registered MemberModule")

    # Task breakdown module
    task_breakdown = TaskBreakdownModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        member_module=member_module, resolver=resolver,
    )
    event_bus.register(task_breakdown)
    logger.info("Registered TaskBreakdownModule")

    daily_report = DailyReportModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        resolver=resolver, storage=storage,
    )
    event_bus.register(daily_report)
    logger.info("Registered DailyReportModule")

    pr_review = PRReviewModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config)
    event_bus.register(pr_review)
    logger.info("Registered PRReviewModule")

    doc_sync = DocSyncModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage)
    event_bus.register(doc_sync)
    logger.info("Registered DocSyncModule")

    # Register webhook routers (need config)
    app.include_router(create_github_webhook_router(
        webhook_secret=config.github.webhook_secret, on_event=handle_event,
    ))
    app.include_router(create_lark_webhook_router(on_event=handle_event))

    # Scheduler
    scheduler = create_scheduler(
        daily_report_time=config.schedules.daily_report,
        doc_drift_time=config.schedules.doc_drift_check,
        timezone=config.work_hours.timezone,
        on_event=handle_event,
    )
    scheduler.start()
    health_state.scheduler_running = True
    logger.info("Scheduler started")

    # Lark WebSocket
    main_loop = asyncio.get_running_loop()
    lark_ws = create_lark_ws_client(
        app_id=config.lark.app_id, app_secret=config.lark.app_secret,
        on_event=handle_event, loop=main_loop,
    )

    async def start_lark_ws():
        try:
            health_state.lark_ws_connected = True
            logger.info("Lark WebSocket starting")
            await asyncio.to_thread(lark_ws.start)
        except Exception:
            health_state.lark_ws_connected = False
            logger.exception("Lark WebSocket disconnected or failed to start")

    lark_task = asyncio.create_task(start_lark_ws())
    logger.info("Grove is ready — %s", config.persona.name)
    yield

    scheduler.shutdown()
    health_state.scheduler_running = False
    lark_task.cancel()
    _member_resolver = None
    logger.info("Grove shutdown complete")


app = FastAPI(title="Grove — AI Product Manager", lifespan=lifespan)
app.include_router(create_health_router(health_state))
