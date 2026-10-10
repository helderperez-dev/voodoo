# WCAG 2.2 AA evidence register

This register is the release-candidate checklist for Voodoo Framework UI and
the Voodoo Site. It distinguishes executable evidence from review evidence;
passing local automation does not claim that a manual criterion has been
certified.

## Evidence status

| Status | Meaning |
| --- | --- |
| `automated` | Covered by a repository contract or browser test that runs in CI. |
| `manual-required` | Requires a human review on the hosted candidate. Record reviewer, date, URL, and result before GA. |
| `not-applicable` | Not present in the candidate; retain the rationale. |

## Applicable criteria register

| Criterion | Surface/evidence | Status | Release evidence |
| --- | --- | --- | --- |
| 1.1.1 Non-text Content | Icon alt/hidden semantics and image component contract | automated | `scripts/run_local_preflight.py --contracts-only` (accessibility stage) |
| 1.3.1 Info and Relationships | Landmark, heading, table, list, label, and ARIA-reference checks | automated | Site browser accessibility contract |
| 1.3.2 Meaningful Sequence | DOM/heading-order checks plus hosted screen-reader walkthrough | manual-required | Hosted axe + screen-reader report |
| 1.4.3 Contrast (Minimum) | Theme-token and visual baselines; computed contrast review | manual-required | Hosted light/dark contrast report |
| 1.4.10 Reflow | Responsive Component Lab and Site mobile matrix | automated | Chromium/Firefox/WebKit browser matrix |
| 1.4.11 Non-text Contrast | Focus, disabled, error, and status visual baselines | manual-required | Hosted visual approval |
| 1.4.12 Text Spacing | Tokenized typography and long-content composition review | manual-required | Hosted typography checklist |
| 1.4.13 Content on Hover or Focus | Popover, tooltip, menu, and drawer keyboard review | manual-required | Hosted keyboard walkthrough |
| 2.1.1 Keyboard | Focus order, activation, drawer trap/restore, and keyboard matrix | automated | Component Lab keyboard contract |
| 2.1.2 No Keyboard Trap | Modal/drawer focus-trap and escape behavior | manual-required | Hosted keyboard walkthrough |
| 2.4.3 Focus Order | Browser focus traversal across representative Site routes | automated | Site accessibility contract |
| 2.4.6 Headings and Labels | Heading-level and accessible-name checks | automated | Site/component accessibility contracts |
| 2.4.7 Focus Visible | Focus-state visual baselines and manual keyboard confirmation | manual-required | Hosted visual + keyboard report |
| 2.4.11 Focus Not Obscured (Minimum) | Responsive overlay and sticky-surface review | manual-required | Hosted keyboard walkthrough |
| 2.5.3 Label in Name | Accessible-name/source-label agreement review | manual-required | Hosted screen-reader report |
| 3.3.1 Error Identification | Form error and `aria-invalid` contracts | automated | Control-state contract |
| 3.3.2 Labels or Instructions | Input/form label and description checks | automated | Component accessibility contract |
| 4.1.2 Name, Role, Value | Role/name/value and ARIA-reference checks | automated | Component Lab + Site browser contracts |
| 4.1.3 Status Messages | Loading, empty, error, toast, and live-region walkthrough | manual-required | Hosted screen-reader report |

## Manual sign-off template

Before a general-availability claim, attach one report containing:

1. Candidate revision, hosted URL, browser/OS, assistive technology and
   version.
2. Reviewer name and date for every `manual-required` row above.
3. Reproduction steps and linked issue for every failure.
4. Screenshots or recordings for contrast, focus visibility, reflow, and
   status-message findings.
5. A final disposition: `pass`, `pass-with-known-issue`, or `blocked`.

The local gate is intentionally fail-closed for executable checks while this
manual sign-off remains an explicit release prerequisite.
