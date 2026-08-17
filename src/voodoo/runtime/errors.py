"""Structured execution errors.

Every error that crosses a subsystem boundary preserves runtime context
(``execution_id``, ``trace_id``, ``parent_execution_id``) so that failures
remain attributable and traceable instead of becoming generic exceptions.

Centralized constraint/capability failures map onto these error types so
that Agent, Tool, Worker, Workflow and Task do not each invent their own.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ExecutionError",
    "CapabilityDenied",
    "ConstraintViolation",
    "ResourceExceeded",
    "ExecutionTimeout",
    "ExecutionCancelled",
    "ToolExecutionError",
    "AgentExecutionError",
    "ValidationError",
    "ApprovalRequired",
    "WorkflowFailure",
]


class ExecutionError(Exception):
    """Base class for all structured runtime errors.

    Carries the execution context so it remains meaningful even after it
    propagates across subsystem boundaries.
    """

    def __init__(
        self,
        message: str,
        *,
        execution_id: str | None = None,
        trace_id: str | None = None,
        parent_execution_id: str | None = None,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.execution_id = execution_id
        self.trace_id = trace_id
        self.parent_execution_id = parent_execution_id
        self.context: dict[str, Any] = dict(context) if context else {}
        self.cause = cause

    def describe(self) -> dict[str, Any]:
        return {
            "type": type(self).__name__,
            "message": self.message,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "parent_execution_id": self.parent_execution_id,
            "context": self.context,
        }


class CapabilityDenied(ExecutionError):
    """An actor lacked a required capability."""


class ConstraintViolation(ExecutionError):
    """Execution violated a constraint (cost, latency, iterations, ...)."""


class ResourceExceeded(ExecutionError):
    """A resource limit (tokens, cost, memory, ...) was exceeded."""


class ExecutionTimeout(ExecutionError):
    """Execution did not complete before its deadline."""


class ExecutionCancelled(ExecutionError):
    """Execution was cancelled."""


class ToolExecutionError(ExecutionError):
    """A tool invocation failed."""


class AgentExecutionError(ExecutionError):
    """Agent execution failed."""


class ValidationError(ExecutionError):
    """Structured output validation failed."""


class ApprovalRequired(ExecutionError):
    """Human approval is required before execution may proceed."""


class WorkflowFailure(ExecutionError):
    """A workflow failed to complete."""
