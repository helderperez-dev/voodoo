"""Acceptance coverage for the public Component Lab."""

from __future__ import annotations

import re
import runpy
from pathlib import Path

from starlette.testclient import TestClient

import voodoo.ui as public_ui


def test_component_lab_renders_all_primary_surfaces() -> None:
    namespace = runpy.run_path(
        "examples/web/component_lab/main.py",
        run_name="component_lab_acceptance",
    )

    with TestClient(namespace["app"]) as client:
        for path in (
            "/",
            "/foundations",
            "/shell",
            "/chat",
            "/auth",
            "/forms",
            "/navigation",
            "/advanced",
            "/data",
            "/workspace",
            "/system",
            "/feedback",
        ):
            response = client.get(path)
            assert response.status_code == 200, response.text
            assert "Component Lab" in response.text
            assert "vd-" in response.text

        overview = client.get("/").text
        assert "vd-button--primary" in overview
        assert "vd-card" in overview
        assert "vd-progress" in overview
        assert "vd-empty-state" in overview

        foundations = client.get("/foundations").text
        assert "vd-hero" in foundations
        assert "vd-feature-card" in foundations
        assert "vd-code-block" in foundations
        assert "vd-stats" in foundations
        assert "vd-aspect-ratio" in foundations
        assert "vd-link" in foundations
        assert "vd-list" in foundations
        assert "<article" in foundations
        assert "<figure" in foundations

        shell = client.get("/shell").text
        assert "vd-app-shell" in shell
        assert "vd-sidebar" in shell
        assert "vd-bottom-nav" in shell
        assert "vd-top-bar" in shell
        assert "vd-sidebar-toggle" in shell

        chat = client.get("/chat").text
        assert "vd-chatbox" in chat
        assert "vd-message-list" in chat
        assert "vd-chat-message--assistant" in chat
        assert "vd-composer" in chat

        auth = client.get("/auth").text
        assert "vd-user-badge" in auth
        assert "vd-auth-guard" in auth
        assert "Welcome Back" in auth
        assert "Create an Account" in auth

        forms = client.get("/forms").text
        assert "vd-search-input" in forms
        assert "vd-password-input" in forms
        assert "vd-combobox" in forms
        assert "vd-drop-zone" in forms

        navigation = client.get("/navigation").text
        assert "vd-tabs" in navigation
        assert "vd-dropdown-menu" in navigation
        assert "vd-accordion" in navigation
        assert "vd-pagination" in navigation

        advanced = client.get("/advanced").text
        assert "vd-toggle-group" in advanced
        assert "vd-segmented-control" in advanced
        assert "vd-command-panel" in advanced
        assert "vd-context-menu-panel" in advanced
        assert "vd-command-bar" in advanced

        data = client.get("/data").text
        assert "vd-enhanced-data-table" in data
        assert "vd-description-list" in data
        assert "vd-data-list" in data
        assert "vd-list-box" in data
        assert "vd-log-viewer" in data
        assert "<table" in data

        workspace = client.get("/workspace").text
        assert "vd-resizable-panels" in workspace
        assert "vd-tree-view" in workspace
        assert "vd-toolbar" in workspace
        assert "vd-menubar" in workspace
        assert "vd-master-detail" in workspace
        assert "vd-keyboard-shortcuts" in workspace

        system = client.get("/system").text
        assert "vd-runtime-status" in system
        assert "vd-agent-status" in system
        assert "vd-device-card" in system
        assert "vd-approval-card" in system
        assert "vd-world-entity-inspector" in system
        assert "vd-telemetry-panel" in system


_NON_VISUAL_PUBLIC_TYPES = {
    "Component",
    "Html",
    "UIEvent",
    "StyleAdapter",
    "NoopAdapter",
    "ThemePalette",
    "DismissLayer",
    "LayerManager",
    "Portal",
}


def test_component_lab_exercises_every_public_visual_component() -> None:
    source = Path("examples/web/component_lab/main.py").read_text()
    missing = [
        name
        for name in public_ui.__all__
        if name[:1].isupper()
        and name not in _NON_VISUAL_PUBLIC_TYPES
        and re.search(rf"\b{re.escape(name)}\s*\(", source) is None
    ]
    assert missing == []
