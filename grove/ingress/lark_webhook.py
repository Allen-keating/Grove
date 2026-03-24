"""Lark HTTP webhook for receiving event callbacks (e.g., doc_updated)."""
import hmac
import logging
from typing import Awaitable, Callable
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from grove.core.events import Event, EventType

logger = logging.getLogger(__name__)


def create_lark_webhook_router(
    on_event: Callable[[Event], Awaitable[None]],
    verification_token: str = "",
) -> APIRouter:
    router = APIRouter()

    @router.post("/webhook/lark")
    async def handle_lark_callback(request: Request):
        data = await request.json()
        if "challenge" in data:
            return {"challenge": data["challenge"]}
        # Verify token if configured
        if verification_token:
            token_in_request = data.get("header", {}).get("token", "")
            if not hmac.compare_digest(token_in_request, verification_token):
                logger.warning("Invalid Lark webhook token")
                return JSONResponse(status_code=403, content={"error": "invalid token"})
        event_type = data.get("header", {}).get("event_type", "")
        if event_type == "drive.file.edit_v1":
            event = Event(type=EventType.LARK_DOC_UPDATED, source="lark", payload=data)
            await on_event(event)
            return {"status": "ok"}
        logger.debug("Ignoring Lark callback event: %s", event_type)
        return {"status": "ignored"}

    return router
