from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import UUID

from starlette.requests import Request

from voodoo.auth.passwords import (
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from voodoo.data import BaseModel, get_db
from voodoo.runtime.identity import (
    AuthenticationEvidence,
    Identity,
    IdentityKind,
    IdentityStatus,
    Principal,
)

current_user: ContextVar[Optional["AuthUser"]] = ContextVar(
    "current_user", default=None
)


class AuthUser:
    """Compatibility request-auth projection for a human/service user.

    Runtime authority does not come from this object's roles/scopes. Call
    :meth:`to_principal` to enter the Runtime-native Identity boundary; explicit
    Capability + Policy remains authoritative for execution.
    """

    def __init__(
        self,
        id: int | str | None = None,
        email: str | None = None,
        username: str | None = None,
        role: str = "user",
        roles: list[str] | None = None,
        scopes: list[str] | None = None,
        auth_type: str = "anonymous",
        is_authenticated: bool = False,
        raw_data: dict[str, Any] | None = None,
    ):
        self.id = id
        self.email = email
        self.username = username
        self.role = role
        self.roles = roles or ([role] if role else [])
        if role and role not in self.roles:
            self.roles.append(role)
        self.scopes = scopes or []
        self.auth_type = auth_type
        self.is_authenticated = is_authenticated
        self.raw_data = raw_data or {}

    def has_role(self, *required_roles: str) -> bool:
        if not self.is_authenticated:
            return False
        return any(r in self.roles for r in required_roles)

    def has_scope(self, *required_scopes: str) -> bool:
        if not self.is_authenticated:
            return False
        return all(s in self.scopes for s in required_scopes)

    def to_principal(self) -> Principal | None:
        """Project authenticated request identity into Runtime semantics.

        Roles/scopes are preserved as non-authoritative claims for compatibility
        and policy inspection. They are intentionally not converted into
        Capability grants.
        """
        if not self.is_authenticated or self.id is None:
            return None
        kind = IdentityKind.SERVICE if self.role == "service" else IdentityKind.USER
        identity_id = f"{kind.value}:{self.id}"
        identity = Identity(
            id=identity_id,
            kind=kind,
            display_name=self.username or self.email or str(self.id),
            status=IdentityStatus.ACTIVE,
            attributes={
                key: value
                for key, value in {
                    "email": self.email,
                    "username": self.username,
                }.items()
                if value is not None
            },
        )
        evidence = AuthenticationEvidence(
            method=self.auth_type,
            subject=str(self.id),
            issuer="voodoo",
        )
        return Principal(
            identity=identity,
            evidence=(evidence,),
            claims={
                "roles": list(self.roles),
                "scopes": list(self.scopes),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "role": self.role,
            "roles": self.roles,
            "scopes": self.scopes,
            "auth_type": self.auth_type,
            "is_authenticated": self.is_authenticated,
        }

    def __repr__(self) -> str:
        return f"<AuthUser id={self.id} email={self.email} role={self.role} authenticated={self.is_authenticated}>"


def get_current_user(request: Request | None = None) -> AuthUser | None:
    if (
        request is not None
        and hasattr(request, "state")
        and hasattr(request.state, "user")
    ):
        u = getattr(request.state, "user", None)
        if isinstance(u, AuthUser):
            return u
    return current_user.get()


def _uses_store() -> bool:
    from voodoo.config import get_config

    return get_config().database.provider.lower() == "voodoo"


def _from_record(record: dict[str, Any]) -> "User":
    user = User()
    for key, value in record.items():
        if key == "id" and isinstance(value, str):
            try:
                value = UUID(value)
            except ValueError:
                pass
        setattr(user, key, value)
    return user


class User(BaseModel):
    """Built-in Runtime user identity persisted in Store by default.

    SQLite/Postgres remain explicit compatibility adapters. Identity semantics
    stay in the Runtime while Voodoo Store owns default durable mechanics.
    """

    __tablename__ = "voodoo_users"
    id: UUID | int
    email: str
    username: str
    hashed_password: str
    role: str
    is_active: bool
    api_key_hash: str
    created_at: str

    @classmethod
    async def create_user(
        cls,
        email: str,
        password: str,
        username: str | None = None,
        role: str = "user",
        api_key_prefix: str | None = None,
    ) -> tuple["User", str | None]:
        hashed = hash_password(password)
        uname = username or email.split("@")[0]
        raw_key, key_hash = generate_api_key(api_key_prefix)
        created = datetime.now(UTC).isoformat()

        values = {
            "email": email,
            "username": uname,
            "hashed_password": hashed,
            "role": role,
            "is_active": True,
            "api_key_hash": key_hash,
            "created_at": created,
        }

        if _uses_store():
            from voodoo.data.store_backend import insert_record

            user_id = insert_record(cls.__tablename__, values)
            return _from_record({"id": user_id, **values}), raw_key

        _ = await get_db()
        await cls._create_table()
        user = cls()
        for key, value in values.items():
            setattr(user, key, value)
        await user.insert()
        return user, raw_key

    @classmethod
    async def authenticate(
        cls, email_or_username: str, password: str
    ) -> Optional["User"]:
        if _uses_store():
            from voodoo.data.store_backend import scan_records

            for record in scan_records(cls.__tablename__):
                if not record.get("is_active"):
                    continue
                if email_or_username not in {
                    record.get("email"),
                    record.get("username"),
                }:
                    continue
                if verify_password(password, str(record["hashed_password"])):
                    return _from_record(record)
                return None
            return None

        db = await get_db()
        await cls._create_table()
        query = (
            "SELECT * FROM voodoo_users "
            "WHERE (email = ? OR username = ?) AND is_active = ?"
        )
        async with db.execute(
            query, [email_or_username, email_or_username, True]
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            user = cls()
            for k in row.keys():
                val = row[k]
                if k == "is_active":
                    val = bool(val)
                setattr(user, k, val)

            if verify_password(password, user.hashed_password):
                return user
            return None

    @classmethod
    async def find_by_api_key(cls, api_key: str) -> Optional["User"]:
        key_hash = hash_api_key(api_key)

        if _uses_store():
            from voodoo.data.store_backend import scan_records

            for record in scan_records(cls.__tablename__):
                if record.get("is_active") and record.get("api_key_hash") == key_hash:
                    return _from_record(record)
            return None

        db = await get_db()
        await cls._create_table()
        query = "SELECT * FROM voodoo_users WHERE api_key_hash = ? AND is_active = ?"
        async with db.execute(query, [key_hash, True]) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            user = cls()
            for k in row.keys():
                val = row[k]
                if k == "is_active":
                    val = bool(val)
                setattr(user, k, val)
            return user

    def to_auth_user(self, auth_type: str = "session") -> AuthUser:
        public_id = str(self.id)
        return AuthUser(
            id=public_id,
            email=self.email,
            username=self.username,
            role=self.role,
            roles=[self.role] if self.role else [],
            scopes=["*"] if self.role == "admin" else ["read", "write"],
            auth_type=auth_type,
            is_authenticated=True,
            raw_data={
                "id": public_id,
                "email": self.email,
                "username": self.username,
                "role": self.role,
            },
        )
