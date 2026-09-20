"""Tests for the Voodoo architectural primitives."""

from datetime import UTC, datetime, timedelta

import pytest

from voodoo.primitives import (
    Capability,
    ComputeKind,
    ComputeSpec,
    Constraint,
    Effect,
    EffectStatus,
    Intent,
    IntentStatus,
    Resource,
    State,
    TimeSpec,
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TestState:
    def test_create_with_defaults(self):
        s = State(kind="user", data={"name": "Ada"})
        assert s.kind == "user"
        assert s.data == {"name": "Ada"}
        assert s.version == 1
        assert s.id  # auto-generated
        assert s.created_at
        assert s.updated_at

    def test_mutate_increments_version(self):
        s = State(kind="user", data={"name": "Ada"})
        s2 = s.mutate(name="Grace")
        assert s2.version == 2
        assert s2.data["name"] == "Grace"
        assert s.version == 1  # original unchanged

    def test_checkpoint_and_restore(self):
        s = State(kind="user", data={"name": "Ada"}, owner="system")
        cp = s.checkpoint()
        restored = State.restore(cp)
        assert restored.id == s.id
        assert restored.kind == s.kind
        assert restored.data == s.data
        assert restored.owner == s.owner

    def test_expire_in(self):
        s = State(kind="session")
        s2 = s.expire_in(3600)
        assert s2.expires_at is not None
        assert s2.expired is False
        assert s2.valid is True

    def test_expired_state(self):
        past = datetime.now(UTC) - timedelta(seconds=1)
        s = State(kind="session", expires_at=past)
        assert s.expired is True
        assert s.valid is False

    def test_describe(self):
        s = State(kind="user", data={"name": "Ada", "age": 30})
        d = s.describe()
        assert d["kind"] == "user"
        assert d["version"] == 1
        assert d["field_count"] == 2


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------


class TestCapability:
    def test_create(self):
        cap = Capability(name="email.send")
        assert cap.name == "email.send"
        assert cap.valid is True
        assert cap.revoked is False
        assert cap.expired is False

    def test_revoke(self):
        cap = Capability(name="email.send")
        cap.revoke()
        assert cap.valid is False
        assert cap.revoked is True

    def test_timed_capability(self):
        cap = Capability.timed("payment.execute", expires_in=0.01)
        assert cap.expires_at is not None
        assert cap.valid is True

    def test_scoped_capability(self):
        cap = Capability.scoped("database.read", resource="customer:123")
        assert cap.scope == "customer:123"

    def test_delegate(self):
        cap = Capability(name="email.send", issued_by="admin")
        delegated = cap.delegate("agent:456")
        assert delegated.delegate_to == "agent:456"
        assert delegated.name == "email.send"
        assert delegated.issued_by == "admin"

    def test_delegate_with_constraints(self):
        cap = Capability(name="payment.execute", constraints={"max_amount": 100})
        delegated = cap.delegate("agent:456", max_amount=50)
        assert delegated.constraints["max_amount"] == 50

    def test_describe(self):
        cap = Capability(name="email.send", scope="user:123")
        d = cap.describe()
        assert d["name"] == "email.send"
        assert d["scope"] == "user:123"
        assert d["valid"] is True


# ---------------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------------


class TestIntent:
    def test_create(self):
        intent = Intent(name="send_invoice", params={"to": "client@example.com"})
        assert intent.status == IntentStatus.CREATED
        assert intent.active is True
        assert intent.finished is False

    def test_lifecycle(self):
        intent = Intent(name="process_order")
        intent.queue()
        assert intent.status == IntentStatus.QUEUED
        intent.evaluate()
        assert intent.status == IntentStatus.EVALUATING
        intent.execute()
        assert intent.status == IntentStatus.EXECUTING
        intent.pause()
        assert intent.status == IntentStatus.PAUSED
        intent.resume()
        assert intent.status == IntentStatus.EXECUTING
        intent.complete(result={"order_id": "ord_123"})
        assert intent.status == IntentStatus.COMPLETED
        assert intent.result == {"order_id": "ord_123"}
        assert intent.finished is True

    def test_reject(self):
        intent = Intent(name="process_order")
        intent.reject(reason="insufficient funds")
        assert intent.status == IntentStatus.REJECTED
        assert intent.error == "insufficient funds"

    def test_cancel(self):
        intent = Intent(name="process_order")
        intent.cancel()
        assert intent.status == IntentStatus.CANCELLED

    def test_require_capability(self):
        intent = Intent(name="send_invoice")
        intent.require("email.send").require("payment.execute")
        assert "email.send" in intent.requires
        assert "payment.execute" in intent.requires

    def test_constrain(self):
        intent = Intent(name="send_invoice")
        c = Constraint.cost(maximum=0.10)
        intent.constrain(c)
        assert len(intent.constraints) == 1
        assert intent.constraints[0].kind == "cost"

    def test_with_deadline(self):
        intent = Intent(name="send_invoice")
        intent.with_deadline(3600)
        assert intent.deadline is not None
        assert intent.expired is False

    def test_add_effect(self):
        intent = Intent(name="send_invoice")
        intent.add_effect("effect_123")
        assert "effect_123" in intent.effect_ids

    def test_describe(self):
        intent = Intent(name="send_invoice", requires=["email.send"])
        d = intent.describe()
        assert d["name"] == "send_invoice"
        assert d["status"] == "created"
        assert d["requires"] == ["email.send"]


# ---------------------------------------------------------------------------
# Effect
# ---------------------------------------------------------------------------


class TestEffect:
    def test_create(self):
        effect = Effect(
            name="send_email", intent_id="int_123", capability_name="email.send"
        )
        assert effect.status == EffectStatus.PENDING
        assert effect.pending is True
        assert effect.reversible is False
        assert effect.idempotent is False

    def test_succeed(self):
        effect = Effect(name="send_email")
        effect.mark_succeeded(result={"message_id": "msg_123"})
        assert effect.succeeded is True
        assert effect.completed is True
        assert effect.executed_at is not None

    def test_fail(self):
        effect = Effect(name="send_email")
        effect.mark_failed("SMTP timeout")
        assert effect.failed is True
        assert effect.completed is True
        assert effect.error == "SMTP timeout"

    def test_rollback_requires_reversible(self):
        effect = Effect(name="send_email", reversible=False)
        with pytest.raises(ValueError, match="not reversible"):
            effect.mark_rolled_back()

    def test_rollback_succeeds_when_reversible(self):
        effect = Effect(name="write_record", reversible=True)
        effect.mark_succeeded()
        effect.mark_rolled_back()
        assert effect.status == EffectStatus.ROLLED_BACK

    def test_describe(self):
        effect = Effect(name="send_email", reversible=True, idempotent=True)
        d = effect.describe()
        assert d["name"] == "send_email"
        assert d["reversible"] is True
        assert d["idempotent"] is True


# ---------------------------------------------------------------------------
# Constraint
# ---------------------------------------------------------------------------


class TestConstraint:
    def test_cost_constraint(self):
        c = Constraint.cost(maximum=0.10)
        assert c.kind == "cost"
        assert c.evaluate(0.05) is True
        assert c.evaluate(0.15) is False

    def test_latency_constraint(self):
        c = Constraint.latency(maximum_ms=100)
        assert c.evaluate(50) is True
        assert c.evaluate(150) is False

    def test_locality_constraint(self):
        c = Constraint.locality(must_be="local")
        assert c.evaluate("local") is True
        assert c.evaluate("cloud") is False

    def test_approval_required(self):
        c = Constraint.approval_required()
        assert c.evaluate(True) is True
        assert c.evaluate(False) is False

    def test_max_amount(self):
        c = Constraint.max_amount(100)
        assert c.evaluate(50) is True
        assert c.evaluate(100) is True  # <=
        assert c.evaluate(150) is False

    def test_evaluate_type_error(self):
        c = Constraint(kind="cost", operator="<", value=0.10)
        # Type mismatch should return False, not raise
        assert c.evaluate("not a number") is False

    def test_unknown_operator(self):
        c = Constraint(kind="cost", operator="~=", value=0.10)
        with pytest.raises(ValueError, match="Unknown operator"):
            c.evaluate(0.05)

    def test_describe(self):
        c = Constraint.cost(maximum=0.10)
        d = c.describe()
        assert d["kind"] == "cost"
        assert d["value"] == 0.10


# ---------------------------------------------------------------------------
# TimeSpec
# ---------------------------------------------------------------------------


class TestTimeSpec:
    def test_with_deadline(self):
        t = TimeSpec.with_deadline(3600)
        assert t.deadline is not None
        assert t.expired is False
        assert t.remaining > 3599

    def test_with_expiration(self):
        t = TimeSpec.with_expiration(0.01)
        assert t.expires_at is not None

    def test_with_retry(self):
        t = TimeSpec.with_retry(retry_after=30, max_retries=3)
        assert t.retry_after == 30
        assert t.max_retries == 3

    def test_with_interval(self):
        t = TimeSpec.with_interval(60)
        assert t.interval == 60

    def test_deadline_passed(self):
        past = datetime.now(UTC) - timedelta(seconds=1)
        t = TimeSpec(deadline=past)
        assert t.deadline_passed is True

    def test_expired(self):
        past = datetime.now(UTC) - timedelta(seconds=1)
        t = TimeSpec(expires_at=past)
        assert t.expired is True

    def test_no_deadline(self):
        t = TimeSpec()
        assert t.remaining is None
        assert t.expired is False

    def test_describe(self):
        t = TimeSpec.with_deadline(3600)
        d = t.describe()
        assert d["has_deadline"] is True
        assert d["deadline_passed"] is False


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------


class TestComputeSpec:
    def test_deterministic(self):
        c = ComputeSpec.deterministic()
        assert c.kind == ComputeKind.DETERMINISTIC
        assert c.provider is None

    def test_reasoning(self):
        c = ComputeSpec.reasoning(provider="openai", model="gpt-4o")
        assert c.kind == ComputeKind.REASONING
        assert c.provider == "openai"
        assert c.model == "gpt-4o"

    def test_inference(self):
        c = ComputeSpec.inference(provider="local", model="llama-3")
        assert c.kind == ComputeKind.INFERENCE

    def test_human(self):
        c = ComputeSpec.human()
        assert c.kind == ComputeKind.HUMAN

    def test_chaining(self):
        c = (
            ComputeSpec.reasoning()
            .with_provider("anthropic", "claude-3")
            .constrain(Constraint.cost(maximum=0.05))
        )
        assert c.provider == "anthropic"
        assert c.model == "claude-3"
        assert len(c.constraints) == 1

    def test_with_resources(self):
        r = Resource(cost=0.03, latency_ms=500)
        c = ComputeSpec.reasoning().with_resources(r)
        assert c.resources is not None
        assert c.resources.cost == 0.03

    def test_describe(self):
        c = ComputeSpec.reasoning(provider="openai", model="gpt-4o")
        d = c.describe()
        assert d["kind"] == "reasoning"
        assert d["provider"] == "openai"
        assert d["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Resource
# ---------------------------------------------------------------------------


class TestResource:
    def test_defaults(self):
        r = Resource()
        assert r.cost == 0.0

    def test_add(self):
        a = Resource(cost=0.01, latency_ms=100)
        b = Resource(cost=0.02, latency_ms=200)
        combined = a.add(b)
        assert combined.cost == 0.03
        assert combined.latency_ms == 200  # max

    def test_add_tokens(self):
        a = Resource(tokens=100)
        b = Resource(tokens=50)
        combined = a.add(b)
        assert combined.tokens == 150

    def test_describe(self):
        r = Resource(cost=0.03, latency_ms=500, energy="high")
        d = r.describe()
        assert d["cost"] == 0.03
        assert d["latency_ms"] == 500
        assert d["energy"] == "high"


# ---------------------------------------------------------------------------
# Composition: primitives working together
# ---------------------------------------------------------------------------


class TestComposition:
    """Test that primitives compose naturally, matching the architecture doc:

    ENTITY → STATE → INTENT → CAPABILITY → EXECUTION → EFFECT → STATE
    TIME + CONSTRAINT surround the entire lifecycle.
    RESOURCE determines how execution should be performed.
    """

    def test_full_lifecycle_composition(self):
        # State: the durable truth
        user_state = State(kind="user", data={"name": "Ada", "balance": 500})

        # Intent: what we want to accomplish
        intent = Intent(
            name="process_payment",
            params={"amount": 100, "to": "vendor@example.com"},
        )
        intent.require("payment.execute")
        intent.require("email.send")
        intent.with_deadline(3600)
        intent.constrain(Constraint.cost(maximum=0.10))
        intent.constrain(Constraint.approval_required())

        # Capability: explicit permission
        cap = Capability.timed("payment.execute", expires_in=600)
        assert cap.valid

        # Compute: how to perform the computation
        compute = ComputeSpec.reasoning(provider="local").with_resources(
            Resource(cost=0.01, latency_ms=50)
        )
        assert compute.resources is not None
        assert compute.resources.cost == 0.01

        # Effect: the side effect
        effect = Effect(
            name="charge_payment",
            intent_id=intent.id,
            capability_name=cap.name,
            reversible=True,
            idempotent=True,
        )

        # Execute the intent lifecycle
        intent.queue()
        intent.evaluate()
        intent.execute()

        # Simulate effect execution
        effect.mark_executing()
        effect.mark_succeeded(result={"transaction_id": "txn_123"})

        # Record effect on intent
        intent.add_effect(effect.id)
        intent.complete(result={"transaction_id": "txn_123"})

        # State changes as a result
        new_state = user_state.mutate(balance=400)

        # Assertions
        assert intent.status == IntentStatus.COMPLETED
        assert effect.succeeded is True
        assert new_state.version == 2
        assert new_state.data["balance"] == 400
        assert cap.valid  # still valid

    def test_constraint_evaluation_against_resource(self):
        """Constraints should be evaluable against resource values."""
        cost_constraint = Constraint.cost(maximum=0.10)
        latency_constraint = Constraint.latency(maximum_ms=100)

        resource = Resource(cost=0.05, latency_ms=50)
        assert cost_constraint.evaluate(resource.cost) is True
        assert latency_constraint.evaluate(resource.latency_ms) is True

        expensive = Resource(cost=0.15, latency_ms=150)
        assert cost_constraint.evaluate(expensive.cost) is False
        assert latency_constraint.evaluate(expensive.latency_ms) is False

    def test_capability_delegation_chain(self):
        """Capabilities can be delegated without transferring identity."""
        admin_cap = Capability(name="payment.execute", issued_by="admin")
        agent_cap = admin_cap.delegate("agent:456")
        sub_agent_cap = agent_cap.delegate("agent:789")

        assert admin_cap.issued_by == "admin"
        assert agent_cap.delegate_to == "agent:456"
        assert sub_agent_cap.delegate_to == "agent:789"
        assert sub_agent_cap.name == "payment.execute"

        # Revoking the original doesn't auto-revoke delegates
        # (that would require a registry; primitives are composable, not magical)
        admin_cap.revoke()
        assert admin_cap.valid is False
        assert agent_cap.valid is True  # delegate is independent

    def test_time_surrounds_lifecycle(self):
        """TimeSpec wraps the entire intent lifecycle."""
        deadline_spec = TimeSpec.with_deadline(3600)
        retry_spec = TimeSpec.with_retry(retry_after=30, max_retries=3)

        intent = Intent(name="long_running_task")
        intent.deadline = deadline_spec.deadline

        assert intent.expired is False
        assert deadline_spec.remaining > 3599
        assert retry_spec.max_retries == 3
