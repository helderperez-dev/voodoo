# Voodoo Component Lab

The Component Lab is Voodoo's visual and behavioral acceptance application. It
uses public framework APIs only and intentionally contains no application CSS.

Run it locally:

```bash
voodoo dev examples.web.component_lab.main:app
```

Routes cover foundations, application shell, chat/AI, auth, forms, navigation,
advanced interactions, data-heavy UI, desktop workspace, Runtime/system
surfaces and feedback states.

## Real-browser acceptance

Install the optional browser tooling and Chromium:

```bash
uv sync --extra browser
uv run playwright install chromium
```

Then run:

```bash
VOODOO_BROWSER_TESTS=1 uv run pytest tests/browser/test_component_lab_browser.py
```

The browser contract checks keyboard/dialog behavior, tab activation, input
focus, theme switching and mobile horizontal overflow. Screenshot regression
will build on this harness once browser provisioning is enabled in the release
workflow.
