from voodoo.routing.api import api
from voodoo.telemetry.store import telemetry_store


@api.get("/voodoo/metrics")
async def get_metrics() -> dict[str, object]:
    return telemetry_store.get_summary()
