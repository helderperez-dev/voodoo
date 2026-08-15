#!/usr/bin/env python
"""Voodoo micro-benchmarks.

Measures the Phase 0 baseline metrics from the implementation plan:
import time, app build time, SSR render time, and request latency.

Usage:
    uv run python scripts/benchmark.py           # human-readable table
    uv run python scripts/benchmark.py --json    # machine-readable JSON
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

# Point the framework at a throwaway database before any voodoo import reads config.
_TMP = tempfile.mkdtemp(prefix="voodoo-bench-")
os.environ.setdefault("VOODOO_DB_PATH", os.path.join(_TMP, "bench.db"))

IMPORT_SNIPPET = (
    "import time; t = time.perf_counter(); import voodoo; "
    "print((time.perf_counter() - t) * 1000)"
)


def bench_import_voodoo(runs: int = 5) -> float:
    """Median wall time (ms) to `import voodoo` in a fresh interpreter."""
    times = []
    for _ in range(runs):
        out = subprocess.run(
            [sys.executable, "-c", IMPORT_SNIPPET],
            capture_output=True,
            text=True,
            check=True,
        )
        times.append(float(out.stdout.strip().splitlines()[-1]))
    return statistics.median(times)


def bench_create_app(runs: int = 25) -> float:
    """Median time (ms) to build a Starlette app via create_app()."""
    from voodoo.core import create_app

    times = []
    for _ in range(runs):
        start = time.perf_counter()
        create_app(app_dir=os.path.join(_TMP, "no-such-app-dir"))
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def bench_render_page(runs: int = 200) -> float:
    """Median time (ms) for a full SSR render_page() of a small tree."""
    from voodoo.components import Card, Div, Heading, Text
    from voodoo.core import render_page

    tree = Card(Heading("Benchmark"), Text("hello world"), Div(Text("row")))
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        render_page(tree)
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def bench_request_latency(runs: int = 100) -> float:
    """Median latency (ms) for GET /openapi.json through the full middleware stack."""
    import logging

    from starlette.testclient import TestClient

    from voodoo.config import config
    from voodoo.core import create_app

    logging.getLogger("voodoo.telemetry").setLevel(logging.WARNING)
    config.security.rate_limit_requests = 10**6  # don't measure the rate limiter

    app = create_app(app_dir=os.path.join(_TMP, "no-such-app-dir"))
    with TestClient(app) as client:
        client.get("/openapi.json")  # warm up
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            response = client.get("/openapi.json")
            times.append((time.perf_counter() - start) * 1000)
            assert response.status_code == 200, response.status_code
    return statistics.median(times)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    results = {
        "import_voodoo_ms": bench_import_voodoo(),
        "create_app_ms": bench_create_app(),
        "render_page_ms": bench_render_page(),
        "request_latency_ms": bench_request_latency(),
    }
    results = {k: round(v, 3) for k, v in results.items()}

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\nVoodoo benchmarks (median)\n")
        print(f"  import voodoo       : {results['import_voodoo_ms']:>10.2f} ms")
        print(f"  create_app()        : {results['create_app_ms']:>10.2f} ms")
        print(f"  render_page() (SSR) : {results['render_page_ms']:>10.2f} ms")
        print(f"  GET /openapi.json   : {results['request_latency_ms']:>10.2f} ms")
        print()


if __name__ == "__main__":
    main()
