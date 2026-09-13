"""Native styles for Voodoo operational system components."""

from voodoo.ui.styles.theme import Theme


def generate_voodoo_system_css(theme: Theme) -> str:
    """Return the visual language for canonical runtime concepts."""

    return """
/* ── Voodoo System Components ─────────────────────────────────────── */

.vd-runtime-status,
.vd-agent-status,
.vd-device-card,
.vd-execution-status,
.vd-approval-card,
.vd-world-entity-inspector,
.vd-policy-decision,
.vd-edge-node,
.vd-telemetry-panel {
    min-inline-size: 0;
}

.vd-runtime-status {
    display: grid;
    gap: var(--vd-space-xl);
    padding-block: var(--vd-space-md) var(--vd-space-lg);
}

.vd-system-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--vd-space-lg);
    min-inline-size: 0;
}
.vd-system-heading > .vd-heading { margin: 0; min-inline-size: 0; }

.vd-system-metric-strip,
.vd-telemetry-panel {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
    gap: clamp(var(--vd-space-lg), 3vw, var(--vd-space-xxl));
}

.vd-agent-status,
.vd-device-card,
.vd-execution-status,
.vd-approval-card,
.vd-world-entity-inspector,
.vd-policy-decision,
.vd-edge-node {
    display: grid;
    gap: var(--vd-space-md);
    padding-block: var(--vd-space-lg);
    border-block-end: 1px solid var(--vd-color-border-soft);
}

.vd-system-id {
    color: var(--vd-color-text-muted);
    font-family: var(--vd-font-mono);
    font-size: var(--vd-text-xs);
    overflow-wrap: anywhere;
}
.vd-system-meta,
.vd-system-description {
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
    line-height: var(--vd-leading-normal);
}

.vd-system-facts {
    display: flex;
    flex-wrap: wrap;
    gap: var(--vd-space-xl);
    padding-block-start: var(--vd-space-sm);
}
.vd-system-fact {
    display: grid;
    gap: 0.125rem;
}
.vd-system-fact-label {
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-xs);
}
.vd-system-fact-value {
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
}

.vd-system-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--vd-space-sm);
    padding-block-start: var(--vd-space-sm);
}

.vd-approval-card {
    border: 1px solid color-mix(in srgb, var(--vd-color-warning) 28%, var(--vd-color-border-soft));
    border-radius: var(--vd-radius-lg);
    padding: var(--vd-space-xl);
    background: color-mix(in srgb, var(--vd-color-warning) 4%, var(--vd-color-surface));
}

.vd-property-list {
    display: grid;
    border-block-start: 1px solid var(--vd-color-border-soft);
    margin-block-start: var(--vd-space-sm);
}
.vd-property-row {
    display: grid;
    grid-template-columns: minmax(7rem, 0.65fr) minmax(0, 1.35fr);
    gap: var(--vd-space-lg);
    padding-block: var(--vd-space-sm);
    border-block-end: 1px solid var(--vd-color-border-soft);
}
.vd-property-key {
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
}
.vd-property-value {
    color: var(--vd-color-text);
    font-family: var(--vd-font-mono);
    font-size: var(--vd-text-xs);
    overflow-wrap: anywhere;
}

.vd-capability-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--vd-space-sm);
}
.vd-capability {
    display: inline-flex;
    align-items: center;
    min-height: 1.65rem;
    padding-inline: var(--vd-space-sm);
    border: 1px solid var(--vd-color-border-soft);
    border-radius: var(--vd-radius-sm);
    color: var(--vd-color-text-muted);
    background: var(--vd-muted-fill);
    font-family: var(--vd-font-mono);
    font-size: var(--vd-text-xs);
}

.vd-edge-node {
    position: relative;
}
.vd-edge-node::before {
    content: "EDGE";
    position: absolute;
    inset-block-start: var(--vd-space-lg);
    inset-inline-end: 0;
    color: var(--vd-color-text-muted);
    font-family: var(--vd-font-mono);
    font-size: 0.625rem;
    letter-spacing: 0.12em;
}

@media (max-width: 640px) {
    .vd-system-heading { align-items: flex-start; }
    .vd-system-facts { gap: var(--vd-space-lg); }
    .vd-property-row { grid-template-columns: 1fr; gap: 0.2rem; }
    .vd-system-actions { justify-content: stretch; }
    .vd-system-actions > .vd-button { flex: 1; }
}
"""
