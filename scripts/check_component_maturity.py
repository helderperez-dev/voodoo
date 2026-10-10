"""Validate the explicit component maturity contract."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import voodoo.ui as ui
from voodoo.ui import Component

ROOT = Path(__file__).parents[1]
STATUSES = {"stable", "beta", "experimental", "deprecated"}
TIERS = {
    "primitive",
    "layout",
    "form",
    "data_display",
    "feedback_overlay",
    "navigation",
    "application_shell",
    "experimental/composite",
}


def _validate_tiers(manifest: dict[str, object], classes: set[str]) -> None:
    default_tier = manifest.get("default_tier")
    if default_tier not in TIERS:
        raise SystemExit(f"invalid default tier: {default_tier}")
    tier_seen: dict[str, str] = {}
    for tier, names in manifest.get("tiers", {}).items():
        if tier not in TIERS or tier == default_tier:
            raise SystemExit(f"invalid explicit tier: {tier}")
        for name in names:
            if name not in classes:
                raise SystemExit(f"{tier} component is not exported: {name}")
            if name in tier_seen:
                raise SystemExit(f"component has multiple tiers: {name}")
            tier_seen[name] = tier
    tier_seen.update({name: default_tier for name in classes if name not in tier_seen})
    if len(tier_seen) != len(classes):
        raise SystemExit("component tiers do not cover every exported component")


def _validate_stable_contract(
    name: str, contract: dict[str, object], example: tuple[object, ...]
) -> None:
    constructor = getattr(ui, name)
    component = constructor(*example, render_key=f"contract/{name}")
    rendered = component.render()
    # Stable components must be safe for server rendering and hydration: the
    # same immutable input produces byte-identical markup without generated
    # event handlers or executable content.
    if rendered != constructor(*example, render_key=f"contract/{name}").render():
        raise SystemExit(f"stable component render is not deterministic: {name}")
    opening = re.match(r"^<([a-z0-9]+)([^>]*)>", rendered)
    if opening is None:
        raise SystemExit(f"stable component does not render an opening tag: {name}")
    expected_tag = contract.get("tag")
    if expected_tag == "h1" and opening.group(1) not in {f"h{i}" for i in range(1, 7)}:
        raise SystemExit(f"{name} must render a semantic heading tag")
    if expected_tag != "h1" and opening.group(1) != expected_tag:
        raise SystemExit(
            f"{name} rendered <{opening.group(1)}>; expected <{expected_tag}>"
        )
    attrs = opening.group(2)
    for attribute in contract.get("required_attrs", []):
        if not re.search(rf"\b{re.escape(attribute)}(?:=|\s|$)", attrs):
            raise SystemExit(f"{name} is missing required attribute: {attribute}")
    if "<script" in rendered.lower():
        raise SystemExit(f"stable component emitted a script tag: {name}")
    if re.search(r"\son[a-z-]+\s*=", rendered, re.IGNORECASE):
        raise SystemExit(f"stable component emitted an inline event handler: {name}")


def _validate_stable_contracts(manifest: dict[str, object], classes: set[str]) -> None:
    """Smoke-test the explicit semantic/accessibility contract for stable UI."""
    examples = {
        "A": ("Link",),
        "Alert": ("Message",),
        "Badge": ("New",),
        "Button": ("Save",),
        "Card": ("Content",),
        "Container": ("Content",),
        "Div": ("Content",),
        "Flex": ("Content",),
        "Form": ("Fields",),
        "Grid": ("Content",),
        "Heading": ("Title",),
        "Input": (),
        "Label": ("Name",),
        "Page": ("Content",),
        "Stack": ("Content",),
        "Text": ("Content",),
    }
    contracts = manifest.get("stable_contracts", {})
    if not isinstance(contracts, dict):
        raise SystemExit("stable_contracts must be an object")
    stable = set(manifest.get("stable", []))
    if set(contracts) - stable:
        raise SystemExit("stable contract references a non-stable component")
    for name, contract in contracts.items():
        if name not in classes or not isinstance(contract, dict):
            raise SystemExit(f"invalid stable contract: {name}")
        _validate_stable_contract(name, contract, examples[name])


def _validate_component_families(classes: set[str]) -> None:  # noqa: C901 - schema validation branches are explicit
    """Ensure overlapping families have one documented preferred API."""
    path = ROOT / "docs/component_families.json"
    data = json.loads(path.read_text())
    families = data.get("families", [])
    if not isinstance(families, list) or not families:
        raise SystemExit("component_families must declare at least one family")
    seen: set[str] = set()
    for family in families:
        if not isinstance(family, dict):
            raise SystemExit("component family entries must be objects")
        name = family.get("name")
        preferred = family.get("preferred")
        alternatives = family.get("alternatives")
        guidance = family.get("guidance")
        if not all(isinstance(value, str) and value for value in (name, preferred, guidance)):
            raise SystemExit("component families require name, preferred, and guidance")
        if preferred not in classes:
            raise SystemExit(f"component family preferred API is not exported: {preferred}")
        if not isinstance(alternatives, list) or not alternatives:
            raise SystemExit(f"component family has no alternatives: {name}")
        for alternative in alternatives:
            if alternative not in classes:
                raise SystemExit(f"component family alternative is not exported: {alternative}")
            if alternative == preferred:
                raise SystemExit(f"component family repeats preferred API: {name}")
            if alternative in seen:
                raise SystemExit(f"component appears in multiple overlap families: {alternative}")
            seen.add(alternative)


def _validate_stable_documentation(manifest: dict[str, object]) -> None:
    """Require concise API guidance for every stable component."""
    docs = json.loads((ROOT / "docs/stable_component_docs.json").read_text())
    entries = docs.get("components")
    stable = set(manifest.get("stable", []))
    if not isinstance(entries, dict) or set(entries) != stable:
        raise SystemExit("stable component documentation must cover exactly the stable tier")
    required = ("summary", "example", "do", "dont", "accessibility", "site_route")
    for name, entry in entries.items():
        if not isinstance(entry, dict) or any(
            not isinstance(entry.get(field), str) or not entry[field].strip()
            for field in required
        ):
            raise SystemExit(f"stable component documentation is incomplete: {name}")


def _validate_stable_signatures(stable: set[str]) -> None:
    """Require typed explicit parameters on the curated stable API.

    ``children`` and the deliberate HTML ``kwargs`` escape hatch are shared by
    the component base class. Every other constructor parameter is part of a
    stable component's public contract and must carry an annotation.
    """
    for name in sorted(stable):
        signature = inspect.signature(getattr(ui, name))
        for parameter in signature.parameters.values():
            if parameter.name in {"children", "kwargs"}:
                continue
            if parameter.annotation is inspect.Parameter.empty:
                raise SystemExit(
                    f"stable component parameter is untyped: {name}.{parameter.name}"
                )


def _validate_exported_signatures(classes: set[str]) -> None:
    """Keep every exported component constructor introspectable and typed.

    Experimental components do not promise stable semantics yet, but their
    public signatures still need annotations so generated docs, IDE tooling,
    and future promotion checks can reason about the catalog without falling
    back to untyped ``Any`` parameters.
    """
    for name in sorted(classes):
        signature = inspect.signature(getattr(ui, name))
        for parameter in signature.parameters.values():
            if parameter.name in {"children", "kwargs"}:
                continue
            if parameter.annotation is inspect.Parameter.empty:
                raise SystemExit(
                    f"exported component parameter is untyped: {name}.{parameter.name}"
                )


def main() -> int:
    manifest = json.loads((ROOT / "docs/component_maturity.json").read_text())
    default = manifest["default_status"]
    if default not in STATUSES:
        raise SystemExit(f"invalid default status: {default}")
    classes = {
        name
        for name in ui.__all__
        if inspect.isclass(getattr(ui, name, None))
        and issubclass(getattr(ui, name), Component)
    }
    seen: dict[str, str] = {}
    for status in STATUSES - {default}:
        for name in manifest.get(status, []):
            if name not in classes:
                raise SystemExit(f"{status} component is not exported: {name}")
            if name in seen:
                raise SystemExit(f"component has multiple statuses: {name}")
            seen[name] = status
    for name in classes:
        seen.setdefault(name, default)
    if len(seen) != len(classes):
        raise SystemExit("component maturity does not cover every exported component")
    _validate_tiers(manifest, classes)
    _validate_stable_contracts(manifest, classes)
    _validate_component_families(classes)
    _validate_stable_documentation(manifest)
    _validate_exported_signatures(classes)
    _validate_stable_signatures(set(manifest.get("stable", [])))
    print(f"component maturity passed ({len(classes)} components classified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
