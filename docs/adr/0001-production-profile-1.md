# ADR-0001: Production Profile 1 is single-node and single-writer

- **Status:** Accepted
- **Date:** 2026-10-06
- **Owners:** Voodoo Framework and Voodoo Store maintainers
- **Scope:** Framework Runtime, Store integration, generated applications, and
  the release/support contract

## Decision

The first supported production profile is deliberately local-first:

1. one application instance;
2. one Voodoo Runtime process;
3. one Voodoo Store writer for each Store path;
4. multiple isolated authenticated browser sessions; and
5. durable local state with verified backup and restore.

Runtime remains the authority for lifecycle, authorization, session ownership,
effects, and retries. Store owns durable mechanics, checksums, recovery, and
format compatibility. Applications must use the documented Store backup and
restore contract rather than copying an active Store file while Runtime is
writing.

## Consequences

- The default deployment is understandable, observable, and testable without
  implying distributed consistency that the implementation does not provide.
- A second Runtime process must use a different Store path unless a future
  profile explicitly defines coordination and ownership.
- Operational readiness includes startup validation, readiness/health checks,
  verified backups, restore drills, graceful shutdown, and actionable failure
  logs.
- Features that need coordination across processes must first define their
  consistency, failure, authorization, and migration semantics; they do not
  silently bypass Runtime or Store ownership.

## Explicit non-goals

Profile 1 does not promise replication, automatic failover, consensus,
multi-writer Store access, cluster-wide rate limits, cross-process workflow
coordination, or zero-downtime distributed upgrades. Those require a separate
architecture decision and a separately tested production profile.

## Evidence and operating procedure

- Security boundaries and residual risks: [`THREAT_MODEL.md`](../THREAT_MODEL.md)
- Deployment, backup, restore, and incident procedure:
  [`PRODUCTION_PROFILE_1_RUNBOOK.md`](../PRODUCTION_PROFILE_1_RUNBOOK.md)
- Framework/Store version and format policy: repository-level
  [`COMPATIBILITY.md`](../../../COMPATIBILITY.md)

Changes to the supported profile must update this ADR, the runbook, the threat
model, compatibility policy, and the relevant release gates in the same change.
