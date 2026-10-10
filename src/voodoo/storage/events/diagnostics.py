"""Shared diagnostics for non-fatal event subscriber failures."""

from __future__ import annotations

import logging
from typing import Any

from voodoo.security.redaction import redact_string

logger = logging.getLogger("voodoo.events")


def report_handler_failure(provider: str, event_type: str, error: Any) -> None:
    """Report a subscriber failure without making delivery silently disappear."""
    logger.warning(
        "event subscriber failed provider=%s event_type=%s error=%s",
        provider,
        event_type,
        redact_string(str(error)),
    )
