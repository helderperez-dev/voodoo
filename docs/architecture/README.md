# Architecture

Voodoo architecture documentation is split by purpose:

- [Repository architecture](repository.md) — canonical domains, dependency
  direction, tests, docs, examples, and package-root law.
- [Architecture governance](governance.md) — mandatory placement rules,
  invariants, PR checklist, and release rule for future changes.
- [Repository migration map](repository-migration.md) — final RA1–RA6 ownership
  decisions and retained compatibility surfaces.

For runtime behavior and public API evolution, follow the corresponding concept
and reference documents. Repository governance is intentionally separate from
runtime semantics: directory structure must express the model without becoming
the model itself.
