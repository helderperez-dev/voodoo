from voodoo.observability.store import telemetry_store
from voodoo.routing.api import api


@api.get("/voodoo/metrics")
async def get_metrics() -> dict[str, object]:
    return telemetry_store.get_summary()
