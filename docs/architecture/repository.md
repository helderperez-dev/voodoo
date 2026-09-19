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
├── core/             application facade and framework kernel
├── runtime/          execution, reconciliation, scheduling and agency
├── primitives/       shared semantic value objects/contracts
├── world/            entities, observations and operational world
├── protocol/         language-neutral/wire contracts
├── ui/               application UI and reactive presentation
├── data/             application persistence/model API
├── auth/             application authentication
├── ai/               AI compute, agents and tools
├── edge/             physical/external participants
├── integrations/     optional external-system adapters
├── observability/    telemetry and runtime inspection surfaces
├── cli/              developer tooling
└── _internal/        implementation details with no compatibility promise
```

This is a semantic target, not permission to move code blindly. Existing
public imports remain compatibility surface until a deliberate major-version
migration removes them.

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

Moves into these groups require an import/dependency audit first. Compatibility
re-exports are preferred to breaking import paths during the current release
line.

## Tests

Target structure:

```text
tests/
├── unit/             mirrors src/voodoo semantic ownership
├── integration/      interactions across two or more domains
├── e2e/              developer/user journeys
├── contracts/        provider/protocol behavioral contracts
├── compatibility/    intentionally preserved public/legacy behavior
└── fixtures/
```

A test belongs at repository root only when it is genuinely repository-wide.
New unit tests should not be added directly under `tests/`.

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

`voodoo.__init__` is a curated compatibility/application facade, not a catalog.
A module at `src/voodoo/<name>.py` must be either a deliberate public facade or
moved under its semantic owner. Historical facades may remain temporarily to
preserve compatibility, but new ones require an explicit API decision.

## Repository rules

- No vendor-specific SDK dependency in Core/Runtime/World/Primitives/Protocol.
- No `# noqa` suppressions to bypass architecture or lint failures.
- No duplicate execution authority.
- No filesystem move that silently changes a documented public import.
- Prefer small mechanical moves with green CI over a repository-wide big bang.
- Every new source domain must define its semantic owner and dependency
  direction.
