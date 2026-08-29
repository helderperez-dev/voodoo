"""JSON Schema export for Voodoo protocol entities.

Usage::

    from voodoo.protocol import export_json_schemas

    # Export all schemas as a dict
    schemas = export_json_schemas()

    # Write to a file
    import json
    with open("voodoo-protocol.json", "w") as f:
        json.dump(schemas, f, indent=2)
"""

from __future__ import annotations

import json
from typing import Any

from .schemas import PROTOCOL_ENTITIES, SCHEMA_VERSION

__all__ = [
    "export_json_schemas",
    "export_json_schemas_json",
    "schema_for",
]


def export_json_schemas() -> dict[str, Any]:
    """Export JSON Schema for all protocol entities.

    Returns a dict keyed by entity name, where each value is the
    JSON Schema for that entity (draft 2020-12).
    """
    schemas: dict[str, Any] = {}
    for name, model in PROTOCOL_ENTITIES.items():
        schema = model.model_json_schema()
        # Add protocol-level metadata
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"urn:voodoo:protocol:{name.lower()}:{SCHEMA_VERSION}"
        schema["x-voodoo-schema-version"] = SCHEMA_VERSION
        schemas[name] = schema
    return schemas


def export_json_schemas_json(indent: int = 2) -> str:
    """Export all protocol schemas as a JSON string."""
    return json.dumps(export_json_schemas(), indent=indent, default=str)


def schema_for(entity_name: str) -> dict[str, Any]:
    """Get JSON Schema for a single protocol entity by name.

    Parameters
    ----------
    entity_name:
        The entity name (e.g. "Execution", "Intent").

    Returns
    -------
    dict:
        The JSON Schema for the entity.

    Raises
    ------
    KeyError:
        If the entity name is not a known protocol entity.
    """
    model = PROTOCOL_ENTITIES[entity_name]
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:voodoo:protocol:{entity_name.lower()}:{SCHEMA_VERSION}"
    schema["x-voodoo-schema-version"] = SCHEMA_VERSION
    return schema
