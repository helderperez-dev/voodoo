"""Voodoo computational model.

The fundamental ontology from which all higher-level capabilities emerge:

    Entity      — anything that holds state (conceptual; represented via State)
    State       — durable system truth
    Intent      — what the system is trying to accomplish (an outcome)
    Capability  — explicit permission to produce an effect
    Effect      — a change caused outside pure computation

The runtime mechanism is Execution; its dimensions are Compute, Time,
Resource, and Constraint. AI is one form of Compute.

These are computational concepts, not application features.

    ENTITY → STATE → INTENT → CAPABILITY → EXECUTION → EFFECT → STATE
    TIME + CONSTRAINT surround the entire lifecycle.
    RESOURCE determines how execution should be performed.

The sophistication should be in the model, not in the API surface.
"""

from voodoo.primitives.capability import Capability
from voodoo.primitives.compute import ComputeKind, ComputeSpec
from voodoo.primitives.constraint import Constraint
from voodoo.primitives.effect import Effect, EffectStatus
from voodoo.primitives.intent import Intent, IntentStatus
from voodoo.primitives.resource import Resource
from voodoo.primitives.state import State
from voodoo.primitives.time import TimeSpec

__all__ = [
    "State",
    "Capability",
    "Intent",
    "IntentStatus",
    "Effect",
    "EffectStatus",
    "TimeSpec",
    "ComputeSpec",
    "ComputeKind",
    "Resource",
    "Constraint",
]
