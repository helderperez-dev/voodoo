"""Fail CI when the full-package mypy error count regresses.

The production-critical boundary is checked strictly in CI. The remaining
package-wide errors are tracked by this ratchet until they can be removed
without hiding new type failures.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BASELINE = Path(__file__).with_name("mypy_error_baseline.txt")
ERROR_RE = re.compile(r"^.*: error: ")


def main() -> int:
    expected = int(BASELINE.read_text().strip())
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "src/voodoo", "--follow-imports=silent"],
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    actual = sum(bool(ERROR_RE.match(line)) for line in output.splitlines())
    if actual > expected:
        print(f"mypy regression: {actual} errors (baseline {expected})", file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    print(f"mypy ratchet passed: {actual} errors (baseline {expected})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
