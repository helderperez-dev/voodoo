# Voodoo Design Constitution

> **Status:** Foundational  
> **Scope:** Voodoo Framework, Voodoo Runtime, Voodoo Edge, Voodoo Protocol, official examples, templates and first-party applications  
> **Purpose:** Define the visual and interaction principles that make Voodoo products feel modern, timeless, precise, fast and unmistakably intentional.

---

## 1. The Voodoo design thesis

Voodoo must make complex systems feel simple without pretending that the complexity does not exist.

The design system should not behave like a decorative layer added after the product is built. It must be part of the architecture itself.

A Voodoo application should communicate three things immediately:

1. **This is powerful.**
2. **This is understandable.**
3. **This feels exceptionally well made.**

The goal is not to create interfaces that look fashionable in 2026.

The goal is to create interfaces that still feel correct years from now.

Voodoo must therefore avoid visual trends that become the identity of the product. Effects may be used, but they must never become the product.

The desired feeling is:

> **Calm precision. Invisible complexity. Technical beauty. Quiet personality.**

---

## 2. What Voodoo should feel like

A Voodoo product should feel:

- precise without being sterile;
- minimal without being empty;
- technical without being intimidating;
- sophisticated without being luxurious for the sake of appearance;
- fast without feeling rushed;
- expressive without becoming visually noisy;
- opinionated without trapping developers inside one visual style.

The interface should make the user think:

> “Of course it works this way.”

That sense of inevitability is one of the highest design goals of Voodoo.

---

## 3. Design references

Voodoo should not copy any person or company.

Instead, it should absorb principles from several schools of design.

### 3.1 Dieter Rams — discipline and honesty

Key ideas to absorb:

- less, but better;
- every element must justify its existence;
- objects should explain themselves;
- design should not disguise poor function;
- ornament must never replace clarity;
- longevity is more important than novelty.

Application to Voodoo:

- never add a visual element only because the screen feels “too empty”;
- avoid unnecessary containers;
- avoid redundant labels;
- remove UI before adding UI;
- prefer clear structure over decorative separation.

---

### 3.2 Jony Ive — integration and reduction

Key ideas to absorb:

- hardware, software and interaction should feel like one product;
- simplicity is the result of deep work, not superficial minimalism;
- details matter because the user experiences the whole;
- form should emerge from the purpose of the object.

Application to Voodoo:

- Framework, Runtime, Edge and Protocol must share one design language;
- components should feel designed together, not assembled from unrelated libraries;
- default states must be as considered as hero screens;
- empty, loading, error, offline and degraded states are part of the product;
- the implementation should reduce friction for developers, not transfer complexity to them.

---

### 3.3 Naoto Fukasawa — natural interaction

Key ideas to absorb:

- the best interaction often feels obvious;
- products should match human expectation;
- behavior should feel familiar before it needs explanation.

Application to Voodoo:

- controls should behave predictably;
- common actions should not require tutorials;
- feedback must happen at the moment of action;
- dangerous actions should feel intentionally different;
- the interface should guide without constantly explaining itself.

---

### 3.4 Kenya Hara — emptiness and possibility

Key ideas to absorb:

- empty space is not unused space;
- restraint creates focus;
- simplicity can create room for identity and meaning.

Application to Voodoo:

- spacing is a structural tool;
- do not fill every area with cards;
- allow applications to inherit their own brand identity;
- Voodoo should provide a strong foundation without visually overpowering the product built on top of it.

---

### 3.5 Josef Müller-Brockmann — grid and hierarchy

Key ideas to absorb:

- structure creates clarity;
- typography can carry hierarchy without excessive decoration;
- consistency improves comprehension.

Application to Voodoo:

- strict spacing and grid rules;
- consistent alignment;
- predictable information density;
- typography and spacing before borders and boxes;
- layout should remain coherent from small screens to large operational dashboards.

---

### 3.6 Linear — software calm

What Voodoo should learn:

- speed is part of design;
- dense information can still feel elegant;
- keyboard-first interaction can coexist with approachable UI;
- transitions should explain state changes, not perform for the user.

Do not copy Linear's visual identity.

Absorb its discipline.

---

### 3.7 Stripe — clarity for complex systems

What Voodoo should learn:

- highly technical workflows can be approachable;
- documentation, product UI and developer experience can share one language;
- complex systems become easier when hierarchy is exceptionally clear.

---

### 3.8 Teenage Engineering — quiet personality

What Voodoo should learn:

- minimalism does not need to be generic;
- small details can create strong identity;
- technical products can feel playful without becoming childish.

Voodoo should have personality, but that personality must be controlled.

---

## 4. The Five Laws of Voodoo Design

These laws are non-negotiable for first-party Voodoo interfaces.

### Law 1 — Nothing without purpose

Every visible element must communicate, enable, separate, orient or confirm something.

If an element exists only to make the interface look richer, remove it.

Questions to ask:

- What does this element do?
- What becomes harder if it is removed?
- Is there a simpler way to communicate the same thing?

---

### Law 2 — Complexity belongs behind the interface

Voodoo may operate complex systems, distributed devices, agents, events and infrastructure.

The user should not be forced to understand the architecture merely to perform an ordinary task.

Complexity should appear progressively.

Default view:

- essential state;
- essential action;
- essential context.

Advanced detail:

- available on demand;
- inspectable;
- never hidden permanently.

Voodoo simplifies access to complexity. It does not destroy observability.

---

### Law 3 — Hierarchy before decoration

Before adding:

- borders;
- shadows;
- gradients;
- glass;
- cards;
- background panels;
- separators;

first solve the interface using:

- typography;
- spacing;
- alignment;
- scale;
- grouping;
- contrast.

Decoration is the last tool, not the first.

---

### Law 4 — Motion explains cause and effect

Animation exists to make state understandable.

Good motion:

- shows where an element came from;
- confirms a state change;
- preserves spatial context;
- demonstrates a relationship between action and result.

Bad motion:

- delays the user;
- exists only to look premium;
- constantly attracts attention;
- makes frequent operations feel theatrical.

Motion should be brief, physical and quiet.

---

### Law 5 — The default must already be excellent

Voodoo should not require extensive customization before it looks professional.

A developer should be able to assemble an interface using default components and receive a result that already feels intentional.

Customization should refine identity, not repair the design system.

---

## 5. Anti-principles

Voodoo explicitly rejects the following defaults.

### 5.1 No “AI app” visual language

Avoid:

- purple-to-blue gradients as identity;
- excessive glowing borders;
- floating translucent cards everywhere;
- animated blobs;
- decorative neural-network imagery;
- excessive rounded containers;
- interfaces that resemble generated landing-page templates.

AI capabilities should be communicated through behavior, not clichés.

---

### 5.2 No glass for the sake of glass

Transparency, blur and glass effects are allowed only when they communicate layering, depth or temporary context.

Never use glass as the default material of every surface.

If a solid surface is clearer, use a solid surface.

---

### 5.3 No cardification

A card is not the default solution for grouping information.

Before creating a card, consider:

- whitespace;
- a section heading;
- a divider;
- a row;
- a table;
- an inline group.

Cards should represent meaningful objects or bounded concepts.

---

### 5.4 No unnecessary gradients

Gradients may be used when they communicate:

- data intensity;
- state progression;
- visual focus;
- brand expression in rare, controlled contexts.

They should not be used merely to make a surface look modern.

---

### 5.5 No fake minimalism

Minimalism does not mean hiding necessary information.

Do not remove:

- labels needed for understanding;
- system status;
- error explanations;
- operational context;
- accessibility cues.

Reduction must improve comprehension.

---

## 6. Visual language

### 6.1 Surfaces

Default surfaces should be calm, flat and structurally clear.

Use elevation sparingly.

Prefer:

1. spacing;
2. tonal separation;
3. subtle borders;
4. elevation only when layering is meaningful.

---

### 6.2 Radius

Rounded corners should not become Voodoo's identity.

Use a small and consistent radius scale.

Suggested direction:

- small controls: subtle radius;
- larger containers: moderate radius;
- pills only for semantic cases such as tags, filters and compact statuses.

Avoid making every object capsule-shaped.

---

### 6.3 Borders

Borders should be low-contrast and functional.

Use them to:

- define input boundaries;
- separate dense data;
- express focus;
- communicate state.

Avoid outlining every container.

---

### 6.4 Shadows

Shadows communicate elevation.

If an element is not elevated, it should not have a shadow.

Do not use shadows as decoration.

---

### 6.5 Color

Color must have meaning.

Primary roles:

- action;
- state;
- emphasis;
- data visualization;
- product branding.

The neutral palette should do most of the structural work.

Voodoo's signature purple may exist as a brand accent, but it must not flood the interface.

The design system must work beautifully in:

- light mode;
- dark mode;
- branded themes;
- high-contrast environments.

---

## 7. Typography

Typography is one of the primary structural systems in Voodoo.

The type scale should be compact.

Avoid creating too many text styles.

Every screen should clearly distinguish:

- page context;
- section context;
- primary content;
- secondary content;
- metadata;
- code or technical identifiers.

Technical information should remain readable, not visually subordinate simply because it is technical.

Monospace should be used intentionally for:

- identifiers;
- commands;
- paths;
- logs;
- code;
- machine values.

Do not use monospace merely to create a “developer” aesthetic.

---

## 8. Spacing

Spacing should create structure before borders do.

Use a consistent spacing scale based on a small set of values.

Every component must follow that scale.

Avoid arbitrary values unless the component has a documented reason.

Dense operational views may reduce spacing, but must preserve rhythm.

---

## 9. Icons

Icons should be:

- simple;
- geometric;
- consistent in stroke and proportion;
- recognizable before stylish.

Never use an icon where a short text label is clearer.

Critical actions should not rely on icon-only controls unless the icon is universally understood or has an accessible label/tooltip.

---

## 10. Component architecture

Voodoo UI should be organized in layers.

### Layer 1 — Primitives

Examples:

- Button
- Input
- Select
- Checkbox
- Radio
- Switch
- Text
- Heading
- Stack
- Grid
- Divider
- Dialog
- Popover
- Tooltip

These components should be highly stable.

---

### Layer 2 — Product components

Examples:

- Command Bar
- Status Badge
- Metric
- Timeline
- Event Row
- Log Viewer
- Data Table
- Inspector Panel
- Activity Feed
- Empty State
- Resource Picker

These express recurring software patterns.

---

### Layer 3 — Voodoo system components

Examples:

- Device Card
- Device Inspector
- Agent Status
- Runtime Status
- Mission Timeline
- Sensor Stream
- Command Execution
- Protocol Event
- Edge Node
- Topology View
- Telemetry Panel

These are where Voodoo becomes visibly different from a generic UI kit.

---

## 11. Component anatomy

Every component must define:

- purpose;
- anatomy;
- variants;
- states;
- size options;
- keyboard behavior;
- accessibility behavior;
- loading behavior;
- empty behavior when relevant;
- error behavior;
- responsive behavior;
- theming tokens;
- examples of correct use;
- examples of incorrect use.

A component is not complete when its default screenshot looks good.

It is complete when its entire behavior is coherent.

---

## 12. Interaction principles

### 12.1 Immediate feedback

Every user action must create immediate feedback.

Examples:

- button state changes;
- optimistic updates when safe;
- progress indicators for longer operations;
- visible confirmation for completed actions.

---

### 12.2 Progressive disclosure

Show the minimum necessary information first.

Allow deeper inspection without forcing navigation when possible.

Example:

A device row may show:

- name;
- health;
- connectivity;
- latest activity.

Opening the inspector may reveal:

- telemetry;
- capabilities;
- logs;
- commands;
- protocol details.

---

### 12.3 Preserve context

Avoid unnecessary full-page navigation.

Use:

- inspectors;
- drawers;
- inline expansion;
- contextual panels;

when the user benefits from keeping the original context visible.

---

### 12.4 Dangerous actions

Destructive actions must be visually and behaviorally explicit.

Do not rely on color alone.

Confirmation should be proportional to the consequence.

---

## 13. Voodoo and real-time systems

Voodoo interfaces often represent systems that continue changing without user input.

Therefore state must be explicit.

A resource may be:

- online;
- offline;
- connecting;
- degraded;
- sleeping;
- executing;
- waiting;
- blocked;
- unknown.

Never make users infer operational state from stale data.

Every real-time component should consider:

- timestamp;
- freshness;
- connection status;
- source;
- confidence when relevant.

---

## 14. Data density

Voodoo will be used for operational applications.

It must support both calm simplicity and high-density information.

The solution is not to make everything large.

The solution is controlled density.

Principles:

- high-density views should remain aligned and scannable;
- repeated metadata should be visually quiet;
- the most important value must remain easy to find;
- tables should be excellent, not treated as a fallback;
- responsive behavior must preserve meaning, not simply stack everything vertically.

---

## 15. Empty states

Empty states should be useful.

They must answer:

1. What is this area?
2. Why is it empty?
3. What can I do next?

Avoid large illustrations unless they provide real value.

Operational products should prefer concise, helpful guidance.

---

## 16. Loading states

Loading should preserve layout whenever possible.

Prefer:

- stable skeletons;
- progressive loading;
- inline progress;
- existing content with freshness indicators.

Avoid replacing an entire application with a spinner.

---

## 17. Error states

Errors must be written for humans.

A good error explains:

- what happened;
- what was affected;
- whether data is safe;
- what the user can do;
- how to inspect technical detail.

Technical detail should be available without becoming the primary message.

---

## 18. AI interactions

AI inside Voodoo should feel native to the product, not like a chatbot pasted onto every screen.

Use conversational UI only when conversation is the correct interaction.

Prefer direct AI-assisted actions when possible.

Examples:

Instead of:

> “Ask the assistant to configure this device.”

Prefer:

> **Configure with AI**

Then show:

- proposed changes;
- confidence;
- affected resources;
- confirm/cancel.

AI should make interfaces simpler, not replace clear interfaces.

---

## 19. Branding and theming

Voodoo should be recognizable without dominating applications built with it.

The design system must support:

- semantic tokens;
- configurable accent;
- typography overrides;
- radius scale;
- density;
- light/dark mode;
- product-specific branding.

Voodoo's identity should live primarily in:

- proportion;
- motion;
- interaction quality;
- component behavior;
- information hierarchy;
- signature system components.

Not in forcing every application to be purple.

---

## 20. Accessibility

Accessibility is not an optional layer.

First-party Voodoo components must support:

- keyboard navigation;
- visible focus;
- semantic structure;
- screen readers;
- sufficient contrast;
- reduced motion;
- scalable text;
- understandable labels;
- non-color state differentiation.

A component that is visually beautiful but inaccessible is unfinished.

---

## 21. Performance is design

A beautiful interface that feels slow is not a beautiful interface.

Voodoo UI must prioritize:

- fast initial render;
- responsive interaction;
- minimal blocking states;
- efficient live updates;
- appropriate virtualization for large datasets;
- restrained animation.

Performance budgets should eventually be part of component acceptance criteria.

---

## 22. The Voodoo signature

Voodoo should develop a recognizable signature through behavior rather than decoration.

Potential signature areas:

### 22.1 State transitions

Events should move through the interface with a consistent visual language.

A command can visually travel through states:

`requested → accepted → executing → completed`

The transition should be subtle but unmistakable.

### 22.2 Operational timelines

Voodoo can make time a first-class interface primitive.

Missions, agents, devices and protocol events can share a common timeline language.

### 22.3 Inspectability

Every important object should feel inspectable.

Users should be able to move naturally from:

`summary → state → history → technical detail`

without losing context.

### 22.4 Physical + cloud continuity

When a physical device changes because of a software action, the UI should make that connection obvious.

This is a core Voodoo opportunity.

---

## 23. Example design language

A Voodoo Runtime screen should not feel like a collection of dashboards.

It should feel like a control environment.

Example hierarchy:

- current context;
- system health;
- primary resources;
- recent activity;
- contextual inspector.

A device view should not repeat the same information in multiple cards.

A mission view should not force users to open five pages to understand one execution.

A log viewer should be dense, fast and excellent.

A command UI should clearly show consequence and execution state.

---

## 24. Design review questions

Before shipping any screen, ask:

1. Can anything be removed?
2. Is the primary action obvious?
3. Is state visible?
4. Is the hierarchy understandable without decoration?
5. Are we using a card because it is necessary or because it is easy?
6. Does motion explain something?
7. Does the interface still work without the brand color?
8. Can a new user understand the screen?
9. Can an expert work quickly?
10. Does this feel like one system?
11. Does it look designed, or merely styled?
12. Would this still look good if current visual trends disappeared?

---

## 25. Definition of “Voodoo quality”

A component or screen reaches Voodoo quality when:

- it is obvious what it is for;
- it behaves predictably;
- every state has been considered;
- its hierarchy is strong without excessive chrome;
- it works with keyboard and assistive technology;
- it remains attractive in light and dark themes;
- it performs well;
- it can be branded without breaking;
- it feels consistent with the rest of Voodoo;
- removing any further element would make it worse.

---

## 26. Final principle

Voodoo should never attempt to look futuristic.

It should look correct.

If we design the system around clarity, proportion, behavior and deep integration, it will feel modern naturally.

> **The future should not look decorated. It should feel inevitable.**
