import pytest
import asyncio
from voodoo.queue import queue, enqueue, start_workers, stop_workers

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
    
    # Allow workers to process the queue
    await asyncio.sleep(0.1)
    
    # Stop workers
    await stop_workers()
    
    assert "item1" in processed_items
    assert "item2" in processed_items
    assert "sync-item3" in processed_items
