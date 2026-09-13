"""Built-in operational dashboard for local/runtime inspection."""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from voodoo.runtime.operations import OperationalRuntime

__all__ = ["runtime_dashboard"]


def runtime_dashboard(
    inspector: OperationalRuntime,
    *,
    path: str = "/_voodoo/runtime",
) -> Callable[[Any], None]:
    """Return an ``App.use`` plugin mounting runtime dashboard + JSON API."""

    def plugin(app: Any) -> None:
        async def dashboard(request: Request) -> HTMLResponse:
            return HTMLResponse(_render(inspector.snapshot()))

        async def runtime_json(request: Request) -> JSONResponse:
            return JSONResponse(inspector.snapshot())

        app.starlette.routes.append(Route(path, dashboard, methods=["GET"]))
        app.starlette.routes.append(Route(f"{path}/api", runtime_json, methods=["GET"]))

    return plugin


def _render(snapshot: dict[str, Any]) -> str:
    summary = snapshot["summary"]
    goals = snapshot["goals"]
    executions = snapshot["executions"]
    approvals = snapshot["approvals"]
    entities = snapshot["entities"]

    cards = "".join(
        _card(label, value)
        for label, value in (
            ("Executions", summary["executions"]),
            ("Active", summary["active_executions"]),
            ("Goals", summary["goals"]),
            ("Approvals", summary["pending_approvals"]),
            ("Entities", summary["entities"]),
        )
    )
    goal_rows = "".join(
        _row(
            goal["goal"]["name"],
            goal["goal"]["status"],
            f"{goal['current_index']}/{len(goal['planned_intents'])}",
            goal["goal"]["id"],
        )
        for goal in goals
    ) or _empty("No goals yet")
    execution_rows = "".join(
        _row(
            (item.get("intent") or {}).get("name", "execution"),
            item["status"],
            item.get("actor", "system"),
            item["id"],
        )
        for item in executions[:50]
    ) or _empty("No executions yet")
    approval_rows = "".join(
        _row(
            item.get("capability") or "approval",
            item["status"],
            item.get("requested_by") or "system",
            item["execution_id"],
        )
        for item in approvals
    ) or _empty("No pending approvals")
    entity_rows = "".join(
        _row(
            item["id"],
            item["type"],
            f"{item['observation_count']} observations",
            f"{item['relationship_count']} relationships",
        )
        for item in entities[:50]
    ) or _empty("No world entities")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voodoo Runtime</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#09090b; color:#f4f4f5; }}
main {{ max-width:1180px; margin:auto; padding:48px 28px 80px; }}
header {{ display:flex; justify-content:space-between; align-items:end; gap:20px; margin-bottom:32px; }}
h1 {{ margin:0; font-size:30px; letter-spacing:-.04em; }}
.sub {{ color:#a1a1aa; font-size:14px; margin-top:7px; }}
.badge {{ border:1px solid #3f3f46; border-radius:999px; padding:7px 11px; color:#d4d4d8; font-size:12px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:32px; }}
.card, section {{ background:#111113; border:1px solid #27272a; border-radius:16px; }}
.card {{ padding:18px; }} .metric {{ font-size:28px; font-weight:700; }} .label {{ color:#a1a1aa; font-size:12px; margin-top:5px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
section {{ overflow:hidden; }} section h2 {{ font-size:14px; margin:0; padding:16px 18px; border-bottom:1px solid #27272a; }}
.row {{ display:grid; grid-template-columns:1.5fr .8fr 1fr 1.4fr; gap:12px; padding:13px 18px; border-bottom:1px solid #1f1f22; font-size:12px; align-items:center; }}
.row:last-child {{ border-bottom:0; }} .status {{ color:#c4b5fd; }} .muted {{ color:#71717a; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.empty {{ padding:24px 18px; color:#71717a; font-size:13px; }}
@media (max-width:800px) {{ .grid {{ grid-template-columns:1fr; }} .row {{ grid-template-columns:1.3fr .8fr; }} .row > :nth-child(n+3) {{ display:none; }} }}
</style>
</head>
<body><main>
<header><div><h1>Voodoo Runtime</h1><div class="sub">Operational state, agency, approvals and world projection.</div></div><div class="badge">live projection</div></header>
<div class="cards">{cards}</div>
<div class="grid">
<section><h2>Goals</h2>{goal_rows}</section>
<section><h2>Pending approvals</h2>{approval_rows}</section>
<section><h2>Executions</h2>{execution_rows}</section>
<section><h2>World entities</h2>{entity_rows}</section>
</div>
</main></body></html>"""


def _card(label: str, value: Any) -> str:
    return f'<div class="card"><div class="metric">{html.escape(str(value))}</div><div class="label">{html.escape(label)}</div></div>'


def _row(primary: Any, status: Any, detail: Any, identifier: Any) -> str:
    return (
        '<div class="row">'
        f"<div>{html.escape(str(primary))}</div>"
        f'<div class="status">{html.escape(str(status))}</div>'
        f'<div class="muted">{html.escape(str(detail))}</div>'
        f'<div class="muted">{html.escape(str(identifier))}</div>'
        "</div>"
    )


def _empty(message: str) -> str:
    return f'<div class="empty">{html.escape(message)}</div>'
