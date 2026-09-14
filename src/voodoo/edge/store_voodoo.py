"""Voodoo Store-backed Edge device persistence.

The Edge gateway shares the Runtime-owned ``application.vstore`` instead of
opening a hidden SQLite database. The implementation preserves the existing
DeviceStoreProtocol and uses the proven in-memory semantics as the mutation
reference while durably mirroring each record into Voodoo Store.
"""

from __future__ import annotations

import json
from typing import Any

from voodoo.edge.models import (
    Device,
    DeviceCredential,
    DeviceEnrollment,
    DeviceSession,
    DeviceStatus,
)
from voodoo.edge.store import EffectDelivery, InMemoryDeviceStore
from voodoo.runtime.store import (
    RuntimeStore,
    StoreProviderError,
    get_active_runtime_store,
)

__all__ = ["VoodooStoreDeviceStore"]

_DEVICE = b"runtime:edge:device:"
_CREDENTIAL = b"runtime:edge:credential:"
_ENROLLMENT = b"runtime:edge:enrollment:"
_SESSION = b"runtime:edge:session:"
_EFFECT = b"runtime:edge:effect:"
_SEEN = b"runtime:edge:seen:"
_RESPONSE = b"runtime:edge:response:"


class VoodooStoreDeviceStore(InMemoryDeviceStore):
    """Durable Edge store sharing the one Runtime-owned Voodoo Store writer."""

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        super().__init__()
        self.runtime_store = runtime_store or get_active_runtime_store()
        if self.runtime_store is None:
            raise StoreProviderError("No active RuntimeStore for Edge persistence")
        provider = self.runtime_store.provider
        if provider is None or not provider.opened:
            raise StoreProviderError(
                "RuntimeStore must be started for Edge persistence"
            )
        if provider.name != "voodoo":
            raise StoreProviderError("VoodooStoreDeviceStore requires Voodoo Store")
        self._native = getattr(provider, "native", None)
        if self._native is None:
            raise StoreProviderError("Active Voodoo Store has no native handle")
        self._hydrate()

    def _put_json(self, prefix: bytes, key: str, value: dict[str, Any]) -> None:
        self._native.put(
            prefix + key.encode("utf-8"),
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        )

    def _delete(self, prefix: bytes, key: str) -> None:
        self._native.delete(prefix + key.encode("utf-8"))

    def _scan(self, prefix: bytes):
        for raw_key, raw_value in self._native.scan_prefix(prefix):
            key = bytes(raw_key)[len(prefix) :].decode("utf-8")
            yield key, bytes(raw_value)

    @staticmethod
    def _delivery_from_dict(data: dict[str, Any]) -> EffectDelivery:
        delivery = EffectDelivery(
            effect_id=str(data["effect_id"]),
            execution_id=str(data["execution_id"]),
            device_id=str(data["device_id"]),
            capability=str(data["capability"]),
            payload=dict(data.get("payload") or {}),
            max_retries=int(data.get("max_retries", 3)),
        )
        delivery.status = str(data.get("status", "pending"))
        delivery.created_at = str(data.get("created_at", delivery.created_at))
        delivery.delivered_at = data.get("delivered_at")
        delivery.acked_at = data.get("acked_at")
        delivery.ack_status = data.get("ack_status")
        delivery.deliveries = int(data.get("deliveries", 0))
        delivery.retry_count = int(data.get("retry_count", 0))
        return delivery

    def _hydrate(self) -> None:
        for key, raw in self._scan(_DEVICE):
            self._devices[key] = Device.from_dict(json.loads(raw))
        for key, raw in self._scan(_CREDENTIAL):
            self._credentials[key] = DeviceCredential.from_dict(json.loads(raw))
        for key, raw in self._scan(_ENROLLMENT):
            self._enrollments[key] = DeviceEnrollment.from_dict(json.loads(raw))
        for key, raw in self._scan(_SESSION):
            self._sessions[key] = DeviceSession.from_dict(json.loads(raw))
        for key, raw in self._scan(_EFFECT):
            self._effects[key] = self._delivery_from_dict(json.loads(raw))
        for key, _raw in self._scan(_SEEN):
            self._seen_messages.add(key)
        for key, raw in self._scan(_RESPONSE):
            self._responses[key] = raw.decode("utf-8")

    def _save_device(self, device_id: str) -> None:
        item = self._devices.get(device_id)
        if item is not None:
            self._put_json(_DEVICE, device_id, item.to_dict())

    def _save_credential(self, credential_id: str) -> None:
        item = self._credentials.get(credential_id)
        if item is not None:
            self._put_json(_CREDENTIAL, credential_id, item.to_dict())

    def _save_enrollment(self, enrollment_id: str) -> None:
        item = self._enrollments.get(enrollment_id)
        if item is not None:
            self._put_json(_ENROLLMENT, enrollment_id, item.to_dict())

    def _save_effect(self, effect_id: str) -> None:
        item = self._effects.get(effect_id)
        if item is not None:
            self._put_json(_EFFECT, effect_id, item.to_dict())

    async def register_device(self, device: Device) -> None:
        await super().register_device(device)
        self._save_device(device.device_id)

    async def update_device_status(self, device_id: str, status: DeviceStatus) -> None:
        await super().update_device_status(device_id, status)
        self._save_device(device_id)

    async def update_device_capabilities(
        self, device_id: str, capabilities: list[str]
    ) -> None:
        await super().update_device_capabilities(device_id, capabilities)
        self._save_device(device_id)

    async def update_device_state(
        self, device_id: str, state: dict[str, Any], state_version: int
    ) -> bool:
        changed = await super().update_device_state(device_id, state, state_version)
        if changed:
            self._save_device(device_id)
        return changed

    async def update_last_seen(self, device_id: str) -> None:
        await super().update_last_seen(device_id)
        self._save_device(device_id)

    async def revoke_device(self, device_id: str) -> bool:
        changed = await super().revoke_device(device_id)
        if changed:
            self._save_device(device_id)
            for credential in self._credentials.values():
                if credential.device_id == device_id:
                    self._save_credential(credential.credential_id)
        return changed

    async def create_credential(self, credential: DeviceCredential) -> None:
        await super().create_credential(credential)
        self._save_credential(credential.credential_id)

    async def mark_credential_used(self, credential_id: str) -> None:
        await super().mark_credential_used(credential_id)
        self._save_credential(credential_id)

    async def revoke_credential(self, credential_id: str) -> bool:
        changed = await super().revoke_credential(credential_id)
        if changed:
            self._save_credential(credential_id)
        return changed

    async def revoke_device_credentials(self, device_id: str) -> int:
        count = await super().revoke_device_credentials(device_id)
        if count:
            for credential in self._credentials.values():
                if credential.device_id == device_id:
                    self._save_credential(credential.credential_id)
        return count

    async def create_enrollment(self, enrollment: DeviceEnrollment) -> None:
        await super().create_enrollment(enrollment)
        self._save_enrollment(enrollment.enrollment_id)

    async def consume_enrollment(self, enrollment_id: str) -> bool:
        changed = await super().consume_enrollment(enrollment_id)
        if changed:
            self._save_enrollment(enrollment_id)
        return changed

    async def revoke_enrollment(self, enrollment_id: str) -> bool:
        changed = await super().revoke_enrollment(enrollment_id)
        if changed:
            self._save_enrollment(enrollment_id)
        return changed

    async def create_session(self, session: DeviceSession) -> None:
        await super().create_session(session)
        self._put_json(_SESSION, session.session_id, session.to_dict())

    async def delete_session(self, session_id: str) -> None:
        await super().delete_session(session_id)
        self._delete(_SESSION, session_id)

    async def delete_device_sessions(self, device_id: str) -> int:
        session_ids = [
            sid
            for sid, session in self._sessions.items()
            if session.device_id == device_id
        ]
        count = await super().delete_device_sessions(device_id)
        for session_id in session_ids:
            self._delete(_SESSION, session_id)
        return count

    async def add_effect_delivery(self, delivery: EffectDelivery) -> None:
        existed = delivery.effect_id in self._effects
        await super().add_effect_delivery(delivery)
        if not existed:
            self._save_effect(delivery.effect_id)

    async def mark_effect_delivered(self, effect_id: str) -> None:
        await super().mark_effect_delivered(effect_id)
        self._save_effect(effect_id)

    async def mark_effect_acked(
        self, effect_id: str, ack_status: str
    ) -> EffectDelivery | None:
        delivery = await super().mark_effect_acked(effect_id, ack_status)
        if delivery is not None:
            self._save_effect(effect_id)
        return delivery

    async def mark_effect_delivering(self, effect_id: str) -> bool:
        changed = await super().mark_effect_delivering(effect_id)
        if changed:
            self._save_effect(effect_id)
        return changed

    async def mark_effect_delivery_failed(self, effect_id: str) -> bool:
        changed = await super().mark_effect_delivery_failed(effect_id)
        if changed:
            self._save_effect(effect_id)
        return changed

    async def claim_effect(self, device_id: str, effect_id: str) -> bool:
        changed = await super().claim_effect(device_id, effect_id)
        if changed:
            self._save_effect(effect_id)
        return changed

    async def retry_effect(self, effect_id: str) -> bool:
        changed = await super().retry_effect(effect_id)
        if changed:
            self._save_effect(effect_id)
        return changed

    async def mark_message_seen(self, message_id: str) -> None:
        await super().mark_message_seen(message_id)
        self._native.put(_SEEN + message_id.encode("utf-8"), b"1")

    async def store_response(self, message_id: str, response_json: str) -> None:
        await super().store_response(message_id, response_json)
        self._native.put(
            _RESPONSE + message_id.encode("utf-8"), response_json.encode("utf-8")
        )

    async def close(self) -> None:
        """RuntimeStore owns the underlying Store lifecycle."""
