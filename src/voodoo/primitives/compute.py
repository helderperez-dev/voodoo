"""Compute — the act of performing computation.

Compute is NOT synonymous with CPU, server, container, Lambda, GPU, LLM,
OpenAI, or cloud function. Those are implementations.

A Compute operation may execute:
    deterministic code, probabilistic computation, machine learning,
    reasoning, inference, simulation, search, optimization,
    symbolic computation, human-assisted computation

AI is simply one form of Compute. This is one of the most important
architectural decisions in Voodoo. Do not create an "AI framework" —
create Compute. AI becomes a capability of Compute.

Possible execution environments:
    local CPU, local GPU, NPU, browser, mobile device, edge device,
    private server, cloud, specialized accelerator, remote model
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from voodoo.primitives.constraint import Constraint
from voodoo.primitives.resource import Resource


class ComputeKind(StrEnum):
    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"
    REASONING = "reasoning"
    INFERENCE = "inference"
    SEARCH = "search"
    OPTIMIZATION = "optimization"
    SIMULATION = "simulation"
    SYMBOLIC = "symbolic"
    HUMAN = "human"


class ComputeSpec(BaseModel):
    """A specification for computation.

    Semantics:
        kind        — what type of computation
        provider    — which implementation ("openai", "local", "edge", etc.)
        model       — specific model identifier
        constraints — execution constraints
        resources   — resource requirements/consumption
    """

    kind: ComputeKind = ComputeKind.DETERMINISTIC
    provider: str | None = None
    model: str | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    resources: Resource | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    # -- factories ---------------------------------------------------------

    @staticmethod
    def deterministic() -> ComputeSpec:
        """Create a deterministic computation spec."""
        return ComputeSpec(kind=ComputeKind.DETERMINISTIC)

    @staticmethod
    def reasoning(provider: str | None = None, model: str | None = None) -> ComputeSpec:
        """Create a reasoning computation spec (e.g. LLM)."""
        return ComputeSpec(kind=ComputeKind.REASONING, provider=provider, model=model)

    @staticmethod
    def inference(provider: str | None = None, model: str | None = None) -> ComputeSpec:
        """Create an inference computation spec."""
        return ComputeSpec(kind=ComputeKind.INFERENCE, provider=provider, model=model)

    @staticmethod
    def human() -> ComputeSpec:
        """Create a human-assisted computation spec."""
        return ComputeSpec(kind=ComputeKind.HUMAN)

    # -- composition -------------------------------------------------------

    def with_provider(self, provider: str, model: str | None = None) -> ComputeSpec:
        """Set the provider. Returns self for chaining."""
        self.provider = provider
        if model is not None:
            self.model = model
        return self

    def constrain(self, constraint: Constraint) -> ComputeSpec:
        """Add a constraint. Returns self for chaining."""
        self.constraints.append(constraint)
        return self

    def with_resources(self, resources: Resource) -> ComputeSpec:
        """Set resource requirements. Returns self for chaining."""
        self.resources = resources
        return self

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description."""
        return {
            "kind": self.kind.value,
            "provider": self.provider,
            "model": self.model,
            "constraint_count": len(self.constraints),
            "has_resources": self.resources is not None,
            "params": self.params,
        }
