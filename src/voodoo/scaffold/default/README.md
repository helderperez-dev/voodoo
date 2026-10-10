# {{ project_name }}

A Voodoo application created with `voodoo new`.

This scaffold targets Framework 3.2.x on Python 3.12 or newer.

Run the development server with:

```bash
voodoo dev
```

Install the optional quality tools when working on the generated project:

```bash
python -m pip install -e ".[dev]"
ruff check app tests
mypy app
pytest -q
```

The generated repository also includes a Chromium browser/accessibility smoke
workflow under `.github/workflows/quality.yml`; it starts the app and checks the
semantic landing-page contract.

Routes are defined by files under `app/`. Start with `app/page.py`, then add
folders for nested and dynamic routes.

For production, set `VOODOO_ENV=production`, provide a unique
`VOODOO_SECRET_KEY` with at least 32 characters, configure explicit CORS
origins, keep CSRF enabled for cookie authentication, and run `voodoo doctor`.
