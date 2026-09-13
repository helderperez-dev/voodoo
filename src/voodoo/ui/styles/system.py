"""Voodoo Design System 2 native CSS layer.

This stylesheet intentionally sits *after* the legacy generated component CSS.
It expresses the Design Constitution as a small semantic layer: calm surfaces,
consistent control metrics, accessible focus, purposeful motion, reduced-motion
support, compact density and the new semantic primitives.
"""

from voodoo.ui.styles.theme import Theme


def generate_design_system_css(theme: Theme) -> str:
    """Return the native Design System 2 override layer.

    Values reference Voodoo tokens instead of hard-coded brand styling so the
    same component language works across light, dark and branded themes.
    """

    return """
/* ── Voodoo Design System 2 ───────────────────────────────────────── */

:root {
    --vd-control-height-sm: 2rem;
    --vd-control-height-md: 2.5rem;
    --vd-control-height-lg: 2.875rem;
    --vd-control-pad-x: var(--vd-space-lg);
    --vd-focus-ring: color-mix(in srgb, var(--vd-color-secondary) 48%, transparent);
    --vd-surface-hover: color-mix(in srgb, var(--vd-color-text) 4%, var(--vd-color-surface));
    --vd-surface-pressed: color-mix(in srgb, var(--vd-color-text) 7%, var(--vd-color-surface));
    --vd-muted-fill: color-mix(in srgb, var(--vd-color-text) 5%, transparent);
    --vd-overlay: color-mix(in srgb, var(--vd-color-background) 78%, transparent);
}

body {
    letter-spacing: -0.006em;
}

:focus-visible {
    outline: 2px solid var(--vd-color-secondary);
    outline-offset: 2px;
}

/* Controls share one physical language. */
.vd-button,
.vd-input,
.vd-select {
    min-height: var(--vd-control-height-md);
    border-radius: var(--vd-radius-md);
}

.vd-button {
    height: var(--vd-control-height-md);
    padding-inline: var(--vd-control-pad-x);
    border-color: var(--vd-color-border-soft);
    box-shadow: none;
    transition:
        background-color var(--vd-motion-fast) ease,
        border-color var(--vd-motion-fast) ease,
        color var(--vd-motion-fast) ease,
        transform var(--vd-motion-fast) ease,
        opacity var(--vd-motion-fast) ease;
}
.vd-button:hover:not(:disabled) { background: var(--vd-surface-hover); }
.vd-button:active:not(:disabled) { background: var(--vd-surface-pressed); transform: translateY(1px); }
.vd-button:focus-visible { box-shadow: 0 0 0 3px var(--vd-focus-ring); }
.vd-button[data-vd-loading="true"] { cursor: progress; }
.vd-button[data-vd-loading="true"]::before {
    content: "";
    width: 0.9em;
    height: 0.9em;
    border: 1.5px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: vd-spin 700ms linear infinite;
}

.vd-input,
.vd-select,
.vd-textarea {
    background: var(--vd-color-background);
    border-color: var(--vd-color-border-soft);
    box-shadow: none;
    transition:
        border-color var(--vd-motion-fast) ease,
        box-shadow var(--vd-motion-fast) ease,
        background-color var(--vd-motion-fast) ease;
}
.vd-input:hover:not(:disabled),
.vd-select:hover:not(:disabled),
.vd-textarea:hover:not(:disabled) {
    border-color: var(--vd-color-border);
}
.vd-input:focus-visible,
.vd-select:focus-visible,
.vd-textarea:focus-visible {
    border-color: var(--vd-color-secondary);
    box-shadow: 0 0 0 3px var(--vd-focus-ring);
}
[aria-invalid="true"] {
    border-color: var(--vd-color-danger) !important;
}
[aria-invalid="true"]:focus-visible {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--vd-color-danger) 24%, transparent);
}

/* Cards are bounded objects, not the default layout primitive. */
.vd-card {
    border-color: var(--vd-color-border-soft);
    border-radius: var(--vd-radius-lg);
    box-shadow: none;
}

/* Form */
.vd-form {
    display: grid;
    gap: var(--vd-space-md);
}

/* Field */
.vd-field { display: grid; gap: var(--vd-space-sm); }
.vd-field-label {
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
}
.vd-field-control { min-width: 0; }
.vd-field-hint,
.vd-field-error {
    font-size: var(--vd-text-xs);
    line-height: var(--vd-leading-normal);
}
.vd-field-hint { color: var(--vd-color-text-muted); }
.vd-field-error { color: var(--vd-color-danger); }

/* Switch */
.vd-switch {
    display: inline-flex;
    align-items: center;
    gap: var(--vd-space-md);
    position: relative;
}
.vd-switch-input {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    opacity: 0;
    pointer-events: none;
}
.vd-switch-track {
    inline-size: 2.25rem;
    block-size: 1.25rem;
    padding: 2px;
    border-radius: var(--vd-radius-full);
    background: var(--vd-color-surface-raised);
    border: 1px solid var(--vd-color-border);
    transition: background var(--vd-motion-fast) ease, border-color var(--vd-motion-fast) ease;
    cursor: pointer;
}
.vd-switch-thumb {
    display: block;
    inline-size: 0.875rem;
    block-size: 0.875rem;
    border-radius: 50%;
    background: var(--vd-color-text);
    box-shadow: var(--vd-shadow-sm);
    transition: transform var(--vd-motion-fast) ease;
}
.vd-switch-input:checked + .vd-switch-track {
    background: var(--vd-color-secondary);
    border-color: var(--vd-color-secondary);
}
.vd-switch-input:checked + .vd-switch-track .vd-switch-thumb {
    transform: translateX(1rem);
    background: var(--vd-color-on-secondary);
}
.vd-switch-input:focus-visible + .vd-switch-track {
    box-shadow: 0 0 0 3px var(--vd-focus-ring);
}
.vd-switch-input:disabled + .vd-switch-track,
.vd-switch-input:disabled ~ .vd-switch-copy { opacity: 0.5; cursor: not-allowed; }
.vd-switch-copy { display: grid; gap: 0.125rem; cursor: pointer; }
.vd-switch-label { font-size: var(--vd-text-sm); font-weight: var(--vd-weight-medium); }
.vd-switch-description { color: var(--vd-color-text-muted); font-size: var(--vd-text-xs); }

/* Tooltip */
.vd-tooltip { position: relative; display: inline-flex; }
.vd-tooltip-content {
    position: absolute;
    z-index: 70;
    inset-block-end: calc(100% + var(--vd-space-sm));
    inset-inline-start: 50%;
    transform: translate(-50%, 2px);
    max-inline-size: 18rem;
    inline-size: max-content;
    padding: var(--vd-space-sm) var(--vd-space-md);
    border: 1px solid var(--vd-color-border-soft);
    border-radius: var(--vd-radius-sm);
    background: var(--vd-color-text);
    color: var(--vd-color-background);
    font-size: var(--vd-text-xs);
    line-height: var(--vd-leading-normal);
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition: opacity var(--vd-motion-fast) ease, transform var(--vd-motion-fast) ease;
}
.vd-tooltip:hover .vd-tooltip-content,
.vd-tooltip:focus-within .vd-tooltip-content {
    opacity: 1;
    visibility: visible;
    transform: translate(-50%, 0);
}

/* Native popover */
.vd-popover-shell { display: inline-flex; }
.vd-popover {
    margin: 0;
    max-inline-size: min(24rem, calc(100vw - 2rem));
    padding: var(--vd-space-lg);
    border: 1px solid var(--vd-color-border-soft);
    border-radius: var(--vd-radius-lg);
    background: var(--vd-color-surface);
    color: var(--vd-color-text);
    box-shadow: var(--vd-shadow-lg);
}
.vd-popover::backdrop { background: transparent; }

/* Skeleton */
.vd-skeleton { display: grid; gap: var(--vd-space-sm); min-inline-size: 4rem; }
.vd-skeleton-line {
    display: block;
    min-block-size: 0.8rem;
    border-radius: var(--vd-radius-sm);
    background: linear-gradient(
        90deg,
        var(--vd-muted-fill),
        color-mix(in srgb, var(--vd-color-text) 9%, transparent),
        var(--vd-muted-fill)
    );
    background-size: 220% 100%;
    animation: vd-skeleton 1.35s ease-in-out infinite;
}
.vd-skeleton-line--2 { inline-size: 86%; }
.vd-skeleton-line--3 { inline-size: 68%; }

/* Density is an application choice, not a separate component set. */
[data-vd-density="compact"] {
    --vd-control-height-md: 2.125rem;
    --vd-control-pad-x: var(--vd-space-md);
}
[data-vd-density="compact"] .vd-page { font-size: var(--vd-text-sm); }

@keyframes vd-spin { to { transform: rotate(360deg); } }
@keyframes vd-skeleton {
    0% { background-position: 100% 0; }
    100% { background-position: -100% 0; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        scroll-behavior: auto !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

@media (pointer: coarse) {
    .vd-button,
    .vd-input,
    .vd-select { min-height: 2.75rem; }
}
"""
