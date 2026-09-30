# Sprint 29 — Experience Convergence

**Status:** DONE · closed 2026-09-29  
**Started:** 2026-09-28  
**Release target:** Voodoo 3.2.0  
**Primary implementation:** PR #79

## Why this sprint existed

Voodoo 3.1 established a coherent Runtime + Store architecture, but real
application development exposed a product gap: some CLI surfaces still carried
legacy SQLite assumptions, project creation had competing paths, and the UI
library had more breadth than consistent browser-level polish.

Sprint 29 made the experience match the architecture. It intentionally added no
new major Runtime capability; it hardened the product developers actually touch.

## Product laws

1. **Store-first means Store-first everywhere.** A default application may
   create `.voodoo/application.vstore`; it must not silently create SQLite DBs.
2. **`voodoo new` is the canonical beginning.** The default scaffold is built
   into the package, works without a template network dependency and represents
   the current public API.
3. **Variety stays; quality rises.** Public components are not removed merely
   to simplify polish. Every visual family converges on one design language.
4. **Semantic components, not adapter leakage.** First-party components declare
   intent; VoodooCSS and optional adapters translate that intent.
5. **Rendered HTML is not enough.** Important interactions require real-browser
   focus, keyboard, responsive and state acceptance.
6. **Real applications drive corrections.** Acceptance apps do not hide
   framework defects with local workarounds.

## 29.1 — Persistence truth

**Status: DONE**

Default operational flows now converge on the application RuntimeStore:
executions, approvals/HITL, recovery, schedules, objects/artifacts, agents and
CLI inspection. SQLite/PostgreSQL/local filesystem/S3 remain explicit adapters.

The clean-install gate validates the canonical journey:

```text
voodoo new my-app --no-install
cd my-app

.voodoo/
└── application.vstore
```

The generated folder-based application boots through `App()`, public routes
render, `application.vstore` is durable, and the gate fails if any accidental
`*.db` file appears.

## 29.2 — CLI convergence

**Status: DONE**

Canonical direction:

```text
CLI → application context → Runtime services → RuntimeStore → Voodoo Store
```

Delivered:

- `voodoo new` as the visible canonical scaffold;
- remote templates only through explicit `--template`;
- deterministic `--no-install`;
- a Store-first application context shared by operational commands;
- executions, schedules, objects, agents, approvals, recovery and inspection
  migrated away from implicit SQLite;
- generated AI guidance aligned with the Voodoo 3.x `Model` + Store API;
- `voodoo status --json` with a stable application/Runtime/provider summary;
- `voodoo doctor --json` with side-effect-free Store-first diagnostics.

## 29.3 — Component Lab

**Status: DONE**

`examples/web/component_lab` is the visual and behavioral source of truth and
uses public Voodoo APIs with no application CSS.

The Lab covers foundations, semantic HTML primitives, application shell,
chat/AI, auth, forms, navigation, advanced interactions, data-heavy UI,
desktop workspace, Runtime/World/Edge and feedback surfaces.

A regression test now compares the public `voodoo.ui` surface with the Lab and
requires every renderable public visual component to be exercised. Non-rendering
infrastructure types are explicitly excluded rather than pretending they are UI
widgets.

## 29.4 — Design System 4

**Status: DONE**

DS4 is convergence, not decoration: quiet surfaces, consistent control geometry,
strong light/dark behavior, restrained radius/shadow, coherent focus/hover/
selected/disabled/loading/error states and mobile/coarse-pointer ergonomics.

The framework style order is:

```text
primitive structure
→ product structure
→ extended structure
→ Runtime/system structure
→ Design System 4 convergence
→ Theme contract
→ application customization
```

Theme overrides remain the final authority.

## 29.5 — Real-browser acceptance

**Status: DONE · mandatory CI/release gate**

The Playwright/Chromium gate is no longer opt-in CI coverage. It validates:

- dropdown open/Escape behavior;
- tab activation;
- ListBox roving focus and selection;
- TreeView keyboard navigation, expand and collapse;
- modal focus trapping and focus restoration;
- responsive sidebar transitions;
- real input focus/value;
- form validation and submit lifecycle;
- light/dark theme switching;
- light/dark screenshot artifacts for visual review;
- horizontal overflow across all 12 Component Lab routes at mobile width.

Current acceptance result: **20 browser tests passed**.

## 29.6 — Component perfection pass

**Status: DONE for the 3.2 public surface**

The pass hardened API ergonomics, accessibility, browser behavior, native
visual quality, adapter semantics, responsiveness and state behavior across the
public surface.

Concrete defects found by the acceptance work were fixed in the framework,
including legacy utility leakage, ListBox focus semantics, TreeView keyboard and
expand/collapse behavior, closed-dialog rendering, tab activation, modal focus,
responsive sidebar initialization, theme switching and form submit behavior.

## 29.7 — DX convergence

**Status: DONE for 3.2**

Real application pressure was folded back into the framework rather than
documented as local workarounds. The canonical scaffold, Store-first operational
CLI, status/doctor diagnostics, public component surface and browser interaction
kernel now describe one coherent developer experience.

Future product pressure may open a new sprint, but it is not Sprint 29 debt.

## 29.8 — Release gates

**Status: DONE**

The 3.2 release candidate is gated by:

- Ruff + format;
- Mypy on the converged runtime boundary;
- Python 3.12 full test suite;
- Python 3.13 full test suite;
- CodeQL;
- clean Store-first installation;
- canonical `voodoo new --no-install` scaffold lifecycle;
- zero accidental SQLite files;
- complete Component Lab public visual coverage;
- Chromium browser acceptance;
- mobile overflow acceptance;
- light/dark visual artifacts.

The protected CI and release workflows both use the canonical `voodoo new`
path. No workflow exception remains.

## Definition of done

Sprint 29 is complete when:

```bash
pip install voodoo-framework
voodoo new my-app
cd my-app
voodoo dev
```

leads to one coherent product: beautiful UI, predictable interaction, simple
Python, one Runtime, one default Store and an excellent operational CLI.

**Result: achieved.** Sprint 29 is implementation-complete and release-ready;
cutting/publishing Voodoo 3.2.0 remains an explicit release operation.
