# Voodoo 3.0 public API law

Voodoo 3.0 defines one canonical import model and intentionally removes
compatibility-only paths from the 2.x line.

## Rule

The package root is the **small application happy path**, not a catalog of every
Voodoo type. Subsystem APIs live in the namespace that owns their semantics.

Canonical imports for 3.0 are:

```python
# Application surface
from voodoo import App, page, state, Agent, tool, Model, task

# UI catalog
from voodoo.ui import Button, Card, Stack, DataTable, RuntimeStatus

# Runtime / agency
from voodoo.runtime import (
    ExecutionEngine,
    Planner,
    AdaptiveSupervisor,
    Goal,
    GoalRuntime,
)

# Operational world
from voodoo.world import Entity, Relationship, Observation, WorldModel

# Physical/external participants
from voodoo.edge import DeviceGateway, WorldAwareDeviceGateway

# Language-neutral contracts
from voodoo.protocol import Execution, WorldSnapshot, RemoteExecutionRequest
```

## 3.0 package-root contraction

The 3.0 branch performs the major-version break deliberately. The package root
exports exactly the common application vocabulary:

```python
from voodoo import Agent, App, Model, page, state, task, tool
```

Catalog-style exports and deprecation shims are removed rather than carried
forward. Import advanced APIs from their semantic owner. The exact root contract
is pinned by `tests/integration/test_contract_api.py`.

## Laws for new public APIs

1. Do not add a top-level export just because a class is useful.
2. A primitive may be top-level only when it is part of the common application
   vocabulary used across subsystems.
3. Component catalogs belong to `voodoo.ui`.
4. Execution/agency internals belong to `voodoo.runtime`.
5. World concepts belong to `voodoo.world`.
6. Device concepts belong to `voodoo.edge`.
7. Wire schemas belong to `voodoo.protocol`.
8. Compatibility-only paths removed in 3.0 must not be reintroduced; migration
   belongs in documentation, not runtime shims.

## Why this matters

Voodoo's architecture is intentionally broad; its developer surface should not
mirror that breadth one class at a time. The runtime may grow while the happy
path stays small.


## Adaptive application happy path

The canonical `App` owns one canonical Runtime. Application code should declare observed facts, desired state, and executable capabilities through `App`; graph, reconciliation, scheduling, placement, and execution remain runtime internals unless an advanced integration explicitly needs them.

```python
from voodoo import App
from voodoo.primitives import Intent

app = App()
conversion = app.observation("business", "conversion")


@app.goal(
    "grow",
    observes=(conversion,),
    target_entity_id="business",
    propose=lambda goal, world: Intent(name="conversion.adjust"),
)
def growth(world):
    return world is not None and world.entity.properties.get("conversion", 0) >= 0.10


@app.capability("conversion.adjust")
async def improve(ctx):
    return {"accepted": True}
```

Public API laws for adaptive applications:

1. `App` is the application facade; `Runtime` is its canonical execution and reconciliation machine, not a competing application abstraction.
2. `app.observation(...)` returns a handle; the handle type is scoped to `voodoo.core` and is not a package-root export.
3. `@app.goal(...)` constructs the same canonical `Goal` used by the advanced runtime API. It is syntax, not a second goal model.
4. `@app.capability(...)` binds local compute to a capability in the same Runtime. Explicit `Capability(...)` registration remains available when constraints, delegation, or policy metadata are required.
5. Observation handles may be passed directly to `observes`; application code does not need Application Graph resource IDs.
6. An Observation may trigger a bounded cycle. Effects do not become Observations implicitly, and a cycle never recursively runs forever.
7. Advanced runtime primitives remain under `voodoo.runtime`; they are not promoted to the package root merely because they are useful.


## 3.0 clean-break migration status

The 3.0 architecture branch removes compatibility-only namespaces as their
implementation is absorbed by the canonical semantic owner. The first closed
slice is Runtime scheduling:

| Removed 2.x path | 3.0 canonical path |
| --- | --- |
| `voodoo.workers.task` | `from voodoo import task` |
| `voodoo.workers.TaskError` | `voodoo.runtime.scheduling.TaskError` |
| `voodoo.queue.enqueue` | `voodoo.runtime.scheduling.enqueue` |
| `voodoo.queue.start_workers` | `voodoo.runtime.scheduling.start_workers` |
| `voodoo.queue.stop_workers` | `voodoo.runtime.scheduling.stop_workers` |

`task` remains in the package-root happy path intentionally. Worker orchestration
is Runtime scheduling implementation and no longer owns a parallel top-level
namespace.

### Runtime scheduling module contraction

The 3.0 branch also removes the flat Runtime scheduling modules. Import advanced
scheduling types from `voodoo.runtime` when they are part of the supported
Runtime API, or from their canonical implementation domain when extending the
framework:

| Removed module | Canonical owner |
| --- | --- |
| `voodoo.runtime.dispatch` | `voodoo.runtime.scheduling.dispatch` |
| `voodoo.runtime.handoff` | `voodoo.runtime.scheduling.handoff` |
| `voodoo.runtime.scheduler` | `voodoo.runtime.scheduling` |
| `voodoo.runtime.work_scheduler` | `voodoo.runtime.scheduling.work` |


### Mesh versus distributed Runtime ownership

`voodoo.mesh` remains the event/transport-facing application surface. The 3.0
branch removes semantic compatibility modules beneath it: participant identity,
remote execution authority, and replay/idempotency are owned by
`voodoo.runtime.distributed`.

| Removed Mesh module | Canonical owner |
| --- | --- |
| `voodoo.mesh.auth` | `voodoo.runtime.distributed.auth` |
| `voodoo.mesh.remote` | `voodoo.runtime.distributed.remote` |
| `voodoo.mesh.replay` | `voodoo.runtime.distributed.replay` |


### Runtime semantic module contraction

| Removed Runtime module | Canonical owner |
| --- | --- |
| `voodoo.runtime.adaptive` | `voodoo.runtime.agency` |
| `voodoo.runtime.dashboard` | `voodoo.runtime.inspection` |
| `voodoo.runtime.engine` | `voodoo.runtime.execution.engine` |
| `voodoo.runtime.fabric` | `voodoo.runtime.distributed` |
| `voodoo.runtime.goal` | `voodoo.runtime.agency` |
| `voodoo.runtime.goal_store` | `voodoo.runtime.agency` |
| `voodoo.runtime.lineage` | `voodoo.runtime.inspection` |
| `voodoo.runtime.membership` | `voodoo.runtime.distributed` |
| `voodoo.runtime.reconcile` | `voodoo.runtime.reconciliation` |
| `voodoo.runtime.world_execution` | `voodoo.runtime.execution.world` |

### Removed compatibility namespaces

| Removed 2.x path | 3.0 canonical path |
| --- | --- |
| `voodoo.telemetry` | `voodoo.observability` |
| `voodoo.telemetry.otlp` | `voodoo.integrations.otel` |
| `voodoo.mcp` | `voodoo.integrations.mcp` |
| `voodoo.tools` | `voodoo.ai.tools` |
| `voodoo.agent` | `voodoo.ai.agent` |
| `voodoo.api` | `voodoo.routing.api` |
| `voodoo.theme` | `voodoo.ui.styles.theme` |

These paths are removed physically in 3.0. There are no import-time compatibility
redirects, warning shims, or duplicate semantic owners.
