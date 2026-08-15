# Voodoo Auth & Identity

Voodoo provides native, enterprise-grade authentication and user identity management designed for modern full-stack apps and APIs.

## Architecture

Authentication in Voodoo is built with zero mandatory external cryptographic dependencies (utilizing Python's standard `hashlib`, `hmac`, `secrets`, and `time`). It supports:
- **Password Hashing**: PBKDF2-HMAC-SHA256 with cryptographically random 16-byte salt and constant-time validation.
- **JWT Tokens**: Secure HS256 JWT encoding/decoding, expiration management, and token blacklisting/revocation.
- **API Keys**: High-entropy keys prefixed with `voodoo_...` with secure SHA256 hashed storage and scoped permissions.
- **Session Cookies & Bearer Tokens**: Automatic extraction and parsing across requests and WebSockets.
- **Context Management**: `current_user` context variable and `request.state.user` for fast access in async handlers.
- **RBAC & Guards**: Declarative decorators (`@login_required`, `@requires_role`, `@requires_permission`).
- **Auth UI Components**: `LoginForm`, `RegisterForm`, `UserBadge`, `AuthGuard`.

---

## 1. Password Hashing & Verification

```python
from voodoo.auth import hash_password, verify_password

# Hash a plain-text password
stored_hash = hash_password("super-secret-password")

# Verify password against hash in constant time
is_valid = verify_password("super-secret-password", stored_hash) # True
```

---

## 2. JWT Authentication

```python
from voodoo.auth import create_access_token, decode_access_token, AuthUser

# Create a signed JWT token
user = AuthUser(id=1, username="alex", email="alex@voodoo.dev", role="admin")
token = create_access_token(user, expires_in_seconds=3600)

# Decode & verify
payload = decode_access_token(token)
print(payload["sub"]) # "1"
```

---

## 3. API Keys Management

```python
from voodoo.auth import generate_api_key, hash_api_key, verify_api_key

# Generate an API key for a client (shown only once)
raw_key, key_prefix = generate_api_key()
# Store hashed version in DB
key_hash = hash_api_key(raw_key)

# Later, verify incoming X-API-Key header
valid = verify_api_key(raw_key, key_hash)
```

---

## 4. Protecting Routes & Guards

```python
from voodoo.auth import login_required, requires_role, requires_permission
from voodoo.components import Div, Heading, Text

@login_required(redirect_url="/login")
def dashboard(user):
    return Div(
        Heading(f"Welcome back, {user.username}!"),
        Text(f"Your role is {user.role}")
    )

@requires_role("admin")
async def delete_user(request):
    # Only admins can execute this endpoint
    return {"status": "user deleted"}

@requires_permission("billing:manage")
async def update_subscription(request):
    return {"status": "subscription updated"}
```

---

## 5. Ready-to-Use UI Components

```python
from voodoo.components import LoginForm, RegisterForm, UserBadge, AuthGuard
from voodoo.auth import current_user

def page():
    user = current_user.get()
    return Div(
        UserBadge(user=user),
        AuthGuard(
            Div(Heading("Admin Panel")),
            user=user,
            role="admin",
            fallback=LoginForm(action="/api/auth/login")
        )
    )
```

---

## 6. CLI Management

```bash
# Generate a cryptographically secure app secret key
voodoo auth secret-key

# Hash a password
voodoo auth hash-password "mypassword"

# Generate an API key
voodoo auth generate-key --name "Stripe-Webhook"
```
