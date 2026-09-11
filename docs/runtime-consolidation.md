# Runtime consolidation invariants

This document records product/architecture constraints that keep Voodoo coherent as the runtime grows.

1. **`voodoo create` is the primary onboarding path.** It demonstrates the complete local runtime. `voodoo new` is an intentionally minimal UI/routing scaffold for developers who want to opt into capabilities later.
2. **The base package stays provider-SDK free.** AI provider SDKs are optional dependencies and are imported lazily. Installing `voodoo-framework` must not install OpenAI, Anthropic, Gemini or Ollama SDKs.
3. **Execution has a semantic boundary.** Meaningful work is represented as an Execution when durability, authorization, traceability, effects, accounting, recovery, waiting, scheduling or operational observability matters. Internal implementation calls do not become Executions by default.
4. **Similar primitives remain distinct.** Reactive state, domain Models, Memory and Execution state solve different problems. UI events, application events and telemetry solve different problems. Tool, Capability, Task, Agent and Execution solve different problems.
5. **Adaptive execution is opt-in complexity.** Planner and supervisor behavior may enrich the runtime but must not be required for ordinary pages, APIs, tasks, tools or agents.
6. **Mesh is communication fabric, not a second runtime.** It connects participants and application boundaries; execution, durability and workflow semantics remain owned by their respective runtime layers.
7. **The ORM remains application-focused.** Voodoo should provide the common async persistence path without competing feature-for-feature with general-purpose SQL toolkits.
8. **Documentation must describe implemented behavior.** README examples must execute the chain they claim; architecture docs must describe native provider tool calling rather than historical marker protocols.
9. **Every release protects the simple path.** New capabilities must not make the zero-infrastructure local experience harder.
10. **Agency is capability-mediated.** Voodoo should maximize what intelligent entities can perceive, remember, decide, delegate and execute without introducing ambient authority. Freedom to reason is not unlimited authority to act.
11. **Embodiment does not create a second runtime.** Physical devices are external participants connected through Edge. The Voodoo Runtime remains authoritative for identity, execution, policy, durable state and lineage; devices observe the world, execute physical effects and report acknowledgements/state back.
12. **Autonomy closes the loop through state.** Sending an effect is not enough. Autonomous and embodied flows must be able to observe the consequence, reconcile state and continue execution from operational truth.

See [`agency-and-embodiment.md`](agency-and-embodiment.md) for the architectural north star behind the agency and physical-system constraints.

## Canonical acceptance applications

The project should continuously validate four application shapes:

- **Simple Web App:** UI + reactive state + Model + Auth.
- **AI Operational App:** UI + Agent + Tool + Memory + Task + HITL.
- **Distributed Operational App:** API + application events + Worker + Scheduler + production adapters + recovery + telemetry.
- **Embodied AI App:** Edge Event + Runtime State + Agent/Policy + Execution + Effect + physical Device + ACK/state reconciliation.

These are canaries, not separate architectures. They should demonstrate that increasingly complex applications compose the same Voodoo runtime primitives. The embodied canary is especially important because it proves that the same execution model can cross the software/physical boundary and return with observable state instead of becoming a disconnected IoT control path.
