# Voodoo Production Profile 1 threat model

This document defines the security boundary for the supported single-process,
single-Store-writer production profile. It is intentionally narrower than a
distributed deployment claim.

## Assets and trust boundaries

| Asset | Boundary | Required control |
|---|---|---|
| Authenticated sessions and principals | Browser ↔ HTTP/WebSocket | Secure cookies, CSRF/origin checks, session-scoped bindings, revalidation at privileged events |
| Runtime intents, capabilities, and effects | Application code ↔ Runtime | Capability resolution and policy checks at execution/effect boundaries; idempotent effect IDs |
| Store files and backups | Host filesystem ↔ Runtime/Store | One writer, owner-only paths, checksum verification, same-major format policy, verified restore |
| Secrets and signing keys | Environment/filesystem ↔ process | Production startup validation, encrypted secret store, redacted logs |
| Uploaded objects | Request ↔ object adapter | Size/path validation, adapter authorization, no traversal, explicit public URLs |
| Generated projects and docs | Framework package ↔ developer machine | Offline canonical scaffold, executable import/docs checks, dependency audit |

## Threats and mitigations

- **Cross-user state leakage:** UI state, bindings, patches, and WebSocket
  messages are scoped to a `UISession`; regression tests cover two-user and
  disconnect/reconnect behavior.
- **Request forgery and origin spoofing:** production CSRF, same-origin CORS,
  WebSocket origin validation, and trusted-proxy configuration are mandatory.
- **Privilege escalation through tools or agents:** agents are Compute; Runtime
  capability and policy checks remain authoritative before effects execute.
- **Store corruption or torn writes:** checksummed headers/records, recovery
  fault tests, crash tests, verified backups, and retained restore fixtures.
- **Secret disclosure:** encrypted secret storage and structured redaction are
  required; plaintext fallback is development-only and production startup fails.
- **Path traversal/object abuse:** object adapters validate keys and constrain
  local paths; uploads have bounded size and explicit authorization.
- **Supply-chain compromise:** Python/Rust advisory audits, SBOMs, checksums,
  trusted publishing, and provenance attestations are release gates.

## Residual risks and non-goals

Production Profile 1 does not provide multi-writer Store semantics, consensus,
replication, cluster-wide rate limiting, or automatic failover. Operators must
use one Runtime process per Store file and follow the backup/restore runbook.

Report suspected vulnerabilities through the private process in
[`SECURITY.md`](../SECURITY.md); do not disclose exploitable details in public
issues before a fix and advisory are coordinated.
