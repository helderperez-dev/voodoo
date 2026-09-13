from __future__ import annotations

import pytest

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import (
    ApprovalRequired,
    CapabilityDenied,
    ExecutionContext,
    ExecutionEngine,
    PolicyDecision,
    PolicyEngine,
    PolicyResult,
    Resolution,
)
from voodoo.world import Entity, WorldModel


def test_policy_defaults_to_allow_after_capability_is_granted():
    policy = PolicyEngine()
    context = ExecutionContext(actor="agent:support", intent=Intent(name="read"))

    result = policy.evaluate("customer.read", context=context)

    assert result.decision is PolicyDecision.ALLOW


def test_deny_policy_overrides_granted_capability():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="payment.refund"))
    engine.capabilities.policy.register(
        lambda request: (
            PolicyResult(
                PolicyDecision.DENY,
                reason="support agents cannot issue this refund",
            )
            if request.actor == "agent:support"
            else None
        ),
        name="support-refund-boundary",
    )
    context = ExecutionContext(
        actor="agent:support",
        intent=Intent(name="refund").require("payment.refund"),
    )

    assert (
        engine.capabilities.resolve("payment.refund", context=context)
        is Resolution.DENIED
    )
    with pytest.raises(CapabilityDenied, match="support agents cannot issue"):
        engine.capabilities.authorize("payment.refund", context=context)


def test_world_aware_policy_can_require_approval():
    world = WorldModel()
    world.put_entity(Entity(type="order", id="order-42"))
    world.observe(
        "order-42",
        "refund.amount",
        130.0,
        source="billing",
    )

    policy = PolicyEngine(world=world)

    def refund_policy(request):
        if request.capability != "payment.refund" or request.world is None:
            return None
        amount = request.world.entity.get("refund.amount", 0)
        if amount > 50:
            return PolicyResult(
                PolicyDecision.REQUIRE_APPROVAL,
                reason=f"refund amount {amount} exceeds autonomous limit",
            )
        return PolicyDecision.ALLOW

    policy.register(refund_policy, name="refund-limit")
    context = ExecutionContext(
        actor="agent:support",
        intent=Intent(
            name="refund",
            params={"entity_id": "order-42"},
        ),
    )

    result = policy.evaluate("payment.refund", context=context)

    assert result.decision is PolicyDecision.REQUIRE_APPROVAL
    assert result.policy == "refund-limit"
    assert result.reason == "refund amount 130.0 exceeds autonomous limit"


def test_policy_target_can_come_from_execution_metadata():
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))
    world.observe("robot-1", "battery.level", 0.12, source="bms")
    policy = PolicyEngine(world=world)
    policy.register(
        lambda request: (
            PolicyDecision.DENY
            if request.world and request.world.entity.get("battery.level") < 0.2
            else None
        ),
        name="battery-safety",
    )
    context = ExecutionContext(actor="agent:operator", intent=Intent(name="move"))
    context.metadata["target_entity_id"] = "robot-1"

    result = policy.evaluate("motor.drive", context=context)

    assert result.decision is PolicyDecision.DENY
    assert result.policy == "battery-safety"


def test_deny_dominates_approval_and_allow():
    policy = PolicyEngine()
    policy.register(lambda request: PolicyDecision.ALLOW, name="allow")
    policy.register(
        lambda request: PolicyDecision.REQUIRE_APPROVAL,
        name="approval",
    )
    policy.register(lambda request: PolicyDecision.DENY, name="deny")

    result = policy.evaluate(
        "machine.start",
        context=ExecutionContext(actor="agent:operator", intent=Intent(name="start")),
    )

    assert result.decision is PolicyDecision.DENY
    assert result.policy == "deny"


@pytest.mark.asyncio
async def test_engine_turns_policy_approval_into_durable_wait_boundary():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="payment.refund"))
    engine.capabilities.policy.register(
        lambda request: PolicyResult(
            PolicyDecision.REQUIRE_APPROVAL,
            reason="refund requires human review",
        ),
        name="refund-review",
    )
    intent = Intent(name="refund").require("payment.refund")

    with pytest.raises(ApprovalRequired, match="refund requires human review"):
        await engine.execute(
            intent,
            lambda ctx: "should-not-run",
            actor="agent:support",
            capabilities=["payment.refund"],
        )

    execution = next(iter(engine.executions.values()))
    assert execution.status.value == "waiting"
    approval = engine.approvals.get(execution.id)
    assert approval is not None
    assert approval.capability == "payment.refund"
