"""Primitive color scales and token helpers for the Voodoo design system.

The palette is the low-level color layer. Components should prefer semantic
roles such as ``primary`` and ``danger`` for meaning, while application UI can
reach for a specific step when it needs deliberate visual composition.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field, field_validator

PALETTE_STEPS = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)

# A focused set of Tailwind-compatible scales. OKLCH keeps perceived lightness
# more consistent across hues than hex/HSL when composing custom themes.
DEFAULT_PALETTE: dict[str, dict[int, str]] = {
    "zinc": {
        50: "oklch(98.5% 0 0)",
        100: "oklch(96.7% 0.001 286.375)",
        200: "oklch(92% 0.004 286.32)",
        300: "oklch(87.1% 0.006 286.286)",
        400: "oklch(70.5% 0.015 286.067)",
        500: "oklch(55.2% 0.016 285.938)",
        600: "oklch(44.2% 0.017 285.786)",
        700: "oklch(37% 0.013 285.805)",
        800: "oklch(27.4% 0.006 286.033)",
        900: "oklch(21% 0.006 285.885)",
        950: "oklch(14.1% 0.005 285.823)",
    },
    "violet": {
        50: "oklch(96.9% 0.016 293.756)",
        100: "oklch(94.3% 0.029 294.588)",
        200: "oklch(89.4% 0.057 293.283)",
        300: "oklch(81.1% 0.111 293.571)",
        400: "oklch(70.2% 0.183 293.541)",
        500: "oklch(60.6% 0.25 292.717)",
        600: "oklch(54.1% 0.281 293.009)",
        700: "oklch(49.1% 0.27 292.581)",
        800: "oklch(43.2% 0.232 292.759)",
        900: "oklch(38% 0.189 293.745)",
        950: "oklch(28.3% 0.141 291.089)",
    },
    "blue": {
        50: "oklch(97% 0.014 254.604)",
        100: "oklch(93.2% 0.032 255.585)",
        200: "oklch(88.2% 0.059 254.128)",
        300: "oklch(80.9% 0.105 251.813)",
        400: "oklch(70.7% 0.165 254.624)",
        500: "oklch(62.3% 0.214 259.815)",
        600: "oklch(54.6% 0.245 262.881)",
        700: "oklch(48.8% 0.243 264.376)",
        800: "oklch(42.4% 0.199 265.638)",
        900: "oklch(37.9% 0.146 265.522)",
        950: "oklch(28.2% 0.091 267.935)",
    },
    "emerald": {
        50: "oklch(97.9% 0.021 166.113)",
        100: "oklch(95% 0.052 163.051)",
        200: "oklch(90.5% 0.093 164.15)",
        300: "oklch(84.5% 0.143 164.978)",
        400: "oklch(76.5% 0.177 163.223)",
        500: "oklch(69.6% 0.17 162.48)",
        600: "oklch(59.6% 0.145 163.225)",
        700: "oklch(50.8% 0.118 165.612)",
        800: "oklch(43.2% 0.095 166.913)",
        900: "oklch(37.8% 0.077 168.94)",
        950: "oklch(26.2% 0.051 172.552)",
    },
    "amber": {
        50: "oklch(98.7% 0.022 95.277)",
        100: "oklch(96.2% 0.059 95.617)",
        200: "oklch(92.4% 0.12 95.746)",
        300: "oklch(87.9% 0.169 91.605)",
        400: "oklch(82.8% 0.189 84.429)",
        500: "oklch(76.9% 0.188 70.08)",
        600: "oklch(66.6% 0.179 58.318)",
        700: "oklch(55.5% 0.163 48.998)",
        800: "oklch(47.3% 0.137 46.201)",
        900: "oklch(41.4% 0.112 45.904)",
        950: "oklch(27.9% 0.077 45.635)",
    },
    "red": {
        50: "oklch(97.1% 0.013 17.38)",
        100: "oklch(93.6% 0.032 17.717)",
        200: "oklch(88.5% 0.062 18.334)",
        300: "oklch(80.8% 0.114 19.571)",
        400: "oklch(70.4% 0.191 22.216)",
        500: "oklch(63.7% 0.237 25.331)",
        600: "oklch(57.7% 0.245 27.325)",
        700: "oklch(50.5% 0.213 27.518)",
        800: "oklch(44.4% 0.177 26.899)",
        900: "oklch(39.6% 0.141 25.723)",
        950: "oklch(25.8% 0.092 26.042)",
    },
}

_TOKEN_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_TOKEN_REFERENCE = re.compile(r"^(?P<name>[a-z][a-z0-9-]*)[.-](?P<step>\d{2,3})$")
_UNSAFE_CSS_VALUE = re.compile(r"[;{}<>]")


class ThemePalette(BaseModel):
    """Named primitive color scales using familiar ``50`` through ``950`` steps."""

    scales: dict[str, dict[int, str]] = Field(
        default_factory=lambda: deepcopy(DEFAULT_PALETTE)
    )

    @field_validator("scales", mode="before")
    @classmethod
    def validate_scales(cls, value: Any) -> dict[str, dict[int, str]]:
        if value is None:
            return deepcopy(DEFAULT_PALETTE)
        if not isinstance(value, dict):
            raise TypeError("palette scales must be a mapping")

        merged = deepcopy(DEFAULT_PALETTE)
        for raw_name, raw_scale in value.items():
            name = str(raw_name)
            if not _TOKEN_NAME.fullmatch(name):
                raise ValueError(f"invalid palette name: {name!r}")
            if not isinstance(raw_scale, dict):
                raise TypeError(f"palette scale {name!r} must be a mapping")
            scale = merged.setdefault(name, {})
            for raw_step, color_value in raw_scale.items():
                step = int(raw_step)
                if step not in PALETTE_STEPS:
                    raise ValueError(
                        f"invalid palette step {step}; expected one of {PALETTE_STEPS}"
                    )
                value_text = str(color_value).strip()
                if not value_text or _UNSAFE_CSS_VALUE.search(value_text):
                    raise ValueError(
                        f"invalid CSS color value for {name}-{step}: {color_value!r}"
                    )
                scale[step] = value_text
        return merged

    def css_tokens(self) -> dict[str, str]:
        """Return flattened token names such as ``violet-500``."""
        return {
            f"{name}-{step}": value
            for name, scale in self.scales.items()
            for step, value in sorted(scale.items())
        }


def color(name: str, step: int | None = None) -> str:
    """Return a CSS variable reference for a semantic role or palette step.

    ``color("primary")`` resolves a semantic role and
    ``color("violet", 500)`` resolves a primitive palette token.
    """
    if not _TOKEN_NAME.fullmatch(name):
        raise ValueError(f"invalid color token name: {name!r}")
    if step is not None and step not in PALETTE_STEPS:
        raise ValueError(f"invalid palette step {step}; expected one of {PALETTE_STEPS}")
    suffix = f"-{step}" if step is not None else ""
    return f"var(--vd-color-{name}{suffix})"


def color_reference(token: str) -> str:
    """Resolve ``"primary"``, ``"violet-500"`` or ``"violet.500"``."""
    token = token.strip().lower()
    match = _TOKEN_REFERENCE.fullmatch(token)
    if match:
        return color(match.group("name"), int(match.group("step")))
    return color(token)


__all__ = [
    "DEFAULT_PALETTE",
    "PALETTE_STEPS",
    "ThemePalette",
    "color",
    "color_reference",
]
