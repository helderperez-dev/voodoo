# Sprint 25 — UI Magic Progress

> Status: **Complete**
> Completed: 2026-09-13
> Working tracker for the implementation of `SPRINT_25_UI_MAGIC.md`.

## Final status

- 25.1 Callable event bindings — complete in PR #33.
- 25.2 Reactive render graph — complete in PR #33.
- 25.3 Context-preserving DOM patching — complete in PR #33.
- 25.4 Soft navigation — complete in PR #33.
- 25.5 Component API normalization — complete in PR #37 (`89836657`).
- 25.6 Voodoo Design System 2 — complete in PR #37 (`89836657`).
- 25.7 Product components — complete in PR #38 (`b1c8b7b7`).
- 25.8 Voodoo system components — complete in PR #39 (`31dacaec`).
- 25.9 Delight, docs and acceptance app — complete in PR #40 (`7f5cb7ea`).

## Acceptance proof

`examples/ui_magic/main.py` is the Sprint 25 acceptance application. It demonstrates the complete happy path using Python application code only: callable events, reactive state, async handlers, semantic forms, soft navigation, product components, Voodoo runtime/system components, theme behavior and density.

`tests/test_ui_magic_acceptance.py` executes the real application handlers, rerenders the interface and verifies that state changes become visible without inline application JavaScript or custom CSS.

The final PR passed:

- Ruff format;
- Ruff lint;
- Python 3.12 test suite;
- Python 3.13 test suite;
- CodeQL.

## Quality rule

A milestone is only marked complete after CI and CodeQL pass and the corresponding change is merged into `main`.

## Developer-experience rule

Python expresses intent. Voodoo owns browser mechanics.

The common path does not require event-name strings, inline JavaScript, DOM IDs, manual rerenders, custom CSS or full-page reloads.
