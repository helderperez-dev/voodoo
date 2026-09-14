"""Release gates for the Store-only default installation."""

from __future__ import annotations

import subprocess
import sys


def test_import_voodoo_does_not_require_aiosqlite() -> None:
    code = r"""
import importlib.abc
import sys

class BlockAioSQLite(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aiosqlite" or fullname.startswith("aiosqlite."):
            raise ImportError("aiosqlite intentionally blocked by release gate")
        return None

sys.meta_path.insert(0, BlockAioSQLite())
import voodoo
assert voodoo.Model is not None
assert voodoo.__version__
assert "aiosqlite" not in sys.modules
assert "voodoo.storage.database.sqlite" not in sys.modules
assert "voodoo.storage.events.sqlite" not in sys.modules
assert "voodoo.storage.queue.sqlite" not in sys.modules
assert "voodoo.storage.execution.sqlite" not in sys.modules
assert "voodoo.storage.scheduler.sqlite" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_runtime_startup_does_not_require_aiosqlite() -> None:
    code = r"""
import importlib.abc
import sys

class BlockAioSQLite(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aiosqlite" or fullname.startswith("aiosqlite."):
            raise ImportError("aiosqlite intentionally blocked by startup release gate")
        return None

sys.meta_path.insert(0, BlockAioSQLite())

from starlette.testclient import TestClient
from voodoo.core import create_app

with TestClient(create_app()) as client:
    assert client is not None

assert "aiosqlite" not in sys.modules
assert "voodoo.storage.scheduler.sqlite" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_public_model_module_has_no_sql_fallback_import() -> None:
    code = r"""
import sys
from voodoo import Model

assert Model.__module__ == "voodoo.data.store_facade"
assert "voodoo.data.base" not in sys.modules
assert "voodoo.data.model" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
