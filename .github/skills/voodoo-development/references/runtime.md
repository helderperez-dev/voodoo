# Runtime and Execution

Canonical mental model:

```text
World -> Observation -> Goal -> Intent -> Plan
-> Capability + Policy -> Execution -> Effect
-> Participant -> ACK/Observation -> World
```

Simplified:

```text
Entity -> State -> Intent -> Capability -> Execution -> Effect -> State
```

Runtime owns:

- intent
- capabilities
- policy
- authorization
- goals/plans
- execution semantics
- effects
- participants
- interpretation of observations

Store owns durable mechanics.

LLMs and agents participate as Compute. They do not become a privileged parallel Runtime.

## Effect != Observation

An attempted change is an Effect.
Evidence that the world changed is an Observation.

Do not collapse the two merely because an external API returned success.
