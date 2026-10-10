# Production Profile 1 runbook

Production Profile 1 is intentionally single-node: one Runtime process and one
Voodoo Store writer. Do not run multiple writers against the same Store path.

## Before deploy

1. Set `VOODOO_ENV=production` and a high-entropy `VOODOO_SECRET_KEY`.
2. Configure explicit allowed CORS origins, secure cookies, HSTS, and CSRF.
3. Install the encrypted secrets extra and provision its key through the host
   secret manager; never commit the key or local secret file.
4. Run `voodoo doctor --json` and verify the Store path is writable.
5. Create and verify an initial backup using the Store backup contract.
6. Confirm the Store path and backup destination use encrypted host/filesystem
   storage; Store checksums provide integrity, not confidentiality.

## Backup and restore drill

```python
from pathlib import Path
from voodoo_store import Store

source = Path(".voodoo/application.vstore")
backup = Path("backups/application.vstore")
restored = Path("/tmp/voodoo-restored.vstore")

with Store.open(source) as store:
    store.backup_to(backup)

assert Store.verify(backup).store_id
Store.restore_copy(backup, restored)
assert Store.verify(restored).store_id
```

Destroy the disposable restored copy after validating semantic records. A
backup that fails verification must never be activated.

For the disposable disaster-recovery rehearsal, run the same retained-release
fixture used by the release preflight from the `voodoo-store` checkout:

```bash
uv run python scripts/dr_game_day.py \
  --fixture tests/fixtures/legacy-0.2.2.vstore
```

The command must finish with a JSON record whose `status` is `passed`. Preserve
that record with the release evidence; it proves manifest verification,
corruption rejection, restore, compaction, and a post-process-boundary reopen.
The minimum success envelope is `{"status": "passed"}`; additional fields
identify the fixture, format, and restored/compacted key counts.
This local rehearsal complements (and does not replace) the scheduled hosted
game-day run against the published artifact.

## Shutdown and incident response

- Stop accepting new work, then allow in-flight Runtime work to drain or be
  cancelled according to its retry policy.
- Stop the Runtime before replacing or copying the active Store file.
- On disk-full, corruption, or failed verification, preserve the original file
  and logs, switch to the last verified backup, and record the Store/framework
  versions from `COMPATIBILITY.md`.
- After recovery, run the restore drill and inspect Store health before traffic
  is re-enabled.

## Diagnosis and maintenance

Check the deployment probes before opening traffic: `GET /healthz` is process
liveness only, while `GET /readyz` is the Store/recovery/capacity readiness
decision. A non-ready response must keep the instance out of rotation. The
`/status` response includes an `attention` mapping with safe next actions for
each degraded or down service; do not copy raw provider errors into incident
notes.

Start with read-only evidence and preserve the active file before attempting a
write or repair:

```bash
voodoo-store inspect .voodoo/application.vstore
voodoo-store verify .voodoo/application.vstore
```

Record the Store/framework versions, file size, format, pending transactions,
capacity pressure, queue lag, commit errors, and lock-contention counters in
the incident log. A failed `verify` is an incident signal; do not repeatedly
reopen or mutate the file while investigating.

For compaction, stop the Runtime, create a verified backup, and write to a
new destination only:

```bash
voodoo-store compact-copy .voodoo/application.vstore /data/application.compacted.vstore
voodoo-store verify /data/application.compacted.vstore
```

Compare the compacted health report and representative application records
before an operator-controlled activation. Never compact in place and never
delete the source or backup until the replacement has passed verification.

Repair is deliberately separate from inspection. Torn-tail recovery may be
performed only after preserving the original and confirming the failure is at
the physical tail; corruption in a previously valid prefix requires restore
from a verified backup or an explicit migration, not an automatic repair.

## Rollback decision

- **Failed startup/readiness:** keep the original Store untouched, restore the
  most recent verified backup to a fresh path, and inspect health before traffic.
- **Failed upgrade or migration:** stop the Runtime and restore the retained
  pre-upgrade artifact to a fresh path; do not overwrite the active file.
- **Suspected corruption:** preserve the file and logs, run `verify` once, then
  use the last verified backup. Retain the corrupt artifact for forensic review.
- **Disk full/quota:** stop writes, free or expand the documented capacity,
  verify the file, and only then resume; do not treat `DiskFull` as a missing
  record or silently retry without bounds.

Profile 1 does not promise replication, automatic failover, cluster-wide rate
limits, or multi-writer operation.
