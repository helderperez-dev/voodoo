"""Acceptance coverage for the public Component Lab."""

from __future__ import annotations

import runpy

from starlette.testclient import TestClient


def test_component_lab_renders_all_primary_surfaces() -> None:
    namespace = runpy.run_path(
        "examples/web/component_lab/main.py",
        run_name="component_lab_acceptance",
    )

    with TestClient(namespace["app"]) as client:
        for path in ("/", "/forms", "/navigation", "/advanced", "/data", "/workspace", "/system", "/feedback"):
            response = client.get(path)
            assert response.status_code == 200, response.text
            assert "Component Lab" in response.text
            assert "vd-" in response.text

        overview = client.get("/").text
        assert "vd-button--primary" in overview
        assert "vd-card" in overview
        assert "vd-progress" in overview
        assert "vd-empty-state" in overview

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

        data = client.get("/data").text
        assert "vd-enhanced-data-table" in data
        assert "vd-description-list" in data
        assert "vd-data-list" in data
        assert "vd-list-box" in data
        assert "vd-log-viewer" in data

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
