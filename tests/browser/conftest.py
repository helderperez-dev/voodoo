"""Browser-test fixture isolation.

The repository-wide database cleanup fixture is async and intentionally wraps
normal Python tests. Sync Playwright cannot run while that fixture's event loop
is active, and browser acceptance does not touch the database layer. Shadow the
fixture locally so browser tests stay synchronous without weakening cleanup for
the rest of the suite.
"""

import pytest


@pytest.fixture(autouse=True)
def _close_db_after_test():
    yield
