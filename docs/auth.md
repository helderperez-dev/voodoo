# Authentication, Identity & Authority

## The separation that matters

Voodoo separates three concerns that must not be collapsed:

```text
Identity                 who/what exists
    ↓
AuthenticationEvidence   how identity was proven
    ↓
Principal                authenticated subject inside the Runtime
    ↓
Capability + Policy      what it may do now
    ↓
Execution                governed work
```

Authentication does **not** automatically grant Runtime Capability. Roles,
scopes and node advertisements may be preserved as claims/context, but they do
not become authority by themselves.

## Runtime Identity

First-class Runtime identity kinds are:

```text
user
agent
service
device
node
```

```python
from voodoo.runtime import (
    AuthenticationEvidence,
    Identity,
    IdentityKind,
    Principal,
)

principal = Principal(
    identity=Identity(id="user:42", kind=IdentityKind.USER),
    evidence=(
        AuthenticationEvidence(
            method="session",
            subject="42",
            issuer="voodoo",
        ),
    ),
)
```

`Principal` intentionally carries no automatic Capability grants.

## Built-in user authentication

The existing web-auth compatibility surface remains available:

```python
from voodoo.auth import User, create_access_token

user, raw_api_key = await User.create_user(
    email="ada@example.com",
    password="SecurePass99!",
    role="admin",
)

user = await User.authenticate("ada@example.com", "SecurePass99!")
token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
```

With the default Runtime configuration, built-in `User` records are persisted
through Voodoo Store in `.voodoo/application.vstore`. SQLite/PostgreSQL user
persistence remains available only when an explicit SQL database adapter is
selected.

## `AuthUser` is a compatibility projection

HTTP middleware/guards still expose `AuthUser` for the 2.x compatibility API.
It can be projected into Runtime-native identity:

```python
principal = auth_user.to_principal()
```

Roles and scopes are copied as non-authoritative claims. For example,
`role="admin"` or `scope="*"` does **not** automatically result in a Runtime
Capability grant.

## Route guards

Route-level compatibility guards remain useful for web access control:

```python
from voodoo import page
from voodoo.auth import require_auth, require_roles


@page("/dashboard")
@require_auth(redirect_url="/login")
async def dashboard(request): ...


@page("/admin")
@require_roles("admin")
async def admin_panel(request): ...
```

These guards answer whether a request may enter a web route. They do not replace
Capability + Policy checks for governed Runtime Effects.

## API key authentication

```python
from voodoo.auth import require_api_key


@api.post("/api/sync")
@require_api_key(scopes=["write"])
async def sync_endpoint(request): ...
```

On the default Store path, API-key lookup reads the built-in user records from
Voodoo Store. Raw API keys are not persisted; their hashes are stored.

## Cookie / bearer authentication

`AuthMiddleware` supports the compatibility request-auth mechanisms used by the
web stack, including API keys, bearer tokens and the auth cookie. A successful
authentication produces request identity context; Runtime code should project
that identity to a `Principal` when entering governed Execution.

```python
from voodoo.auth import clear_auth_cookie, set_auth_cookie
```

## Capability authority

Sensitive Effects must still be explicitly authorized through Runtime
Capability/Policy even for authenticated administrators.

```text
Authenticated admin
       ↓
Principal(claims={roles:[admin]})
       ↓
NO automatic payment.execute capability
       ↓
explicit Capability grant + Policy decision required
```

This prevents authentication mechanisms and legacy RBAC from becoming ambient
Runtime authority.

## Node identity

Nodes use the same Identity model. Authentication can produce a
`Principal(kind=NODE)`, after which membership/discovery may advertise
capabilities/services/resources/ownership.

Advertisement means "this node says it can service X"; it does not mean "this
node is authorized to exercise X". Remote work still passes Capability + Policy
before canonical Execution.

## Secrets in authentication evidence

`AuthenticationEvidence` records non-secret facts such as method, subject,
issuer and timestamps. Never place raw passwords, API keys, bearer tokens or
private keys inside Runtime identity evidence.

## Passwords and API keys

The compatibility auth module provides:

- password hashing/verification;
- API-key generation and hashing;
- JWT creation/validation;
- cookie helpers.

Treat generated raw API keys like credentials: return/display them only at the
appropriate creation boundary and persist only their hash.

## Identity persistence

Runtime-native identity records can be persisted through the Store-backed
identity store. Store owns durable mechanics; Identity semantics remain Runtime
semantics.

Do not infer authorization from persisted identity attributes.

## Current boundaries

The Runtime Identity foundation is not a claim that Voodoo already provides a
production PKI/OIDC/mTLS platform. Enterprise identity federation and managed
credential infrastructure remain future work.

The current contract is:

- first-class Identity/Principal semantics;
- built-in Store-first user persistence;
- compatibility JWT/API-key/cookie auth;
- explicit separation of auth claims from Runtime Capability;
- node/device/service/agent identities represented by the same Runtime model.

## API reference

### Runtime identity

- `Identity`
- `IdentityKind`
- `AuthenticationEvidence`
- `Principal`

### Web-auth compatibility

- `User.create_user()`
- `User.authenticate()`
- `User.find_by_api_key()`
- `AuthUser.to_principal()`
- `require_auth()`
- `require_roles()`
- `require_scopes()`
- `require_api_key()`
- `create_access_token()` / `decode_access_token()`
- password/API-key helpers
- `AuthMiddleware`
