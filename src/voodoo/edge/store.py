"""Device persistence — Protocol, in-memory, and SQLite stores (Sprint 23).

The store manages Devices, credentials, enrollments, sessions, pending
effects, and message idempotency. It uses the same local-first pattern as
the agent registry: SQLite by default, no external infrastructure.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from voodoo.edge.errors import DeviceNotFoundError
from voodoo.edge.models import (
    CredentialStatus,
    Device,
    DeviceCredential,
    DeviceEnrollment,
    DeviceSession,
    DeviceStatus,
    EnrollmentStatus,
    _iso_now,
)

__all__ = [
    "DeviceStoreProtocol",
    "InMemoryDeviceStore",
    "SQLiteDeviceStore",
    "EffectDelivery",
]


# ---------------------------------------------------------------------------
# Delivery record for effects targeting a device (EDGE §25–§29)
# ---------------------------------------------------------------------------


class EffectDelivery:
    """Tracks delivery state of one effect to one device.

    Lifecycle: ``pending → delivered → acked`` (completed/failed/rejected).
    Delivery is at-least-once; the stable ``effect_id`` provides
    idempotency for the device (EDGE §28).
    """

    __slots__ = (
        "effect_id",
        "execution_id",
        "device_id",
        "capability",
        "payload",
        "status",
        "created_at",
        "delivered_at",
        "acked_at",
        "ack_status",
        "deliveries",
    )

    def __init__(
        self,
        effect_id: str,
        execution_id: str,
        device_id: str,
        capability: str,
        payload: dict[str, Any],
    ) -> None:
        self.effect_id = effect_id
        self.execution_id = execution_id
        self.device_id = device_id
        self.capability = capability
        self.payload = payload
        self.status = "pending"
        self.created_at = _iso_now()
        self.delivered_at: str | None = None
        self.acked_at: str | None = None
        self.ack_status: str | None = None
        self.deliveries = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "execution_id": self.execution_id,
            "device_id": self.device_id,
            "capability": self.capability,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "acked_at": self.acked_at,
            "ack_status": self.ack_status,
            "deliveries": self.deliveries,
        }


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class DeviceStoreProtocol(Protocol):
    """Persistence contract for the Device Gateway (EDGE §70)."""

    # -- devices -----------------------------------------------------------

    async def register_device(self, device: Device) -> None: ...
    async def get_device(self, device_id: str) -> Device | None: ...
    async def list_devices(self, limit: int = 100) -> list[Device]: ...
    async def update_device_status(
        self, device_id: str, status: DeviceStatus
    ) -> None: ...
    async def update_device_capabilities(
        self, device_id: str, capabilities: list[str]
    ) -> None: ...
    async def update_device_state(
        self, device_id: str, state: dict[str, Any], state_version: int
    ) -> bool: ...
    async def update_last_seen(self, device_id: str) -> None: ...
    async def revoke_device(self, device_id: str) -> bool: ...

    # -- credentials ---------------------------------------------------------

    async def create_credential(self, credential: DeviceCredential) -> None: ...
    async def get_active_credential(
        self, device_id: str
    ) -> DeviceCredential | None: ...
    async def find_credential_by_hash(
        self, credential_hash: str
    ) -> DeviceCredential | None: ...
    async def mark_credential_used(self, credential_id: str) -> None: ...
    async def revoke_credential(self, credential_id: str) -> bool: ...
    async def revoke_device_credentials(self, device_id: str) -> int: ...

    # -- enrollments ---------------------------------------------------------

    async def create_enrollment(self, enrollment: DeviceEnrollment) -> None: ...
    async def find_enrollment_by_hash(
        self, key_hash: str
    ) -> DeviceEnrollment | None: ...
    async def consume_enrollment(self, enrollment_id: str) -> bool: ...
    async def revoke_enrollment(self, enrollment_id: str) -> bool: ...

    # -- sessions ------------------------------------------------------------

    async def create_session(self, session: DeviceSession) -> None: ...
    async def delete_session(self, session_id: str) -> None: ...
    async def get_session(self, session_id: str) -> DeviceSession | None: ...

    # -- effects -------------------------------------------------------------

    async def add_effect_delivery(self, delivery: EffectDelivery) -> None: ...
    async def get_effect_delivery(self, effect_id: str) -> EffectDelivery | None: ...
    async def pending_effects(
        self, device_id: str, limit: int = 50
    ) -> list[EffectDelivery]: ...
    async def mark_effect_delivered(self, effect_id: str) -> None: ...
    async def mark_effect_acked(
        self, effect_id: str, ack_status: str
    ) -> EffectDelivery | None: ...

    # -- idempotency -----------------------------------------------------------

    async def seen_message(self, message_id: str) -> bool: ...
    async def mark_message_seen(self, message_id: str) -> None: ...

    # -- lifecycle -------------------------------------------------------------

    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# In-memory implementation (tests, embedded runtimes)
# ---------------------------------------------------------------------------


class InMemoryDeviceStore:
    """Non-durable store — reference semantics for tests and adapters."""

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        self._credentials: dict[str, DeviceCredential] = {}
        self._enrollments: dict[str, DeviceEnrollment] = {}
        self._sessions: dict[str, DeviceSession] = {}
        self._effects: dict[str, EffectDelivery] = {}
        self._seen_messages: set[str] = set()

    # -- devices -----------------------------------------------------------

    async def register_device(self, device: Device) -> None:
        self._devices[device.device_id] = device

    async def get_device(self, device_id: str) -> Device | None:
        return self._devices.get(device_id)

    async def list_devices(self, limit: int = 100) -> list[Device]:
        return list(self._devices.values())[:limit]

    async def update_device_status(self, device_id: str, status: DeviceStatus) -> None:
        device = self._devices.get(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        device.status = status
        device.updated_at = _iso_now()

    async def update_device_capabilities(
        self, device_id: str, capabilities: list[str]
    ) -> None:
        device = self._devices.get(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        device.capabilities = list(capabilities)
        device.updated_at = _iso_now()

    async def update_device_state(
        self, device_id: str, state: dict[str, Any], state_version: int
    ) -> bool:
        """Atomic compare-and-swap on state_version.

        Returns ``True`` when applied; ``False`` when the incoming version
        is stale — newer Runtime state is never silently overwritten
        (EDGE §23).
        """
        device = self._devices.get(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if state_version < device.state_version:
            return False
        device.state = dict(state)
        device.state_version = state_version
        device.updated_at = _iso_now()
        return True

    async def update_last_seen(self, device_id: str) -> None:
        device = self._devices.get(device_id)
        if device is not None:
            device.last_seen_at = _iso_now()

    async def revoke_device(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if device is None:
            return False
        device.status = DeviceStatus.REVOKED
        device.updated_at = _iso_now()
        # Cascade: revoke every active credential for this device (EDGE §49).
        for cred in self._credentials.values():
            if cred.device_id == device_id and cred.status == CredentialStatus.ACTIVE:
                cred.status = CredentialStatus.REVOKED
                cred.revoked_at = _iso_now()
        return True

    # -- credentials ---------------------------------------------------------

    async def create_credential(self, credential: DeviceCredential) -> None:
        self._credentials[credential.credential_id] = credential

    async def get_active_credential(self, device_id: str) -> DeviceCredential | None:
        for cred in self._credentials.values():
            if cred.device_id == device_id and cred.status == CredentialStatus.ACTIVE:
                return cred
        return None

    async def find_credential_by_hash(
        self, credential_hash: str
    ) -> DeviceCredential | None:
        for cred in self._credentials.values():
            if (
                cred.credential_hash == credential_hash
                and cred.status == CredentialStatus.ACTIVE
            ):
                return cred
        return None

    async def mark_credential_used(self, credential_id: str) -> None:
        cred = self._credentials.get(credential_id)
        if cred is not None:
            cred.last_used_at = _iso_now()

    async def revoke_credential(self, credential_id: str) -> bool:
        cred = self._credentials.get(credential_id)
        if cred is None:
            return False
        cred.status = CredentialStatus.REVOKED
        cred.revoked_at = _iso_now()
        return True

    async def revoke_device_credentials(self, device_id: str) -> int:
        count = 0
        for cred in self._credentials.values():
            if cred.device_id == device_id and cred.status == CredentialStatus.ACTIVE:
                cred.status = CredentialStatus.REVOKED
                cred.revoked_at = _iso_now()
                count += 1
        return count

    # -- enrollments ---------------------------------------------------------

    async def create_enrollment(self, enrollment: DeviceEnrollment) -> None:
        self._enrollments[enrollment.enrollment_id] = enrollment

    async def find_enrollment_by_hash(self, key_hash: str) -> DeviceEnrollment | None:
        for enrollment in self._enrollments.values():
            if enrollment.enrollment_key_hash == key_hash:
                return enrollment
        return None

    async def consume_enrollment(self, enrollment_id: str) -> bool:
        """Single-use consumption — only a PENDING enrollment converts."""
        enrollment = self._enrollments.get(enrollment_id)
        if enrollment is None or enrollment.status != EnrollmentStatus.PENDING:
            return False
        enrollment.status = EnrollmentStatus.CONSUMED
        enrollment.consumed_at = _iso_now()
        return True

    async def revoke_enrollment(self, enrollment_id: str) -> bool:
        enrollment = self._enrollments.get(enrollment_id)
        if enrollment is None:
            return False
        enrollment.status = EnrollmentStatus.REVOKED
        return True

    # -- sessions ------------------------------------------------------------

    async def create_session(self, session: DeviceSession) -> None:
        self._sessions[session.session_id] = session

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def get_session(self, session_id: str) -> DeviceSession | None:
        return self._sessions.get(session_id)

    # -- effects -------------------------------------------------------------

    async def add_effect_delivery(self, delivery: EffectDelivery) -> None:
        # Idempotent: re-adding an existing effect_id is a no-op (EDGE §28).
        self._effects.setdefault(delivery.effect_id, delivery)

    async def get_effect_delivery(self, effect_id: str) -> EffectDelivery | None:
        return self._effects.get(effect_id)

    async def pending_effects(
        self, device_id: str, limit: int = 50
    ) -> list[EffectDelivery]:
        out = [
            e
            for e in self._effects.values()
            if e.device_id == device_id and e.status == "pending"
        ]
        return out[:limit]

    async def mark_effect_delivered(self, effect_id: str) -> None:
        delivery = self._effects.get(effect_id)
        if delivery is not None:
            delivery.deliveries += 1
            delivery.delivered_at = _iso_now()
            if delivery.status == "pending":
                delivery.status = "delivered"

    async def mark_effect_acked(
        self, effect_id: str, ack_status: str
    ) -> EffectDelivery | None:
        delivery = self._effects.get(effect_id)
        if delivery is None:
            return None
        delivery.acked_at = _iso_now()
        delivery.ack_status = ack_status
        delivery.status = ack_status
        return delivery

    # -- idempotency -----------------------------------------------------------

    async def seen_message(self, message_id: str) -> bool:
        return message_id in self._seen_messages

    async def mark_message_seen(self, message_id: str) -> None:
        self._seen_messages.add(message_id)

    # -- lifecycle -------------------------------------------------------------

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# SQLite implementation (durable default)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS devices (
    device_id      TEXT PRIMARY KEY,
    entity_id      TEXT NOT NULL,
    type           TEXT NOT NULL DEFAULT 'generic',
    name           TEXT NOT NULL DEFAULT '',
    capabilities   TEXT NOT NULL DEFAULT '[]',
    state          TEXT NOT NULL DEFAULT '{}',
    state_version  INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'registered',
    metadata       TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    last_seen_at   TEXT
);

CREATE TABLE IF NOT EXISTS device_credentials (
    credential_id   TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL,
    credential_hash TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    expires_at      TEXT,
    revoked_at      TEXT,
    last_used_at    TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_device_credentials_hash
    ON device_credentials(credential_hash);
CREATE INDEX IF NOT EXISTS idx_device_credentials_device
    ON device_credentials(device_id);

CREATE TABLE IF NOT EXISTS device_enrollments (
    enrollment_id       TEXT PRIMARY KEY,
    enrollment_key_hash TEXT NOT NULL,
    device_type         TEXT NOT NULL DEFAULT 'generic',
    device_name         TEXT NOT NULL DEFAULT '',
    capabilities        TEXT NOT NULL DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TEXT NOT NULL,
    expires_at          TEXT,
    consumed_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_device_enrollments_hash
    ON device_enrollments(enrollment_key_hash);

CREATE TABLE IF NOT EXISTS device_sessions (
    session_id       TEXT PRIMARY KEY,
    device_id        TEXT NOT NULL,
    transport        TEXT NOT NULL DEFAULT 'http',
    connected_at     TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    protocol_version TEXT NOT NULL DEFAULT '1'
);

CREATE TABLE IF NOT EXISTS device_effect_deliveries (
    effect_id     TEXT PRIMARY KEY,
    execution_id  TEXT NOT NULL,
    device_id     TEXT NOT NULL,
    capability    TEXT NOT NULL,
    payload       TEXT NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TEXT NOT NULL,
    delivered_at  TEXT,
    acked_at      TEXT,
    ack_status    TEXT,
    deliveries    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_effect_deliveries_device
    ON device_effect_deliveries(device_id);

CREATE TABLE IF NOT EXISTS device_message_log (
    message_id  TEXT PRIMARY KEY,
    seen_at     TEXT NOT NULL
);
"""


def _device_row_to_obj(row: dict[str, Any]) -> Device:
    return Device(
        device_id=row["device_id"],
        entity_id=row["entity_id"],
        type=row["type"],
        name=row["name"],
        capabilities=json.loads(row["capabilities"]),
        state=json.loads(row["state"]),
        state_version=row["state_version"],
        status=DeviceStatus(row["status"]),
        metadata=json.loads(row["metadata"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_seen_at=row["last_seen_at"],
    )


def _delivery_row_to_obj(row: dict[str, Any]) -> EffectDelivery:
    delivery = EffectDelivery(
        effect_id=row["effect_id"],
        execution_id=row["execution_id"],
        device_id=row["device_id"],
        capability=row["capability"],
        payload=json.loads(row["payload"]),
    )
    delivery.status = row["status"]
    delivery.created_at = row["created_at"]
    delivery.delivered_at = row["delivered_at"]
    delivery.acked_at = row["acked_at"]
    delivery.ack_status = row["ack_status"]
    delivery.deliveries = row["deliveries"]
    return delivery


class SQLiteDeviceStore:
    """Durable SQLite-backed device store (WAL mode, busy_timeout=5000)."""

    def __init__(self, db_path: str = "data/devices.db") -> None:
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    async def close(self) -> None:
        self._conn.close()

    # -- devices -----------------------------------------------------------

    async def register_device(self, device: Device) -> None:
        d = device.to_dict()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO devices
                (device_id, entity_id, type, name, capabilities, state,
                 state_version, status, metadata, created_at, updated_at,
                 last_seen_at)
            VALUES
                (:device_id, :entity_id, :type, :name, :capabilities, :state,
                 :state_version, :status, :metadata, :created_at, :updated_at,
                 :last_seen_at)
            """,
            {
                **d,
                "capabilities": json.dumps(d["capabilities"]),
                "state": json.dumps(d["state"]),
                "metadata": json.dumps(d["metadata"]),
            },
        )
        self._conn.commit()

    async def get_device(self, device_id: str) -> Device | None:
        cur = self._conn.execute(
            "SELECT * FROM devices WHERE device_id = ?", (device_id,)
        )
        row = cur.fetchone()
        return _device_row_to_obj(dict(row)) if row else None

    async def list_devices(self, limit: int = 100) -> list[Device]:
        cur = self._conn.execute(
            "SELECT * FROM devices ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [_device_row_to_obj(dict(r)) for r in cur.fetchall()]

    async def update_device_status(self, device_id: str, status: DeviceStatus) -> None:
        self._conn.execute(
            "UPDATE devices SET status = ?, updated_at = ? WHERE device_id = ?",
            (status.value, _iso_now(), device_id),
        )
        self._conn.commit()

    async def update_device_capabilities(
        self, device_id: str, capabilities: list[str]
    ) -> None:
        self._conn.execute(
            "UPDATE devices SET capabilities = ?, updated_at = ? WHERE device_id = ?",
            (json.dumps(capabilities), _iso_now(), device_id),
        )
        self._conn.commit()

    async def update_device_state(
        self, device_id: str, state: dict[str, Any], state_version: int
    ) -> bool:
        """Conditional UPDATE rejects stale state atomically (EDGE §23)."""
        cur = self._conn.execute(
            """
            UPDATE devices
            SET state = ?, state_version = ?, updated_at = ?
            WHERE device_id = ? AND state_version < ?
            """,
            (json.dumps(state), state_version, _iso_now(), device_id, state_version),
        )
        self._conn.commit()
        return cur.rowcount > 0

    async def update_last_seen(self, device_id: str) -> None:
        now = _iso_now()
        self._conn.execute(
            "UPDATE devices SET last_seen_at = ?, updated_at = ? WHERE device_id = ?",
            (now, now, device_id),
        )
        self._conn.commit()

    async def revoke_device(self, device_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE devices SET status = ?, updated_at = ? WHERE device_id = ?",
            (DeviceStatus.REVOKED.value, _iso_now(), device_id),
        )
        self._conn.execute(
            "UPDATE device_credentials SET status = ?, revoked_at = ? "
            "WHERE device_id = ? AND status = ?",
            (
                CredentialStatus.REVOKED.value,
                _iso_now(),
                device_id,
                CredentialStatus.ACTIVE.value,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # -- credentials ---------------------------------------------------------

    async def create_credential(self, credential: DeviceCredential) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO device_credentials
                (credential_id, device_id, credential_hash, status, created_at,
                 expires_at, revoked_at, last_used_at)
            VALUES
                (:credential_id, :device_id, :credential_hash, :status, :created_at,
                 :expires_at, :revoked_at, :last_used_at)
            """,
            credential.to_dict(),
        )
        self._conn.commit()

    async def get_active_credential(self, device_id: str) -> DeviceCredential | None:
        cur = self._conn.execute(
            "SELECT * FROM device_credentials WHERE device_id = ? AND status = ?",
            (device_id, CredentialStatus.ACTIVE.value),
        )
        row = cur.fetchone()
        return DeviceCredential.from_dict(dict(row)) if row else None

    async def find_credential_by_hash(
        self, credential_hash: str
    ) -> DeviceCredential | None:
        cur = self._conn.execute(
            "SELECT * FROM device_credentials WHERE credential_hash = ? AND status = ?",
            (credential_hash, CredentialStatus.ACTIVE.value),
        )
        row = cur.fetchone()
        return DeviceCredential.from_dict(dict(row)) if row else None

    async def mark_credential_used(self, credential_id: str) -> None:
        self._conn.execute(
            "UPDATE device_credentials SET last_used_at = ? WHERE credential_id = ?",
            (_iso_now(), credential_id),
        )
        self._conn.commit()

    async def revoke_credential(self, credential_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE device_credentials SET status = ?, revoked_at = ? "
            "WHERE credential_id = ? AND status = ?",
            (
                CredentialStatus.REVOKED.value,
                _iso_now(),
                credential_id,
                CredentialStatus.ACTIVE.value,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    async def revoke_device_credentials(self, device_id: str) -> int:
        cur = self._conn.execute(
            "UPDATE device_credentials SET status = ?, revoked_at = ? "
            "WHERE device_id = ? AND status = ?",
            (
                CredentialStatus.REVOKED.value,
                _iso_now(),
                device_id,
                CredentialStatus.ACTIVE.value,
            ),
        )
        self._conn.commit()
        return cur.rowcount

    # -- enrollments ---------------------------------------------------------

    async def create_enrollment(self, enrollment: DeviceEnrollment) -> None:
        d = enrollment.to_dict()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO device_enrollments
                (enrollment_id, enrollment_key_hash, device_type, device_name,
                 capabilities, status, created_at, expires_at, consumed_at)
            VALUES
                (:enrollment_id, :enrollment_key_hash, :device_type, :device_name,
                 :capabilities, :status, :created_at, :expires_at, :consumed_at)
            """,
            {**d, "capabilities": json.dumps(d["capabilities"])},
        )
        self._conn.commit()

    async def find_enrollment_by_hash(self, key_hash: str) -> DeviceEnrollment | None:
        cur = self._conn.execute(
            "SELECT * FROM device_enrollments WHERE enrollment_key_hash = ?",
            (key_hash,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["capabilities"] = json.loads(d["capabilities"])
        return DeviceEnrollment.from_dict(d)

    async def consume_enrollment(self, enrollment_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE device_enrollments SET status = ?, consumed_at = ? "
            "WHERE enrollment_id = ? AND status = ?",
            (
                EnrollmentStatus.CONSUMED.value,
                _iso_now(),
                enrollment_id,
                EnrollmentStatus.PENDING.value,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    async def revoke_enrollment(self, enrollment_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE device_enrollments SET status = ? "
            "WHERE enrollment_id = ? AND status = ?",
            (
                EnrollmentStatus.REVOKED.value,
                enrollment_id,
                EnrollmentStatus.PENDING.value,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # -- sessions ------------------------------------------------------------

    async def create_session(self, session: DeviceSession) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO device_sessions
                (session_id, device_id, transport, connected_at, last_seen_at,
                 protocol_version)
            VALUES
                (:session_id, :device_id, :transport, :connected_at, :last_seen_at,
                 :protocol_version)
            """,
            session.to_dict(),
        )
        self._conn.commit()

    async def delete_session(self, session_id: str) -> None:
        self._conn.execute(
            "DELETE FROM device_sessions WHERE session_id = ?", (session_id,)
        )
        self._conn.commit()

    async def get_session(self, session_id: str) -> DeviceSession | None:
        cur = self._conn.execute(
            "SELECT * FROM device_sessions WHERE session_id = ?", (session_id,)
        )
        row = cur.fetchone()
        return DeviceSession.from_dict(dict(row)) if row else None

    # -- effects -------------------------------------------------------------

    async def add_effect_delivery(self, delivery: EffectDelivery) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO device_effect_deliveries
                (effect_id, execution_id, device_id, capability, payload, status,
                 created_at, delivered_at, acked_at, ack_status, deliveries)
            VALUES
                (:effect_id, :execution_id, :device_id, :capability, :payload, :status,
                 :created_at, :delivered_at, :acked_at, :ack_status, :deliveries)
            """,
            {**delivery.to_dict(), "payload": json.dumps(delivery.payload)},
        )
        self._conn.commit()

    async def get_effect_delivery(self, effect_id: str) -> EffectDelivery | None:
        cur = self._conn.execute(
            "SELECT * FROM device_effect_deliveries WHERE effect_id = ?", (effect_id,)
        )
        row = cur.fetchone()
        return _delivery_row_to_obj(dict(row)) if row else None

    async def pending_effects(
        self, device_id: str, limit: int = 50
    ) -> list[EffectDelivery]:
        cur = self._conn.execute(
            "SELECT * FROM device_effect_deliveries "
            "WHERE device_id = ? AND status = ? ORDER BY created_at LIMIT ?",
            (device_id, "pending", limit),
        )
        return [_delivery_row_to_obj(dict(r)) for r in cur.fetchall()]

    async def mark_effect_delivered(self, effect_id: str) -> None:
        self._conn.execute(
            "UPDATE device_effect_deliveries SET deliveries = deliveries + 1, "
            "delivered_at = ?, status = CASE WHEN status = 'pending' "
            "THEN 'delivered' ELSE status END WHERE effect_id = ?",
            (_iso_now(), effect_id),
        )
        self._conn.commit()

    async def mark_effect_acked(
        self, effect_id: str, ack_status: str
    ) -> EffectDelivery | None:
        self._conn.execute(
            "UPDATE device_effect_deliveries SET acked_at = ?, ack_status = ?, "
            "status = ? WHERE effect_id = ?",
            (_iso_now(), ack_status, ack_status, effect_id),
        )
        self._conn.commit()
        return await self.get_effect_delivery(effect_id)

    # -- idempotency -----------------------------------------------------------

    async def seen_message(self, message_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM device_message_log WHERE message_id = ?", (message_id,)
        )
        return cur.fetchone() is not None

    async def mark_message_seen(self, message_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO device_message_log (message_id, seen_at) "
            "VALUES (?, ?)",
            (message_id, _iso_now()),
        )
        self._conn.commit()
