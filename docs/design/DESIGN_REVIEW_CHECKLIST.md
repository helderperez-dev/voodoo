# Voodoo Design Review Checklist

Use this checklist for every new Voodoo component, page, template or first-party application.

A component should not be considered finished merely because its default state looks good.

---

## 1. Purpose

- [ ] The component has one clear primary purpose.
- [ ] Every visible element has a reason to exist.
- [ ] Redundant text, controls or decoration have been removed.
- [ ] The component solves a recurring problem rather than a one-off screenshot.

---

## 2. Hierarchy

- [ ] The primary information is immediately identifiable.
- [ ] Typography and spacing create hierarchy before borders or effects.
- [ ] Secondary information is visually quieter.
- [ ] The layout remains understandable without brand color.
- [ ] Alignment follows the Voodoo grid and spacing system.

---

## 3. Visual restraint

- [ ] No decorative gradient is being used without purpose.
- [ ] No glass/blur effect is being used merely to look modern.
- [ ] Cards are used only when the content represents a meaningful bounded object.
- [ ] Shadows indicate real elevation.
- [ ] Border radius is consistent with system tokens.
- [ ] Borders are subtle and functional.
- [ ] The component does not resemble generic “AI app” styling.

---

## 4. States

- [ ] Default state is designed.
- [ ] Hover state is designed.
- [ ] Focus state is designed.
- [ ] Active/pressed state is designed.
- [ ] Disabled state is designed.
- [ ] Loading state is designed.
- [ ] Empty state is designed when relevant.
- [ ] Error state is designed.
- [ ] Success state is designed when relevant.
- [ ] Offline/degraded state is designed when relevant.
- [ ] Unknown state is designed when relevant.

---

## 5. Interaction

- [ ] User actions produce immediate feedback.
- [ ] Motion explains cause and effect.
- [ ] Animation does not delay frequent actions.
- [ ] Dangerous actions are explicit.
- [ ] Confirmation is proportional to consequence.
- [ ] The component preserves context when possible.
- [ ] Advanced detail is progressively disclosed.

---

## 6. Real-time behavior

For components that represent live systems:

- [ ] Connection state is visible.
- [ ] Data freshness is understandable.
- [ ] Timestamps are available where useful.
- [ ] Stale state is visually distinguishable from live state.
- [ ] The UI behaves correctly during reconnects.
- [ ] Rapid updates do not make the interface visually unstable.

---

## 7. Accessibility

- [ ] Fully usable with keyboard.
- [ ] Focus is always visible.
- [ ] Correct semantic HTML/roles are used.
- [ ] Screen-reader labels are meaningful.
- [ ] Color is not the only indicator of state.
- [ ] Contrast meets accessibility targets.
- [ ] Reduced-motion preferences are respected.
- [ ] Text scaling does not break the layout.
- [ ] Tooltips are not required to understand critical actions.

---

## 8. Responsive behavior

- [ ] Works on narrow mobile screens where applicable.
- [ ] Works on standard laptop layouts.
- [ ] Works on wide operational displays where applicable.
- [ ] Responsive behavior preserves meaning.
- [ ] Dense information does not simply become an excessively long vertical stack.
- [ ] Touch targets remain usable.

---

## 9. Theming

- [ ] Works in light mode.
- [ ] Works in dark mode.
- [ ] Works without Voodoo purple as the accent.
- [ ] Uses semantic tokens instead of hard-coded colors.
- [ ] Supports product-level branding.
- [ ] Customization does not require forking the component.

---

## 10. Performance

- [ ] Interaction feels immediate.
- [ ] Animation is inexpensive.
- [ ] Large collections are virtualized when appropriate.
- [ ] Real-time updates are batched or throttled where appropriate.
- [ ] Loading preserves layout.
- [ ] The component does not introduce unnecessary network calls.

---

## 11. Developer experience

- [ ] Default usage requires minimal code.
- [ ] The API is predictable.
- [ ] Props/options have clear names.
- [ ] Common use cases are easy.
- [ ] Advanced customization remains possible.
- [ ] Sensible defaults are provided.
- [ ] Documentation includes a minimal example.
- [ ] Documentation includes advanced examples where necessary.
- [ ] Incorrect combinations fail clearly.

---

## 12. Documentation

Each production-ready component should document:

- [ ] Purpose
- [ ] Anatomy
- [ ] Variants
- [ ] Sizes
- [ ] States
- [ ] Accessibility behavior
- [ ] Keyboard behavior
- [ ] Responsive behavior
- [ ] Theming
- [ ] Loading behavior
- [ ] Error behavior
- [ ] Correct usage
- [ ] Incorrect usage
- [ ] Code examples

---

## 13. Voodoo-specific components

For Device, Agent, Runtime, Mission, Edge or Protocol components:

- [ ] Operational state is immediately visible.
- [ ] Current state and historical events are clearly separated.
- [ ] Important identifiers can be inspected or copied.
- [ ] Technical detail is available without dominating the default view.
- [ ] Commands show execution state.
- [ ] The relationship between software action and physical effect is clear when relevant.
- [ ] Timeline/event semantics are consistent with the rest of Voodoo.

---

## 14. Final “Voodoo quality” test

Before approval, answer yes to all:

- [ ] Is it obvious what this is for?
- [ ] Can anything else be removed?
- [ ] Does it feel calm?
- [ ] Does it feel precise?
- [ ] Does it feel fast?
- [ ] Does it avoid trendy visual clichés?
- [ ] Would it still look good without gradients, glass or glow?
- [ ] Can a beginner understand it?
- [ ] Can an expert move quickly?
- [ ] Does it feel like part of one coherent system?
- [ ] Is the default experience already excellent?
- [ ] Does it look designed rather than merely styled?
- [ ] Would we still be comfortable shipping this visual language several years from now?

---

## Approval rule

A component is ready only when its **behavior, states, accessibility, responsiveness and developer API** are as carefully designed as its default appearance.

> Voodoo quality is not a screenshot. It is the entire experience.
