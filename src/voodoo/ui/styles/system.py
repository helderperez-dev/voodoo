"""Voodoo native design-system override layer.

The native component stylesheet provides the structural baseline. This module
owns the opinionated visual language that makes a zero-custom-CSS Voodoo app
look intentional in both light and dark themes.
"""

from voodoo.ui.styles.theme import Theme


def generate_design_system_css(theme: Theme) -> str:
    """Return the premium Voodoo design-system layer.

    The layer is deliberately token-driven. Applications can still replace
    colors and typography through Theme while keeping Voodoo's spacing,
    hierarchy, focus, motion and component ergonomics coherent.
    """

    return """
/* ── Voodoo Design System 3 ───────────────────────────────────────── */

:root {
    --vd-brand: #7c3aed;
    --vd-brand-hover: #6d28d9;
    --vd-brand-strong: #5b21b6;
    --vd-brand-soft: color-mix(in srgb, var(--vd-brand) 10%, transparent);
    --vd-brand-softer: color-mix(in srgb, var(--vd-brand) 5%, transparent);
    --vd-brand-line: color-mix(in srgb, var(--vd-brand) 22%, transparent);
    --vd-brand-glow: color-mix(in srgb, var(--vd-brand) 20%, transparent);

    --vd-control-height-sm: 2rem;
    --vd-control-height-md: 2.5rem;
    --vd-control-height-lg: 2.875rem;
    --vd-control-pad-x: 0.95rem;
    --vd-focus-ring: color-mix(in srgb, var(--vd-brand) 28%, transparent);

    --vd-canvas: #ffffff;
    --vd-panel: #ffffff;
    --vd-panel-subtle: #fafafa;
    --vd-panel-muted: #f6f6f8;
    --vd-line: #e8e8ed;
    --vd-line-strong: #d9d9e2;
    --vd-ink: #111118;
    --vd-ink-muted: #6f6f7b;
    --vd-ink-faint: #9797a3;
    --vd-surface-hover: #f7f7f9;
    --vd-surface-pressed: #f1f1f5;
    --vd-overlay: rgb(255 255 255 / 0.82);

    --vd-shadow-card: 0 1px 2px rgb(15 15 25 / 0.03), 0 8px 30px rgb(15 15 25 / 0.035);
    --vd-shadow-float: 0 18px 50px rgb(15 15 25 / 0.13), 0 2px 8px rgb(15 15 25 / 0.05);
    --vd-shadow-brand: 0 8px 24px color-mix(in srgb, var(--vd-brand) 20%, transparent);

    --vd-content-sm: 42rem;
    --vd-content-md: 56rem;
    --vd-content-lg: 72rem;
    --vd-content-xl: 88rem;
}

.dark {
    --vd-canvas: #09090f;
    --vd-panel: #101017;
    --vd-panel-subtle: #0d0d13;
    --vd-panel-muted: #171720;
    --vd-line: #252532;
    --vd-line-strong: #343444;
    --vd-ink: #f7f7fb;
    --vd-ink-muted: #aaaab7;
    --vd-ink-faint: #777784;
    --vd-surface-hover: #171720;
    --vd-surface-pressed: #20202a;
    --vd-overlay: rgb(9 9 15 / 0.82);

    --vd-shadow-card: 0 1px 1px rgb(0 0 0 / 0.35), 0 14px 44px rgb(0 0 0 / 0.18);
    --vd-shadow-float: 0 22px 64px rgb(0 0 0 / 0.5), 0 2px 12px rgb(0 0 0 / 0.25);
}

html {
    background: var(--vd-canvas);
    color-scheme: light;
}
html.dark { color-scheme: dark; }

body {
    margin: 0;
    background: var(--vd-canvas);
    color: var(--vd-ink);
    letter-spacing: -0.008em;
    font-feature-settings: "ss01" 1, "cv01" 1, "cv02" 1;
}

#root { min-height: 100vh; }

::selection {
    background: color-mix(in srgb, var(--vd-brand) 24%, transparent);
    color: var(--vd-ink);
}

:focus-visible {
    outline: 2px solid var(--vd-brand);
    outline-offset: 2px;
}

/* ── Typography ───────────────────────────────────────────────────── */
.vd-heading {
    color: var(--vd-ink);
    font-family: var(--vd-font-display);
    letter-spacing: -0.032em;
    text-wrap: balance;
}
.vd-heading--h1 {
    font-size: clamp(2.15rem, 4vw, 3.5rem);
    line-height: 1.02;
    letter-spacing: -0.045em;
}
.vd-heading--h2 {
    font-size: clamp(1.65rem, 2.6vw, 2.35rem);
    line-height: 1.08;
}
.vd-heading--h3 { font-size: 1.35rem; line-height: 1.18; }
.vd-heading--h4 { font-size: 1.05rem; line-height: 1.25; }
.vd-paragraph {
    color: var(--vd-ink-muted);
    line-height: 1.7;
    letter-spacing: -0.004em;
}
.vd-text { color: var(--vd-ink); }
.vd-text--muted { color: var(--vd-ink-muted); }
.vd-link,
a:not([class]) {
    color: var(--vd-brand);
    text-decoration: none;
    text-underline-offset: 0.18em;
}
.vd-link:hover,
a:not([class]):hover { color: var(--vd-brand-hover); text-decoration: underline; }

/* ── Page geometry ───────────────────────────────────────────────── */
.vd-page {
    width: 100%;
    max-width: none;
    margin: 0;
    color: var(--vd-ink);
}
.vd-page--pad { padding: clamp(1.25rem, 3vw, 2.5rem); }
.vd-page--sm { max-width: var(--vd-content-sm); margin-inline: auto; }
.vd-page--md { max-width: var(--vd-content-md); margin-inline: auto; }
.vd-page--lg { max-width: var(--vd-content-lg); margin-inline: auto; }
.vd-page--xl { max-width: var(--vd-content-xl); margin-inline: auto; }

.vd-container { width: min(100%, var(--vd-content-xl)); }
.vd-container--centered { margin-inline: auto; }
.vd-container--sm { max-width: var(--vd-content-sm); }
.vd-container--md { max-width: var(--vd-content-md); }
.vd-container--lg { max-width: var(--vd-content-lg); }
.vd-container--xl { max-width: var(--vd-content-xl); }

.vd-grid { min-width: 0; }
.vd-flex { min-width: 0; }

/* ── Buttons ─────────────────────────────────────────────────────── */
.vd-button {
    min-height: var(--vd-control-height-md);
    height: var(--vd-control-height-md);
    padding-inline: var(--vd-control-pad-x);
    border: 1px solid var(--vd-line);
    border-radius: 0.625rem;
    background: var(--vd-panel);
    color: var(--vd-ink);
    box-shadow: 0 1px 1px rgb(15 15 25 / 0.025);
    font-size: 0.875rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    transition:
        background-color 140ms ease,
        border-color 140ms ease,
        color 140ms ease,
        transform 140ms ease,
        box-shadow 140ms ease,
        opacity 140ms ease;
}
.vd-button:hover:not(:disabled) {
    background: var(--vd-surface-hover);
    border-color: var(--vd-line-strong);
}
.vd-button:active:not(:disabled) { transform: translateY(1px); }
.vd-button:focus-visible { box-shadow: 0 0 0 3px var(--vd-focus-ring); }
.vd-button:disabled { opacity: 0.42; cursor: not-allowed; }

.vd-button--primary,
.vd-button--secondary {
    border-color: var(--vd-brand);
    background: linear-gradient(180deg, #8b5cf6 0%, var(--vd-brand) 100%);
    color: white;
    box-shadow: var(--vd-shadow-brand), inset 0 1px 0 rgb(255 255 255 / 0.18);
}
.vd-button--primary:hover:not(:disabled),
.vd-button--secondary:hover:not(:disabled) {
    background: linear-gradient(180deg, #8250ee 0%, var(--vd-brand-hover) 100%);
    border-color: var(--vd-brand-hover);
}
.vd-button--outline { background: transparent; border-color: var(--vd-line-strong); }
.vd-button--ghost { background: transparent; border-color: transparent; color: var(--vd-ink-muted); }
.vd-button--ghost:hover:not(:disabled) { color: var(--vd-ink); background: var(--vd-brand-softer); }
.vd-button--danger { border-color: #ef4444; background: #ef4444; color: white; }
.vd-button--sm { min-height: var(--vd-control-height-sm); height: var(--vd-control-height-sm); padding-inline: 0.75rem; }
.vd-button--lg { min-height: var(--vd-control-height-lg); height: var(--vd-control-height-lg); padding-inline: 1.2rem; }
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

/* ── Surfaces and cards ──────────────────────────────────────────── */
.vd-card {
    overflow: hidden;
    background: var(--vd-panel);
    border: 1px solid var(--vd-line);
    border-radius: 0.875rem;
    padding: clamp(1rem, 2vw, 1.35rem);
    box-shadow: var(--vd-shadow-card);
}
.vd-card:hover { border-color: var(--vd-line-strong); }

.vd-divider { border-color: var(--vd-line); }

/* ── Inputs and forms ─────────────────────────────────────────────── */
.vd-form { display: grid; gap: 1rem; }
.vd-field { display: grid; gap: 0.45rem; }
.vd-field-label,
.vd-label {
    color: var(--vd-ink);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: -0.004em;
}
.vd-field-hint,
.vd-field-error { font-size: 0.75rem; line-height: 1.45; }
.vd-field-hint { color: var(--vd-ink-muted); }
.vd-field-error { color: #dc2626; }

.vd-input,
.vd-select,
.vd-textarea {
    width: 100%;
    min-height: var(--vd-control-height-md);
    border: 1px solid var(--vd-line-strong);
    border-radius: 0.625rem;
    background: var(--vd-panel);
    color: var(--vd-ink);
    box-shadow: 0 1px 1px rgb(15 15 25 / 0.02);
    transition: border-color 140ms ease, box-shadow 140ms ease, background-color 140ms ease;
}
.vd-input,
.vd-select { height: var(--vd-control-height-md); }
.vd-textarea { min-height: 6.5rem; resize: vertical; }
.vd-input::placeholder,
.vd-textarea::placeholder { color: var(--vd-ink-faint); }
.vd-input:hover:not(:disabled),
.vd-select:hover:not(:disabled),
.vd-textarea:hover:not(:disabled) { border-color: color-mix(in srgb, var(--vd-brand) 35%, var(--vd-line-strong)); }
.vd-input:focus-visible,
.vd-select:focus-visible,
.vd-textarea:focus-visible {
    outline: none;
    border-color: var(--vd-brand);
    box-shadow: 0 0 0 3px var(--vd-focus-ring);
}
[aria-invalid="true"] { border-color: #ef4444 !important; }
[aria-invalid="true"]:focus-visible { box-shadow: 0 0 0 3px rgb(239 68 68 / 0.18); }

.vd-checkbox,
.vd-radio { accent-color: var(--vd-brand); }

/* ── Badges ──────────────────────────────────────────────────────── */
.vd-badge {
    min-height: 1.45rem;
    padding: 0.18rem 0.55rem;
    border-radius: 999px;
    border: 1px solid transparent;
    font-size: 0.7rem;
    font-weight: 650;
    letter-spacing: -0.005em;
}
.vd-badge--default,
.vd-badge--primary {
    background: var(--vd-brand-soft);
    color: var(--vd-brand);
    border-color: var(--vd-brand-line);
}
.vd-badge--secondary {
    background: var(--vd-panel-muted);
    color: var(--vd-ink-muted);
    border-color: var(--vd-line);
}
.vd-badge--outline { background: transparent; color: var(--vd-ink); border-color: var(--vd-line-strong); }
.vd-badge--success { background: rgb(16 185 129 / 0.1); color: #059669; border-color: rgb(16 185 129 / 0.2); }
.vd-badge--warning { background: rgb(245 158 11 / 0.11); color: #b45309; border-color: rgb(245 158 11 / 0.22); }
.vd-badge--danger { background: rgb(239 68 68 / 0.1); color: #dc2626; border-color: rgb(239 68 68 / 0.2); }
.dark .vd-badge--success { color: #6ee7b7; }
.dark .vd-badge--warning { color: #fbbf24; }
.dark .vd-badge--danger { color: #fca5a5; }

/* ── Navigation ──────────────────────────────────────────────────── */
.vd-navbar {
    min-height: 4rem;
    padding: 0.65rem clamp(1rem, 3vw, 2rem);
    background: var(--vd-overlay);
    border-bottom: 1px solid var(--vd-line);
    backdrop-filter: blur(18px) saturate(140%);
    -webkit-backdrop-filter: blur(18px) saturate(140%);
}
.vd-navbar--sticky { position: sticky; top: 0; z-index: 60; }
.vd-brand { color: var(--vd-ink); font-weight: 720; letter-spacing: -0.025em; }
.vd-nav-link {
    border-radius: 0.5rem;
    color: var(--vd-ink-muted);
    font-size: 0.84rem;
    font-weight: 540;
    text-decoration: none;
    transition: background-color 140ms ease, color 140ms ease;
}
.vd-nav-link:hover { color: var(--vd-ink); background: var(--vd-surface-hover); }
.vd-nav-link--active { color: var(--vd-brand); background: var(--vd-brand-soft); }

.vd-sidebar {
    background: var(--vd-panel-subtle);
    border-right: 1px solid var(--vd-line);
}

/* ── Theme toggle ────────────────────────────────────────────────── */
.vd-theme-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.35rem;
    height: 2.35rem;
    padding: 0;
    border: 1px solid var(--vd-line);
    border-radius: 0.625rem;
    background: var(--vd-panel);
    color: var(--vd-ink-muted);
    cursor: pointer;
}
.vd-theme-toggle:hover { background: var(--vd-surface-hover); color: var(--vd-ink); }

/* ── Tables ──────────────────────────────────────────────────────── */
.vd-table {
    width: 100%;
    overflow: hidden;
    border: 1px solid var(--vd-line);
    border-radius: 0.8rem;
    background: var(--vd-panel);
    border-collapse: separate;
    border-spacing: 0;
}
.vd-table th {
    color: var(--vd-ink-muted);
    background: var(--vd-panel-subtle);
    font-size: 0.72rem;
    font-weight: 650;
    text-align: left;
    letter-spacing: 0.015em;
    text-transform: uppercase;
}
.vd-table th,
.vd-table td { padding: 0.8rem 0.95rem; border-bottom: 1px solid var(--vd-line); }
.vd-table tr:last-child td { border-bottom: 0; }
.vd-table tbody tr:hover td { background: var(--vd-surface-hover); }

/* ── Modal / dialog / popover ────────────────────────────────────── */
.vd-modal,
.vd-dialog,
.vd-popover {
    border: 1px solid var(--vd-line);
    border-radius: 0.95rem;
    background: var(--vd-panel);
    color: var(--vd-ink);
    box-shadow: var(--vd-shadow-float);
}
.vd-popover { max-inline-size: min(24rem, calc(100vw - 2rem)); padding: 1rem; }
.vd-popover::backdrop { background: transparent; }

/* ── Tooltip ─────────────────────────────────────────────────────── */
.vd-tooltip { position: relative; display: inline-flex; }
.vd-tooltip-content {
    position: absolute;
    z-index: 80;
    inset-block-end: calc(100% + 0.5rem);
    inset-inline-start: 50%;
    transform: translate(-50%, 2px);
    max-inline-size: 18rem;
    inline-size: max-content;
    padding: 0.45rem 0.65rem;
    border: 1px solid var(--vd-line-strong);
    border-radius: 0.45rem;
    background: var(--vd-ink);
    color: var(--vd-canvas);
    box-shadow: var(--vd-shadow-card);
    font-size: 0.72rem;
    line-height: 1.4;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition: opacity 120ms ease, transform 120ms ease;
}
.vd-tooltip:hover .vd-tooltip-content,
.vd-tooltip:focus-within .vd-tooltip-content {
    opacity: 1;
    visibility: visible;
    transform: translate(-50%, 0);
}

/* ── Switch ──────────────────────────────────────────────────────── */
.vd-switch { display: inline-flex; align-items: center; gap: 0.75rem; position: relative; }
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
    border-radius: 999px;
    background: var(--vd-panel-muted);
    border: 1px solid var(--vd-line-strong);
    transition: background 140ms ease, border-color 140ms ease;
    cursor: pointer;
}
.vd-switch-thumb {
    display: block;
    inline-size: 0.875rem;
    block-size: 0.875rem;
    border-radius: 50%;
    background: var(--vd-ink-muted);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.16);
    transition: transform 140ms ease, background 140ms ease;
}
.vd-switch-input:checked + .vd-switch-track { background: var(--vd-brand); border-color: var(--vd-brand); }
.vd-switch-input:checked + .vd-switch-track .vd-switch-thumb { transform: translateX(1rem); background: white; }
.vd-switch-input:focus-visible + .vd-switch-track { box-shadow: 0 0 0 3px var(--vd-focus-ring); }
.vd-switch-copy { display: grid; gap: 0.125rem; cursor: pointer; }
.vd-switch-label { font-size: 0.84rem; font-weight: 600; }
.vd-switch-description { color: var(--vd-ink-muted); font-size: 0.74rem; }

/* ── Skeleton ────────────────────────────────────────────────────── */
.vd-skeleton { display: grid; gap: 0.5rem; min-inline-size: 4rem; }
.vd-skeleton-line {
    display: block;
    min-block-size: 0.8rem;
    border-radius: 0.35rem;
    background: linear-gradient(90deg, var(--vd-panel-muted), var(--vd-surface-hover), var(--vd-panel-muted));
    background-size: 220% 100%;
    animation: vd-skeleton 1.35s ease-in-out infinite;
}
.vd-skeleton-line--2 { inline-size: 86%; }
.vd-skeleton-line--3 { inline-size: 68%; }

/* ── Product/system surfaces ─────────────────────────────────────── */
.vd-metric,
.vd-status-badge,
.vd-inspector-panel,
.vd-command-bar,
.vd-runtime-status,
.vd-agent-status,
.vd-device-card,
.vd-execution-status,
.vd-telemetry-panel {
    --vd-local-border: var(--vd-line);
}

.vd-metric,
.vd-inspector-panel,
.vd-runtime-status,
.vd-agent-status,
.vd-device-card,
.vd-telemetry-panel {
    background: var(--vd-panel);
    border-color: var(--vd-line);
    box-shadow: var(--vd-shadow-card);
}

/* ── App-shell helpers ────────────────────────────────────────────── */
.vd-header,
.vd-footer { border-color: var(--vd-line); }
.vd-main { min-width: 0; }
.vd-section { min-width: 0; }

/* Density remains an application choice, not a second component set. */
[data-vd-density="compact"] {
    --vd-control-height-md: 2.125rem;
    --vd-control-pad-x: 0.75rem;
}
[data-vd-density="compact"] .vd-page { font-size: 0.875rem; }

@keyframes vd-spin { to { transform: rotate(360deg); } }
@keyframes vd-skeleton {
    0% { background-position: 100% 0; }
    100% { background-position: -100% 0; }
}

@media (max-width: 760px) {
    .vd-page--pad { padding: 1rem; }
    .vd-card { border-radius: 0.75rem; padding: 1rem; }
    .vd-navbar { min-height: 3.5rem; padding-inline: 1rem; }
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
