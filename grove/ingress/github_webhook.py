"""GitHub webhook receiver with signature verification."""
import hashlib
import hmac
import logging
from typing import Awaitable, Callable
from fastapi import APIRouter, Request, Response
from grove.core.events import Event, EventType

logger = logging.getLogger(__name__)

_EVENT_MAP: dict[tuple[str, str], str] = {
    ("issues", "opened"): EventType.ISSUE_OPENED,
    ("issues", "edited"): EventType.ISSUE_UPDATED,
    ("issues", "closed"): EventType.ISSUE_UPDATED,
    ("issues", "reopened"): EventType.ISSUE_UPDATED,
    ("issues", "labeled"): EventType.ISSUE_LABELED,
    ("issue_comment", "created"): EventType.ISSUE_COMMENTED,
    ("pull_request", "opened"): EventType.PR_OPENED,
    ("pull_request", "closed"): EventType.PR_MERGED,
    ("pull_request", "review_requested"): EventType.PR_REVIEW_REQUESTED,
}


def _verify_signature(payload: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_github_webhook_router(
    webhook_secret: str,
    on_event: Callable[[Event], Awaitable[None]],
) -> APIRouter:
    router = APIRouter()

    @router.post("/webhook/github")
    async def handle_webhook(request: Request):
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(body, webhook_secret, signature):
            logger.warning("Invalid webhook signature")
            return Response(status_code=403, content="Invalid signature")
        gh_event = request.headers.get("X-GitHub-Event", "")
        data = await request.json()
        action = data.get("action", "")
        event_type = _EVENT_MAP.get((gh_event, action))
        if event_type is None:
            logger.debug("Ignoring GitHub event: %s/%s", gh_event, action)
            return {"status": "ignored"}
        if gh_event == "pull_request" and action == "closed":
            if data.get("pull_request", {}).get("merged"):
                event_type = EventType.PR_MERGED
            else:
                return {"status": "ignored"}
        event = Event(type=event_type, source="github", payload=data)
        await on_event(event)
        return {"status": "ok"}

    return router
