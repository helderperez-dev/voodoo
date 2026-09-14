"""JSON Schema export for Voodoo protocol entities.

Usage::

    from voodoo.protocol import export_json_schemas

    schemas = export_json_schemas()
"""

from __future__ import annotations

import json
from typing import Any

from .fabric import FABRIC_PROTOCOL_ENTITIES
from .operational import OPERATIONAL_PROTOCOL_ENTITIES
from .schemas import PROTOCOL_ENTITIES, SCHEMA_VERSION

__all__ = [
    "export_json_schemas",
    "export_json_schemas_json",
    "schema_for",
]


def _entities() -> dict[str, Any]:
    return {
        **PROTOCOL_ENTITIES,
        **OPERATIONAL_PROTOCOL_ENTITIES,
        **FABRIC_PROTOCOL_ENTITIES,
    }


def export_json_schemas() -> dict[str, Any]:
    """Export JSON Schema for all stable protocol entities."""
    schemas: dict[str, Any] = {}
    for name, model in _entities().items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"urn:voodoo:protocol:{name.lower()}:{SCHEMA_VERSION}"
        schema["x-voodoo-schema-version"] = SCHEMA_VERSION
        schemas[name] = schema
    return schemas


def export_json_schemas_json(indent: int = 2) -> str:
    """Export all protocol schemas as a JSON string."""
    return json.dumps(export_json_schemas(), indent=indent, default=str)


def schema_for(entity_name: str) -> dict[str, Any]:
    """Get JSON Schema for a single protocol entity by name."""
    model = _entities()[entity_name]
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:voodoo:protocol:{entity_name.lower()}:{SCHEMA_VERSION}"
    schema["x-voodoo-schema-version"] = SCHEMA_VERSION
    return schema
