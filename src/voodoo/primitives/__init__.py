"""Voodoo architectural primitives.

The fundamental computational model from which all higher-level
framework capabilities emerge:

    State       — durable system truth
    Capability  — explicit permission to act
    Intent      — what the system is trying to accomplish
    Effect      — a change caused outside pure computation
    Time        — first-class temporal concept
    Compute     — the act of performing computation
    Resource    — something consumed or depended upon
    Constraint  — what the system must or must not do

These are architectural primitives, not application features.

    STATE → INTENT → CAPABILITY → COMPUTE → EFFECT → STATE
    TIME + CONSTRAINTS surround the entire lifecycle.
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
