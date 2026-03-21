"""Lark WebSocket long-connection client for receiving messages."""
import asyncio
import json
import logging
from typing import Awaitable, Callable

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from grove.core.events import Event, EventType
from grove.integrations.lark.models import LarkMessage

logger = logging.getLogger(__name__)


def _parse_lark_message(data: P2ImMessageReceiveV1) -> LarkMessage | None:
    try:
        msg = data.event.message
        sender = data.event.sender
        content = json.loads(msg.content)
        text = content.get("text", "")
        mentions = msg.mentions or []
        is_mention = any(m.name == "Grove" or m.key == "@_all" for m in mentions)
        for m in mentions:
            text = text.replace(f"@_user_{m.id.open_id}", "").strip()
        return LarkMessage(
            message_id=msg.message_id,
            chat_id=msg.chat_id,
            sender_id=sender.sender_id.open_id,
            text=text,
            is_mention=is_mention,
            chat_type=msg.chat_type,
        )
    except Exception:
        logger.exception("Failed to parse Lark message")
        return None


def create_lark_ws_client(
    app_id: str,
    app_secret: str,
    on_event: Callable[[Event], Awaitable[None]],
    loop: asyncio.AbstractEventLoop | None = None,
) -> lark.ws.Client:
    """Create a Lark WebSocket client. Callbacks dispatch to the main asyncio loop via run_coroutine_threadsafe."""
    _loop = loop or asyncio.get_running_loop()

    def handle_message(data: P2ImMessageReceiveV1):
        msg = _parse_lark_message(data)
        if msg is None:
            return
        if not msg.is_mention and msg.chat_type != "p2p":
            return
        event = Event(
            type=EventType.LARK_MESSAGE,
            source="lark",
            payload={
                "message_id": msg.message_id,
                "chat_id": msg.chat_id,
                "sender_id": msg.sender_id,
                "text": msg.text,
                "chat_type": msg.chat_type,
            },
        )
        asyncio.run_coroutine_threadsafe(on_event(event), _loop)

    def handle_card_action(data):
        """Handle Lark interactive card button clicks."""
        try:
            action = data.event.action
            operator = data.event.operator
            event = Event(
                type=EventType.LARK_CARD_ACTION,
                source="lark",
                payload={
                    "action": {"value": action.value if hasattr(action, "value") else {}},
                    "operator_id": operator.open_id if hasattr(operator, "open_id") else "",
                },
            )
            asyncio.run_coroutine_threadsafe(on_event(event), _loop)
        except Exception:
            logger.exception("Failed to parse card action")

    # NOTE: register_p2_card_action_trigger requires lark-oapi >= 1.4.0.
    # If the SDK version does not support it, card actions are received via the
    # HTTP webhook fallback already implemented in lark_webhook.py.
    event_handler_builder = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(handle_message)
    if hasattr(event_handler_builder, "register_p2_card_action_trigger"):
        event_handler_builder = event_handler_builder.register_p2_card_action_trigger(
            handle_card_action
        )
    event_handler = event_handler_builder.build()

    ws_client = lark.ws.Client(
        app_id=app_id,
        app_secret=app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    return ws_client
