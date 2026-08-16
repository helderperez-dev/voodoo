# Auth

## What it is

Voodoo ships with a complete identity system: password hashing (PBKDF2), JWT tokens, API keys, session cookies, and RBAC route guards. All middleware runs by default.

## Minimal example

```python
from voodoo.auth import User, create_access_token

# Create a user
user, raw_api_key = await User.create_user(
    email="ada@example.com",
    password="SecurePass99!",
    role="admin",
)

# Authenticate
user = await User.authenticate("ada@example.com", "SecurePass99!")

# Create a token
token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
```

## Common usage

### Route guards

```python
from voodoo.auth import require_auth, require_roles


@page("/dashboard")
@require_auth(redirect_url="/login")
async def dashboard(request):
    return Text("Dashboard")


@page("/admin")
@require_roles("admin")
async def admin_panel(request):
    return Text("Admin only")
```

### API key auth

```python
from voodoo.auth import require_api_key


@api.post("/api/sync")
@require_api_key(scopes=["write"])
async def sync_endpoint(request):
    return JSONResponse({"status": "ok"})
```

### Cookie-based login

```python
from voodoo.auth import set_auth_cookie, clear_auth_cookie


@api.post("/api/login")
async def login(request):
    user = await User.authenticate(email, password)
    if user:
        token = create_access_token({"sub": user.id})
        response = JSONResponse({"ok": True})
        set_auth_cookie(response, token)
        return response
    return JSONResponse({"error": "Invalid"}, status_code=401)
```

## How it works

The `AuthMiddleware` extracts user identity from three sources (in priority):

1. `X-API-Key` header → database lookup
2. `Authorization: Bearer <token>` → JWT decode
3. Session cookie (`voodoo_auth`) → JWT decode

The resolved user is placed on `request.state.user` and in a `ContextVar` for the request lifetime.

## Advanced

### Scopes

```python
from voodoo.auth import require_scopes


@api.post("/api/admin/users")
@require_scopes("users:write")
async def create_user(request): ...
```

### AuthUser

```python
from voodoo.auth import AuthUser

user = AuthUser(id=1, email="ada@x.io", role="admin", is_authenticated=True)
user.has_role("admin")  # True
user.has_scope("read")  # True
```

## API reference

- `User` — built-in user model with `create_user()`, `authenticate()`, `find_by_api_key()`.
- `AuthUser` — identity object in request context.
- `require_auth(redirect_url=None)` — guard requiring authenticated user.
- `require_roles(*roles)` — guard requiring specific roles.
- `require_scopes(*scopes)` — guard requiring specific scopes.
- `require_api_key(scopes=None)` — guard for machine-to-machine API keys.
- `create_access_token(data, expires_delta_seconds=None)` — create a JWT.
- `decode_access_token(token)` — decode and validate a JWT.
- `hash_password(password)` / `verify_password(password, hash)` — PBKDF2 hashing.
- `generate_api_key(prefix=None)` — generate a secure API key.
- `set_auth_cookie(response, token)` / `clear_auth_cookie(response)` — cookie helpers.
- `AuthMiddleware` — ASGI middleware (auto-installed).
