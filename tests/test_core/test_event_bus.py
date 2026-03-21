# tests/test_core/test_event_bus.py
import asyncio
import logging

import pytest

from grove.core.event_bus import EventBus, subscribe
from grove.core.events import Event, EventType


class TestEventBus:
    @pytest.fixture
    def bus(self):
        return EventBus()

    async def test_subscribe_and_dispatch(self, bus: EventBus):
        received = []

        class TestModule:
            @subscribe(EventType.PR_OPENED)
            async def on_pr(self, event: Event):
                received.append(event)

        module = TestModule()
        bus.register(module)

        event = Event(type=EventType.PR_OPENED, source="github", payload={"pr": 1})
        await bus.dispatch(event)

        assert len(received) == 1
        assert received[0].payload == {"pr": 1}

    async def test_dispatch_to_multiple_subscribers(self, bus: EventBus):
        results = {"a": [], "b": []}

        class ModuleA:
            @subscribe(EventType.PR_MERGED)
            async def handle(self, event: Event):
                results["a"].append(event)

        class ModuleB:
            @subscribe(EventType.PR_MERGED)
            async def handle(self, event: Event):
                results["b"].append(event)

        bus.register(ModuleA())
        bus.register(ModuleB())

        event = Event(type=EventType.PR_MERGED, source="github", payload={})
        await bus.dispatch(event)

        assert len(results["a"]) == 1
        assert len(results["b"]) == 1

    async def test_no_cross_dispatch(self, bus: EventBus):
        received = []

        class TestModule:
            @subscribe(EventType.PR_OPENED)
            async def on_pr(self, event: Event):
                received.append(event)

        bus.register(TestModule())

        event = Event(type=EventType.ISSUE_OPENED, source="github", payload={})
        await bus.dispatch(event)

        assert len(received) == 0

    async def test_handler_error_does_not_block_others(self, bus: EventBus, caplog):
        results = []

        class BadModule:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event: Event):
                raise ValueError("boom")

        class GoodModule:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event: Event):
                results.append("ok")

        bus.register(BadModule())
        bus.register(GoodModule())

        event = Event(type=EventType.PR_OPENED, source="github", payload={})
        with caplog.at_level(logging.ERROR):
            await bus.dispatch(event)

        assert len(results) == 1
        assert "boom" in caplog.text

    async def test_multiple_subscriptions_on_same_module(self, bus: EventBus):
        received = []

        class MultiModule:
            @subscribe(EventType.PR_OPENED)
            async def on_pr(self, event: Event):
                received.append("pr")

            @subscribe(EventType.ISSUE_OPENED)
            async def on_issue(self, event: Event):
                received.append("issue")

        bus.register(MultiModule())

        await bus.dispatch(Event(type=EventType.PR_OPENED, source="github", payload={}))
        await bus.dispatch(Event(type=EventType.ISSUE_OPENED, source="github", payload={}))

        assert received == ["pr", "issue"]

    async def test_emit_internal_event(self, bus: EventBus):
        received = []

        class Producer:
            def __init__(self, bus: EventBus):
                self.bus = bus

            @subscribe(EventType.LARK_MESSAGE)
            async def on_message(self, event: Event):
                await self.bus.dispatch(
                    Event(
                        type=EventType.INTERNAL_NEW_REQUIREMENT,
                        source="internal",
                        payload={"text": event.payload["text"]},
                        member=event.member,
                    )
                )

        class Consumer:
            @subscribe(EventType.INTERNAL_NEW_REQUIREMENT)
            async def on_requirement(self, event: Event):
                received.append(event.payload["text"])

        bus.register(Producer(bus))
        bus.register(Consumer())

        await bus.dispatch(
            Event(type=EventType.LARK_MESSAGE, source="lark", payload={"text": "新需求"})
        )

        assert received == ["新需求"]
