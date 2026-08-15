from typing import Any

from voodoo.api import api
from voodoo.components import Card, Div, Heading
from voodoo.data import get_db
from voodoo.i18n import _
from voodoo.queue import _queues, _worker_tasks
from voodoo.storage import storage


async def check_database() -> dict[str, Any]:
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        return {"status": "Operational", "latency": "ok"}
    except Exception as e:
        return {"status": "Down", "error": str(e)}


async def check_queue() -> dict[str, Any]:
    try:
        total_workers = len(_worker_tasks)
        active_queues = len(_queues)
        return {
            "status": "Operational" if total_workers > 0 else "Degraded",
            "workers": total_workers,
            "queues": active_queues,
        }
    except Exception as e:
        return {"status": "Down", "error": str(e)}


async def check_storage() -> dict[str, Any]:
    try:
        if storage.use_s3 and storage.s3_client:
            return {"status": "Operational", "type": "S3"}
        else:
            import os

            if os.path.exists(storage.base_dir):
                return {"status": "Operational", "type": "Local"}
            return {"status": "Degraded", "type": "Local", "error": "Dir missing"}
    except Exception as e:
        return {"status": "Down", "error": str(e)}


async def check_agent() -> dict[str, Any]:
    # Placeholder for Agent connectivity
    return {"status": "Operational", "provider": "Simulated"}


@api.get("/status")
async def get_status():
    db_health = await check_database()
    queue_health = await check_queue()
    storage_health = await check_storage()
    agent_health = await check_agent()

    status_code = 200
    if any(
        s["status"] == "Down"
        for s in [db_health, queue_health, storage_health, agent_health]
    ):
        status_code = 503

    return {
        "services": {
            "database": db_health,
            "queue": queue_health,
            "storage": storage_health,
            "agent": agent_health,
        },
        "overall": "Operational" if status_code == 200 else "Down",
    }


@api.get("/status/locales")
async def get_status_locales():
    return {
        "database": _("status.database"),
        "queue": _("status.queue"),
        "storage": _("status.storage"),
        "agent": _("status.agent"),
        "Operational": _("status.operational"),
        "Degraded": _("status.degraded"),
        "Down": _("status.down"),
    }


class ServiceStatus(Div):
    def __init__(self, **kwargs):
        # Provide default glass aesthetics for the card
        classes = kwargs.pop("className", "")
        card_classes = f"bg-[var(--color-surface)] border-[var(--color-border)] backdrop-blur-xl {classes}".strip()
        super().__init__(
            Card(
                Heading(
                    _("status.title"),
                    level=2,
                    className="text-xl font-semibold mb-6 text-[var(--color-text)] tracking-tight",
                ),
                Div(id="service-status-container", className="space-y-3"),
                Div(
                    """
                    <script>
                        async function fetchStatus() {
                            try {
                                const [resStatus, resLocales] = await Promise.all([
                                    fetch('/status'),
                                    fetch('/status/locales')
                                ]);
                                const data = await resStatus.json();
                                const locales = await resLocales.json();

                                const container = document.getElementById('service-status-container');
                                let html = '';
                                for (const [service, info] of Object.entries(data.services)) {
                                    let color = info.status === 'Operational' ? 'text-green-400' : (info.status === 'Degraded' ? 'text-yellow-400' : 'text-red-400');
                                    let dot = info.status === 'Operational' ? 'bg-green-400' : (info.status === 'Degraded' ? 'bg-yellow-400' : 'bg-red-400');
                                    let serviceName = locales[service] || service;
                                    let statusName = locales[info.status] || info.status;
                                    html += `
                                        <div class="flex items-center justify-between p-3 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] backdrop-blur-sm">
                                            <div class="flex items-center space-x-3">
                                                <div class="w-2.5 h-2.5 rounded-full ${dot} shadow-[0_0_8px_rgba(0,0,0,0.5)] shadow-${dot.replace('bg-', '')}"></div>
                                                <span class="capitalize text-[var(--color-text)] font-medium tracking-wide">${serviceName}</span>
                                            </div>
                                            <span class="${color} font-semibold text-sm tracking-wide">${statusName}</span>
                                        </div>
                                    `;
                                }
                                container.innerHTML = html;
                            } catch (e) {
                                console.error('Failed to fetch status', e);
                            }
                        }
                        fetchStatus();
                        setInterval(fetchStatus, 10000);
                    </script>
                    """
                ),
                className=card_classes,
                **kwargs,
            )
        )
