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
from grove.core.module_registry import ModuleRegistry, merge_module_state
from grove.core.storage import Storage
from grove.ingress.admin import create_admin_router
from grove.ingress.github_webhook import create_github_webhook_router
from grove.ingress.health import HealthState, create_health_router
from grove.ingress.lark_webhook import create_lark_webhook_router
from grove.ingress.lark_websocket import create_lark_ws_client
from grove.ingress.scheduler import create_scheduler
from grove.integrations.github.async_client import AsyncGitHubClient
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
from grove.modules.project_scanner.handler import ProjectScannerModule
from grove.modules.project_overview.handler import ProjectOverviewModule
from grove.modules.morning_dispatch.handler import MorningDispatchModule
from grove.modules.prd_baseline.handler import PRDBaselineModule

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

    sync_github = GitHubClient(
        app_id=config.github.app_id,
        private_key_path=config.github.private_key_path,
        installation_id=config.github.installation_id,
    )
    app.state.github_client = AsyncGitHubClient(sync_github)
    app.state.lark_client = LarkClient(
        app_id=config.lark.app_id, app_secret=config.lark.app_secret,
    )
    app.state.llm_client = LLMClient(
        api_key=config.llm.api_key, model=config.llm.model,
    )

    # Merge config + runtime state
    effective_modules = merge_module_state(config.modules, storage)

    # Module registry
    registry = ModuleRegistry(bus=event_bus, storage=storage)
    app.state.module_registry = registry

    # Conversation manager
    conv_manager = ConversationManager(storage)

    # Always instantiate all modules
    member_module = MemberModule(resolver=resolver, storage=storage)
    communication = CommunicationModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, registry=registry,
        storage=storage,
    )
    prd_generator = PRDGeneratorModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, conv_manager=conv_manager,
        storage=storage,
    )
    task_breakdown = TaskBreakdownModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        member_module=member_module, resolver=resolver, storage=storage,
    )
    daily_report = DailyReportModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
        resolver=resolver, storage=storage,
    )
    pr_review = PRReviewModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config,
    )
    doc_sync = DocSyncModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )
    project_scanner = ProjectScannerModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )
    project_overview = ProjectOverviewModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )
    morning_dispatch = MorningDispatchModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
        resolver=resolver, member_module=member_module,
    )
    prd_baseline = PRDBaselineModule(
        bus=event_bus, llm=app.state.llm_client, lark=app.state.lark_client,
        github=app.state.github_client, config=config, storage=storage,
    )

    # Register via registry (respects merged state)
    registry.add("communication", communication, enabled=effective_modules["communication"])
    registry.add("prd_generator", prd_generator, enabled=effective_modules["prd_generator"])
    registry.add("member", member_module, enabled=effective_modules["member"])
    registry.add("task_breakdown", task_breakdown, enabled=effective_modules["task_breakdown"])
    registry.add("daily_report", daily_report, enabled=effective_modules["daily_report"])
    registry.add("pr_review", pr_review, enabled=effective_modules["pr_review"])
    registry.add("doc_sync", doc_sync, enabled=effective_modules["doc_sync"])
    registry.add("project_scanner", project_scanner, enabled=effective_modules["project_scanner"])
    registry.add("project_overview", project_overview, enabled=effective_modules["project_overview"])
    registry.add("morning_dispatch", morning_dispatch, enabled=effective_modules["morning_dispatch"])
    registry.add("prd_baseline", prd_baseline, enabled=effective_modules["prd_baseline"])

    # Admin API (only if token configured)
    if config.admin_token:
        app.include_router(create_admin_router(registry, config.admin_token))
        logger.info("Admin API enabled at /admin/modules")

    # Register webhook routers (need config)
    app.include_router(create_github_webhook_router(
        webhook_secret=config.github.webhook_secret, on_event=handle_event,
    ))
    app.include_router(create_lark_webhook_router(
        on_event=handle_event, verification_token=config.lark.verification_token,
    ))

    # Scheduler
    scheduler = create_scheduler(
        schedules=config.schedules,
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
