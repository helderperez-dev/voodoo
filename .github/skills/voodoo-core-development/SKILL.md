---
name: voodoo-core-development
description: Develop and review the Voodoo Framework core while preserving Runtime authority, Store ownership, canonical execution semantics, native adapter boundaries, public API discipline, and release gates. Use when changing Runtime, Model internals, execution, adapters, Store integration, agents, framework architecture, CI, tests, or releases.
---

# Voodoo Core Development

Use this skill for framework implementation work.

## Non-negotiable invariants

1. One canonical Runtime execution lifecycle.
2. Runtime owns semantics and authority.
3. Store owns durable mechanics.
4. AI is Compute.
5. Effect != Observation.
6. One Runtime process owns one Store writer.
7. Prefer native Store primitives over compatibility storage.
8. Local-first by default.
9. Never claim distributed guarantees not implemented.
10. Keep the public API smaller than the implementation.

Read [architecture.md](references/architecture.md), [binding.md](references/binding.md), and [release-gates.md](references/release-gates.md) before substantial subsystem work.

## Core change procedure

Before implementing:

1. identify the architectural owner;
2. inspect current implementation and tests;
3. verify whether Store already exposes a native primitive;
4. verify exact Python binding signatures when consuming Store;
5. preserve canonical execution semantics;
6. avoid compatibility shims unless a real external user requires them;
7. test both internal behavior and public/runtime seams;
8. update docs and skills when public semantics change.

Temporary Git pins to an unpublished Store candidate are acceptable on validation branches only. They must not remain when a Framework PR merges.
