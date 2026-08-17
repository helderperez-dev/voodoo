# Voodoo CLI — Visual Identity & UX Redesign

Redesign the Voodoo CLI output to match the new Voodoo brand identity.

The goal is NOT to reproduce the Voodoo logo inside the terminal.

The Voodoo logo is a visual brand asset designed for websites, products, documentation, merchandise, etc. It should NOT be converted into ASCII art, Unicode symbols, terminal drawings, or approximations.

For the CLI, the brand identity should be expressed through typography, spacing, hierarchy, color, motion, and extremely intentional minimalism.

The CLI should feel like a tool created by a world-class infrastructure company in 2026–2030.

Think:
- modern infrastructure tooling
- Stripe CLI
- Vercel CLI
- Cloudflare tooling
- Bun
- modern Unix tools
- Linear's product design philosophy

Do NOT copy any of these products. Use only their level of simplicity and polish as inspiration.

---

## 1. Core Design Philosophy

The Voodoo CLI should communicate:

- minimal
- technical
- precise
- calm
- premium
- modern
- developer-first
- infrastructure-grade
- quietly distinctive

The CLI should NOT feel:

- cyberpunk
- hacker-themed
- game-like
- magical
- noisy
- overly colorful
- playful
- decorated
- like a terminal demo

The name "voodoo" itself is enough to establish the brand.

Do NOT create a new terminal logo.

Do NOT use:
- ASCII art
- large ASCII banners
- Unicode logo approximations
- emoji
- decorative symbols
- excessive box drawing
- fake terminal art
- gradients
- excessive colors
- unnecessary borders

The visual identity must come from restraint.

---

## 2. CLI Wordmark

Use:

    voodoo

Always lowercase.

Do not use:

    VOODOO
    Voodoo
    ◆ voodoo
    [ voodoo ]
    > voodoo

The lowercase wordmark should be the primary textual brand signature.

For example:

    voodoo 0.1.0

This should feel intentional and premium.

Do not introduce a special Unicode character next to the word "voodoo".

---

## 3. Color System

Implement a restrained terminal palette.

Base colors:

    Background: #0A0A0A
    Primary text: #EDEDED
    Secondary text: #A3A3A3
    Muted text: #737373
    Subtle text: #525252
    Divider/border: #262626

Voodoo accent:

    #C8FF3D

The accent color is a BRAND ACCENT, not a general-purpose highlight color.

Use it sparingly.

Good uses:

- selected interactive item
- important active state
- success state where appropriate
- current operation
- small brand detail
- command emphasis
- active indicator

Do NOT color entire sections green.

Do NOT make every successful operation bright green.

The CLI should remain predominantly monochromatic.

Semantic colors may be used when necessary:

    error: #FF5C5C
    warning: #F2C94C

Keep semantic colors restrained as well.

---

## 4. Typography

Use a clean modern monospace font when the environment supports it.

Preferred hierarchy:

    voodoo
    command
    section labels
    primary information
    secondary information
    muted metadata

Use weight and brightness rather than excessive colors to create hierarchy.

Do not use decorative typography.

Spacing is a major part of the design.

Prefer:

    voodoo 0.1.0

    runtime      ready
    environment  development

    local        http://localhost:3000
    inspector    http://localhost:3000/_voodoo

over dense output such as:

    [INFO] runtime started successfully on localhost:3000

---

## 5. Whitespace

Whitespace is a key part of the Voodoo visual language.

Prefer breathing room.

Example:

    voodoo

    runtime      ready
    environment  development

    local        http://localhost:3000
    inspector    http://localhost:3000/_voodoo

Do not fill every available line.

Do not unnecessarily wrap output in boxes.

Do not make the terminal look dense.

The CLI should feel almost editorial.

---

## 6. Headers

Keep headers extremely simple.

Preferred:

    voodoo 0.1.0

Avoid:

    ╔══════════════════════════════╗
    ║        VOODOO CLI            ║
    ╚══════════════════════════════╝

Avoid large banners entirely.

The word "voodoo" is the header.

---

## 7. Command Output

Example:

    $ voodoo dev

    runtime      ready
    environment  development

    local        http://localhost:3000
    inspector    http://localhost:3000/_voodoo

    watching     src/

The output should communicate state immediately.

Avoid verbose sentences when structured information works better.

Prefer:

    database     ready

over:

    ✓ Database connection established successfully.

---

## 8. Status Language

Use concise state words:

    ready
    running
    waiting
    stopped
    failed
    connected
    disconnected
    created
    removed
    building
    deploying

Avoid overly conversational status messages.

Do NOT use:

    🎉 Everything is ready!
    🚀 Server successfully started!
    ✨ Amazing! Your app is ready!

The Voodoo CLI should be confident and quiet.

---

## 9. Success States

Success should feel understated.

Example:

    voodoo init

    creating project
    installing primitives
    configuring runtime

    ready

Avoid excessive success animation.

A final:

    ready.

is enough.

---

## 10. Errors

Errors should be extremely clear and actionable.

Example:

    voodoo dev

    runtime      failed

    Port 3000 is already in use.

    → use --port 3001

Avoid:

    ❌ ERROR!!!
    Something went horribly wrong!!!

Errors should feel like professional infrastructure tooling.

---

## 11. Progress Indicators

Avoid noisy spinners and animated decorative elements.

If progress animation is necessary, keep it subtle.

Example:

    resolving dependencies

then:

    resolving dependencies     done

Avoid:

    🚀 Installing...
    ✨ Working...
    🔥 Almost there!!!

Motion should communicate state, not decorate the interface.

---

## 12. Interactive Prompts

Interactive CLI flows should be minimal.

Example:

    voodoo create agent

    name
    › researcher

    model
    › claude

    memory
    › persistent

    tools
    › browser, filesystem

Avoid heavy borders and large menus.

Use the Voodoo accent color only for the active selection/cursor.

---

## 13. Inspect / System Output

The Voodoo architecture should be visible through clean structured output.

Example:

    voodoo inspect

    primitives

      runtime
      state
      event
      task
      agent
      memory
      transport
      resource

Do not overdecorate this tree.

The architecture itself should be the visual element.

---

## 14. Agent Output

Example:

    voodoo inspect agent researcher

    agent       researcher
    status      ready

    model       claude
    memory      enabled
    tools       4
    tasks       12

Keep the output structured and quiet.

---

## 15. Doctor / Diagnostics

Example:

    voodoo doctor

    environment

    node          22.14.0       ready
    bun           1.2.5         ready
    git           2.50.0        ready
    docker        28.3.0        ready

    runtime

    core          installed     ready
    primitives    14             ready
    adapters      4              ready

    system       ready

The exact data obviously depends on the actual implementation.

---

## 16. CLI Help

The help output should also follow the brand.

Example:

    voodoo

    build systems, not glue.

    usage

      voodoo <command>

    commands

      init        create a project
      dev         start the runtime
      build       build the application
      inspect     inspect the system
      doctor      diagnose the environment
      add         add a primitive
      remove      remove a primitive
      deploy      deploy the application

    options

      --verbose
      --json
      --help
      --version

Keep descriptions short.

Do not generate walls of text.

---

## 17. CLI Commands

Preserve the existing command architecture unless there is a strong technical reason to change it.

The visual redesign should NOT unnecessarily change the framework API.

Potential command style:

    voodoo init
    voodoo dev
    voodoo build
    voodoo inspect
    voodoo doctor
    voodoo add
    voodoo remove
    voodoo deploy

The CLI should feel like a coherent language.

---

## 18. Machine-readable Output

Where practical, support:

    --json

Human output should be beautiful and minimal.

Machine output should be deterministic and clean JSON.

Example:

    voodoo inspect --json

    {
      "runtime": "ready",
      "agents": 3,
      "primitives": 14,
      "environment": "development"
    }

Do not mix colors, terminal formatting, spinners, or human-readable decoration into JSON output.

---

## 19. Implementation Architecture

Do not scatter ANSI escape sequences throughout the CLI implementation.

Create a centralized terminal presentation layer.

For example, conceptually:

    colors
    typography
    spacing
    status
    output
    prompts
    progress
    tables

The CLI should have reusable primitives for:

- heading
- label/value
- status
- muted text
- accent text
- divider
- error
- warning
- success
- prompt
- table
- tree
- progress

This ensures the entire Voodoo CLI shares one visual language.

---

## 20. Important Constraint

Do NOT redesign the CLI as a visual experiment.

This is a framework CLI intended to be used every day by developers.

Optimize for:

    clarity
    speed
    readability
    consistency
    accessibility
    terminal compatibility
    CI compatibility

The visual identity must emerge from the system rather than decoration.

---

## 21. Brand Principle

The final design should embody this principle:

    "The magic is in the simplicity."

Voodoo is the brand.

The terminal does not need to explain the brand.

It needs to feel unmistakably Voodoo.

The ideal reaction from a developer should be:

    "This is extremely clean."

followed by:

    "I know exactly what is happening."

and eventually:

    "I recognize this as Voodoo."

---

## 22. Final Target

The overall visual language should resemble:

    voodoo 0.1.0

    runtime      ready
    environment  development

    local        http://localhost:3000
    inspector    http://localhost:3000/_voodoo

    watching     src/

Not:

    ╔══════════════════════════════════╗
    ║         🔮 VOODOO 🔮             ║
    ║      THE FUTURE IS HERE          ║
    ╚══════════════════════════════════╝

The first is the target.

The second is explicitly what we are trying to eliminate.

Before implementing, inspect the existing CLI architecture and identify where output, colors, prompts, logging, progress indicators, errors, and help text are currently implemented.

Then refactor toward a centralized Voodoo terminal design system instead of applying isolated visual changes command by command.

Do not change framework behavior or APIs unless required.

The objective is to make the existing CLI feel like a polished, cohesive, premium Voodoo product.
:::