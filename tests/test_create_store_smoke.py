"""Fresh-project smoke test for the official ``voodoo create`` template."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from voodoo.cli.create import _MAIN_PY


def _run(project: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )


def test_generated_project_boots_creates_store_and_reopens_data(tmp_path: Path) -> None:
    project = tmp_path / "generated"
    project.mkdir()
    (project / "app").mkdir()
    (project / ".voodoo").mkdir()
    (project / "main.py").write_text(_MAIN_PY.format(name="generated"))

    first = _run(
        project,
        """
import runpy
from starlette.testclient import TestClient
ns = runpy.run_path('main.py', run_name='generated_app')
with TestClient(ns['app']) as client:
    response = client.get('/')
    assert response.status_code == 200, response.text
""",
    )
    assert first.returncode == 0, first.stderr

    store_path = project / ".voodoo" / "application.vstore"
    assert store_path.exists()
    assert store_path.stat().st_size > 0

    second = _run(
        project,
        """
import asyncio
import runpy
from starlette.testclient import TestClient
ns = runpy.run_path('main.py', run_name='generated_app')
with TestClient(ns['app']):
    count = asyncio.run(ns['Counter'].count())
    assert count == 1, count
""",
    )
    assert second.returncode == 0, second.stderr
