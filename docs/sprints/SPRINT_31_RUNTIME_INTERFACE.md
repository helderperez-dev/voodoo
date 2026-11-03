# Sprint 31 — Runtime Interface

**Status:** IN PROGRESS · Phase A started 2026-11-02
**Proposed:** 2026-11-02
**Source architecture:** [`ROADMAP.md`](../../ROADMAP.md),
[`DESIGN_CONSTITUTION.md`](../design/DESIGN_CONSTITUTION.md),
[`COMPONENT_API.md`](../design/COMPONENT_API.md)

> Activated on 2026-11-02 by product-owner decision and declared active in
> `SPRINT_PLAN.md`. It validates existing primitives, has recurring product
> value, creates a strong end-to-end acceptance target and makes later work
> simpler. Decisions taken at activation are listed under **Decided**.

## Thesis

Voodoo UI is not a component kit bolted onto a runtime. It is the **visual
projection of the Runtime**.

```text
World / Execution / Goal / HITL / Edge / Store
                    ↓
          Runtime events + snapshots
                    ↓
        Live, session-scoped UI bindings
                    ↓
  Primitives → Product patterns → System components
                    ↓
     Runtime Console · Store Studio · Builder · user apps
```

Sprint 29 and Sprint 30 hardened breadth, session isolation and evidence. They
did not make the interface *feel* like the Design Constitution describes —
"calm precision, invisible complexity" — and they did not connect the UI to the
Runtime it is supposed to express. Sprint 31 closes both gaps with one coherent
interface platform and proves it by building Voodoo's own operational product
surface with it.

## Why this is more than a component refresh

Restyling components would fix screenshots. The audit below shows that the
problems sit underneath the components:

1. the **style architecture** grew by accretion and has no single owner;
2. the **rendering engine** replaces DOM subtrees instead of reconciling them;
3. the **system components** are static dict renderers, not Runtime-aware;
4. Voodoo's own operational surfaces (`runtime_dashboard`) **do not use the
   UI system at all**;
5. the **visual evidence** gates certify defects instead of catching them.

Fixing (1) without (2)–(5) would produce a prettier kit that still cannot carry
the ROADMAP's Studio, Console and Builder products.

## Audit (2026-11-02)

Evidence was collected by running `examples/web/component_lab` in Chromium at
1360×900 (light/dark) and 390×844.

### A. Visual defects visible in the acceptance application

| Route | Defect |
|---|---|
| `/data` | `Metric` renders unstyled (`Requests12.8k+8%`); three table variants render three unrelated visual languages; an inspector drawer opens by default and covers the header. |
| `/forms` | Password reveal renders below the input; `NumberInput` steppers stack vertically; `Slider` uses the native browser accent; URL prefix addon is detached; label-to-control spacing differs per control. |
| `/workspace` | Resizable splitter overlaps the panel heading; tree indentation and selection geometry are inconsistent. |
| `/system` | `EdgeNode` kind label overlaps its status badge; card heights/alignment differ inside one row. |
| Header | Twelve unstyled inline links; wraps to four lines on mobile. |

The committed visual baselines under `tests/browser/visual_baselines/` were
generated from this state, so the visual gate currently **protects** these
defects.

### B. Style architecture

- Six generated CSS layers are concatenated into every page:
  `adapters/voodoo_css.py`, `ui/styles/system.py`, `ui/styles/extended.py`,
  `ui/styles/product.py`, `ui/styles/voodoo_system.py`,
  `ui/styles/theme_contract.py`.
- The same selectors are owned by several layers (`.vd-button` in 4 files,
  `.vd-input` in 3, `.vd-table` and `.vd-metric` in 2). Later "convergence"
  layers override earlier ones instead of replacing them.
- ~150 KB of CSS is inlined into every HTML response; nothing is cacheable.
- Design System 4 hard-codes Voodoo purple tokens even though the Constitution
  (§19) says identity must not depend on forcing every application to be purple.
- The shareable preset system already exists (`theme.json`, URL, user directory,
  `voodoo-theme-<name>` PyPI packages), but the visual layer bypasses it:
  `ui/styles/system.py` contains 67 literal colors, and
  `ui/styles/theme_contract.py` decides whether a Theme value is
  "explicitly customized" by comparing it to the old default. A theme that
  happens to reuse a default value is silently ignored, and no preset can
  re-skin the whole interface through tokens alone.
- The Tailwind adapter injects `cdn.tailwindcss.com`, a development-only build
  (`ui/rendering.py`), which conflicts with the production CSP posture of
  Sprint 30.

### C. Rendering engine

- `static/client.js` applies patches through `innerHTML` replacement with a
  focus snapshot. Scroll position inside subtrees, text selection, open
  overlays, CSS transitions and media state are lost on every patch.
- There is no keyed reconciliation, so list updates re-create every row and the
  Constitution's "state transitions" signature (§22.1) cannot be animated.

### D. Catalog shape

- `voodoo.ui` exports **219** names; **16** are `stable`.
- Overlapping families remain (`DataTable`/`Table`/`EnhancedDataTable`,
  `List`/`ListBox`/`DataList`, `Dialog`/`Modal`/`AlertDialog`, …).
- Component classes are spread across `library.py`, `controls.py`,
  `forms_extended.py`, `data_extended.py`, `navigation_extended.py`,
  `workspace.py`, `product.py`, `voodoo_system.py` with no anatomy contract.

### E. Runtime connection

- `ui/voodoo_system.py` components (`RuntimeStatus`, `ExecutionTimeline`,
  `ApprovalCard`, `WorldEntityInspector`, …) accept duck-typed dicts and render
  a snapshot. They do not subscribe to Runtime events, show freshness, source or
  connection state (Constitution §13), or support the
  `summary → state → history → technical detail` inspection path (§22.3).
- `runtime/inspection/dashboard.py` builds HTML strings by hand instead of
  composing Voodoo components — Voodoo does not dogfood its own UI.

## Product laws

1. **The Runtime is the source of truth; the UI is its projection.** System
   components bind to Runtime identities (execution id, entity id, goal id),
   not to copied dicts.
2. **One owner per visual decision.** Every token, selector and behavior has
   exactly one source file.
3. **Reconcile, never replace.** A patch must preserve focus, selection,
   scroll, open layers and running transitions.
4. **Fewer, finished components.** A component ships only when the full
   Constitution §11 anatomy is satisfied. Breadth follows quality.
5. **No default brand color.** The default theme is neutral and monochrome.
   Voodoo is recognizable by proportion, motion, inspection and state
   language — never by a hue. Every color is a theme decision.
6. **Themes are complete, small and shareable.** A theme is a data file that
   can restyle every component without CSS. Components contain zero literal
   colors.
7. **Dogfood first.** Voodoo's own operational surfaces are built with the
   public UI API and are acceptance applications.
8. **Evidence must be able to fail.** Visual and behavioral gates detect
   unstyled, overlapping and overflowing elements before humans approve images.
9. **Zero application JavaScript and zero custom CSS remain the happy path.**

## Workstreams

### 31.1 Interface foundations — one style owner

- [ ] ADR: single stylesheet architecture. One source of CSS organized with
  cascade layers: `@layer reset, tokens, base, components, patterns, system,
  utilities`. Delete the accreted convergence layers instead of overriding them.
- [x] Ship CSS and client runtime as **static, content-hashed, cacheable
  assets** served by the framework (no per-response inlining; CSP `'self'`).
  Done: `voodoo.ui.assets` publishes `/_voodoo/assets/<sha256>.css|js` with
  immutable caching and conditional GET. A page dropped from ~224 KB to ~27 KB,
  and all 12 Component Lab routes now render in Chromium under the production
  CSP (`style-src 'self'`, no inline runtime) with zero violations, enforced by
  a permanent browser test. Pixel comparison of 24 light/dark captures showed no
  change apart from one fixed defect.
- [x] Framework components no longer emit inline `style` attributes for static
  presentation: `tone`, heading `size`, `Box` padding scale, common
  `AspectRatio` ratios, `ScrollArea` axis, column alignment and named
  `MasterDetail` widths are semantic `data-vd-*` attributes styled by the
  stylesheet. Only caller-supplied raw values (`css={}`, a custom ratio or
  width) remain inline, as the documented reviewed escape hatch.
- [ ] Three-tier token model generated from the public `Theme`:
  reference tokens → semantic tokens → component tokens. `Theme` stays the only
  public customization contract.
- [x] Component CSS consumes only semantic and component tokens; literal
  colors outside the token layer fail CI. (Done: `check_component_style_tokens.py`
  now covers `system.py` and `voodoo_css.py`; only neutral black/white scrims
  remain legal.)
- [ ] First-class `density` (`comfortable`, `compact`) and `radius` scales
  applied at page/system context, as `COMPONENT_API.md` already promises.
- [ ] Decide the Tailwind adapter's future (see Open decisions). Under no
  option may production pages load `cdn.tailwindcss.com`.
- [ ] Typography scale, spacing scale and icon set audited against the
  Constitution §7–§9 and documented once.

### 31.2 Theme platform — neutral, complete, shareable

Decision (2026-11-02): **Voodoo has no default brand color.** The default
theme is a minimal monochrome neutral; color is entirely a theme concern, and
themes must be easy to create, swap and share with the community.

- [x] **Neutral default theme**: grayscale surfaces, near-black/near-white
  primary actions, restrained borders. It must be beautiful on its own and pass
  every visual gate. Semantic status colors (success, warning, danger, info)
  remain themable, never hard-coded.
- [ ] **Seed-driven themes**: a theme can be declared from a few seeds —
  neutral scale, optional accent, radius, density, font families, and
  light/dark — and every other token is derived deterministically (OKLCH
  ramps). Any derived semantic or component token can still be overridden.
- [ ] **Customization ladder**, each step optional and documented:
  1. seeds;
  2. semantic tokens (`surface`, `text-muted`, `border`, `accent`, `danger`…);
  3. component tokens (`button.radius`, `input.height`, `table.row-hover`…);
  4. preset `custom.css` as a reviewed escape hatch, loaded in its own cascade
     layer so it cannot break component structure.
- [x] Remove the DS4 bridge heuristic in `theme_contract.py`: Theme values are
  authoritative, with explicit `None` meaning "derive".
- [ ] **Versioned, language-neutral theme format**: `theme.json` gains
  `schema_version`, `name`, `version`, `author`, `license`, `description`,
  seeds, tokens and light/dark variants. Its JSON Schema is published through
  `voodoo.protocol` so Store Studio, the Builder and future non-Python clients
  read the same themes.
- [ ] **Theme tooling** on the existing `voodoo theme` CLI (`new` and `validate`
  are done, with automatic light-mode accent contrast fixing; `preview` and
  `package` remain):
  - `voodoo theme new <name> [--accent …] [--from <preset>]` scaffolds a theme;
  - `voodoo theme validate` checks schema, token completeness and WCAG
    contrast for every foreground/background pairing in light and dark;
  - `voodoo theme preview` opens the Component Lab with the theme applied;
  - `voodoo theme package` produces a publishable `voodoo-theme-<name>` package.
- [ ] **Community distribution** keeps the existing local-first channels
  (file, user directory, PyPI package) and adds an optional static index that
  `voodoo theme list --remote` can read. Remote themes are always snapshotted
  into `.voodoo/theme/` by `voodoo theme use`; nothing is fetched at request
  time.
- [ ] Runtime switching without reload (light/dark/system and theme swap) and
  subtree scoping via `data-theme` for embedded surfaces.
- [x] Built-in presets prove completeness (`default`, `voodoo-purple` and
  `ember-paper` all pass the contrast gate; the visual/layout gates remain with
  31.8): `neutral` (default) plus at least
  two contrasting presets (for example a Voodoo-purple preset and
  `ember-paper`). Every built-in preset runs the full visual, contrast and
  layout gates.

### 31.3 Rendering engine — reconcile, don't replace

- [ ] Keyed DOM reconciliation (morphing) in the framework client runtime,
  implemented in-repo without a new required dependency. Stable identity comes
  from the existing `render_key`/`id` contract.
- [ ] Preserve focus, caret/selection, subtree scroll, `open` state of dialogs,
  popovers and details, and in-flight transitions across patches.
- [ ] Enter/exit/move hooks so state transitions can animate deterministically
  and respect `prefers-reduced-motion`.
- [ ] Split `client.js` into a small core plus interaction-kernel modules
  loaded as static assets.
- [ ] Performance budgets enforced in CI: initial HTML weight, CSS/JS weight,
  patch latency, and list update cost for 1,000 keyed rows.

### 31.4 Primitives — fewer, finished

- [ ] Machine-readable **component contract** per component (purpose, anatomy
  slots, variants, sizes, states, keyboard map, ARIA, responsive behavior,
  tokens consumed). Extends `docs/component_maturity.json`; docs and Component
  Lab pages are generated from it.
- [ ] Rebuild the Layer 1 primitive set to full Constitution §11 quality:
  Button, IconButton, Input (with prefix/suffix/addon/reveal slots), Textarea,
  NumberInput, Select, Combobox, Checkbox, Radio, Switch, Slider, Field, Form,
  Text, Heading, Stack, Grid, Divider, Dialog, AlertDialog, Popover, Tooltip,
  DropdownMenu, Tabs, Toast.
- [ ] Collapse overlapping families to one owner each; compatibility variants
  become documented thin wrappers or are scheduled for removal in the next
  major (no new duplicate owners).
- [ ] Consolidate component source files by layer:
  `ui/primitives/`, `ui/patterns/`, `ui/system/` (subject to an architecture
  decision per `docs/architecture/repository.md`).

### 31.5 Product patterns — operational excellence

- [ ] `DataTable` as an excellent primary surface (Constitution §14): sorting,
  column sizing, sticky header, selection, row actions, empty/loading/error,
  compact density and windowed rendering for large datasets.
- [ ] `LogViewer` that is dense, fast, filterable and follows live streams.
- [ ] `Timeline` / `EventRow` with one shared time language.
- [ ] `InspectorPanel` supporting `summary → state → history → technical`
  without losing context.
- [ ] `CommandPalette` / `CommandBar` with keyboard-first navigation.
- [ ] `Metric`, `StatusBadge`, `EmptyState`, `ActivityFeed`, `ResourcePicker`.
- [ ] Page patterns for the Constitution §23 control-environment hierarchy:
  current context → system health → primary resources → recent activity →
  contextual inspector. `AppShell` with adaptive sidebar and proper mobile
  navigation.

### 31.6 Runtime-aware system components — the Voodoo signature

- [ ] A **live binding** seam: a system component can be given a Runtime
  identity and a read model, subscribes to the corresponding namespaced Runtime
  events through the existing session-scoped state/patch pipeline, and
  re-renders only its keyed subtree.
- [ ] Every live component shows **freshness, source, connection state and
  confidence** where relevant (Constitution §13). Stale data is never shown as
  current.
- [ ] Canonical operational state vocabulary rendered consistently:
  `requested → accepted → executing → waiting → completed / failed`, plus
  `online / offline / connecting / degraded / unknown` for participants.
- [ ] Rebuild Layer 3 components on Runtime read models instead of dicts:
  `ExecutionView`, `ExecutionTimeline`, `ApprovalCard` (HITL with consequence
  and confirm/cancel), `PolicyDecision`, `GoalView`, `WorldEntityInspector`,
  `ObservationFeed` (evidence with provenance), `DeviceCard`/`EdgeNode`,
  `NodeTopology`, `TelemetryPanel`, `StoreHealth`.
- [ ] **Effect ≠ Observation** is visible: an attempted Effect and the
  Observation that confirms it are rendered as distinct, linked states
  (Constitution §22.4).
- [ ] AI-assisted action pattern (Constitution §18): proposed changes,
  confidence, affected resources, confirm/cancel — built on HITL, not a chat box.
- [ ] Read models live in Runtime-owned namespaces (`voodoo.runtime.inspection`,
  `voodoo.world`); the UI never reaches into Store encodings and never becomes
  a second authority model.

### 31.7 Voodoo Console — dogfood acceptance product

- [ ] `voodoo console`: a local, loopback-only operational surface built
  **only** with public `voodoo.ui` APIs and the live binding seam. It replaces
  the hand-written HTML in `runtime/inspection/dashboard.py`.
- [ ] Surfaces: Overview (health, active executions, pending approvals),
  Executions (list → inspector → lineage/trace), Approvals (HITL queue),
  World (entities, relationships, observations), Goals, Edge devices,
  Nodes, Jobs/Schedules, Store health.
- [ ] Read-only by default; mutating actions (approve, retry, cancel) execute
  as Intents through Capability + Policy, never as direct state writes.
- [ ] The Console's inspection primitives are designed to be reused by Voodoo
  Store Studio (Store ROADMAP M7.5: "Studio is built with Voodoo when the
  framework capability is mature enough") and the future Builder, sharing one
  Design System and one execution/trace vocabulary.

### 31.8 Evidence that can fail

- [ ] Automated layout lint in the browser suite: unstyled-component detection
  (computed style vs. contract), element overlap, horizontal overflow, clipped
  text, touch-target size and contrast — run on every Component Lab route and
  every Console surface, light/dark, desktop/mobile, LTR/RTL.
- [ ] Discard the current visual baselines; regenerate only after 31.1–31.5
  land and after **human approval** of a published review gallery.
- [ ] Hosted axe + keyboard matrix on Chromium, Firefox and WebKit
  (closes the remaining Sprint 30.5 hosted item).
- [ ] Performance budgets from 31.3 as release gates.

### 31.9 Documentation and developer experience

- [ ] Component documentation generated from the component contracts, with
  correct and incorrect usage examples (Constitution §11).
- [ ] Component Lab reorganized by layer (primitives / patterns / system) and
  doubling as the documentation gallery.
- [ ] `voodoo new` template upgraded to the new page patterns and AppShell.
- [ ] Theming guide: accent, neutrals, density, radius, typography, dark mode.
- [ ] Update `docs/design_system.md`, `docs/components.md`, `docs/state.md`,
  `ROADMAP.md` (UI and Design System section) and `ARCHITECTURE.md`.

## Phasing

| Phase | Scope | Exit evidence |
|---|---|---|
| A — Foundations | 31.1 + 31.2 + 31.3 + layout lint from 31.8 | One stylesheet, zero literal colors in component CSS, neutral default plus two presets, versioned theme schema, static hashed assets, keyed reconciliation preserving focus/scroll/open state, layout lint running and failing on today's defects. |
| B — Primitives | 31.4 | Every Layer 1 primitive has a contract and passes lint, keyboard and a11y in light/dark/mobile. |
| C — Patterns | 31.5 | DataTable, LogViewer, Timeline, Inspector, CommandPalette and AppShell pass contracts and perf budgets. |
| D — Runtime-aware | 31.6 | Live system components render real Runtime state with freshness and Effect/Observation distinction. |
| E — Console | 31.7 + 31.8 + 31.9 | `voodoo console` operates a real app end to end; new baselines approved; docs generated. |

Each phase is independently releasable as a minor version if it does not break
the public API; breaking changes are collected for the next major per the
compatibility policy.

## Acceptance target

Sprint 31 is complete when a developer can run:

```bash
voodoo new ops-demo
cd ops-demo
voodoo dev
voodoo console
```

and observe, with zero custom CSS and zero application JavaScript:

1. the generated app and the Console share one calm, neutral design language
   in light and dark, desktop and mobile;
2. `voodoo theme new acme --accent "#0ea5e9"` followed by
   `voodoo theme use acme` re-skins the app and the Console completely —
   including status colors, radius, density and typography — with no code or
   CSS changes, and `voodoo theme validate` passes;
3. a community theme installed with `voodoo theme install <name>` behaves
   identically;
4. an Execution started from the app appears in the Console, moves through
   `requested → accepted → executing → waiting`, requests approval, is
   approved from the Console through Capability + Policy and completes — with
   live, animated, context-preserving updates;
5. a simulated Edge device Effect is shown separately from the Observation
   that confirms it;
6. every surface passes layout lint, keyboard, axe and performance gates on
   Chromium, Firefox and WebKit;
7. the visual baselines were approved by a human from a published gallery.

## Non-goals

- A React/Vue clone or a client-side component framework.
- A required JavaScript build step for applications.
- Charting libraries, rich text editors or design tools beyond what the
  Console needs.
- Store Studio itself (it consumes this work in the Store repository).
- Remote/multi-tenant Console hosting (loopback only; remote access is a
  later Capability-gated product decision).

## Decided

- **Sprint 30 absorption** (2026-11-02): Sprint 31 Phases A–B absorb Sprint
  30's open catalog-wide component standardization so components are not
  standardized twice.

- **No default brand color** (2026-11-02): neutral monochrome default; color
  lives in shareable themes. See 31.2.

## Open decisions for the selection gate

1. **Activation timing.** Start after Sprint 30 closes, or absorb Sprint 30's
   open "catalog-wide component standardization" item into Sprint 31 Phase A–B
   so production readiness and interface work do not standardize the same
   components twice.
2. **Tailwind adapter.** (a) remove in the next major; (b) keep as an opt-in
   adapter that requires an application-owned build and never loads the CDN;
   (c) keep only as a class-name mapping without bundled runtime.
3. **Catalog contraction.** Which non-stable families are deprecated in 3.x and
   removed in 4.0.
4. **Source layout.** Approve `ui/primitives/`, `ui/patterns/`, `ui/system/`
   as the new physical ownership.
