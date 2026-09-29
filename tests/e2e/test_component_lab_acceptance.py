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
        for path in ("/", "/forms", "/navigation", "/feedback"):
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
