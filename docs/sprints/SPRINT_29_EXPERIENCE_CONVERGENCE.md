# Sprint 29 — Experience Convergence

**Status:** ACTIVE  
**Started:** 2026-09-28  
**Release target:** Voodoo 3.2.0  
**Primary implementation:** PR #79

## Why this sprint exists

Voodoo 3.1 established a coherent Runtime + Store architecture, but real
application development exposed a product gap: some CLI surfaces still carried
legacy SQLite assumptions, project creation had competing paths, and the UI
library had more breadth than consistent browser-level polish.

Sprint 29 makes the experience match the architecture. It intentionally avoids
a new major Runtime capability until the current framework is consistently
excellent to create with, operate and look at.

## Product laws

1. **Store-first means Store-first everywhere.** A default application may
   create `.voodoo/application.vstore`; it must not silently create SQLite DBs.
2. **`voodoo new` is the canonical beginning.** The default scaffold is built
   into the package, works without a template network dependency and represents
   the current public API.
3. **Variety stays; quality rises.** Public components are not removed merely
   to simplify polish. Every family converges on one design language.
4. **Semantic components, not adapter leakage.** First-party components declare
   intent; VoodooCSS and optional adapters translate that intent.
5. **Rendered HTML is not enough.** Important interactions require real-browser
   focus, keyboard, responsive and state acceptance.
6. **Real applications drive corrections.** Acceptance apps do not hide
   framework defects with local workarounds.

## 29.1 — Persistence truth

**Status: IMPLEMENTED IN PR #79 · CI validation pending**

Default operational flows are converging on the application RuntimeStore:
executions, approvals/HITL, recovery, schedules, objects/artifacts, agents and
CLI inspection. SQLite/PostgreSQL/local filesystem/S3 remain explicit adapters.

Acceptance law:

```text
voodoo new my-app
cd my-app
voodoo dev

.voodoo/
└── application.vstore
```

No accidental `*.db` file is allowed in this journey.

## 29.2 — CLI convergence

**Status: ACTIVE**

Canonical direction:

```text
CLI → application context → Runtime services → RuntimeStore → Voodoo Store
```

Current branch work includes the canonical Store-first CLI context, managed
domain resources, `voodoo new` as the visible scaffold, remote templates only
through `--template`, deterministic `--no-install`, Store-aware `dev`/`doctor`
and generated AI guidance aligned with the 3.x API.

Remaining work includes command grouping, consistent JSON/exit behavior, deeper
`doctor` diagnostics and a coherent Runtime/application summary.

## 29.3 — Component Lab

**Status: ACTIVE · canonical acceptance app created**

`examples/web/component_lab` is the visual source of truth and uses public
Voodoo APIs with no application CSS. Current families include foundations,
application shell, chat/AI, auth, forms, navigation, advanced interactions,
data-heavy UI, desktop workspace, Runtime/World/Edge and feedback surfaces.

## 29.4 — Design System 4

**Status: ACTIVE**

DS4 is convergence, not decoration: quiet surfaces, consistent control geometry,
excellent light/dark behavior, restrained radius/shadow, coherent focus/hover/
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

## 29.5 — Real-browser acceptance

**Status: HARNESS IMPLEMENTED · CI browser provisioning pending**

The opt-in Playwright suite currently checks dropdown/Escape behavior, tabs,
real input focus/value, theme switching and mobile horizontal overflow.
Next slices add focus trapping/restoration, menu/listbox/tree keyboard traversal,
responsive sidebar transitions, form lifecycle and light/dark screenshot baselines.

## 29.6 — Component perfection pass

**Status: ACTIVE**

Every public family is reviewed for API ergonomics, accessibility, browser
behavior, native visual quality, adapter parity, responsiveness and complete
empty/loading/error/disabled states.

The Component Lab already exposed a concrete legacy defect: `UserBadge` embedded
old utility classes and stale `--color-*` variables despite native semantic
styles existing. Sprint 29 migrates this class of defect into semantic styles.

## 29.7 — DX convergence

**Status: NEXT**

Real applications will pressure composition depth, state/events, forms and
validation, Model binding, navigation, jobs/schedules, objects and agent/HITL
flows. Repetitive framework plumbing is fixed in Voodoo, not documented as a
workaround.

## 29.8 — Release gates

**Status: PARTIALLY IMPLEMENTED**

Before 3.2.0: Python 3.12/3.13, Ruff/format, Mypy and CodeQL must pass; clean
installation and `voodoo new` must boot; the default journey must create only
`application.vstore`; all Component Lab routes must render; critical browser
interactions and mobile overflow must pass; Theme overrides must stay
authoritative; light/dark visual baselines must be reviewed.

The protected Actions workflow still needs its clean-install command changed
from legacy `voodoo create` to `voodoo new --no-install`. The current connector
cannot write workflow files, so that workflow edit remains an explicit release
follow-up.

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
