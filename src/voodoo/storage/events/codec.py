"""Versioned event-envelope codec shared by every event adapter."""

from __future__ import annotations

from typing import Any

EVENT_SCHEMA_VERSION = 1


class EventCodecError(ValueError):
    """Raised when a durable event cannot be safely interpreted."""


def validate_event(event: Any) -> dict[str, Any]:
    """Validate and return an event envelope without silently downgrading it."""
    if not isinstance(event, dict):
        raise EventCodecError("event envelope must be a JSON object")
    version = event.get("schema_version", 1)
    if isinstance(version, bool) or not isinstance(version, int):
        raise EventCodecError("event schema version must be an integer")
    if version > EVENT_SCHEMA_VERSION:
        raise EventCodecError(f"unsupported event schema version: {version}")
    if version < 1:
        raise EventCodecError(f"invalid event schema version: {version}")
    for field in ("event_id", "event_type", "timestamp", "source", "payload"):
        if field not in event:
            raise EventCodecError(f"event envelope is missing {field!r}")
    return event
