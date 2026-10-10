"""Validate that framework CSS references declared semantic design tokens."""

from __future__ import annotations

import re

from voodoo.ui.styles.system import generate_design_system_css
from voodoo.ui.styles.theme import default_theme

REQUIRED_FAMILIES = (
    "color-",
    "space-",
    "radius-",
    "shadow-",
    "motion-",
    "density-",
    "focus-",
    "font-",
    "text-",
    "leading-",
    "weight-",
    "breakpoint-",
)


def main() -> int:
    css = generate_design_system_css(default_theme) + default_theme.to_css_variables()
    references = set(re.findall(r"var\((--vd-[a-z0-9-]+)", css))
    declarations = set(re.findall(r"(--vd-[a-z0-9-]+)\s*:", css))
    undefined = sorted(references - declarations)
    if undefined:
        raise SystemExit(f"undefined Voodoo design tokens: {', '.join(undefined)}")
    missing = [
        family
        for family in REQUIRED_FAMILIES
        if not any(token.startswith(f"--vd-{family}") for token in declarations)
    ]
    if missing:
        raise SystemExit(f"missing Voodoo design-token families: {', '.join(missing)}")
    print(
        f"design tokens passed ({len(declarations)} declarations, "
        f"{len(references)} references)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
