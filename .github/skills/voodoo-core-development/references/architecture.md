# Architecture Invariants

Canonical lifecycle:

```text
World -> Observation -> Goal -> Intent -> Plan
-> Capability + Policy -> Execution -> Effect
-> Participant -> ACK/Observation -> World
```

## Runtime / Store split

Runtime:
- semantics
- authority
- policies
- capabilities
- intent
- execution
- effect interpretation

Store:
- persistence
- transactions
- indexes
- jobs/queues
- streams/topics
- objects
- workflow state
- CDC
- storage lifecycle mechanics

## Distribution

The current architecture should not silently turn local Store semantics into distributed guarantees.

Node-local Stores + Runtime Fabric is the conceptual distributed direction. Consensus, global ordering, replication policy, and conflict resolution require explicit design.
