"""Canonical Voodoo 3.0 import-law tests."""

from __future__ import annotations


def test_canonical_application_surface_imports() -> None:
    from voodoo import Agent, App, Model, page, state, task, tool

    assert all((Agent, App, Model, page, state, task, tool))


def test_canonical_subsystem_namespace_imports() -> None:
    from voodoo.edge import DeviceGateway, WorldAwareDeviceGateway
    from voodoo.protocol import RemoteExecutionRequest, WorldSnapshot
    from voodoo.runtime import ExecutionEngine, Goal, GoalRuntime, Planner
    from voodoo.ui import Button, Card, DataTable
    from voodoo.world import Entity, Observation, WorldModel

    assert all(
        (
            DeviceGateway,
            WorldAwareDeviceGateway,
            RemoteExecutionRequest,
            WorldSnapshot,
            ExecutionEngine,
            Goal,
            GoalRuntime,
            Planner,
            Button,
            Card,
            DataTable,
            Entity,
            Observation,
            WorldModel,
        )
    )


def test_package_root_is_only_the_application_happy_path() -> None:
    import voodoo

    assert set(voodoo.__all__) == {
        "Agent",
        "App",
        "Model",
        "page",
        "state",
        "task",
        "tool",
    }
