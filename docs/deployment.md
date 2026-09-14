# Deployment

## What it is

Voodoo is a standard ASGI application, but its default durable substrate is an
embedded Voodoo Store. That changes one important deployment rule:

> **One Voodoo Runtime process owns one local `.vstore` writer.**

Do not run multiple OS workers against the same `application.vstore` file.
Horizontal scale is modeled as multiple Voodoo Nodes, each with its own local
Store, rather than multiple processes sharing one Store file.

## Development

```bash
voodoo dev
```

The default Store is created at:

```text
.voodoo/application.vstore
```

## Production: one Store-backed node

Run one ASGI worker for one local Store:

```bash
export VOODOO_ENV=production
export VOODOO_SECRET_KEY="replace-with-a-real-secret"
export VOODOO_STORE_PATH="/data/application.vstore"

uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

`--workers 1` is intentional. The Store rejects conflicting live writers rather
than pretending a shared-file multi-writer topology is safe.

## Horizontal scale

Scale by adding Voodoo Nodes with node-local Stores:

```text
load balancer / ingress
          |
          +-- Voodoo Node A -> /data/a/application.vstore
          +-- Voodoo Node B -> /data/b/application.vstore
          `-- Voodoo Node C -> /data/c/application.vstore
```

Runtime Fabric membership, discovery, capability/policy-aware placement,
ownership, leases, health and bounded failover determine where governed work
runs. Application semantics should remain topology-agnostic.

Voodoo does **not** currently replicate Store data automatically between those
node-local files. Distributed ownership comes before distributed storage.

## Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install voodoo-framework
ENV VOODOO_ENV=production
ENV VOODOO_STORE_PATH=/data/application.vstore
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

Persist `/data`:

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      VOODOO_ENV: production
      VOODOO_SECRET_KEY: ${SECRET_KEY}
      VOODOO_STORE_PATH: /data/application.vstore
    volumes:
      - app-data:/data

volumes:
  app-data:
```

A second replica must use a different Store path/volume and join as a separate
Voodoo Node. Do not mount one `.vstore` file read-write into multiple replicas.

## Store operations

The Runtime exposes Store/fabric inspection commands:

```bash
voodoo fabric status
voodoo fabric health
voodoo fabric verify
voodoo fabric backup
```

Use `verify` before/after operational maintenance and create backups according
to your recovery policy.

## Explicit PostgreSQL adapter

A workload may explicitly move the database domain to PostgreSQL:

```bash
pip install "voodoo-framework[postgres]"
```

```toml
[database]
provider = "postgres"
url = "postgresql://voodoo:secret@db:5432/voodoo"
```

Or with environment variables:

```bash
export VOODOO_DATABASE_PROVIDER=postgres
export VOODOO_DATABASE_URL="postgresql://voodoo:secret@db:5432/voodoo"
```

This replaces the selected database domain. It does not automatically turn all
other Runtime domains into PostgreSQL-backed services.

## Explicit Redis queue/cache adapter

```bash
pip install "voodoo-framework[redis]"
```

```toml
[queue]
provider = "redis"
url = "redis://redis:6379/0"

[cache]
provider = "redis"
url = "redis://redis:6379/1"
```

Redis durability depends on the Redis deployment configuration. Voodoo does
not upgrade Redis semantics into exactly-once delivery.

## Explicit S3-compatible object adapter

```bash
pip install "voodoo-framework[s3]"
```

```toml
[objects]
provider = "s3"
bucket = "my-bucket"
endpoint = "https://object.example.com"
```

Set the provider credentials using the normal environment variables required by
the configured S3-compatible service.

## Explicit SQLite adapter

SQLite remains available for compatibility or a deliberately selected SQL
workload:

```bash
pip install "voodoo-framework[sqlite]"
```

```toml
[database]
provider = "sqlite"
path = ".voodoo/state/data.db"
```

It is not the default fresh-application backend.

## Reverse proxy

Voodoo works behind nginx, Caddy, or another HTTP reverse proxy. Preserve both
HTTP and WebSocket upgrades:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location /_voodoo_ws {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

location /voodoo/mesh/ws {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## Security in production

Set at least:

```bash
export VOODOO_ENV=production
export VOODOO_SECRET_KEY="a-long-random-production-secret"
```

Production mode enables the production cookie/security behavior configured by
Voodoo. TLS should normally terminate at the reverse proxy/load balancer.

## Graceful shutdown

The App lifespan shuts down Runtime-owned services before closing the Store:
workers, scheduler, execution persistence, data bindings, and finally the
RuntimeStore writer. Give the ASGI process enough termination grace time to
finish that lifecycle.

## Deployment laws

1. one process owns one live local Store writer;
2. never coordinate Voodoo Nodes by sharing a `.vstore` over a network filesystem;
3. use separate node-local Stores for horizontal Runtime Fabric topology;
4. external providers are explicit domain overrides, not hidden defaults;
5. no claim of Store replication, distributed consensus, global transactions,
   or global exactly-once execution;
6. scaling topology must not require rewriting application business semantics.

## API reference

- `App.run(...)` — single-process application server helper.
- `create_app(app_dir="app")` — Starlette/ASGI application factory.
- `voodoo dev` — development server with reload support.
- `voodoo fabric status|health|verify|join|backup` — local fabric/Store operations.
