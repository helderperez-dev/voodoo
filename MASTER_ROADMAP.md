# VOODOO — MASTER DEVELOPMENT ROADMAP

**Date:** 2026-08-17  

**Repository:** `helderperez-dev/voodoo`  

**Purpose:** single source of truth for development until the first stable runtime.

## 1. North Star

Voodoo began as an AI-native Python application framework. It is evolving into a **runtime and protocol for durable intelligent software**.

The target is software that can:

- have identity and durable state

- reason through models

- use explicit capabilities and tools

- create observable external effects

- persist memory and artifacts

- schedule future work

- communicate through events and messages

- survive worker/process failure

- involve humans in execution

- delegate work to other runtimes

- collaborate across a Voodoo Mesh

- remain provider-neutral

- operate locally with zero infrastructure installation

The final developer experience should be:

```text

voodoo new my-agent

cd my-agent

voodoo dev

```

No Redis, Postgres, Kafka, S3 emulator or external queue is required for local development.

The architectural thesis is:

> **Build the semantics once. Swap the infrastructure underneath.**

And the product thesis is:

> **Make autonomous software durable, capable, connected, observable and controllable — from one laptop to a distributed Mesh.**

---

# 2. Where We Are Today

The repository already contains a significant foundation.

The current README defines Voodoo as an AI-native Python framework combining reactive UIs, APIs, agents, workers, realtime systems, MCP tools and data applications. It already includes Agents, Tools, MCP, Voodoo Mesh, Workers, SQLite, authentication, security, telemetry, a unified Execution Engine, Human-in-the-Loop, recovery, planning and adaptive execution.

The architecture already defines eight important primitives:

```text

State

Capability

Intent

Effect

Time

Compute

Resource

Constraint

```

The documented execution model is:

```text

STATE → INTENT → CAPABILITY → COMPUTE → EFFECT → STATE

```

The runtime already has concepts such as:

```text

ExecutionEngine

ExecutionContext

Execution

CapabilityResolver

ConstraintEnforcer

ResourceAccountant

Planner

AdaptiveSupervisor

Human-in-the-Loop

JSONL execution persistence

recovery

```

The Mesh already provides local events, remote WebSocket communication, event envelopes, correlation IDs, exposed functions and MCP bridging.

Workers already provide `@task`, retries, timeouts, telemetry and enqueue semantics.

The important point is:

> **We are not starting over. We are consolidating and making durable what already exists.**

The largest architectural gap is durability.

The current worker documentation explicitly describes an `asyncio.Queue` with `asyncio.Task` workers and positions it as a seam for future distributed backends. That is acceptable for the prototype, but it is not yet the durable runtime we want.

The architecture documentation also currently describes JSONL execution persistence. That is a useful foundation, but it should evolve into a formal ExecutionStore.

---

# 3. The Final Architecture

```text

                    APPLICATION

                         |

                         v

                VOODOO PROTOCOL

                         |

                         v

                 VOODOO RUNTIME

                         |

        +----------------+----------------+

        |                |                |

      State            Tasks            Events

      Memory          Workers          Messaging

      Effects         Scheduler        Objects

      Security        Recovery         Telemetry

        |                |                |

        +----------------+----------------+

                         |

                  PROVIDER ADAPTERS

                         |

       +-----------------+------------------+

       |                 |                  |

     Database          Storage           Messaging

       |                 |                  |

 SQLite/Postgres     Local/S3/R2      Local/Postgres

                                      Redis/SQS/NATS/Kafka

                         |

                         v

                    VOODOO MESH

                         |

             +-----------+-----------+

             |           |           |

          Runtime A   Runtime B   Runtime C

             |           |           |

           Agent       Agent       Agent

             |           |           |

             +-----------+-----------+

                         |

                         v

                    WORLD

```

The framework is the developer surface.

The runtime is the execution substrate.

The protocol is the semantic contract.

The Mesh is the network of runtimes.

Agents are intelligent compute participants.

---

# 4. The Architectural Constitution

Create and maintain an `ARCHITECTURE.md` containing these invariants:

1. Workers are disposable.

2. Executions are durable.

3. Tasks are durable.

4. Events are facts.

5. Commands request actions.

6. Effects represent external side effects.

7. Agents are runtime participants.

8. Providers are replaceable.

9. SQLite is a first-class embedded runtime.

10. PostgreSQL is a first-class production backend.

11. Object storage is a first-class primitive.

12. MCP is an integration, not the Voodoo Protocol.

13. Memory is a semantic capability, not a specific vector database.

14. Mesh is a distributed runtime network, not a blockchain.

15. Capability is the primary security boundary.

16. External effects are observable.

17. At-least-once delivery requires idempotency.

18. Restart must not destroy durable execution.

19. Local development requires zero external infrastructure.

20. Distributed infrastructure is an implementation detail.

21. Protocol entities are versioned.

22. Persisted state is schema-based.

23. Arbitrary Python process memory is never the source of truth.

24. Humans can be durable participants in execution.

25. Powerful actions require explicit authority.

26. Failure semantics must be defined.

27. Runtime state must be inspectable.

28. Reliability comes before ecosystem size.

29. New abstractions require semantic justification.

30. Existing strong primitives should be extended before new competing concepts are introduced.

These rules exist primarily to protect the project from AI-driven architecture drift.

---

# 5. Master Development Phases

The project moves through these phases:

```text

0  Architecture Freeze

1  Durable State Foundation

2  Durable Tasks and Workers

3  Durable Execution and Recovery

4  Events, Messaging and Scheduling

5  Object Storage

6  Voodoo Protocol V1

7  Provider Adapters

8  Agent Runtime

9  Memory and Artifacts

10 Capabilities, Security and Effects

11 Voodoo Mesh V1

12 Local Runtime / WAMP for Autonomous Software

13 Reference Agent

14 Chaos and Failure Testing

15 Stability Candidate

16 Final Integrated Test

```

A phase is complete because its invariant is proven, not because code exists.

---

# 6. Phase 0 — Architecture Freeze

Create:

```text

ARCHITECTURE.md

ROADMAP.md

PROTOCOL.md

ADR/

```

Record major decisions such as:

```text

SQLite = embedded runtime database

PostgreSQL = primary production relational backend

Workers = disposable

Executions = durable

Providers = adapters

Events = facts

Tasks = work

Mesh = distributed runtime network, not blockchain

MCP = integration, not core protocol

```

**Gate:** the AI developing Voodoo can read these documents before making architectural changes.

---

# 7. Phase 1 — Durable State Foundation

Make SQLite the durable local source of truth.

Define provider-neutral interfaces:

```text

Database

StateStore

ExecutionStore

TaskStore

EventStore

ScheduleStore

ArtifactMetadataStore

```

SQLite should support:

- transactions

- migrations

- indexes

- WAL where appropriate

- concurrency-safe access

- atomic state transitions

Do not expose SQLite-specific behavior as the public API.

**Gate:** restart Voodoo and prove all required runtime metadata survives.

---

# 8. Phase 2 — Durable Tasks and Workers

Replace process-memory queue semantics as the source of truth.

Target:

```text

VoodooQueue

 ├── SQLiteQueue

 ├── PostgreSQLQueue

 ├── RedisQueue

 └── SQSQueue

```

A task should contain:

```text

task_id

type

payload

status

priority

available_at

attempts

max_attempts

idempotency_key

locked_by

locked_at

lease_until

trace_id

execution_id

created_at

started_at

completed_at

last_error

```

Lifecycle:

```text

PENDING → CLAIMED → RUNNING → COMPLETED

                       |

                       +→ RETRYING

                       |

                       +→ FAILED

```

If a worker dies:

```text

RUNNING

   ↓

lease expires

   ↓

PENDING / RETRYING

   ↓

another worker

```

The worker is disposable. The task is durable.

**Gate:** kill a worker during execution and prove another worker can recover its task.

---

# 9. Phase 3 — Durable Execution and Recovery

Execution becomes the real source of truth.

Execution should contain:

```text

execution_id

parent_execution_id

actor

intent

status

current_step

state

checkpoint

capabilities

effects

artifacts

result

error

trace_id

created_at

updated_at

```

Add an execution journal:

```text

execution.created

execution.started

step.started

model.called

model.completed

tool.called

tool.completed

state.changed

task.scheduled

execution.waiting

execution.resumed

execution.completed

execution.failed

```

Checkpoint at safe boundaries.

Never use arbitrary Python object serialization as the canonical persistence format.

Prefer:

```text

structured state

typed data

object references

stable IDs

versioned schemas

```

**Gate:** start a long execution, kill the process, restart Voodoo and resume it without losing durable state.

---

# 10. Phase 4 — Events, Messaging and Scheduling

Keep these concepts distinct.

**Event:** a fact.

```text

agent.started

lead.created

execution.completed

```

**Task:** work that should happen.

```text

send_email

generate_report

sync_crm

```

**Command:** request to perform an operation.

```text

create_lead

approve_payment

```

**Message:** transport envelope.

The scheduler must be durable:

```text

schedule.at()

schedule.after()

schedule.every()

```

A schedule must survive a Voodoo restart.

**Gate:** schedule work, stop Voodoo, restart it, and prove the work still executes according to defined scheduling semantics.

---

# 11. Phase 5 — Object Storage

Object storage becomes a first-class primitive.

```text

ObjectStore

 ├── LocalObjectStore

 ├── S3ObjectStore

 ├── R2ObjectStore

 ├── GCSObjectStore

 └── AzureBlobObjectStore

```

API:

```text

put

get

delete

exists

stat

list

```

Local:

```text

.voodoo/objects/

```

Large artifacts should not normally live inside SQLite.

Use references containing:

```text

object_id

provider

key

size

content_type

checksum

metadata

```

**Gate:** generate a large artifact, restart Voodoo and retrieve it through the same API.

---

# 12. Phase 6 — Voodoo Protocol V1

The Protocol is the semantic language of Voodoo.

V1 should define:

```text

Identity

Capability

Intent

Execution

Task

Command

Event

Message

Effect

Object

Artifact

Schedule

Agent

Tool

Model

Memory

Constraint

```

Transport is separate.

The same semantics may travel through:

```text

function calls

process boundaries

WebSocket

HTTP

RPC

MCP where appropriate

future transports

```

Protocol objects require:

- stable IDs

- schema versions

- timestamps where appropriate

- correlation IDs

- causation IDs

- serialization-safe representations

**Gate:** an implementation can exchange protocol objects without sharing Python classes.

---

# 13. Phase 7 — Provider Adapters

Adapters are a central part of the Voodoo value proposition.

Application code must never need:

```text

boto3

redis

psycopg

SQS SDK

provider-specific model SDK

```

Business logic should use:

```text

storage.put()

tasks.enqueue()

events.publish()

model.generate()

memory.write()

execution.resume()

```

Provider implementations sit below the boundary.

Every adapter declares capabilities such as:

```text

durable

ordering

delivery semantics

transactions

delayed delivery

visibility timeout

idempotency

consistency

limits

```

Do not pretend providers are identical.

Create common contract tests:

```text

QueueContractTests

ObjectStoreContractTests

EventBusContractTests

DatabaseContractTests

ModelProviderContractTests

```

**Gate:** switch a serious application from SQLite/local storage to PostgreSQL/S3 without rewriting business logic.

---

# 14. Phase 8 — Agent Runtime

Agents become first-class runtime entities.

An Agent has:

```text

identity

state

capabilities

model policy

tools

memory

permissions

history

```

But it must NOT create a separate persistence architecture.

The model is:

```text

Agent

  ↓

Execution

  ↓

Model / Tool / Effect / Task / Event

  ↓

State

  ↓

Checkpoint

```

Model providers become adapters:

```text

OpenAI

Anthropic

Gemini

Ollama

OpenRouter

custom

```

Normalize semantics while preserving provider capability differences.

**Gate:** a real agent executes through the common Execution Engine and its tool calls are durable and observable.

---

# 15. Phase 9 — Memory and Artifacts

Do not define AI memory as "a vector database."

Memory layers:

```text

working memory

execution memory

durable application state

episodic memory

semantic memory

external knowledge

```

Semantic API:

```text

memory.write()

memory.read()

memory.search()

```

Possible backends can evolve later.

Artifacts are durable outputs:

```text

reports

images

datasets

code patches

browser snapshots

model outputs

documents

```

Record provenance:

```text

artifact_id

execution_id

parent_artifact_id

created_by

source

checksum

timestamp

```

**Gate:** an agent can create an artifact, restart Voodoo, retrieve its history and continue using it.

---

# 16. Phase 10 — Capabilities, Security and Effects

The trust chain is:

```text

Human

  ↓

Application

  ↓

Agent

  ↓

Capability

  ↓

Tool

  ↓

Effect

  ↓

External World

```

Agents receive explicit capabilities, never ambient authority.

Examples:

```text

browser.read

browser.write

filesystem.read

filesystem.write

network.http

secrets.read

email.send

payment.execute

code.execute

```

Sensitive effects should have:

```text

effect_id

execution_id

capability

actor

resource

input_reference

output_reference

status

timestamp

retryability

idempotency_key

```

Use capability expiration, scopes, resource constraints and approval gates where appropriate.

**Gate:** an agent cannot perform an unauthorized action even when an LLM requests it.

---

# 17. Phase 11 — Voodoo Mesh V1

The current Mesh already provides a strong starting point: local events, remote WebSocket communication, namespaced events, envelopes, correlation IDs, exposed functions and MCP bridging.

The next step is to turn it into a network of Voodoo runtimes.

A Mesh node may be:

```text

developer machine

server

cloud worker

edge device

private agent runtime

enterprise runtime

specialized compute node

```

Nodes advertise capabilities.

Example:

```text

node-A:

  reasoning

node-B:

  browser.control

node-C:

  gpu.inference

  vision

```

The Mesh can route work to a capable node.

---

# 18. The Blockchain Analogy — What We Keep and What We Reject

The blockchain analogy is useful, but Voodoo should NOT become a blockchain.

Useful similarities:

```text

independent nodes

identity

signed messages

distributed state

event propagation

provenance

peer communication

fault tolerance

heterogeneous participants

```

But blockchain normally emphasizes:

```text

consensus

replicated ledgers

economic incentives

deterministic state transitions

trust minimization

```

Voodoo should emphasize:

```text

intelligent computation

capabilities

execution

collaboration

agents

tools

effects

privacy

policy

observability

useful work

```

Therefore:

> **Voodoo Mesh is a distributed intelligent runtime network, not a blockchain.**

Do not add consensus merely because the system is distributed.

Use the minimum coordination mechanism required by each problem.

---

# 19. Mesh Identity and Envelopes

A future node identity should contain:

```text

node_id

runtime_id

identity key

protocol version

capabilities

metadata

health

trust/policy metadata

```

A Mesh envelope should conceptually contain:

```text

message_id

protocol_version

source_node

destination_node

source_runtime

destination_runtime

timestamp

ttl

correlation_id

causation_id

message_type

capability

payload

signature

provenance

```

Cryptography should be introduced because a defined threat requires it, not for marketing.

---

# 20. Mesh Discovery and Collaboration

Nodes should eventually answer:

```text

Who are you?

What can you do?

Are you available?

What policy do you expose?

What trust relationship exists?

What resources do you have?

```

The most useful discovery unit is a capability.

Instead of:

```text

Node B is a server.

```

prefer:

```text

Node B can execute:

    vision.inference

    with defined limits and policies

```

This enables distributed intelligent work.

Example:

```text

Agent A

  ↓

needs video understanding

  ↓

discovers B = transcription

discovers C = vision

discovers D = reasoning

discovers E = storage

  ↓

delegates

  ↓

aggregates results

  ↓

continues execution

```

---

# 21. Mesh Trust Modes

Do not start with an open global Mesh.

Support progressive modes:

```text

Local Mesh

Private Mesh

Federated Mesh

Open Mesh

```

Local/private/federated environments should come first.

An open Mesh requires stronger:

```text

identity

sandboxing

reputation

resource accounting

abuse prevention

capability policy

cryptographic identity

anti-spam

```

The architecture should make this possible without making it the immediate implementation target.

---

# 22. Distributed Execution

An Execution can span nodes:

```text

Execution E1

  ├── Task T1 → Node A

  ├── Task T2 → Node B

  ├── Task T3 → Node C

  └── aggregate → continue

```

Parent and child executions must preserve:

```text

correlation

causation

identity

capabilities

effects

artifacts

failure state

```

If a node dies, the runtime must have a defined response:

```text

retry

delegate

wait

fail explicitly

```

Never silently lose work.

---

# 23. AI Safety as Architecture

The more powerful the agent, the more important the runtime boundary becomes.

Do not rely only on:

```text

"the model should behave."

```

Build structural controls:

```text

least privilege

capability expiration

approval gates

effect logging

execution budgets

resource constraints

network boundaries

sandboxing

human-in-the-loop

kill switches

audit trails

provenance

model/tool isolation

```

The runtime should make safe behavior structurally easier.

The long-term goal is not maximum autonomy at any cost.

It is:

> **Useful autonomy under explicit authority, with observable effects and recoverable execution.**

---

# 24. Resource and Constraint Control

Agents need hard limits.

Examples:

```text

max_tokens

max_cost

max_runtime

max_tool_calls

max_network_requests

max_storage

max_child_executions

max_delegation_depth

```

This is where the existing `Resource` and `Constraint` primitives become important.

The runtime should be able to stop an execution because:

```text

budget exhausted

time limit reached

capability expired

approval missing

policy denied

resource unavailable

```

---

# 25. Local Runtime — "WAMP for Autonomous Software"

This should become a defining Voodoo experience.

```text

voodoo new my-agent

cd my-agent

voodoo dev

```

Voodoo provides locally:

```text

runtime

SQLite

durable queue

workers

scheduler

events

local Mesh

object storage

agent runtime

MCP

telemetry

```

The developer should not have to understand infrastructure.

This is the modern equivalent of the old "install one package and get a working development stack" experience.

---

# 26. Production

The same semantics should scale to:

```text

PostgreSQL

S3/R2

Redis

NATS/SQS/Kafka

distributed workers

external model providers

secret managers

OpenTelemetry backends

```

Configuration changes.

Application semantics do not.

Example:

```text

Development:

  SQLite

  local objects

  SQLite queue

  local events

Small production:

  PostgreSQL

  S3/R2

  PostgreSQL queue

  PostgreSQL/local event backend

Large production:

  PostgreSQL

  S3/R2

  Redis/SQS

  NATS/Kafka

  distributed workers

```

Do not make Redis mandatory just because it is useful at scale.

---

# 27. Human-in-the-Loop

Human approval is a durable runtime state.

```text

Execution

   ↓

WAITING_FOR_HUMAN

   ↓

process may stop

   ↓

human approves

   ↓

event/command

   ↓

execution resumes

```

Examples:

```text

approve payment

approve deployment

approve external message

approve access to sensitive data

approve destructive operation

```

The original worker must not need to remain alive.

---

# 28. Observability

Every important operation must be inspectable:

```text

request

execution

task

worker

model call

tool call

effect

event

artifact

Mesh message

```

The CLI should evolve toward:

```text

voodoo status

voodoo executions

voodoo execution <id>

voodoo tasks

voodoo workers

voodoo events

voodoo mesh

voodoo artifacts

voodoo recover

voodoo doctor

```

The developer must be able to answer:

```text

What happened?

Why did it happen?

Which agent caused it?

Which capability was used?

Which tool was called?

Which node executed it?

What failed?

What recovered?

What can be audited?

```

---

# 29. Testing Strategy

Testing must become failure-oriented.

## Unit

Test primitives and state machines.

## Contract

Every provider passes the same semantic tests.

## Integration

Test:

```text

Execution

Queue

Worker

Database

Events

Storage

Agent

Tools

Scheduler

```

## Recovery

Kill:

```text

worker

process

server

```

and recover.

## Chaos

Inject:

```text

latency

timeouts

duplicate delivery

network failures

database failures

provider failures

malformed messages

```

## Security

Test:

```text

capability escalation

unauthorized tools

malicious events

SSRF

secret leakage

tool injection

prompt injection

cross-node privilege escalation

```

## Reference System

Run the complete reference agent.

---

# 30. The Death Test

This becomes a symbolic Voodoo test.

Start a long-running execution.

Then:

```text

kill -9 Voodoo

```

Restart.

The execution continues.

Kill the worker.

Another worker continues.

Disable a provider.

Execution enters a recoverable state.

Restore provider.

Execution continues.

Request human approval.

Execution waits.

Shutdown Voodoo.

Restart later.

Approval arrives.

Execution resumes.

If this works, Voodoo has crossed an important architectural boundary.

---

# 31. The World Test

After the Death Test, perform a real-world test.

The reference agent must:

```text

observe

  ↓

reason

  ↓

call tools

  ↓

create artifact

  ↓

communicate through Mesh

  ↓

persist memory

  ↓

wait

  ↓

resume

  ↓

act again

```

This proves that intelligence is connected to durable action.

---

# 32. The Mesh Test

Create three local Voodoo nodes:

```text

node-a

node-b

node-c

```

Give each different capabilities:

```text

A = reasoning

B = browser

C = storage

```

An agent on A receives an objective requiring all three.

Expected:

```text

A discovers B

A delegates browser task

B executes

B returns result

A continues

A creates artifact

C stores artifact

A receives storage result

execution completes

```

Then kill B during execution.

The system must:

```text

retry

delegate

wait

or fail explicitly

```

It must never silently lose the work.

---

# 33. The Reference Agent

Build one agent specifically to exercise the architecture.

Example mission:

> Research a topic, gather information, create a structured report, save it as an artifact, notify another participant, wait for human approval, and publish the approved artifact.

It should exercise:

```text

model

tools

tasks

events

memory

object storage

scheduler

human approval

execution checkpoints

capabilities

telemetry

Mesh

```

Then run:

```text

start

→ execute

→ kill process

→ restart

→ recover

→ continue

→ delegate

→ approve

→ complete

```

This is not merely an example.

It is the **integration test for the architecture**.

---

# 34. Milestones

## Milestone A — Foundation

SQLite is durable and provider boundaries exist.

**Proof:** restart does not lose runtime truth.

## Milestone B — Durable Runtime

Tasks, workers and executions survive failures.

**Proof:** Death Test passes.

## Milestone C — Protocol V1

Semantic objects are versioned and portable.

**Proof:** protocol objects can be exchanged without shared Python classes.

## Milestone D — Portable Runtime

PostgreSQL and S3/R2 work through the same semantics.

**Proof:** application moves providers without rewriting business logic.

## Milestone E — AI Runtime

Agents, models, tools, memory and artifacts use the common runtime.

**Proof:** Reference Agent works.

## Milestone F — Mesh

Multiple Voodoo runtimes collaborate.

**Proof:** three-node delegation works.

## Milestone G — Safety

Powerful AI actions are explicitly authorized and observable.

**Proof:** security/capability tests pass.

## Milestone H — Stability

The whole system survives failures and performs meaningful work.

**Proof:** Death Test + World Test + Mesh Test + Chaos Test.

---

# 35. Exact Development Order

The AI implementing Voodoo should use this as the priority sequence:

```text

01 Architecture Constitution

02 Storage interfaces

03 Durable ExecutionStore

04 Durable TaskStore

05 SQLite Queue

06 Worker leases

07 Retry/idempotency semantics

08 Recovery engine

09 Execution journal/checkpoints

10 EventStore/EventBus

11 Durable Scheduler

12 ObjectStore contract

13 Local ObjectStore

14 Protocol schemas

15 Protocol versioning

16 Adapter contract tests

17 PostgreSQL adapter

18 S3/R2 adapter

19 Agent integration with Execution

20 ModelProvider contract

21 Tool/Effect integration

22 Memory abstraction

23 Capability/security hardening

24 Human-in-the-loop recovery

25 Mesh identity

26 Mesh protocol envelope

27 Mesh capability discovery

28 Mesh delegation

29 Multi-node recovery

30 CLI observability

31 Reference Agent

32 Death Test

33 World Test

34 Mesh Test

35 Security Test

36 Chaos Test

37 Stability Candidate

38 Core freeze

39 Final integrated test

```

This is the default order. A deviation should be documented as an ADR.

---

# 36. What NOT to Build Before Stability

Do not prioritize:

```text

custom programming language

custom database

blockchain

cryptocurrency

token economics

custom Kubernetes

giant workflow DSL

proprietary LLM

custom vector database

autonomous financial infrastructure

self-modifying production code

global public Mesh

dozens of provider integrations

unnecessary UI abstractions

```

The next achievement is reliability, not feature count.

---

# 37. Stability Definition

"Stable" does not mean:

```text

feature complete

perfect

infinitely scalable

every provider supported

```

Stable means:

1. Core semantics are defined.

2. Public APIs are intentional.

3. Durable execution works.

4. Durable tasks work.

5. Recovery works.

6. Provider boundaries work.

7. SQLite local runtime works.

8. PostgreSQL production path works.

9. Object storage works.

10. Events work.

11. Scheduler works.

12. Agents use the common runtime.

13. Tools use capabilities.

14. Human approval is durable.

15. Mesh works in controlled multi-node environments.

16. Failure semantics are explicit.

17. Security boundaries are tested.

18. Contract tests pass.

19. Documentation matches implementation.

20. The reference agent survives the Death Test.

---

# 38. Stability Candidate

Create an explicit milestone:

```text

Voodoo 0.x — Stability Candidate

```

It should contain:

```text

Protocol V1

Runtime V1

durable execution

durable queue

local runtime

adapter contracts

agent runtime

object storage

events

scheduler

capability security

Mesh V1

reference agent

failure test suite

```

After this point:

> **Freeze the core before adding more major architecture.**

---

# 39. The Test Moment

The phrase:

> **"Agora é hora de testar isso que criamos."**

should have an exact meaning.

It means:

1. Start a local Voodoo runtime.

2. Start three Mesh nodes.

3. Start the reference agent.

4. Give it a meaningful objective.

5. Allow model use.

6. Allow tool use.

7. Allow task creation.

8. Allow event publication.

9. Allow memory.

10. Allow artifact creation.

11. Kill a worker.

12. Recover.

13. Kill the main process.

14. Restart.

15. Recover.

16. Delegate across Mesh.

17. Kill a Mesh node.

18. Recover or reroute.

19. Request human approval.

20. Stop Voodoo.

21. Restart later.

22. Approve.

23. Resume.

24. Complete.

25. Inspect the complete execution history.

Then ask:

```text

What did the agent see?

What did it decide?

What did it do?

Which capabilities did it use?

Which nodes participated?

Which effects occurred?

Which artifacts were created?

Which events were emitted?

What survived failure?

What was blocked?

What can be audited?

```

If the answers are clear, Voodoo is no longer just an architectural idea.

It is a runtime.

---

# 40. What We Should Expect to Discover

The first full test will probably reveal:

```text

race conditions

serialization gaps

retry edge cases

idempotency mistakes

unclear failure semantics

Mesh topology problems

authorization gaps

memory boundaries

provider inconsistencies

performance bottlenecks

developer-experience problems

```

That is success, not failure.

The response should not be random abstraction.

Return every discovery to the primitives:

```text

State?

Intent?

Capability?

Compute?

Effect?

Time?

Resource?

Constraint?

Execution?

Task?

Event?

Object?

```

Then improve the semantic model or implementation.

---

# 41. The Long-Term AI Model

Traditional software:

```text

request → function → response

```

Typical agent framework:

```text

prompt → model → tool → response

```

Voodoo:

```text

intent

  ↓

execution

  ↓

observe

  ↓

reason

  ↓

act

  ↓

persist

  ↓

wait

  ↓

receive event

  ↓

recover

  ↓

continue

  ↓

collaborate

  ↓

act again

```

The runtime gives intelligent software a durable place to operate.

"Life" here is a software/runtime metaphor:

```text

identity

state

memory

capability

perception

reasoning

action

communication

time

recovery

```

It is not a claim about consciousness.

---

# 42. The Human Safety Principle

The goal is not maximum autonomy.

The goal is:

> **Maximum useful capability under explicit authority.**

Voodoo should make increasingly capable AI:

```text

useful

inspectable

bounded

recoverable

auditable

controllable

collaborative

```

The more powerful the agent becomes, the more important the runtime boundary becomes.

The runtime should make it possible to:

```text

stop an agent

revoke a capability

require approval

inspect an effect

trace an action

recover execution

limit resources

isolate tools

audit provenance

```

This is how infrastructure can help make powerful AI safer rather than merely more powerful.

---

# 43. The Final Vision of the Mesh

The Mesh should eventually allow:

```text

Agent A

  |

  | intent

  v

Mesh

  |

  +---- discovers capability

  |

  +---- selects compute

  |

  +---- delegates execution

  |

  +---- observes result

  |

  +---- records provenance

  |

  +---- continues

```

A future network could contain thousands or millions of Voodoo runtimes, but

the initial implementation should remain much smaller.

The important idea is not scale.

It is the semantic property:

> **Intelligent software can discover and safely use capabilities beyond the machine on which it started.**

That is the seed of a distributed AI runtime.

---

# 44. The One-Sentence Architecture

When the project becomes confusing, return to this:

> **Voodoo is a durable runtime and protocol that lets intelligent software persist, reason, act, communicate and collaborate under explicit authority — from one laptop to a distributed Mesh.**

---

# 45. Final Checklist Before Saying "Test It"

```text

[ ] Architecture Constitution exists

[ ] Existing primitives are preserved

[ ] SQLite is durable

[ ] ExecutionStore is durable

[ ] TaskStore is durable

[ ] Queue is durable

[ ] Worker leases exist

[ ] Retry semantics are explicit

[ ] Idempotency exists

[ ] Execution journal exists

[ ] Checkpoints exist

[ ] Recovery works after process restart

[ ] Scheduler is durable

[ ] Event semantics are explicit

[ ] Message semantics are explicit

[ ] ObjectStore is first-class

[ ] Local object storage works

[ ] Protocol schemas are versioned

[ ] Adapter contract tests exist

[ ] PostgreSQL backend works

[ ] S3/R2 backend works

[ ] Agent uses common Execution

[ ] ModelProvider is stable

[ ] Tools are capability-controlled

[ ] Effects are observable

[ ] Memory is durable

[ ] Artifacts have provenance

[ ] Human approval is durable

[ ] Resource constraints work

[ ] Security tests pass

[ ] Mesh identity exists

[ ] Mesh envelopes are versioned

[ ] Mesh discovery works

[ ] Mesh delegation works

[ ] Multi-node recovery works

[ ] CLI can inspect runtime state

[ ] Reference Agent exists

[ ] Death Test passes

[ ] World Test passes

[ ] Mesh Test passes

[ ] Security Test passes

[ ] Chaos Test passes

[ ] Documentation matches implementation

[ ] Core API is frozen enough for external testing

```

---

# 46. FINAL GATE

Do not declare success because:

```text

pytest passes

```

Declare the first major milestone when:

```text

the system can fail and recover

```

Then:

```text

the agent can act and be audited

```

Then:

```text

multiple runtimes can collaborate

without becoming one trusted process

```

Then:

```text

infrastructure can change

without changing application semantics

```

Then:

```text

humans can control powerful actions

without stopping the runtime

```

Then:

```text

the whole system can run locally

without external infrastructure

```

When these are true:

> **STOP ADDING ARCHITECTURE.**

Run the tests.

Observe reality.

Fix what reality reveals.

Only then expand.

That is the point where Voodoo stops being an architectural vision and becomes

a system that can be evaluated in the real world.

---

# 47. NORTH STAR

The ultimate question is:

> **Can Voodoo provide a safe, durable, provider-neutral substrate through which intelligent software can perceive, reason, act, communicate, collaborate and continue operating over time?**

If yes:

```text

the runtime works

```

If the runtime works:

```text

the protocol matters

```

If the protocol works:

```text

the Mesh matters

```

If the Mesh works:

```text

distributed intelligent software becomes possible

```

If the safety boundaries work:

```text

greater capability does not have to mean

greater uncontrolled authority

```

That is the north star.

---

# 48. FINAL PRINCIPLE

Voodoo should feel simple at the surface and extraordinarily capable underneath.

The developer should see:

```text

Agent

Task

Event

Storage

Memory

Tool

Execution

```

while Voodoo handles:

```text

persistence

queues

workers

leases

recovery

scheduling

providers

security

telemetry

distributed execution

```

The user should not have to assemble the infrastructure required for

intelligent software.

**Voodoo should be that substrate.**

And the next objective is not to prove that Voodoo can do everything.

The next objective is to prove that what we already built can **survive,

recover, communicate, collaborate and safely act in the real world.**

That is the test.

That is the milestone.

That is where the architecture becomes Voodoo.