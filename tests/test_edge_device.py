"""Edge device tests — Phase 1: models, store, auth, enrollment (Sprint 23)."""

from __future__ import annotations

import pytest

from voodoo.edge.auth import (
    authenticate_device,
    consume_enrollment,
    create_enrollment,
    rotate_device_credential,
)
from voodoo.edge.errors import (
    AuthenticationFailedError,
    DeviceRevokedError,
)
from voodoo.edge.models import (
    Device,
    DeviceCredential,
    DeviceEnrollment,
    DeviceStatus,
    EnrollmentStatus,
)
from voodoo.edge.store import InMemoryDeviceStore, SQLiteDeviceStore

# ---------------------------------------------------------------------------
# Device model
# ---------------------------------------------------------------------------


class TestDeviceModel:
    async def test_device_defaults(self):
        device = Device(type="esp32", name="Sensor 1")
        assert device.device_id.startswith("device_")
        assert device.entity_id == f"device:{device.device_id}"
        assert device.status is DeviceStatus.REGISTERED
        assert device.state_version == 0

    async def test_device_roundtrip(self):
        device = Device(type="esp32", name="Sensor", capabilities=["sensor.read"])
        device.state = {"temperature": 31.4}
        device.state_version = 42
        restored = Device.from_dict(device.to_dict())
        assert restored.device_id == device.device_id
        assert restored.capabilities == ["sensor.read"]
        assert restored.state == {"temperature": 31.4}
        assert restored.state_version == 42
        assert restored.status is DeviceStatus.REGISTERED

    async def test_revoked_is_not_connection_state(self):
        """Connection states cycle; REVOKED is terminal (EDGE §7)."""
        device = Device()
        device.status = DeviceStatus.DISCONNECTED
        device.status = DeviceStatus.CONNECTED  # can reconnect while valid
        device.status = DeviceStatus.REVOKED
        assert DeviceStatus.REVOKED in DeviceStatus


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------


class TestInMemoryStore:
    async def test_register_and_get(self):
        store = InMemoryDeviceStore()
        device = Device(type="esp32")
        await store.register_device(device)
        fetched = await store.get_device(device.device_id)
        assert fetched is not None
        assert fetched.type == "esp32"

    async def test_stale_state_rejected(self):
        """Stale state_version never overwrites newer state (EDGE §23/§48)."""
        store = InMemoryDeviceStore()
        device = Device()
        await store.register_device(device)

        ok = await store.update_device_state(device.device_id, {"v": 42}, 42)
        assert ok is True
        stale = await store.update_device_state(device.device_id, {"v": 41}, 41)
        assert stale is False
        fetched = await store.get_device(device.device_id)
        assert fetched.state == {"v": 42}
        assert fetched.state_version == 42

    async def test_equal_version_idempotent(self):
        store = InMemoryDeviceStore()
        device = Device()
        await store.register_device(device)
        assert await store.update_device_state(device.device_id, {"v": 1}, 1)
        # Same version → accepted as idempotent retry
        assert await store.update_device_state(device.device_id, {"v": 1}, 1)

    async def test_revoke_cascades_credentials(self):
        store = InMemoryDeviceStore()
        device = Device()
        await store.register_device(device)
        await store.create_credential(
            DeviceCredential(device_id=device.device_id, credential_hash="h1")
        )
        assert await store.revoke_device(device.device_id)
        fetched = await store.get_device(device.device_id)
        assert fetched.status is DeviceStatus.REVOKED
        assert await store.get_active_credential(device.device_id) is None


# ---------------------------------------------------------------------------
# SQLite store
# ---------------------------------------------------------------------------


class TestSQLiteStore:
    async def test_roundtrip_and_stale_state(self, tmp_path):
        store = SQLiteDeviceStore(str(tmp_path / "devices.db"))
        try:
            device = Device(type="esp32", name="S1", capabilities=["relay.control"])
            await store.register_device(device)

            fetched = await store.get_device(device.device_id)
            assert fetched is not None
            assert fetched.capabilities == ["relay.control"]

            assert await store.update_device_state(device.device_id, {"fan": True}, 5)
            assert not await store.update_device_state(
                device.device_id, {"fan": False}, 4
            )
            fetched = await store.get_device(device.device_id)
            assert fetched.state == {"fan": True}
            assert fetched.state_version == 5
        finally:
            await store.close()

    async def test_credential_lifecycle(self, tmp_path):
        store = SQLiteDeviceStore(str(tmp_path / "devices.db"))
        try:
            device = Device()
            await store.register_device(device)
            cred = DeviceCredential(
                device_id=device.device_id, credential_hash="hash123"
            )
            await store.create_credential(cred)
            found = await store.find_credential_by_hash("hash123")
            assert found is not None
            assert found.device_id == device.device_id
            await store.mark_credential_used(found.credential_id)

            assert await store.revoke_credential(found.credential_id)
            assert await store.find_credential_by_hash("hash123") is None
        finally:
            await store.close()

    async def test_enrollment_single_use(self, tmp_path):
        store = SQLiteDeviceStore(str(tmp_path / "devices.db"))
        try:
            enrollment = DeviceEnrollment(enrollment_key_hash="kh", device_type="esp32")
            await store.create_enrollment(enrollment)
            assert await store.consume_enrollment(enrollment.enrollment_id)
            # Single-use: second consumption fails
            assert not await store.consume_enrollment(enrollment.enrollment_id)
        finally:
            await store.close()

    async def test_effect_delivery_idempotent(self, tmp_path):
        store = SQLiteDeviceStore(str(tmp_path / "devices.db"))
        try:
            from voodoo.edge.store import EffectDelivery

            delivery = EffectDelivery(
                effect_id="effect_1",
                execution_id="exec_1",
                device_id="device_1",
                capability="relay.control",
                payload={"state": "on"},
            )
            await store.add_effect_delivery(delivery)
            # Duplicate submission is a no-op (EDGE §28/§47)
            await store.add_effect_delivery(delivery)
            pending = await store.pending_effects("device_1")
            assert len(pending) == 1
            assert pending[0].effect_id == "effect_1"

            await store.mark_effect_delivered("effect_1")
            await store.mark_effect_acked("effect_1", "completed")
            assert await store.pending_effects("device_1") == []
            acked = await store.get_effect_delivery("effect_1")
            assert acked.status == "completed"
            assert acked.ack_status == "completed"
        finally:
            await store.close()

    async def test_message_idempotency_log(self, tmp_path):
        store = SQLiteDeviceStore(str(tmp_path / "devices.db"))
        try:
            assert not await store.seen_message("msg_1")
            await store.mark_message_seen("msg_1")
            assert await store.seen_message("msg_1")
        finally:
            await store.close()


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


class TestEnrollment:
    async def test_full_flow(self):
        store = InMemoryDeviceStore()
        key = await create_enrollment(
            store,
            device_type="esp32",
            device_name="Fan Controller",
            capabilities=["relay.fan.control"],
        )
        assert key.startswith("vde_")

        device, credential = await consume_enrollment(store, key)
        assert device.type == "esp32"
        assert device.name == "Fan Controller"
        assert device.capabilities == ["relay.fan.control"]
        assert credential.startswith("vdk_")

        # Device + credential are persisted
        assert await store.get_device(device.device_id) is not None
        assert await store.get_active_credential(device.device_id) is not None

    async def test_enrollment_single_use(self):
        store = InMemoryDeviceStore()
        key = await create_enrollment(store)
        await consume_enrollment(store, key)
        with pytest.raises(AuthenticationFailedError):
            await consume_enrollment(store, key)

    async def test_expired_enrollment_rejected(self):
        store = InMemoryDeviceStore()
        key = await create_enrollment(store, expires_in_seconds=0)
        # Already expired (0 seconds)
        expired = await store.find_enrollment_by_hash(
            __import__(
                "voodoo.edge.auth", fromlist=["hash_enrollment_key"]
            ).hash_enrollment_key(key)
        )
        assert expired is not None
        # Force the expired state
        expired.status = EnrollmentStatus.EXPIRED
        with pytest.raises(AuthenticationFailedError):
            await consume_enrollment(store, key)

    async def test_unknown_key_rejected(self):
        store = InMemoryDeviceStore()
        with pytest.raises(AuthenticationFailedError):
            await consume_enrollment(store, "vde_bogus")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestAuthentication:
    async def _enrolled(self):
        store = InMemoryDeviceStore()
        key = await create_enrollment(store, capabilities=["relay.control"])
        device, credential = await consume_enrollment(store, key)
        return store, device, credential

    async def test_valid_credential(self):
        store, device, credential = await self._enrolled()
        ctx, session = await authenticate_device(store, credential)
        assert ctx.device_id == device.device_id
        assert ctx.capabilities == ["relay.control"]
        assert session.session_id
        assert session.device_id == device.device_id

    async def test_invalid_credential(self):
        store, device, _ = await self._enrolled()
        with pytest.raises(AuthenticationFailedError):
            await authenticate_device(store, "vdk_bogus")

    async def test_credential_device_binding_enforced(self):
        """A claimed device_id without matching credential is rejected (EDGE §11)."""
        store, device, credential = await self._enrolled()
        with pytest.raises(AuthenticationFailedError):
            await authenticate_device(
                store, credential, claimed_device_id="device_somethingelse"
            )

    async def test_revoked_device_rejected(self):
        """Revocation cascades to credentials — a revoked device's
        credential is rejected at the boundary (EDGE §49)."""
        store, device, credential = await self._enrolled()
        await store.revoke_device(device.device_id)
        with pytest.raises(AuthenticationFailedError):
            await authenticate_device(store, credential)
        assert await store.get_active_credential(device.device_id) is None

    async def test_revoked_device_with_live_credential_rejected(self):
        """Even if a credential somehow stays active, the REVOKED status
        itself blocks authentication (defense in depth)."""
        store, device, credential = await self._enrolled()
        await store.revoke_device(device.device_id)
        # Simulate an unrevoked credential pointing at the revoked device.
        from voodoo.edge.auth import hash_device_credential

        await store.create_credential(
            DeviceCredential(
                device_id=device.device_id,
                credential_hash=hash_device_credential("vdk_live"),
            )
        )
        with pytest.raises(DeviceRevokedError):
            await authenticate_device(store, "vdk_live")

    async def test_rotated_credential(self):
        store, device, credential = await self._enrolled()
        new_credential = await rotate_device_credential(store, device.device_id)
        assert new_credential.startswith("vdk_")
        assert new_credential != credential
        # Old credential no longer authenticates
        with pytest.raises(AuthenticationFailedError):
            await authenticate_device(store, credential)
        # New one does
        ctx, _ = await authenticate_device(store, new_credential)
        assert ctx.device_id == device.device_id
