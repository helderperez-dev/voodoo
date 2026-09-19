# Voodoo 3.0 public API law

Sprint 27 defines the canonical import model for the next major release while
preserving 2.x source compatibility.

## Rule

The package root is a **2.x compatibility facade**, not the long-term catalog of
every Voodoo type. New subsystem APIs must live in the namespace that owns their
semantics.

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

## 2.x compatibility policy

Existing imports from `voodoo` continue to resolve during the 2.x line. Sprint
27 does not silently break applications merely to make `__all__` smaller.
Catalog-style exports that already exist at the package root are compatibility
surface; documentation and new examples should import them from their defining
namespace.

The actual breaking contraction of the package-root namespace, if performed,
is a 3.0 release operation and must include a migration table and a deliberate
update to `tests/test_contract_api.py`.

## Laws for new public APIs

1. Do not add a top-level export just because a class is useful.
2. A primitive may be top-level only when it is part of the common application
   vocabulary used across subsystems.
3. Component catalogs belong to `voodoo.ui`.
4. Execution/agency internals belong to `voodoo.runtime`.
5. World concepts belong to `voodoo.world`.
6. Device concepts belong to `voodoo.edge`.
7. Wire schemas belong to `voodoo.protocol`.
8. Existing compatibility imports must either keep working or fail only in a
   documented major-version migration.

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
