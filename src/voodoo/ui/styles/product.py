"""Native styles for Voodoo product-level components."""

from voodoo.ui.styles.theme import Theme


def generate_product_css(theme: Theme) -> str:
    """Return semantic CSS for reusable product patterns."""

    return """
/* ── Voodoo Product Components ────────────────────────────────────── */

.vd-status-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--vd-space-sm);
    min-height: 1.5rem;
    padding-inline: var(--vd-space-sm);
    border-radius: var(--vd-radius-full);
    border: 1px solid var(--vd-color-border-soft);
    background: color-mix(in srgb, var(--vd-color-surface) 72%, transparent);
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-medium);
    white-space: nowrap;
}
.vd-status-dot {
    inline-size: 0.45rem;
    block-size: 0.45rem;
    border-radius: 50%;
    background: var(--vd-color-text-muted);
}
.vd-status-dot--success { background: var(--vd-color-success); }
.vd-status-dot--info { background: var(--vd-color-info); }
.vd-status-dot--warning { background: var(--vd-color-warning); }
.vd-status-dot--danger { background: var(--vd-color-danger); }
[data-pulse="true"] .vd-status-dot {
    box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 30%, transparent);
    animation: vd-status-pulse 1.8s ease-out infinite;
}

.vd-metric {
    display: grid;
    align-content: start;
    gap: 0.2rem;
    min-inline-size: 0;
}
.vd-metric-label {
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
}
.vd-metric-value {
    color: var(--vd-color-text);
    font-size: clamp(var(--vd-text-xl), 3vw, var(--vd-text-xxxl));
    line-height: var(--vd-leading-tight);
    font-weight: var(--vd-weight-semibold);
    letter-spacing: -0.035em;
    font-variant-numeric: tabular-nums;
}
.vd-metric-change,
.vd-metric-description { font-size: var(--vd-text-xs); }
.vd-metric-description { color: var(--vd-color-text-muted); }
.vd-metric-change--success { color: var(--vd-color-success); }
.vd-metric-change--danger { color: var(--vd-color-danger); }
.vd-metric-change--warning { color: var(--vd-color-warning); }
.vd-metric-change--muted { color: var(--vd-color-text-muted); }

.vd-empty-state {
    display: grid;
    justify-items: start;
    max-inline-size: 34rem;
    padding-block: clamp(2rem, 7vw, 5rem);
    gap: var(--vd-space-md);
}
.vd-empty-state-icon { color: var(--vd-color-text-muted); }
.vd-empty-state-title { margin: 0; }
.vd-empty-state-description {
    max-inline-size: 52ch;
    color: var(--vd-color-text-muted);
    line-height: var(--vd-leading-normal);
}
.vd-empty-state-action { margin-block-start: var(--vd-space-sm); }

.vd-data-table {
    inline-size: 100%;
    min-inline-size: 0;
}
.vd-data-table-scroll {
    inline-size: 100%;
    overflow: auto;
    border-block: 1px solid var(--vd-color-border-soft);
}
.vd-data-table-table {
    inline-size: 100%;
    border-collapse: collapse;
    font-size: var(--vd-text-sm);
    text-align: start;
}
.vd-data-table-caption {
    padding-block: var(--vd-space-md);
    color: var(--vd-color-text-muted);
    text-align: start;
    font-size: var(--vd-text-xs);
}
.vd-data-table th {
    padding: var(--vd-space-md) var(--vd-space-lg);
    border-block-end: 1px solid var(--vd-color-border-soft);
    color: var(--vd-color-text-muted);
    background: color-mix(in srgb, var(--vd-color-surface) 52%, transparent);
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-medium);
    letter-spacing: 0.015em;
    white-space: nowrap;
}
.vd-data-table td {
    padding: var(--vd-space-md) var(--vd-space-lg);
    border-block-end: 1px solid var(--vd-color-border-soft);
    color: var(--vd-color-text);
    vertical-align: middle;
}
.vd-data-table tbody tr:last-child td { border-block-end: 0; }
.vd-data-table [data-align="center"] { text-align: center; }
.vd-data-table [data-align="end"] { text-align: end; }
.vd-data-table-row[role="button"] {
    cursor: pointer;
    outline: none;
    transition: background var(--vd-motion-fast) ease;
}
.vd-data-table-row[role="button"]:hover { background: var(--vd-surface-hover); }
.vd-data-table-row[role="button"]:focus-visible {
    box-shadow: inset 3px 0 0 var(--vd-color-secondary);
    background: var(--vd-surface-hover);
}
.vd-data-table-empty-value { color: var(--vd-color-text-muted); }
[data-vd-density="compact"] .vd-data-table th,
[data-vd-density="compact"] .vd-data-table td {
    padding-block: var(--vd-space-sm);
    padding-inline: var(--vd-space-md);
}

.vd-timeline {
    display: grid;
    gap: 0;
}
.vd-event-row {
    position: relative;
    display: grid;
    grid-template-columns: 1.25rem minmax(0, 1fr) auto;
    gap: var(--vd-space-md);
    min-block-size: 3.75rem;
    padding-block: var(--vd-space-sm) var(--vd-space-lg);
}
.vd-event-row-rail {
    position: relative;
    inline-size: 100%;
}
.vd-event-row-rail::before {
    content: "";
    position: absolute;
    inset-block-start: 0.35rem;
    inset-inline-start: 50%;
    inline-size: 0.5rem;
    block-size: 0.5rem;
    transform: translateX(-50%);
    border-radius: 50%;
    background: var(--vd-color-text-muted);
    box-shadow: 0 0 0 3px var(--vd-color-background);
}
.vd-event-row-rail::after {
    content: "";
    position: absolute;
    inset-block-start: 1rem;
    inset-block-end: calc(var(--vd-space-lg) * -1);
    inset-inline-start: 50%;
    inline-size: 1px;
    background: var(--vd-color-border-soft);
}
.vd-event-row:last-child .vd-event-row-rail::after { display: none; }
.vd-event-row-copy { display: grid; gap: 0.15rem; min-inline-size: 0; }
.vd-event-row-title { color: var(--vd-color-text); font-size: var(--vd-text-sm); font-weight: var(--vd-weight-medium); }
.vd-event-row-detail,
.vd-event-row-meta,
.vd-event-row-time { color: var(--vd-color-text-muted); font-size: var(--vd-text-xs); }
.vd-event-row-tail {
    display: flex;
    align-items: flex-start;
    gap: var(--vd-space-sm);
    white-space: nowrap;
}

.vd-inspector-panel {
    position: fixed;
    inset: 0 0 0 auto;
    inline-size: min(30rem, 100vw);
    block-size: 100dvh;
    max-block-size: none;
    margin: 0;
    padding: 0;
    border: 0;
    border-inline-start: 1px solid var(--vd-color-border-soft);
    background: var(--vd-color-background);
    color: var(--vd-color-text);
    box-shadow: -1rem 0 3rem rgb(0 0 0 / 0.12);
}
.vd-inspector-panel::backdrop { background: rgb(0 0 0 / 0.24); }
.vd-inspector-header {
    display: grid;
    gap: var(--vd-space-xs);
    padding: var(--vd-space-xl);
    border-block-end: 1px solid var(--vd-color-border-soft);
}
.vd-inspector-description { color: var(--vd-color-text-muted); font-size: var(--vd-text-sm); }
.vd-inspector-body { padding: var(--vd-space-xl); overflow: auto; }

.vd-log-viewer {
    display: grid;
    align-content: start;
    max-block-size: 30rem;
    overflow: auto;
    padding: var(--vd-space-md);
    border: 1px solid var(--vd-color-border-soft);
    border-radius: var(--vd-radius-md);
    background: var(--vd-code-background);
    color: var(--vd-code-text);
    font-family: var(--vd-font-mono);
    font-size: var(--vd-text-xs);
    line-height: 1.65;
}
.vd-log-line {
    display: block;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
.vd-log-viewer-empty { color: var(--vd-code-comment); }

.vd-command-bar {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--vd-space-sm);
    padding: var(--vd-space-sm);
    border: 1px solid var(--vd-color-border-soft);
    border-radius: var(--vd-radius-lg);
    background: var(--vd-color-surface);
}
.vd-command-bar-icon { margin-inline-start: var(--vd-space-sm); color: var(--vd-color-text-muted); }
.vd-command-bar .vd-input {
    border: 0;
    background: transparent;
    box-shadow: none;
}
.vd-command-bar .vd-input:focus-visible { box-shadow: none; }

@keyframes vd-status-pulse {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--vd-color-success) 35%, transparent); }
    70% { box-shadow: 0 0 0 0.35rem transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
}

@media (max-width: 640px) {
    .vd-event-row { grid-template-columns: 1rem minmax(0, 1fr); }
    .vd-event-row-tail { grid-column: 2; flex-wrap: wrap; }
    .vd-data-table th,
    .vd-data-table td { padding-inline: var(--vd-space-md); }
    .vd-command-bar { grid-template-columns: auto minmax(0, 1fr); }
    .vd-command-bar > .vd-button { grid-column: 1 / -1; inline-size: 100%; }
}
"""
