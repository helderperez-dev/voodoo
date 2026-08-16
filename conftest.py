"""Repository-root conftest.

Makes the ``src/`` layout importable for bare ``pytest`` runs (no install
required). CI and development use ``uv sync`` which installs the package
editable; this keeps direct ``python -m pytest`` working too.
"""

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
