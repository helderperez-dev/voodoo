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
