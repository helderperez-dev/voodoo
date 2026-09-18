"""Optional application layout conventions.

Conventions provide discoverability, never hidden registration semantics.
Explicit Runtime registration remains authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ApplicationLayout:
    root: Path
    pages: Path | None = None
    api: Path | None = None
    agents: Path | None = None
    workers: Path | None = None
    goals: Path | None = None
    workflows: Path | None = None
    models: Path | None = None
    capabilities: Path | None = None
    effects: Path | None = None
    public: Path | None = None


def discover_layout(root: str | Path = ".") -> ApplicationLayout:
    base = Path(root)
    app = base / "app"

    def existing(path: Path) -> Path | None:
        return path if path.exists() else None

    return ApplicationLayout(
        root=base,
        pages=existing(app / "pages"),
        api=existing(app / "api"),
        agents=existing(app / "agents"),
        workers=existing(app / "workers"),
        goals=existing(app / "goals"),
        workflows=existing(app / "workflows"),
        models=existing(base / "models"),
        capabilities=existing(base / "capabilities"),
        effects=existing(base / "effects"),
        public=existing(base / "public"),
    )


__all__ = ["ApplicationLayout", "discover_layout"]
