# Security Policy

## Supported Versions

Voodoo is actively developed and the latest release on `main` is always
the supported version. Security fixes are backported to the most recent
minor release line.

| Version | Supported          |
| ------- | ------------------ |
| 3.2.x   | ✅ Current line    |
| < 3.2   | ❌ Not supported   |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in Voodoo, please report it
responsibly:

1. **Email:** **contact@helderperez.com** with the subject
   `[SECURITY] Voodoo — <brief description>`.
2. **Include:**
   - A description of the vulnerability and its potential impact
   - Steps to reproduce (proof of concept, if possible)
   - Affected versions
   - Suggested fix (if you have one)
3. **Do not** disclose the vulnerability publicly until a fix has been
   released.

### Response timeline

| Step                          | Target       |
| ----------------------------- | ------------ |
| Acknowledge receipt           | 48 hours     |
| Initial assessment            | 5 days       |
| Fix or mitigation released    | 30 days      |
| Public disclosure (if agreed) | After fix    |

You will receive updates throughout the process. If a vulnerability is
declined (not reproducible, not a security issue, or expected behavior),
we will explain why.

## Security Features

Voodoo includes development-safe defaults and a fail-closed production profile:

- **CSRF Protection** — Enabled automatically in production; non-cookie
  exemptions require authentication validated by `AuthMiddleware`
- **Security Headers** — CSP, HSTS, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, Permissions-Policy
- **Production CSP** — the production profile defaults `script-src` to
  `'self'` and rejects `unsafe-inline`, `unsafe-eval`, and wildcard script
  sources at configuration validation time. The security middleware adds
  response-bound SHA-256 hashes for inline HTML scripts, while applications
  that need durable inline behavior should migrate it to same-origin assets
  or an explicit nonce/hash policy before deployment.
- **CORS** — Same-origin by default in production; wildcard credentials are
  rejected at startup and denied by middleware
- **Rate Limiting** — Bounded single-process sliding window keyed by validated
  principal or client address
- **Input Sanitization** — HTML escaping and XSS prevention
- **JWT Authentication** — HS256 signature and time-claim validation
- **API Key Management** — High-entropy keys with SHA256 hashed storage
- **RBAC** — Role-based access control with declarative guards

### Production hardening checklist

Before deploying Voodoo to production:

- [ ] Set `VOODOO_SECRET_KEY` to a cryptographically secure random value
      (`voodoo auth secret-key` generates one)
- [ ] Set `VOODOO_ENV=production` (disables debug mode)
- [ ] Configure `VOODOO_CORS_ORIGINS` only when cross-origin access is needed
- [ ] Set a restrictive Content-Security-Policy
- [ ] Keep HSTS and CSRF enabled (production startup rejects disabling them)
- [ ] Configure rate limiting for sensitive endpoints
- [ ] Use HTTPS (terminate TLS at a reverse proxy or load balancer)
- [ ] Set `VOODOO_TOKEN_EXPIRY` to an appropriate value for your app
- [ ] Review and restrict database permissions
- [ ] Install `voodoo-framework[secrets]` before using `LocalSecretStore`; it
      never falls back to plaintext

## Dependency Security

Voodoo's dependencies are pinned in `uv.lock`. To audit for known
vulnerabilities:

```bash
uv audit   # or: pip-audit
```

Security-related dependencies:

- `python-dotenv` — environment variable loading (never commit `.env`)
- `pydantic` — input validation and settings management
- `starlette` — ASGI framework with built-in security middleware

## Responsible Disclosure

We appreciate responsible disclosure and will credit researchers in
release notes (unless they prefer to remain anonymous). We do not offer
monetary bounties at this time.
