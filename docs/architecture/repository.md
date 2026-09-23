# Repository architecture

Voodoo's repository layout is part of its architecture. Physical ownership must
make the runtime model easier to understand rather than mirror the project's
history.

## Goals

1. A contributor should understand the major Voodoo domains from the directory
   tree without reading implementation details.
2. Public namespaces have semantic owners. Files are not placed at package root
   merely for convenience.
3. Internal dependencies point inward toward stable semantic contracts.
4. Tests mirror source ownership and distinguish unit, integration, end-to-end,
   contract and compatibility coverage.
5. Documentation and examples form a progressive developer journey.
6. Repository organization must not force artificial package boundaries.

## Canonical source domains

```text
src/voodoo/
├── core/             application facade, lifecycle, state and events
├── primitives/       foundational semantic value objects/contracts
├── runtime/          canonical execution and operational semantics
├── world/            entities, observations and operational world
├── edge/             physical/external participant boundary
├── protocol/         language-neutral/wire contracts
├── ai/               native AI compute, agents and tools
├── integrations/     MCP, provider SDK and OpenTelemetry integrations
├── observability/    framework-owned traces, metrics and telemetry state
├── storage/          infrastructure contracts and adapters
├── adapters/         provider registry and adapter plumbing
├── data/             Store-first application persistence/model API
├── ui/               application UI and reactive presentation
├── routing/          page/API routing
├── mesh/             realtime/event transport application surface
├── auth/             application credential/session APIs
├── security/         HTTP security and redaction
└── cli/              developer tooling
```

This is the Voodoo 3.x ownership model. Compatibility-only 2.x namespaces were
removed deliberately in 3.0 and must not be recreated as parallel semantic
owners. New top-level source domains require an explicit architecture decision.

## Dependency direction

The architectural center is:

```text
primitives / protocol
        ↑
world / core contracts
        ↑
runtime
        ↑
application surfaces (ui, data, auth, ai, edge)
        ↑
integrations / cli
```

Exceptions must be explicit architectural seams, not accidental circular
imports. Vendor SDKs must not become dependencies of the semantic core.

## Runtime internal ownership

The runtime may evolve toward grouped implementation domains while preserving
the public `voodoo.runtime` namespace:

```text
runtime/
├── execution/
├── reconciliation/
├── scheduling/
├── agency/
├── distributed/
└── inspection/
```

Moves into these groups require an import/dependency audit first. Voodoo 3.x
uses the grouped owners as canonical paths; removed 2.x compatibility re-exports
must not be restored unless a future version adopts an explicit compatibility
policy.

## Tests

Current ownership structure:

```text
tests/
├── unit/             mirrors src/voodoo semantic ownership
├── integration/      interactions across two or more domains
├── e2e/              developer/user journeys
├── contracts/        provider/protocol behavioral contracts
└── architecture/     repository and dependency invariants
```

Shared fixtures live in `tests/conftest.py`. A test belongs at repository root
only when it is genuinely repository-wide; new `test_*.py` files must not be
added directly under `tests/`.

## Documentation

Target structure:

```text
docs/
├── getting-started/
├── concepts/
├── guides/
├── reference/
├── architecture/
└── internals/
```

Root-level architecture documents remain concise entry points; detailed
architecture belongs under `docs/architecture/`.

## Examples

Target structure:

```text
examples/
├── basics/
├── web/
├── data/
├── ai/
├── adaptive/
├── distributed/
└── edge/
```

Examples are executable documentation and should progress from simple
application concepts to operational/adaptive systems.

## Package-root law

`voodoo.__init__` is the intentionally small 3.x application happy path, not a
catalog or compatibility facade. It exports only the common application
vocabulary defined by `docs/public-api-3.md`. A module at
`src/voodoo/<name>.py` must be a deliberate root-level application surface or
be moved under its semantic owner. Removed 2.x facades are forbidden by
architecture tests.

## Repository rules

- No vendor-specific SDK dependency in Core/Runtime/World/Primitives/Protocol.
- No `# noqa` suppressions to bypass architecture or lint failures.
- No duplicate execution authority.
- No public-import change without an explicit versioned API decision and documentation.
- Prefer small mechanical moves with green CI over a repository-wide big bang.
- Every new source domain must define its semantic owner and dependency
  direction.
