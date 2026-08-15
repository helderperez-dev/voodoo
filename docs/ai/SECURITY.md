# Voodoo Security & Hardening

Voodoo incorporates modern security best practices out of the box to safeguard applications against top web vulnerabilities (OWASP Top 10).

## Architecture

Voodoo security includes:
- **CSRF Protection**: Double-submit cookie with cryptographic validation and auto-injected tokens in components.
- **Security Headers Middleware**: Automatic configuration of Content-Security-Policy (CSP), HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
- **Rate Limiting**: Configurable token bucket / sliding window limiter with in-memory or custom storage.
- **CORS Protection**: Origin validation, allowed headers, exposed headers, credentials, and max-age settings.
- **Input Sanitization**: Built-in HTML escaping and XSS prevention utilities.
- **IP Filtering**: Allowlist and blocklist support for sensitive endpoints.

---

## 1. Security Headers Configuration

Configure security headers in `voodoo.yaml` or directly via Python middleware:

```python
from voodoo.security import SecurityHeadersMiddleware, SecurityConfig

app.add_middleware(
    SecurityHeadersMiddleware,
    config=SecurityConfig(
        content_security_policy="default-src 'self'; script-src 'self' 'unsafe-inline';",
        hsts_max_age=31536000,
        frame_options="DENY",
        content_type_options="nosniff",
        referrer_policy="strict-origin-when-cross-origin",
    ),
)
```

---

## 2. CSRF Protection

CSRF is enabled by default for state-changing HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`):

```python
from voodoo.security import CSRFMiddleware

# Added to Voodoo app middleware pipeline
app.add_middleware(CSRFMiddleware, secret_key="your-app-secret-key")
```

In templates and components, forms automatically receive and validate the token:
```python
from voodoo.components import LoginForm

# csrf_token will be rendered as a hidden field
LoginForm(action="/login", csrf_token=request.state.csrf_token)
```

---

## 3. Rate Limiting

Protect endpoints from abuse and brute-force attacks:

```python
from voodoo.security import rate_limit


@rate_limit(requests=5, window_seconds=60)  # Max 5 requests per minute
async def sensitive_api(request):
    return {"message": "Rate limited endpoint"}
```

---

## 4. Input Sanitization & XSS Defense

```python
from voodoo.security import sanitize_html, escape_xss

raw_input = "<script>alert('pwned')</script>Hello"
safe_text = sanitize_html(raw_input)  # "Hello"
escaped_text = escape_xss(raw_input)  # "&lt;script&gt;..."
```
