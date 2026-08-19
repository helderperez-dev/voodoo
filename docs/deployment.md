# Deployment

## What it is

Voodoo runs on standard ASGI. The built-in dev server (`voodoo dev`) uses uvicorn. For production, use uvicorn or gunicorn with uvicorn workers.

## Minimal example

```bash
# Development
voodoo dev

# Production
# `voodoo dev` auto-discovers the app; for manual ASGI deployment use:
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Common usage

### With gunicorn

```bash
# `voodoo dev` auto-discovers the app; for gunicorn use:
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Environment configuration

```bash
export VOODOO_ENV=production
export VOODOO_SECRET_KEY="your-secure-secret-key"
export VOODOO_DB_PATH="/data/app.db"
export VOODOO_PORT=8000
export VOODOO_HOST=0.0.0.0
```

### PostgreSQL in production (Sprint 11)

For a server-backed deployment, point the database, queue, and event bus at
PostgreSQL. Install the optional extra and set the provider + URL:

```bash
pip install "voodoo-framework[postgres]"

export VOODOO_DATABASE_PROVIDER=postgres
export VOODOO_DATABASE_URL="postgresql://voodoo:voodoo@db:5432/voodoo"
export VOODOO_QUEUE_PROVIDER=postgres
export VOODOO_EVENTS_PROVIDER=postgres
```

The queue and event bus reuse the same `VOODOO_DATABASE_URL` when their own
URLs are unset. The app lifespan runs the durable execution store on
PostgreSQL automatically when `database.provider: postgres`; the scheduler
remains SQLite-backed (documented).

### S3/R2 object storage in production (Sprint 12)

For uploads and static objects at scale, point the object store at any
S3-compatible endpoint — AWS S3, MinIO, or Cloudflare R2. Install the
optional extra and set the provider + credentials:

```bash
pip install "voodoo-framework[s3]"

export VOODOO_OBJECTS_PROVIDER=s3
export VOODOO_BUCKET="my-bucket"
# MinIO / R2 / local S3-compatible endpoints (AWS uses its default endpoint):
export VOODOO_OBJECTS_ENDPOINT="https://<account>.r2.cloudflarestorage.com"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="auto"   # R2; omit for AWS default
```

The `s3` provider automatically selects path-style addressing for non-AWS
endpoints (MinIO, R2) and virtual-hosted style for AWS. It supports
presigned GET/PUT URLs, checksum + content-type metadata, and multipart
uploads for objects ≥ 8 MiB. Without the extra installed (or without
credentials), the object store falls back to the local filesystem provider
(`VOODOO_OBJECTS_DIR`, default `.voodoo/objects`).

For local development parity, run MinIO and point the contract tests at it:

```bash
just minio-up
export VOODOO_TEST_S3_ENDPOINT=http://localhost:9000
export VOODOO_TEST_S3_BUCKET=voodoo-test
export VOODOO_TEST_S3_KEY=minioadmin
export VOODOO_TEST_S3_SECRET=minioadmin
uv run pytest tests/contracts/test_objectstore_s3.py -q
```

### Redis queue + cache in production (Sprint 13)

For a shared, durable, multi-process queue and a TTL-capable cache, point
them at Redis. Install the optional extra and set the provider + URL:

```bash
pip install "voodoo-framework[redis]"

export VOODOO_QUEUE_PROVIDER=redis
export VOODOO_QUEUE_URL="redis://redis:6379/0"
export VOODOO_CACHE_PROVIDER=redis
export VOODOO_CACHE_URL="redis://redis:6379/0"
```

The URL resolves from the provider's own `url` → `VOODOO_QUEUE_URL` /
`VOODOO_CACHE_URL` → `VOODOO_REDIS_URL` → `extra.host`/`port`/`db` →
`redis://localhost:6379/0`. `RedisQueue` implements the full `VoodooQueue`
protocol (priority, delayed delivery, idempotency keys, lease-based claiming,
per-status stats) via atomic Lua scripts; `RedisCache` implements
`VoodooCache` with TTL + durability.

**Durability note:** Redis is an in-memory store — for production durability
enable AOF persistence (`appendonly yes`) or run a managed service (Redis
Enterprise, AWS ElastiCache, Upstash) with persistence enabled. `RedisQueue`
declares `at_least_once` delivery and `best_effort` ordering honestly; if you
need exactly-once or strict ordering, use the PostgreSQL queue instead.

For local development parity, run Redis and point the contract tests at it:

```bash
just redis-up
export VOODOO_TEST_REDIS_URL=redis://localhost:6379/0
uv run pytest tests/contracts/test_queue_redis.py tests/contracts/test_cache_redis.py -q
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install voodoo-framework
EXPOSE 8000
# `voodoo dev` auto-discovers the app; for Docker use:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Docker Compose

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - VOODOO_ENV=production
      - VOODOO_SECRET_KEY=${SECRET_KEY}
      - VOODOO_DB_PATH=/data/app.db
    volumes:
      - app-data:/data
volumes:
  app-data:
```

## Advanced

### Running behind a reverse proxy

Voodoo works behind nginx, Caddy, or any HTTP reverse proxy:

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

### Security headers in production

In production mode (`VOODOO_ENV=production`), Voodoo automatically:
- Sets `Secure` flag on auth cookies
- Enables HSTS headers
- Enforces HTTPS on cookies

### Graceful shutdown

Voodoo's lifespan handler starts/stops background workers. ASGI servers handle SIGTERM gracefully:
- Workers are cancelled
- Database connections are closed

## API reference

- `App.run(host=None, port=None, *, reload=False)` — start the dev server.
- `create_app(app_dir="app")` — build a Starlette app (for manual ASGI deployment).
- `voodoo dev` — CLI dev server with hot-reload.
- `voodoo routes` — list all registered routes.
