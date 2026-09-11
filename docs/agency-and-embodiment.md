# Agency and Embodiment

Voodoo exists to give intelligent systems **durable agency in software and a governed body in the physical world**.

This is the north star for the runtime.

Voodoo is not an agent wrapper, an IoT platform, or a robotics framework. It is the programmable runtime beneath applications in which humans, software, AI models, workers, and physical devices can participate in one coherent execution model.

The computational model remains:

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

For embodied systems, that model closes a larger loop:

```text
World
  ↓ observation
Sensor / Device
  ↓ Event + State
Runtime
  ↓ Intent
AI / Compute / Human / Worker
  ↓ decision
Capability
  ↓ authorization
Execution
  ↓ Effect
Software / Human / Device
  ↓ ACK + observation
State
  ↺
```

The purpose of Voodoo is to make that loop durable, inspectable, composable, and capable of crossing the boundary between software and the physical world.

## 1. What “agency” means

Agency is not just producing text. An agent has meaningful agency when it can participate in an ongoing system and cause authorized changes over time.

In Voodoo, agency is built from existing runtime primitives:

- **Identity** — an agent or device has a stable identity rather than existing only for one request.
- **State** — the runtime knows relevant operational truth.
- **Memory** — an entity can retain and recall useful history.
- **Intent** — desired outcomes are explicit runtime objects, not hidden in prompt strings.
- **Capabilities** — the runtime knows what an entity is allowed to do.
- **Execution** — meaningful work is durable, observable, recoverable, and attributable.
- **Tools and effects** — reasoning can produce changes outside the model.
- **Delegation** — work can cross agent, worker, human, service, and device boundaries while retaining lineage.
- **Time** — work can wait, retry, resume, schedule, or continue after process death.
- **Constraints and resources** — autonomy can operate inside explicit budgets and operational limits.
- **Human participation** — a human can become part of an execution when judgment or approval is required.

A Voodoo agent should therefore be able to perceive useful state, reason, remember, choose an intent, invoke capabilities, create effects, observe the result, and continue from the new state.

## 2. Freedom is not ambient authority

Voodoo should maximize what an AI system can accomplish **without confusing freedom to reason with unlimited authority to act**.

The runtime must never require an agent to be artificially passive. At the same time, autonomous action must be explicit and inspectable.

The governing rule is:

```text
Reason freely.
Act through capabilities.
Observe the consequences.
Continue from state.
```

Capabilities are what make practical autonomy possible. They let an application grant broad or narrow authority deliberately instead of choosing between “AI cannot act” and “AI can do anything.”

For example:

```text
agent.home
  capabilities:
    - room.observe
    - light.read
    - light.write
    - climate.read

agent.workshop
  capabilities:
    - machine.observe
    - job.plan
    - notification.send

robot.inspector
  capabilities:
    - navigation.move
    - camera.capture
    - telemetry.publish
```

High-impact effects can additionally require constraints or human approval. This does not weaken agency; it gives agency a reliable contract with the surrounding system.

## 3. What “embodiment” means

Embodiment means an intelligent participant can sense and affect the physical world through runtime-governed devices.

A physical device is not a special universe outside Voodoo. It is an external participant connected through the Edge boundary.

A device may provide:

- sensors,
- actuators,
- local state,
- telemetry,
- events,
- capabilities,
- acknowledgements,
- connectivity and presence.

Examples include an ESP32 with a button and LED, an environmental monitor, a workshop controller, a camera platform, a vehicle subsystem, or a mobile robot.

The device does **not** host a second Voodoo runtime or a second ExecutionEngine. The Runtime remains authoritative for execution, identity, policy, history, and durable operational state. The device executes physical effects and reports observations back.

```text
Voodoo Runtime                       Physical participant
─────────────────                    ────────────────────
Intent
  ↓
Execution
  ↓
Capability check
  ↓
Effect ────────────────────────────► actuator
                                      ↓
                                   physical world
                                      ↓
State  ◄──── ACK / Event / State ── sensor
```

This boundary is intentionally transport-independent. MQTT and HTTP are transports; they are not the semantic model.

## 4. The closed-loop requirement

A system is not embodied merely because it can send a command to hardware. The loop must close.

For a physical effect, Voodoo should be able to answer:

1. Who or what requested the action?
2. What intent was being pursued?
3. Which capability authorized it?
4. Which Execution produced the effect?
5. Which device received it?
6. Was the effect acknowledged?
7. What state changed afterward?
8. Can the runtime continue reasoning from that new state?

The same rule applies to software effects. Sending an email, changing a database record, invoking a remote service, moving a robot, or turning on a relay are all changes produced by execution. They differ in adapters and consequences, not in the fundamental runtime model.

## 5. AI is a participant, not the foundation

Voodoo must remain useful without an LLM. This is an important architectural property, not a limitation.

An AI model is one form of Compute. An agent can enrich an Execution with reasoning, planning, tool choice, interpretation, or adaptation, but the Runtime owns the surrounding lifecycle.

This separation gives Voodoo two important properties:

1. The same application can substitute models, deterministic code, humans, or devices without replacing the execution architecture.
2. AI gains more practical agency because durability, memory, scheduling, tools, security, observability, and physical interfaces do not need to be reinvented inside every agent loop.

## 6. The runtime should make autonomy durable

A useful autonomous system must outlive a single model call and a single process.

Voodoo should make these scenarios ordinary:

```text
observe → reason → act → wait → observe → continue
```

```text
plan → delegate → child execution → result → re-plan
```

```text
act → process crashes → runtime restarts → recover → continue
```

```text
request physical effect → device disconnects → retry/reconnect → ACK → reconcile state
```

```text
agent proposes sensitive effect → execution waits → human approves → resume
```

Autonomy that disappears when a Python process restarts is not durable agency.

## 7. The Edge boundary

`voodoo-edge/v1` is the semantic bridge between the Runtime and constrained or externally implemented devices.

The Edge contract should preserve the core runtime concepts while remaining small enough for embedded systems:

- device identity,
- authentication and enrollment,
- session/reconnect semantics,
- capability declaration,
- event publication,
- state synchronization,
- effect delivery,
- effect acknowledgement,
- heartbeat/presence,
- idempotency,
- correlation and execution lineage where applicable.

The device should not need to understand Voodoo internals. A microcontroller implements the protocol boundary; the Runtime translates that participation into the same state/execution/effect model used by software participants.

## 8. Reference embodied flow

The first physical proof is intentionally small:

```text
ESP32 button
   ↓ EVENT
DeviceGateway
   ↓
Execution
   ↓
Effect
   ↓
ESP32 LED
   ↓
EFFECT_ACK + state
   ↓
Runtime state
```

This proves more than remote LED control. It proves that one Voodoo execution model can cross the software/physical boundary and return with acknowledged state.

Once this primitive is trustworthy, richer systems are compositions of the same loop:

```text
camera → perception → agent → navigation intent → motor effect → robot state
```

```text
temperature → state → agent/policy → climate effect → sensor confirmation
```

```text
workshop sensor → anomaly event → agent → human approval → machine effect
```

## 9. Design constraints

Every feature related to autonomy or embodiment should preserve these constraints:

### One runtime

Do not create a separate orchestration architecture for agents, Edge, robotics, or devices. They converge on Execution.

### Explicit effects

The important boundary is not “AI called a function.” The important boundary is that an Execution produced an Effect that can be authorized, observed, retried where appropriate, and reconciled with state.

### Capability-mediated action

No participant gains ambient authority merely because it is intelligent or trusted. Authority is explicit, delegable, narrowable, and observable.

### Durable identity and lineage

Agent runs, tool calls, worker tasks, human decisions, and device effects must retain enough identity and parent/child correlation to reconstruct why an action happened.

### Idempotency at effect boundaries

Retries are a normal property of distributed and physical systems. Effects that may be redelivered need stable identity and idempotent handling.

### State is operational truth

Prompts are not state. Chat history is not state. Device telemetry is not automatically state. The Runtime should deliberately reconcile observations into the state used for subsequent decisions.

### Local-first development

A developer must be able to explore agency locally without provisioning a cloud control plane. Physical development may require a device and, for MQTT, a local broker, but Voodoo itself retains its zero-infrastructure software defaults.

### Transport independence

HTTP, MQTT, WebSocket, serial gateways, or future transports may carry protocol messages. Application semantics must not depend on a particular transport.

## 10. What Voodoo should not become

The vision does not require Voodoo to become:

- an LLM provider wrapper,
- a prompt framework,
- a Paperclip-style company simulator,
- a generic home-automation server,
- an MQTT broker,
- an Arduino framework,
- a robotics middleware replacement,
- a cloud-only device platform,
- a second operating system inside a microcontroller.

Those products or integrations can exist **on top of** Voodoo when useful.

Voodoo's durable advantage is the shared execution model beneath them.

## 11. North-star acceptance applications

Voodoo should continuously prove itself through increasingly capable applications that use the same primitives rather than separate architectures.

### Simple application

```text
UI → Event → Model → State/UI
```

### AI operational application

```text
UI/API → Agent → Tool → Execution → Effect → Memory/State
                         ↕
                       Human
```

### Distributed operational application

```text
API → Event → Worker → Execution → Adapter → Effect
             ↕                         ↕
          Scheduler                Telemetry
```

### Embodied AI application

```text
Physical sensor
   ↓
Edge Event → Runtime State → Agent/Policy → Execution → Effect
                                                     ↓
                                               Edge device
                                                     ↓
                                            actuator / world
                                                     ↓
                                      ACK + sensor observation
                                                     ↓
                                                Runtime State
```

The embodied application is the strongest proof of the architecture because it combines identity, events, state, agency, capability security, durable execution, effects, transport, recovery, and observation in one loop.

## 12. Decision rule for future features

When considering a new feature, ask:

> Does this make an entity better able to perceive, remember, decide, execute, recover, collaborate, or act across a real boundary while preserving one coherent runtime model?

If yes, it likely belongs in Voodoo or one of its adapters.

If it creates a parallel runtime, a second source of truth, ambient authority, or a provider-specific architecture, it is probably moving away from the project.

## 13. North star

The long-term goal can be stated simply:

> **Voodoo gives AI durable agency in software and a governed body in the physical world.**

The runtime should make it possible for intelligence to participate in real systems for long periods of time: observing, reasoning, remembering, acting, recovering, collaborating with humans and software, and eventually controlling physical machines — without losing identity, authority, lineage, or operational truth.

That is the meaning of freedom and embodiment in Voodoo.
