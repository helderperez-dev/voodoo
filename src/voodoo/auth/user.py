from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Optional

from starlette.requests import Request

from voodoo.auth.passwords import (
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from voodoo.data import BaseModel, get_db

# Context variable for the currently authenticated user in the current async task
current_user: ContextVar[Optional["AuthUser"]] = ContextVar(
    "current_user", default=None
)

# =========================================================================
# Auth User & Context
# =========================================================================


class AuthUser:
    """Represents an authenticated user identity in the request context."""

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
        """Checks if the user has at least one of the required roles."""
        if not self.is_authenticated:
            return False
        return any(r in self.roles for r in required_roles)

    def has_scope(self, *required_scopes: str) -> bool:
        """Checks if the user has all required scopes."""
        if not self.is_authenticated:
            return False
        return all(s in self.scopes for s in required_scopes)

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
    """
    Retrieves the currently authenticated user from request state or ContextVar.
    """
    if (
        request is not None
        and hasattr(request, "state")
        and hasattr(request.state, "user")
    ):
        u = getattr(request.state, "user", None)
        if isinstance(u, AuthUser):
            return u
    return current_user.get()


# =========================================================================
# Built-in User Database Model (extends Voodoo BaseModel)
# =========================================================================


class User(BaseModel):
    """Built-in User entity for relational SQLite storage."""

    __tablename__ = "voodoo_users"
    id: int
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
        """
        Creates and stores a new User in the database with hashed password.
        Optionally generates an initial API key.
        Returns (user, raw_api_key)
        """
        _ = await get_db()
        # Ensure table exists
        await cls._create_table()

        hashed = hash_password(password)
        uname = username or email.split("@")[0]
        raw_key, key_hash = generate_api_key(api_key_prefix)
        created = datetime.now(UTC).isoformat()

        user = cls()
        user.email = email
        user.username = uname
        user.hashed_password = hashed
        user.role = role
        user.is_active = True
        user.api_key_hash = key_hash
        user.created_at = created

        await user.insert()
        return user, raw_key

    @classmethod
    async def authenticate(
        cls, email_or_username: str, password: str
    ) -> Optional["User"]:
        """Authenticates user by email/username and password."""
        db = await get_db()
        await cls._create_table()

        query = "SELECT * FROM voodoo_users WHERE (email = ? OR username = ?) AND is_active = 1"
        async with db.execute(query, [email_or_username, email_or_username]) as cursor:
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
        """Finds active user by matching API key hash."""
        db = await get_db()
        await cls._create_table()

        key_hash = hash_api_key(api_key)
        query = "SELECT * FROM voodoo_users WHERE api_key_hash = ? AND is_active = 1"
        async with db.execute(query, [key_hash]) as cursor:
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
        return AuthUser(
            id=self.id,
            email=self.email,
            username=self.username,
            role=self.role,
            roles=[self.role] if self.role else [],
            scopes=["*"] if self.role == "admin" else ["read", "write"],
            auth_type=auth_type,
            is_authenticated=True,
            raw_data={
                "id": self.id,
                "email": self.email,
                "username": self.username,
                "role": self.role,
            },
        )
