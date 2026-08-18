"""Verify Sprint 9 acceptance criteria:

Switching `queue: sqlite` -> `queue: memory` in `voodoo.yaml` changes behavior
with zero application-code edits, verified by running the same app against two
providers.
"""

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

import voodoo.workers.queue as workers_queue
from voodoo.adapters.capabilities import CapabilityError
from voodoo.config import get_config


@pytest.mark.asyncio
async def test_queue_provider_switching_via_config():
    """Verify switching queue provider via config dynamically changes the active backend."""
    cfg_module = sys.modules["voodoo.config"]
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_yaml = Path(tmpdir) / "voodoo_sqlite.yaml"
        with open(sqlite_yaml, "w") as f:
            yaml.dump(
                {
                    "queue": {"provider": "sqlite"},
                    "database": {"provider": "sqlite", "path": ":memory:"},
                },
                f,
            )

        memory_yaml = Path(tmpdir) / "voodoo_memory.yaml"
        with open(memory_yaml, "w") as f:
            yaml.dump(
                {
                    "queue": {"provider": "memory"},
                },
                f,
            )

        # 1. Run app against sqlite queue config
        cfg_sqlite = get_config(str(sqlite_yaml))
        assert cfg_sqlite.queue.provider == "sqlite"

        # Reset global queue
        workers_queue._queue = None
        orig_get_config = cfg_module.get_config
        try:
            cfg_module.get_config = lambda *args, **kwargs: cfg_sqlite
            q_sqlite = await workers_queue._get_queue()
            assert q_sqlite.capabilities().durable is True
            assert q_sqlite.capabilities().delayed_delivery is True

            # 2. Switch to memory queue config without code changes
            cfg_memory = get_config(str(memory_yaml))
            workers_queue._queue = None
            cfg_module.get_config = lambda *args, **kwargs: cfg_memory
            q_memory = await workers_queue._get_queue()
            assert q_memory.capabilities().durable is False
            assert q_memory.capabilities().delayed_delivery is False

            # Enqueue with delay on memory queue raises CapabilityError (Sprint 8 negotiation)
            with pytest.raises(CapabilityError):
                await q_memory.enqueue("test_type", {}, delay=10.0)

        finally:
            workers_queue._queue = None
            cfg_module.get_config = orig_get_config
