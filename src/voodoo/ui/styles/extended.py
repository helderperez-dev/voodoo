"""Native styles for Voodoo extended UI components.

Covers all Priority 1–5 additions: interaction kernel, forms, navigation,
workspace, and data-heavy interfaces.
"""

from voodoo.ui.styles.theme import Theme


def generate_extended_css(theme: Theme) -> str:
    """Return semantic CSS for all extended UI components."""

    return """
/* ══════════════════════════════════════════════════════════════════════
   Voodoo Extended UI — All Priorities
   ══════════════════════════════════════════════════════════════════════ */

/* ── Priority 1: Interaction Kernel ───────────────────────────────── */

/* Alert Dialog */
.vd-alert-dialog { position: relative; }
.vd-alert-dialog-panel {
    position: fixed; inset: 0; z-index: 50;
    display: grid; place-items: center;
    background: color-mix(in srgb, var(--vd-color-background) 80%, transparent);
    padding: var(--vd-space-lg);
}
.vd-alert-dialog-content {
    max-inline-size: 28rem; width: 100%;
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-lg);
    padding: var(--vd-space-xl);
    box-shadow: var(--vd-shadow-lg, 0 10px 40px rgba(0,0,0,.25));
}
.vd-alert-dialog-title {
    font-size: var(--vd-text-lg);
    font-weight: var(--vd-weight-semibold);
    color: var(--vd-color-text);
    margin: 0 0 var(--vd-space-sm);
}
.vd-alert-dialog-description {
    font-size: var(--vd-text-sm);
    color: var(--vd-color-text-muted);
    margin: 0 0 var(--vd-space-lg);
}
.vd-alert-dialog-actions {
    display: flex; justify-content: flex-end; gap: var(--vd-space-sm);
}

/* Toggle Group */
.vd-toggle-group {
    display: inline-flex;
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    overflow: hidden;
}
.vd-toggle-group[data-orientation="vertical"] { flex-direction: column; }
.vd-toggle-item {
    display: inline-flex; align-items: center; justify-content: center;
    min-inline-size: 2.25rem; min-block-size: 2rem;
    padding-inline: var(--vd-space-sm);
    background: transparent;
    border: none;
    border-right: 1px solid var(--vd-color-border);
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    transition: background var(--vd-motion-fast, .15s), color var(--vd-motion-fast, .15s);
}
.vd-toggle-item:last-child { border-right: none; }
.vd-toggle-item:hover { background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent); }
.vd-toggle-item[data-state="on"],
.vd-toggle-item[aria-pressed="true"] {
    background: var(--vd-color-primary);
    color: var(--vd-color-primary-fg, #fff);
}
.vd-toggle-item:disabled { opacity: .5; cursor: not-allowed; }

/* Segmented Control */
.vd-segmented-control {
    display: inline-flex;
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    padding: 2px;
    gap: 2px;
}
.vd-segment {
    flex: 1;
    display: inline-flex; align-items: center; justify-content: center;
    min-block-size: 2rem;
    padding-inline: var(--vd-space-md);
    background: transparent;
    border: none;
    border-radius: calc(var(--vd-radius-md) - 2px);
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
    cursor: pointer;
    transition: background var(--vd-motion-fast, .15s), color var(--vd-motion-fast, .15s);
}
.vd-segment:hover { color: var(--vd-color-text); }
.vd-segment[aria-selected="true"],
.vd-segment[data-state="active"] {
    background: var(--vd-color-primary);
    color: var(--vd-color-primary-fg, #fff);
    box-shadow: var(--vd-shadow-sm, 0 1px 3px rgba(0,0,0,.12));
}

/* Context Menu */
.vd-context-menu-panel {
    position: fixed; z-index: 100;
    min-inline-size: 12rem;
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    padding: var(--vd-space-xs);
    box-shadow: var(--vd-shadow-lg, 0 10px 40px rgba(0,0,0,.25));
}
.vd-menu-group-label {
    padding: var(--vd-space-xs) var(--vd-space-sm);
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-semibold);
    color: var(--vd-color-text-muted);
    text-transform: uppercase;
    letter-spacing: .05em;
}
.vd-menu-item {
    display: flex; align-items: center; gap: var(--vd-space-sm);
    width: 100%;
    padding: var(--vd-space-xs) var(--vd-space-sm);
    background: transparent;
    border: none;
    border-radius: calc(var(--vd-radius-md) - 2px);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    text-align: start;
}
.vd-menu-item:hover,
.vd-menu-item[data-highlighted] {
    background: color-mix(in srgb, var(--vd-color-primary) 12%, transparent);
}
.vd-menu-item:disabled { opacity: .5; cursor: not-allowed; }
.vd-menu-item-icon { inline-size: 1rem; block-size: 1rem; opacity: .7; }
.vd-menu-item-label { flex: 1; }
.vd-menu-item-shortcut {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    font-family: var(--vd-font-mono, monospace);
}
.vd-menu-checkbox-indicator,
.vd-menu-radio-indicator {
    inline-size: 1rem; display: flex; align-items: center; justify-content: center;
}

/* SubMenu */
.vd-sub-menu { position: relative; }
.vd-sub-menu-trigger { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.vd-sub-menu-arrow { inline-size: .75rem; opacity: .5; }
.vd-sub-menu-panel {
    position: absolute; left: 100%; top: 0;
    min-inline-size: 12rem;
    margin-inline-start: var(--vd-space-xs);
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    padding: var(--vd-space-xs);
    box-shadow: var(--vd-shadow-lg, 0 10px 40px rgba(0,0,0,.25));
}

/* Command Palette */
.vd-command-panel {
    position: fixed; inset: 0; z-index: 60;
    display: grid; place-items: start center;
    padding-top: 20vh;
    background: color-mix(in srgb, var(--vd-color-background) 80%, transparent);
}
.vd-command-dialog {
    max-inline-size: 32rem; width: calc(100% - 2rem);
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-lg);
    box-shadow: var(--vd-shadow-lg, 0 10px 40px rgba(0,0,0,.35));
    overflow: hidden;
}
.vd-command-search {
    display: flex; align-items: center; gap: var(--vd-space-sm);
    padding: var(--vd-space-md);
    border-bottom: 1px solid var(--vd-color-border);
}
.vd-command-search-icon { inline-size: 1rem; opacity: .5; flex-shrink: 0; }
.vd-command-input {
    flex: 1; background: transparent; border: none; outline: none;
    font-size: var(--vd-text-sm); color: var(--vd-color-text);
}
.vd-command-results { max-block-size: 20rem; overflow-y: auto; padding: var(--vd-space-xs); }
.vd-command-empty {
    padding: var(--vd-space-xl);
    text-align: center;
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
}
.vd-command-group-heading {
    padding: var(--vd-space-xs) var(--vd-space-sm);
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-semibold);
    color: var(--vd-color-text-muted);
    text-transform: uppercase;
    letter-spacing: .05em;
}
.vd-command-item {
    display: flex; align-items: center; gap: var(--vd-space-sm);
    width: 100%;
    padding: var(--vd-space-xs) var(--vd-space-sm);
    background: transparent;
    border: none;
    border-radius: calc(var(--vd-radius-md) - 2px);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    text-align: start;
}
.vd-command-item:hover,
.vd-command-item[data-highlighted] {
    background: color-mix(in srgb, var(--vd-color-primary) 12%, transparent);
}
.vd-command-item-icon { inline-size: 1rem; opacity: .5; }
.vd-command-item-text { flex: 1; }
.vd-command-item-shortcut {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    font-family: var(--vd-font-mono, monospace);
}

/* Layer / Portal */
.vd-layer { position: relative; z-index: inherit; }
.vd-dismiss-layer { position: fixed; inset: 0; z-index: -1; }

/* ── Priority 2: Complete Forms ───────────────────────────────────── */

/* OTP Input */
.vd-otp-input {
    display: grid; gap: var(--vd-space-sm);
}
.vd-otp-label {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
    color: var(--vd-color-text);
}
.vd-otp-fields {
    display: flex; gap: var(--vd-space-xs);
}
.vd-otp-field {
    inline-size: 2.5rem; block-size: 3rem;
    text-align: center;
    font-size: var(--vd-text-xl);
    font-weight: var(--vd-weight-semibold);
    font-family: var(--vd-font-mono, monospace);
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    color: var(--vd-color-text);
    outline: none;
    transition: border-color var(--vd-motion-fast, .15s), box-shadow var(--vd-motion-fast, .15s);
}
.vd-otp-field:focus {
    border-color: var(--vd-color-primary);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--vd-color-primary) 25%, transparent);
}
.vd-otp-field:disabled { opacity: .5; cursor: not-allowed; }

/* Range Slider */
.vd-range-slider {
    display: grid; gap: var(--vd-space-sm);
}
.vd-range-slider-label {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
    color: var(--vd-color-text);
}
.vd-range-slider-track {
    display: flex; justify-content: space-between;
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
}
.vd-range-slider-fields {
    position: relative; block-size: 2rem;
}
.vd-range-slider-fields input[type="range"] {
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    appearance: none; -webkit-appearance: none;
    background: transparent;
    pointer-events: none;
}
.vd-range-slider-fields input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    inline-size: 1rem; block-size: 1rem;
    border-radius: 50%;
    background: var(--vd-color-primary);
    border: 2px solid var(--vd-color-surface);
    box-shadow: var(--vd-shadow-sm, 0 1px 3px rgba(0,0,0,.2));
    cursor: pointer;
    pointer-events: auto;
}
.vd-range-slider-fields input[type="range"]::-webkit-slider-runnable-track {
    block-size: 4px;
    background: var(--vd-color-border);
    border-radius: var(--vd-radius-full);
}

/* Autocomplete */
.vd-autocomplete { position: relative; }
.vd-autocomplete-list {
    position: absolute; inset-inline-start: 0; inset-block-start: 100%;
    inline-size: 100%;
    margin-block-start: var(--vd-space-xs);
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    box-shadow: var(--vd-shadow-md, 0 4px 16px rgba(0,0,0,.15));
    max-block-size: 15rem;
    overflow-y: auto;
    z-index: 20;
}
.vd-autocomplete-option {
    display: block; width: 100%;
    padding: var(--vd-space-xs) var(--vd-space-sm);
    background: transparent;
    border: none;
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    text-align: start;
}
.vd-autocomplete-option:hover,
.vd-autocomplete-option[aria-selected="true"] {
    background: color-mix(in srgb, var(--vd-color-primary) 12%, transparent);
}
.vd-autocomplete-empty {
    padding: var(--vd-space-md);
    text-align: center;
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
}

/* Form Validation Summary */
.vd-form-validation-summary {
    padding: var(--vd-space-md);
    background: color-mix(in srgb, var(--vd-color-danger, #ef4444) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--vd-color-danger, #ef4444) 30%, transparent);
    border-radius: var(--vd-radius-md);
    margin-block-end: var(--vd-space-md);
}
.vd-form-validation-summary-heading {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-semibold);
    color: var(--vd-color-danger, #ef4444);
    margin: 0 0 var(--vd-space-sm);
}
.vd-form-validation-summary-list {
    list-style: none; padding: 0; margin: 0;
    display: grid; gap: var(--vd-space-xs);
}
.vd-form-validation-summary-link {
    color: var(--vd-color-danger, #ef4444);
    text-decoration: underline;
    font-size: var(--vd-text-sm);
}
.vd-form-validation-summary-link:hover { opacity: .8; }

/* Checkbox / Radio enhanced */
.vd-checkbox-input,
.vd-radio-input {
    display: flex; align-items: flex-start; gap: var(--vd-space-sm);
}
.vd-checkbox-label,
.vd-radio-label {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
    color: var(--vd-color-text);
    cursor: pointer;
}
.vd-checkbox-description,
.vd-radio-description {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    margin-block-start: 0.15rem;
}

/* ── Priority 3: Adaptive Navigation ─────────────────────────────── */

/* Pagination */
.vd-pagination {
    display: flex; align-items: center; gap: var(--vd-space-xs);
}
.vd-pagination-prev,
.vd-pagination-next,
.vd-pagination-page {
    display: inline-flex; align-items: center; justify-content: center;
    min-inline-size: 2rem; min-block-size: 2rem;
    padding-inline: var(--vd-space-xs);
    background: transparent;
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    transition: background var(--vd-motion-fast, .15s), color var(--vd-motion-fast, .15s);
}
.vd-pagination-prev:hover,
.vd-pagination-next:hover,
.vd-pagination-page:hover {
    background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent);
}
.vd-pagination-page[aria-current="page"] {
    background: var(--vd-color-primary);
    color: var(--vd-color-primary-fg, #fff);
    border-color: var(--vd-color-primary);
}
.vd-pagination-prev:disabled,
.vd-pagination-next:disabled,
.vd-pagination-page:disabled {
    opacity: .4; cursor: not-allowed;
}
.vd-pagination-ellipsis {
    inline-size: 2rem; text-align: center;
    color: var(--vd-color-text-muted);
}

/* Stepper */
.vd-stepper { display: flex; gap: var(--vd-space-md); }
.vd-stepper[data-orientation="vertical"] { flex-direction: column; }
.vd-step {
    display: flex; align-items: flex-start; gap: var(--vd-space-sm);
    flex: 1;
}
.vd-step-indicator {
    display: flex; align-items: center; justify-content: center;
    inline-size: 2rem; block-size: 2rem;
    border-radius: 50%;
    border: 2px solid var(--vd-color-border);
    background: var(--vd-color-surface);
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-semibold);
    flex-shrink: 0;
    transition: all var(--vd-motion-fast, .15s);
}
.vd-step[data-vd_step_state="active"] .vd-step-indicator {
    border-color: var(--vd-color-primary);
    background: var(--vd-color-primary);
    color: var(--vd-color-primary-fg, #fff);
}
.vd-step[data-vd_step_state="completed"] .vd-step-indicator {
    border-color: var(--vd-color-success, #22c55e);
    background: var(--vd-color-success, #22c55e);
    color: #fff;
}
.vd-step-label {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
    color: var(--vd-color-text);
}
.vd-step[data-vd_step_state="upcoming"] .vd-step-label { color: var(--vd-color-text-muted); }
.vd-step-description {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    margin-block-start: 0.1rem;
}

/* Anchor Navigation */
.vd-anchor-nav {
    position: sticky; top: var(--vd-space-lg);
    display: grid; gap: var(--vd-space-sm);
    padding: var(--vd-space-md);
    border-inline-start: 2px solid var(--vd-color-border);
}
.vd-anchor-nav-heading {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-semibold);
    color: var(--vd-color-text);
    margin: 0;
}
.vd-anchor-nav-list { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--vd-space-xs); }
.vd-anchor-nav-link {
    display: block;
    padding: var(--vd-space-xs) var(--vd-space-sm);
    color: var(--vd-color-text-muted);
    font-size: var(--vd-text-sm);
    text-decoration: none;
    border-radius: var(--vd-radius-sm);
    transition: color var(--vd-motion-fast, .15s), background var(--vd-motion-fast, .15s);
}
.vd-anchor-nav-link:hover,
.vd-anchor-nav-link.active {
    color: var(--vd-color-primary);
    background: color-mix(in srgb, var(--vd-color-primary) 8%, transparent);
}

/* Action Sheet */
.vd-action-sheet-panel {
    position: fixed; inset-inline: 0; inset-block-end: 0; z-index: 50;
    background: var(--vd-color-surface);
    border-block-start: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-xl) var(--vd-radius-xl) 0 0;
    padding: var(--vd-space-md) var(--vd-space-md) var(--vd-space-xl);
    max-block-size: 80vh;
    overflow-y: auto;
}
.vd-action-sheet-header {
    text-align: center;
    padding-block-end: var(--vd-space-md);
    border-block-end: 1px solid var(--vd-color-border);
    margin-block-end: var(--vd-space-sm);
}
.vd-action-sheet-title {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-semibold);
    margin: 0;
}
.vd-action-sheet-description {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    margin: var(--vd-space-xs) 0 0;
}
.vd-action-sheet-list { display: grid; gap: 1px; }
.vd-action-item {
    display: flex; align-items: center; gap: var(--vd-space-sm);
    width: 100%;
    padding: var(--vd-space-sm);
    background: transparent;
    border: none;
    border-radius: var(--vd-radius-md);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    text-align: start;
}
.vd-action-item:hover { background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent); }
.vd-action-item[data-destructive="true"] { color: var(--vd-color-danger, #ef4444); }
.vd-action-item:disabled { opacity: .5; cursor: not-allowed; }
.vd-action-icon { inline-size: 1.25rem; flex-shrink: 0; }
.vd-action-copy { flex: 1; }
.vd-action-description { font-size: var(--vd-text-xs); color: var(--vd-color-text-muted); display: block; }
.vd-action-sheet-cancel {
    margin-block-start: var(--vd-space-sm);
    padding: var(--vd-space-sm);
    width: 100%;
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-semibold);
    cursor: pointer;
    text-align: center;
}

/* Bottom Sheet */
.vd-bottom-sheet-panel {
    position: fixed; inset-inline: 0; inset-block-end: 0; z-index: 50;
    background: var(--vd-color-surface);
    border-block-start: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-xl) var(--vd-radius-xl) 0 0;
    max-block-size: 90vh;
    display: flex; flex-direction: column;
}
.vd-bottom-sheet-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: var(--vd-space-md);
    border-block-end: 1px solid var(--vd-color-border);
    flex-shrink: 0;
}
.vd-bottom-sheet-title {
    font-size: var(--vd-text-base);
    font-weight: var(--vd-weight-semibold);
    margin: 0;
}
.vd-bottom-sheet-handle {
    inline-size: 2rem; block-size: 4px;
    background: var(--vd-color-border);
    border-radius: var(--vd-radius-full);
    margin: var(--vd-space-sm) auto 0;
}
.vd-bottom-sheet-body {
    flex: 1; overflow-y: auto;
    padding: var(--vd-space-md);
}

/* Top Bar */
.vd-top-bar {
    display: flex; align-items: center; gap: var(--vd-space-md);
    padding-inline: var(--vd-space-md);
    min-block-size: 3rem;
    background: var(--vd-color-surface);
    border-block-end: 1px solid var(--vd-color-border);
}
.vd-top-bar[data-vd_sticky="true"] { position: sticky; top: 0; z-index: 40; }
.vd-top-bar-leading { display: flex; align-items: center; }
.vd-top-bar-center { flex: 1; display: flex; justify-content: center; }
.vd-top-bar-trailing { display: flex; align-items: center; gap: var(--vd-space-sm); }
.vd-top-bar-title {
    font-size: var(--vd-text-base);
    font-weight: var(--vd-weight-semibold);
}

/* Navigation Menu (mega-menu) */
.vd-navigation-menu-list {
    display: flex; gap: var(--vd-space-xs);
    list-style: none; padding: 0; margin: 0;
}
.vd-navigation-menu-trigger {
    display: inline-flex; align-items: center; gap: var(--vd-space-xs);
    padding: var(--vd-space-xs) var(--vd-space-sm);
    background: transparent;
    border: none;
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    border-radius: var(--vd-radius-md);
}
.vd-navigation-menu-trigger:hover {
    background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent);
}
.vd-navigation-menu-content {
    position: absolute; top: 100%;
    min-inline-size: 20rem;
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    padding: var(--vd-space-md);
    box-shadow: var(--vd-shadow-lg, 0 10px 40px rgba(0,0,0,.25));
    z-index: 50;
}
.vd-nav-column { display: grid; gap: var(--vd-space-xs); }
.vd-nav-link-item {
    display: flex; align-items: flex-start; gap: var(--vd-space-sm);
    padding: var(--vd-space-sm);
    border-radius: var(--vd-radius-md);
    text-decoration: none;
    color: var(--vd-color-text);
}
.vd-nav-link-item:hover { background: color-mix(in srgb, var(--vd-color-primary) 8%, transparent); }
.vd-nav-link-description {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    display: block;
}

/* ── Priority 4: Desktop Workspaces ──────────────────────────────── */

/* Resizable Panels */
.vd-resizable-panels {
    display: flex;
    overflow: hidden;
}
.vd-resizable-panels[data-vd_orientation="vertical"] { flex-direction: column; }
.vd-resizable-panels-panel {
    overflow: auto;
    min-inline-size: 0; min-block-size: 0;
}
.vd-resizable-panels-panel[data-vd_collapsed="true"] { display: none; }
.vd-resizable-panels-handle {
    flex-shrink: 0;
    inline-size: 4px; block-size: 100%;
    background: var(--vd-color-border);
    cursor: col-resize;
    transition: background var(--vd-motion-fast, .15s);
}
.vd-resizable-panels-handle:hover,
.vd-resizable-panels-handle:active {
    background: var(--vd-color-primary);
}
.vd-resizable-panels[data-vd_orientation="vertical"] .vd-resizable-panels-handle {
    inline-size: 100%; block-size: 4px;
    cursor: row-resize;
}

/* Scroll Area */
.vd-scroll-area {
    scrollbar-width: thin;
    scrollbar-color: var(--vd-color-border) transparent;
}
.vd-scroll-area::-webkit-scrollbar { width: 6px; height: 6px; }
.vd-scroll-area::-webkit-scrollbar-track { background: transparent; }
.vd-scroll-area::-webkit-scrollbar-thumb {
    background: color-mix(in srgb, var(--vd-color-text-muted) 30%, transparent);
    border-radius: var(--vd-radius-full);
}
.vd-scroll-area::-webkit-scrollbar-thumb:hover {
    background: color-mix(in srgb, var(--vd-color-text-muted) 50%, transparent);
}

/* Tree View */
.vd-tree-view-list,
.vd-tree-view-group {
    list-style: none; padding: 0; margin: 0;
}
.vd-tree-view-group { padding-inline-start: var(--vd-space-md); }
.vd-tree-view-row {
    display: flex; align-items: center; gap: var(--vd-space-xs);
    padding: var(--vd-space-xs) var(--vd-space-sm);
    border-radius: var(--vd-radius-sm);
    cursor: pointer;
    transition: background var(--vd-motion-fast, .15s);
}
.vd-tree-view-row:hover { background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent); }
.vd-tree-view-row[aria-selected="true"] {
    background: color-mix(in srgb, var(--vd-color-primary) 12%, transparent);
    color: var(--vd-color-primary);
}
.vd-tree-view-toggle {
    display: inline-flex; align-items: center; justify-content: center;
    inline-size: 1.25rem; block-size: 1.25rem;
    background: transparent; border: none;
    color: var(--vd-color-text-muted);
    cursor: pointer;
    padding: 0;
}
.vd-tree-view-spacer { inline-size: 1.25rem; flex-shrink: 0; }
.vd-tree-view-icon { inline-size: 1rem; opacity: .7; flex-shrink: 0; }

/* Toolbar */
.vd-toolbar {
    display: flex; align-items: center;
    gap: var(--vd-space-xs);
    padding: var(--vd-space-xs);
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
}
.vd-toolbar[data-aria_orientation="vertical"],
.vd-toolbar[aria-orientation="vertical"] {
    flex-direction: column;
    inline-size: min-content;
}
.vd-toolbar-group {
    display: flex; align-items: center; gap: 2px;
}
.vd-toolbar-button {
    display: inline-flex; align-items: center; justify-content: center;
    min-inline-size: 2rem; min-block-size: 2rem;
    padding: var(--vd-space-xs);
    background: transparent;
    border: none;
    border-radius: calc(var(--vd-radius-md) - 2px);
    color: var(--vd-color-text-muted);
    cursor: pointer;
    transition: background var(--vd-motion-fast, .15s), color var(--vd-motion-fast, .15s);
}
.vd-toolbar-button:hover {
    background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent);
    color: var(--vd-color-text);
}
.vd-toolbar-button[aria-pressed="true"] {
    background: color-mix(in srgb, var(--vd-color-primary) 15%, transparent);
    color: var(--vd-color-primary);
}
.vd-toolbar-button:disabled { opacity: .4; cursor: not-allowed; }
.vd-toolbar-button-icon { inline-size: 1rem; }
.vd-toolbar-separator {
    inline-size: 1px; block-size: 1.5rem;
    background: var(--vd-color-border);
    margin-inline: var(--vd-space-xs);
}

/* Menubar */
.vd-menubar-list {
    display: flex; gap: 2px;
    list-style: none; padding: var(--vd-space-xs); margin: 0;
    background: var(--vd-color-surface);
    border-block-end: 1px solid var(--vd-color-border);
}
.vd-menubar-trigger {
    display: inline-flex; align-items: center;
    padding: var(--vd-space-xs) var(--vd-space-sm);
    background: transparent;
    border: none;
    border-radius: calc(var(--vd-radius-md) - 2px);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
}
.vd-menubar-trigger:hover {
    background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent);
}
.vd-menubar-dropdown {
    position: absolute; top: 100%;
    min-inline-size: 14rem;
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    padding: var(--vd-space-xs);
    box-shadow: var(--vd-shadow-lg, 0 10px 40px rgba(0,0,0,.25));
    z-index: 50;
}
.vd-menubar-dropdown-item {
    display: flex; align-items: center; justify-content: space-between;
    width: 100%;
    padding: var(--vd-space-xs) var(--vd-space-sm);
    background: transparent;
    border: none;
    border-radius: calc(var(--vd-radius-md) - 2px);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    text-align: start;
}
.vd-menubar-dropdown-item:hover {
    background: color-mix(in srgb, var(--vd-color-primary) 12%, transparent);
}
.vd-menubar-shortcut {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    font-family: var(--vd-font-mono, monospace);
}
.vd-menubar-separator {
    border: none;
    border-block-start: 1px solid var(--vd-color-border);
    margin: var(--vd-space-xs) 0;
}

/* Dock */
.vd-dock-list {
    display: flex; align-items: flex-end; justify-content: center;
    gap: var(--vd-space-xs);
    list-style: none; padding: var(--vd-space-sm) var(--vd-space-md); margin: 0;
    background: color-mix(in srgb, var(--vd-color-surface) 80%, transparent);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-xl);
    backdrop-filter: blur(8px);
}
.vd-dock[data-vd_dock_position="top"] .vd-dock-list { align-items: flex-start; }
.vd-dock[data-vd_dock_position="left"] .vd-dock-list,
.vd-dock[data-vd_dock_position="right"] .vd-dock-list { flex-direction: column; }
.vd-dock-button {
    display: flex; flex-direction: column; align-items: center;
    gap: var(--vd-space-xs);
    background: transparent;
    border: none;
    padding: var(--vd-space-xs);
    cursor: pointer;
    border-radius: var(--vd-radius-md);
    transition: transform var(--vd-motion-fast, .15s);
}
.vd-dock-button:hover { transform: scale(1.15); }
.vd-dock-icon { inline-size: 2.5rem; block-size: 2.5rem; }
.vd-dock-tooltip {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text);
    opacity: 0;
    transition: opacity var(--vd-motion-fast, .15s);
    pointer-events: none;
}
.vd-dock-button:hover .vd-dock-tooltip { opacity: 1; }
.vd-dock-badge {
    position: absolute; top: 0; inset-inline-end: 0;
    inline-size: 1rem; block-size: 1rem;
    display: flex; align-items: center; justify-content: center;
    background: var(--vd-color-danger, #ef4444);
    color: #fff;
    border-radius: 50%;
    font-size: .625rem;
    font-weight: var(--vd-weight-bold);
}

/* Master-Detail */
.vd-master-detail {
    display: flex;
    block-size: 100%;
    overflow: hidden;
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
}
.vd-master-detail-master {
    flex-shrink: 0;
    border-inline-end: 1px solid var(--vd-color-border);
    overflow-y: auto;
    background: var(--vd-color-surface);
}
.vd-master-detail-list {
    list-style: none; padding: 0; margin: 0;
}
.vd-master-detail-item-button {
    display: flex; align-items: center; gap: var(--vd-space-sm);
    width: 100%;
    padding: var(--vd-space-sm) var(--vd-space-md);
    background: transparent;
    border: none;
    border-block-end: 1px solid color-mix(in srgb, var(--vd-color-border) 50%, transparent);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    text-align: start;
}
.vd-master-detail-item-button:hover {
    background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent);
}
.vd-master-detail-item-button[aria-selected="true"] {
    background: color-mix(in srgb, var(--vd-color-primary) 10%, transparent);
    color: var(--vd-color-primary);
}
.vd-master-detail-item-icon { inline-size: 1.25rem; flex-shrink: 0; }
.vd-master-detail-item-label { font-weight: var(--vd-weight-medium); }
.vd-master-detail-item-summary {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
}
.vd-master-detail-separator {
    border: none;
    border-inline-start: 1px solid var(--vd-color-border);
    align-self: stretch;
}
.vd-master-detail-detail {
    flex: 1; overflow-y: auto;
    padding: var(--vd-space-md);
}

/* Keyboard Shortcuts */
.vd-keyboard-shortcuts {
    padding: var(--vd-space-md);
}
.vd-keyboard-shortcuts-heading {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-semibold);
    margin: 0 0 var(--vd-space-sm);
}
.vd-keyboard-shortcuts-list {
    list-style: none; padding: 0; margin: 0;
    display: grid; gap: var(--vd-space-xs);
}
.vd-keyboard-shortcuts-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: var(--vd-space-xs) 0;
}
.vd-keyboard-shortcuts-binding { display: flex; align-items: center; gap: var(--vd-space-sm); }
.vd-keyboard-shortcuts-keys {
    display: inline-flex; align-items: center; gap: 2px;
    padding: 2px 6px;
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-sm);
    font-family: var(--vd-font-mono, monospace);
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
    box-shadow: 0 1px 0 var(--vd-color-border);
}
.vd-keyboard-shortcuts-description {
    font-size: var(--vd-text-sm);
    color: var(--vd-color-text-muted);
}

/* ── Priority 5: Data-Heavy Interfaces ───────────────────────────── */

/* Description List */
.vd-description-list {
    display: grid; gap: 0;
}
.vd-description-list[data-vd_orientation="horizontal"] {
    grid-template-columns: max-content 1fr;
    gap: var(--vd-space-xs) var(--vd-space-md);
}
.vd-description-list-section {
    display: contents;
}
.vd-description-list-section-title {
    grid-column: 1 / -1;
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-semibold);
    color: var(--vd-color-text-muted);
    text-transform: uppercase;
    letter-spacing: .05em;
    padding-block-start: var(--vd-space-md);
    border-block-start: 1px solid var(--vd-color-border);
    margin-block-start: var(--vd-space-sm);
}
.vd-description-list-term {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-medium);
    color: var(--vd-color-text-muted);
    padding: var(--vd-space-xs) 0;
}
.vd-description-list-value {
    font-size: var(--vd-text-sm);
    color: var(--vd-color-text);
    padding: var(--vd-space-xs) 0;
}
.vd-description-list-link {
    color: var(--vd-color-primary);
    text-decoration: underline;
}

/* Data List */
.vd-data-list {
    display: grid; gap: 0;
}
.vd-data-list[data-vd_compact="true"] .vd-data-list-term,
.vd-data-list[data-vd_compact="true"] .vd-data-list-value {
    padding: 2px 0;
    font-size: var(--vd-text-xs);
}
.vd-data-list[data-vd_striped="true"] .vd-data-list-term:nth-of-type(odd),
.vd-data-list[data-vd_striped="true"] .vd-data-list-value:nth-of-type(odd) {
    background: color-mix(in srgb, var(--vd-color-surface) 30%, transparent);
}
.vd-data-list-term {
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-medium);
    color: var(--vd-color-text-muted);
    text-transform: uppercase;
    letter-spacing: .03em;
    padding: var(--vd-space-xs);
}
.vd-data-list-value {
    font-size: var(--vd-text-sm);
    color: var(--vd-color-text);
    padding: var(--vd-space-xs);
}
.vd-data-list-value[data-vd_highlight="true"] {
    color: var(--vd-color-primary);
    font-weight: var(--vd-weight-medium);
}
.vd-data-list-value[data-vd_monospace="true"] {
    font-family: var(--vd-font-mono, monospace);
    font-size: var(--vd-text-xs);
}

/* List Box */
.vd-list-box-group {
    list-style: none; padding: var(--vd-space-xs); margin: 0;
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
    max-block-size: 15rem;
    overflow-y: auto;
}
.vd-list-box-option {
    display: flex; align-items: center; gap: var(--vd-space-sm);
    width: 100%;
    padding: var(--vd-space-xs) var(--vd-space-sm);
    background: transparent;
    border: none;
    border-radius: calc(var(--vd-radius-md) - 2px);
    color: var(--vd-color-text);
    font-size: var(--vd-text-sm);
    cursor: pointer;
    text-align: start;
}
.vd-list-box-option:hover {
    background: color-mix(in srgb, var(--vd-color-surface) 60%, transparent);
}
.vd-list-box-option[aria-selected="true"] {
    background: color-mix(in srgb, var(--vd-color-primary) 12%, transparent);
    color: var(--vd-color-primary);
}
.vd-list-box-option:disabled { opacity: .5; cursor: not-allowed; }
.vd-list-box-option-icon { inline-size: 1rem; flex-shrink: 0; }
.vd-list-box-option-label { font-weight: var(--vd-weight-medium); }
.vd-list-box-option-description {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
}

/* Stat Group */
.vd-stat-group {
    display: grid;
    gap: var(--vd-space-md);
}
.vd-stat-group[data-vd_columns="2"] { grid-template-columns: repeat(2, 1fr); }
.vd-stat-group[data-vd_columns="3"] { grid-template-columns: repeat(3, 1fr); }
.vd-stat-group[data-vd_columns="4"] { grid-template-columns: repeat(4, 1fr); }
.vd-stat-group[data-vd_columns="5"] { grid-template-columns: repeat(5, 1fr); }
.vd-stat-group[data-vd_columns="6"] { grid-template-columns: repeat(6, 1fr); }
.vd-stat-card {
    display: grid; gap: 0.15rem;
    padding: var(--vd-space-md);
    background: var(--vd-color-surface);
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
}
.vd-stat-icon { inline-size: 1.25rem; color: var(--vd-color-text-muted); }
.vd-stat-label {
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-medium);
    color: var(--vd-color-text-muted);
    text-transform: uppercase;
    letter-spacing: .03em;
}
.vd-stat-value {
    font-size: var(--vd-text-2xl);
    font-weight: var(--vd-weight-bold);
    color: var(--vd-color-text);
    line-height: 1.2;
}
.vd-stat-prefix,
.vd-stat-suffix {
    font-size: var(--vd-text-sm);
    font-weight: var(--vd-weight-normal);
    color: var(--vd-color-text-muted);
}
.vd-stat-change {
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-medium);
}
.vd-stat-change[data-vd_trend="up"] { color: var(--vd-color-success, #22c55e); }
.vd-stat-change[data-vd_trend="down"] { color: var(--vd-color-danger, #ef4444); }
.vd-stat-change[data-vd_trend="neutral"] { color: var(--vd-color-text-muted); }
.vd-stat-description {
    font-size: var(--vd-text-xs);
    color: var(--vd-color-text-muted);
}

/* Enhanced Data Table */
.vd-enhanced-data-table-container {
    overflow: auto;
    border: 1px solid var(--vd-color-border);
    border-radius: var(--vd-radius-md);
}
.vd-enhanced-data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--vd-text-sm);
}
.vd-enhanced-data-table-head {
    position: sticky; top: 0;
    background: var(--vd-color-surface);
    z-index: 1;
}
.vd-enhanced-data-table-row { border-block-end: 1px solid var(--vd-color-border); }
.vd-enhanced-data-table-row[data-vd_event_click] { cursor: pointer; }
.vd-enhanced-data-table-row[data-vd_event_click]:hover {
    background: color-mix(in srgb, var(--vd-color-surface) 40%, transparent);
}
.vd-enhanced-data-table-col-header {
    display: flex; align-items: center; gap: var(--vd-space-xs);
    padding: var(--vd-space-sm) var(--vd-space-md);
    font-size: var(--vd-text-xs);
    font-weight: var(--vd-weight-semibold);
    color: var(--vd-color-text-muted);
    text-transform: uppercase;
    letter-spacing: .03em;
    white-space: nowrap;
    user-select: none;
}
.vd-enhanced-data-table-col-header[data-vd_pinned="left"] {
    position: sticky; left: 0;
    background: var(--vd-color-surface);
    z-index: 2;
}
.vd-enhanced-data-table-col-header[data-vd_pinned="right"] {
    position: sticky; right: 0;
    background: var(--vd-color-surface);
    z-index: 2;
}
.vd-enhanced-data-table-col-header[data-vd_event_click] { cursor: pointer; }
.vd-enhanced-data-table-col-header[data-vd_event_click]:hover {
    color: var(--vd-color-text);
}
.vd-enhanced-data-table-col-sort-icon { inline-size: .75rem; opacity: .4; }
.vd-enhanced-data-table-cell {
    padding: var(--vd-space-sm) var(--vd-space-md);
    white-space: nowrap;
}
.vd-enhanced-data-table-cell[data-vd_pinned="left"] {
    position: sticky; left: 0;
    background: var(--vd-color-background);
}
.vd-enhanced-data-table-cell[data-vd_pinned="right"] {
    position: sticky; right: 0;
    background: var(--vd-color-background);
}
.vd-enhanced-data-table-cell[data-vd_truncate="true"] {
    max-inline-size: 12rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.vd-enhanced-data-table-cell[data-vd_monospace="true"] {
    font-family: var(--vd-font-mono, monospace);
    font-size: var(--vd-text-xs);
}
/* Density */
[data-vd_density="compact"] .vd-enhanced-data-table-cell,
[data-vd_density="compact"] .vd-enhanced-data-table-col-header {
    padding: 2px var(--vd-space-sm);
    font-size: var(--vd-text-xs);
}
[data-vd_density="comfortable"] .vd-enhanced-data-table-cell,
[data-vd_density="comfortable"] .vd-enhanced-data-table-col-header {
    padding: var(--vd-space-md) var(--vd-space-md);
}
"""
