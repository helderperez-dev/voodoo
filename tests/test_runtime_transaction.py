"""Sprint 28.11 acceptance for the local cross-domain atomic boundary."""

from __future__ import annotations

import json

import pytest

from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store
from voodoo.runtime.transaction import OutboxMessage, RuntimeTransaction, transaction


@pytest.fixture
def runtime_store(tmp_path):
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "application.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        yield runtime
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_transaction_commits_collection_state_and_outbox_atomically(runtime_store) -> None:
    native = runtime_store.provider.native
    native.create_collection(b"orders")
    message = OutboxMessage(
        id="order-created-42",
        topic="order.created",
        payload={"order_id": "42"},
    )

    with transaction() as tx:
        tx.upsert_record(b"orders", b"42", b'{"status":"created"}')
        tx.stage_outbox(message)

    record = native.get_record(b"orders", b"42")
    assert record is not None
    assert bytes(record[1]) == b'{"status":"created"}'
    raw = native.get(b"runtime:outbox:pending:order-created-42")
    assert raw is not None
    envelope = json.loads(bytes(raw))
    assert envelope["topic"] == "order.created"
    assert envelope["payload"] == {"order_id": "42"}


def test_transaction_rolls_back_state_and_outbox_together(runtime_store) -> None:
    native = runtime_store.provider.native
    native.create_collection(b"orders")

    with pytest.raises(RuntimeError, match="abort"):
        with RuntimeTransaction() as tx:
            tx.upsert_record(b"orders", b"99", b'{"status":"created"}')
            tx.stage_outbox(
                OutboxMessage(
                    id="order-created-99",
                    topic="order.created",
                    payload={"order_id": "99"},
                )
            )
            raise RuntimeError("abort")

    assert native.get_record(b"orders", b"99") is None
    assert native.get(b"runtime:outbox:pending:order-created-99") is None


def test_transaction_reads_its_own_staged_kv_write(runtime_store) -> None:
    with transaction() as tx:
        tx.put(b"runtime:test:key", b"value")
        assert tx.get(b"runtime:test:key") == b"value"


def test_transaction_rejects_unstarted_runtime_store(tmp_path) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "closed.vstore"))
    with pytest.raises(Exception, match="started"):
        RuntimeTransaction(runtime)
