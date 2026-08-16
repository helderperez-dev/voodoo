"""Tests for the @event decorator and event dispatch."""

import pytest

from voodoo.core.events import event, event_handlers, register_event


def test_event_decorator_registers_handler():
    @event
    async def my_handler(element_id, value):
        pass

    assert "my_handler" in event_handlers
    assert event_handlers["my_handler"] is my_handler


def test_event_decorator_returns_function_unchanged():
    @event
    async def another_handler(element_id, value):
        return "result"

    assert callable(another_handler)
    assert another_handler.__name__ == "another_handler"


def test_event_decorator_handler_is_async():
    @event
    async def async_handler(element_id, value):
        pass

    import inspect

    assert inspect.iscoroutinefunction(event_handlers["async_handler"])


def test_register_event_directly():
    async def custom_handler(element_id, value):
        pass

    register_event("custom_event", custom_handler)
    assert event_handlers["custom_event"] is custom_handler


@pytest.mark.asyncio
async def test_event_handler_invocation():
    received = []

    @event
    async def test_event_handler(element_id, value):
        received.append((element_id, value))

    handler = event_handlers["test_event_handler"]
    await handler("btn-1", "clicked")
    assert received == [("btn-1", "clicked")]
