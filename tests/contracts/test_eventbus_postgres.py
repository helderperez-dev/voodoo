"""PostgreSQL event bus contract tests (Sprint 7, Sprint 11).

Runs the shared ``EventBusContractTests`` against a real PostgreSQL server
when ``VOODOO_TEST_DATABASE_URL`` is set (CI provides one via a service
container). Skipped locally when no server is configured.
"""

import os
from typing import Any

import pytest

from tests.contracts.test_eventbus import EventBusContractTests

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_DATABASE_URL"),
    reason="VOODOO_TEST_DATABASE_URL not set (no PostgreSQL server available)",
)


@pytest.fixture
async def pg_url() -> str:
    url = os.environ["VOODOO_TEST_DATABASE_URL"]
    # Fresh events table per test so the replay/durability assertions are
    # deterministic.
    import psycopg

    with psycopg.connect(url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS events")
    return url


class TestPostgresEventBusContract(EventBusContractTests):
    @pytest.fixture(autouse=True)
    def setup_bus(self, pg_url) -> None:
        from voodoo.storage.events.postgres import PostgresEventStore

        self.bus = PostgresEventStore(pg_url)
        yield
        self.bus.close()


class TestPostgresEventBusDurability:
    """Durability tests mirroring the SQLite suite, on PostgreSQL."""

    async def test_events_survive_close_and_reopen(self, pg_url) -> None:
        from voodoo.storage.events.postgres import PostgresEventStore

        bus1 = PostgresEventStore(pg_url)
        bus1.publish("test.durable", {"data": "hello"})
        bus1.close()

        received = []

        def handler(event: dict[str, Any]) -> None:
            received.append(event)

        bus2 = PostgresEventStore(pg_url)
        bus2.subscribe("test.durable", handler)
        count = bus2.replay("test.durable", handler)
        bus2.close()

        assert count == 1
        assert len(received) == 1
        assert received[0]["payload"] == {"data": "hello"}

    async def test_correlation_ordering(self, pg_url) -> None:
        """Events replay in timestamp order with stable correlation ids."""
        from voodoo.storage.events.postgres import PostgresEventStore

        bus = PostgresEventStore(pg_url)
        bus.publish(
            "test.ordered",
            {"n": 1},
            correlation_id="c-1",
            source="app",
        )
        bus.publish(
            "test.ordered",
            {"n": 2},
            correlation_id="c-1",
            source="app",
        )
        seen = []

        def handler(event: dict[str, Any]) -> None:
            seen.append(event)

        count = bus.replay("test.ordered", handler)
        bus.close()

        assert count == 2
        assert [e["payload"]["n"] for e in seen] == [1, 2]
        assert all(e["correlation_id"] == "c-1" for e in seen)
