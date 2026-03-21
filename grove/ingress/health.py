"""Health check endpoint for Docker HEALTHCHECK and monitoring."""
from dataclasses import dataclass
from datetime import datetime
from fastapi import APIRouter


@dataclass
class HealthState:
    lark_ws_connected: bool = False
    scheduler_running: bool = False
    last_event_processed: datetime | None = None


def create_health_router(state: HealthState) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        is_healthy = state.lark_ws_connected and state.scheduler_running
        return {
            "status": "healthy" if is_healthy else "degraded",
            "fastapi": True,
            "lark_ws_connected": state.lark_ws_connected,
            "scheduler_running": state.scheduler_running,
            "last_event_processed": (
                state.last_event_processed.isoformat() if state.last_event_processed else None
            ),
        }

    return router
