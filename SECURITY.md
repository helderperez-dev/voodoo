# Security Policy

## Supported Versions

Voodoo is actively developed and the latest release on `main` is always
the supported version. Security fixes are backported to the most recent
minor release line.

| Version | Supported          |
| ------- | ------------------ |
| 1.15.x  | ✅ Current release |
| < 1.15  | ❌ Not supported   |

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

Voodoo includes several security features enabled by default:

- **CSRF Protection** — Double-submit cookie with cryptographic validation
- **Security Headers** — CSP, HSTS, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, Permissions-Policy
- **CORS** — Configurable origin validation
- **Rate Limiting** — Token bucket / sliding window limiter
- **Input Sanitization** — HTML escaping and XSS prevention
- **JWT Authentication** — HS256 with expiration and revocation
- **API Key Management** — High-entropy keys with SHA256 hashed storage
- **RBAC** — Role-based access control with declarative guards

### Production hardening checklist

Before deploying Voodoo to production:

- [ ] Set `VOODOO_SECRET_KEY` to a cryptographically secure random value
      (`voodoo auth secret-key` generates one)
- [ ] Set `VOODOO_ENV=production` (disables debug mode)
- [ ] Configure CORS to only allow your actual origins
- [ ] Set a restrictive Content-Security-Policy
- [ ] Enable HSTS with an appropriate `max-age`
- [ ] Configure rate limiting for sensitive endpoints
- [ ] Use HTTPS (terminate TLS at a reverse proxy or load balancer)
- [ ] Set `VOODOO_TOKEN_EXPIRY` to an appropriate value for your app
- [ ] Review and restrict database permissions

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
