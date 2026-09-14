"""Store-backed persistence behavior for ``voodoo.data.Model``."""

from __future__ import annotations

import asyncio
from typing import Any, get_type_hints

from voodoo.data.store_backend import (
    delete_record,
    insert_record,
    put_record,
    scan_records,
    should_use_store,
)


class StoreModelMixin:
    """Intercept BaseModel persistence when Voodoo Store is the active backend."""

    @classmethod
    async def find_all(cls, user_context: dict | None = None) -> list[Any]:
        if not should_use_store():
            return await super().find_all(user_context=user_context)

        from voodoo.data.base import _get_table_name, _rls_policies

        rows = scan_records(_get_table_name(cls))
        if user_context is None:
            try:
                from voodoo.auth import current_user

                user = current_user.get()
                if user and user.is_authenticated:
                    user_context = user.to_dict()
            except Exception:
                pass

        table_name = _get_table_name(cls)
        if table_name in _rls_policies and user_context:
            # SQL-string RLS policies are legacy adapter semantics. A native
            # predicate policy will replace this in the Identity/Policy slice.
            raise RuntimeError(
                "SQL-string rls_policy is not supported by the Voodoo Store backend; "
                "use an explicit SQL adapter until the policy-native migration lands."
            )

        return [_hydrate(cls, row) for row in rows]

    async def insert(self) -> Any:
        if not should_use_store():
            return await super().insert()

        from voodoo.data.base import _get_table_name, _triggers

        table_name = _get_table_name(self)
        values = _model_values(self, include_id=False)
        self.id = insert_record(table_name, values)
        _fire_hooks(_triggers, table_name, "insert", self)
        return self

    async def update(self) -> Any:
        if not should_use_store():
            return await super().update()

        from voodoo.data.base import _get_table_name, _triggers

        table_name = _get_table_name(self)
        put_record(table_name, self.id, _model_values(self, include_id=False))
        _fire_hooks(_triggers, table_name, "update", self)
        return self

    async def _store_delete(self) -> None:
        from voodoo.data.base import _get_table_name

        delete_record(_get_table_name(self), self.id)


def _model_values(obj: Any, *, include_id: bool) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in get_type_hints(obj.__class__):
        if name.startswith("__") or (name == "id" and not include_id):
            continue
        if hasattr(obj, name):
            values[name] = getattr(obj, name)
    return values


def _hydrate(model: type[Any], row: dict[str, Any]) -> Any:
    obj = model()
    hints = get_type_hints(model)
    for key, value in row.items():
        if key in hints and hints[key] is bool:
            value = bool(value)
        setattr(obj, key, value)
    return obj


def _fire_hooks(
    triggers: dict[str, dict[str, list[Any]]],
    table_name: str,
    event: str,
    obj: Any,
) -> None:
    for hook in triggers.get(table_name, {}).get(event, []):
        if asyncio.iscoroutinefunction(hook):
            asyncio.create_task(hook(obj))
        else:
            hook(obj)
