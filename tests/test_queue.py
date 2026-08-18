import asyncio

import pytest

from voodoo.queue import enqueue, queue, start_workers, stop_workers

processed_items = []


@queue("test_queue")
async def process_item(payload):
    processed_items.append(payload)


@queue("sync_queue")
def process_sync_item(payload):
    processed_items.append(f"sync-{payload}")


@pytest.mark.asyncio
async def test_queue_workers():
    processed_items.clear()

    # Enqueue items
    await enqueue("test_queue", "item1")
    await enqueue("test_queue", "item2")
    await enqueue("sync_queue", "item3")

    # Start workers
    await start_workers()

    # Wait (with a generous deadline) for all three items to be processed —
    # polling is deterministic, unlike a fixed sleep which flakes under load.
    for _ in range(100):
        if {"item1", "item2", "sync-item3"} <= set(processed_items):
            break
        await asyncio.sleep(0.05)

    # Stop workers
    await stop_workers()

    assert "item1" in processed_items
    assert "item2" in processed_items
    assert "sync-item3" in processed_items
