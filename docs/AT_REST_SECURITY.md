# At-rest security decision

## Decision

Production Profile 1 uses **host/filesystem encryption** for Store files,
backups, object bytes, and secret material. Voodoo Store provides integrity and
recovery protections—checksummed headers/records, single-writer locking,
verified backups, and same-major format checks—but it does not encrypt record
contents itself.

Operators must place the Store path and backup destination on an encrypted
volume or managed disk (for example FileVault, LUKS, BitLocker, or a cloud
provider’s encrypted volume) and restrict permissions to the Runtime account.
Backups must inherit equivalent encryption and access controls; copying a
verified file to an unencrypted location is not a production backup.

## Scope and non-goals

- Application-level field/object encryption is not currently promised.
- Store-native encryption is not currently implemented and must not be implied
  by `Store.verify()` or a successful backup manifest.
- Checksums detect corruption/tampering; they do not provide confidentiality.
- Secrets remain in the configured secret manager/encrypted secret store and
  must never be written to telemetry, manifests, or error messages.

A future Store-native encryption design requires an architecture decision,
key-rotation contract, migration fixtures, and a separate recovery campaign.
