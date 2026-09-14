# Store-first migration and compatibility

Voodoo Store is the default durable substrate for new Voodoo applications.
Existing SQLite/PostgreSQL/Redis/S3 configurations remain explicit adapters;
Sprint 28 does not silently reinterpret or migrate external data.

## Rules

1. A fresh application uses `.voodoo/application.vstore` by default.
2. Existing explicit provider configuration keeps its meaning.
3. Removing an explicit legacy provider opts that domain into the Store-first path.
4. Voodoo never copies production data from SQLite/PostgreSQL/Redis/S3 into Store during startup.
5. Migration is an operator-controlled export/import operation with verification and rollback.
6. Store files are node-local. Do not place one `.vstore` on a shared filesystem and open it from multiple nodes.
7. Multi-node scaling uses Runtime routing and explicit ownership before any future Store replication protocol.

## Recommended migration sequence

```text
1. upgrade Framework + voodoo-store
2. keep existing explicit adapters enabled
3. verify application behavior
4. migrate one infrastructure domain at a time
5. verify the resulting application.vstore
6. retain the old data source as rollback evidence
7. remove the explicit adapter only after acceptance
```

## Provider overrides

The Runtime semantic layer is unchanged by an adapter override:

```toml
# Store-first defaults remain for every unspecified domain.

[database]
provider = "postgres"
url = "..."

[queue]
provider = "redis"

[objects]
provider = "s3"
```

An override changes persistence/transport mechanics for that domain. It does not
create another Identity, Capability, Policy or Execution model.

## SQLite

SQLite is supported as an explicit compatibility adapter. It is no longer a hidden
fresh-application default. Existing SQLite applications should keep
`database.provider = "sqlite"` until their data is intentionally migrated.

## Verification and backup

Use:

```text
voodoo fabric verify
voodoo fabric health
voodoo fabric backup backups/application.vstore
```

`fabric backup` is intentionally a cold backup: it must acquire the Store writer lock
before copying the file and verifies the destination afterward. It refuses to present
a live multi-writer copy as safe.

## Distributed migration

Do not migrate by making multiple nodes share one Store file. Give each Voodoo Node
its own local Store and advertise ownership through Runtime membership. Routing moves
work to the owner; future replication/sync is a separate protocol concern.
