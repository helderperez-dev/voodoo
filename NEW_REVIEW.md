Voodoo Sprint 23.1 — Edge Hardening & Runtime Integration

Status: Planned
Prerequisite: Sprint 23 — Edge Readiness, Device Gateway & Edge Protocol
Target: Voodoo 2.6.x
Scope: Runtime, Device Gateway, HTTP, MQTT, persistence, reliability, security, protocol, tests, documentation
Explicitly out of scope: ESP32 firmware/client implementation

⸻

1. Mission

Sprint 23.1 is a hardening and integration sprint.

Sprint 23 successfully introduced the first Voodoo Edge architecture:

Device
   ↓
Voodoo Edge Protocol v1
   ↓
Device Gateway
   ↓
Voodoo Runtime

with HTTP and MQTT transports, Device identity, credentials, capabilities, state, events, effects, acknowledgements, persistence, and a simulator.

However, before building the first real ESP32 client, the Edge implementation must be hardened and fully integrated with the existing Runtime architecture.

The objective of Sprint 23.1 is therefore:

Make Voodoo Edge a reliable external boundary of the existing Voodoo Runtime rather than an isolated subsystem.

The final architecture must be:

                         VOODOO RUNTIME
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
          ExecutionEngine               Event System
                 │                           │
                 └─────────────┬─────────────┘
                               │
                             Effects
                               │
                        Device Gateway
                               │
                    ┌──────────┴──────────┐
                    │                     │
                   HTTP                  MQTT
                    │                     │
                    └──────────┬──────────┘
                               │
                         Voodoo Edge
                               │
                             Device

There must be no second execution architecture.

⸻

2. Primary Goals

Sprint 23.1 must accomplish all of the following:

1. Correct HTTP session semantics.
2. Correct MQTT authentication/session lifecycle.
3. Bind MQTT topics to authenticated Device identities.
4. Protect Device enrollment.
5. Integrate Effects with the actual Execution lifecycle.
6. Complete Effect delivery state semantics.
7. Complete Device reconnect and State reconciliation.
8. Improve protocol-level idempotency.
9. Harden authentication and authorization.
10. Improve secret redaction and observability.
11. Validate HTTP/MQTT semantic equivalence.
12. Add adversarial/security tests.
13. Run the complete existing Voodoo regression suite.
14. Update all architecture and Edge documentation.
15. Update sprint/release documentation.
16. Establish a clean contract for the upcoming ESP32 implementation.

⸻

3. Non-Goals

Do NOT implement the following during Sprint 23.1:

ESP32 firmware
ESP32 C/C++ SDK
Raspberry Pi SDK
local Edge AI
offline autonomous execution
Edge workflow engine
Edge Agent runtime
distributed consensus
exactly-once delivery
new frontend
cloud device management UI

The purpose of this sprint is correctness and integration.

⸻

4. Architectural Rules

These rules are mandatory.

4.1 One Runtime

There is only one authoritative Voodoo Runtime.

Device
 ↓
Event
 ↓
Execution
 ↓
Effect
 ↓
Device

must use the existing:

Event
Execution
Effect
Capability
State
Identity
Persistence

systems.

Do not create:

DeviceExecution
DeviceExecutionEngine
DeviceWorkflow
DeviceWorkflowEngine
DeviceEventEngine
DeviceEffectEngine

unless an existing Runtime primitive cannot satisfy the requirement and the architectural reason is explicitly documented.

⸻

5. HTTP Session Semantics

Problem

The current HTTP handlers authenticate through the Device Gateway and create a session/context for individual requests.

This creates semantics similar to:

POST /events
    ↓
create session
POST /state
    ↓
create another session
POST /heartbeat
    ↓
create another session

This is incorrect if DeviceSession is intended to represent an actual persistent connection.

Required behavior

HTTP must use stateless request authentication unless a persistent session is explicitly required by the protocol.

The preferred model is:

HTTP Request
    ↓
Authenticate Device Credential
    ↓
AuthenticatedDeviceContext
    ↓
Validate Message
    ↓
Process Message
    ↓
Return Response
    ↓
Request complete

Do not create unnecessary persistent sessions for ordinary HTTP requests.

⸻

6. HTTP Authentication Context

Implement a clean internal authentication context.

Conceptually:

AuthenticatedDeviceContext(
    device_id=...,
    credential_id=...,
    tenant_id=...,
    capabilities=...,
)

The exact implementation must follow existing Voodoo conventions.

The context must be available to:

Event ingestion
State updates
Heartbeat
Effect ACK
Device metadata updates

The device_id supplied by the message must never override the authenticated identity.

⸻

7. HTTP Identity Validation

For every authenticated request verify:

credential
    ↓
device identity
    ↓
message device_id

The following must all match:

authenticated device_id
==
message device_id

If they do not match:

403 / authorization failure

Do not silently replace one with the other.

⸻

8. MQTT Authentication Lifecycle

Problem

MQTT is connection-oriented while the current Gateway protocol requires authentication/session context for subsequent messages.

The following flow must work:

MQTT CONNECT
     ↓
HELLO
     ↓
AUTH
     ↓
authenticated session
     ↓
EVENT
     ↓
STATE_SYNC
     ↓
EFFECT_ACK
     ↓
HEARTBEAT
     ↓
disconnect

The authenticated Device context must remain associated with the MQTT connection/session.

⸻

9. MQTT Session Registry

Introduce or adapt a lightweight MQTT session registry.

Conceptually:

MQTT connection
     ↓
session_id
     ↓
AuthenticatedDeviceContext

The session must contain at least:

session_id
device_id
connection identity
protocol version
connected_at
last_seen_at
transport = mqtt

Do not treat the session as an Entity or Execution.

⸻

10. MQTT Authentication Requirements

Before AUTH:

EVENT
STATE_SYNC
EFFECT_ACK
HEARTBEAT

must be rejected unless the protocol explicitly permits a specific unauthenticated handshake message.

After AUTH:

authenticated device context

must be attached to every subsequent message.

If authentication fails:

reject message
optionally terminate connection
do not create Runtime events
do not update Device state

⸻

11. MQTT Topic Identity Binding

MQTT topics contain:

voodoo/v1/devices/{device_id}/...

The Device ID in the topic must be treated as an identity claim that must be validated.

Require:

topic device_id
==
authenticated session device_id
==
message device_id

Any mismatch must be rejected.

Example attack:

Authenticated Device A
        │
        │ publish
        ▼
voodoo/v1/devices/device-B/events

must fail.

Likewise:

topic = device-A
message.device_id = device-B

must fail.

⸻

12. MQTT Topic Authorization

Verify that an authenticated Device can publish only to authorized topics.

At minimum:

devices/{own_id}/events
devices/{own_id}/state
devices/{own_id}/ack
devices/{own_id}/heartbeat

The Device must not publish to another Device’s namespace.

Runtime-generated Effects must be published only to the target Device topic.

⸻

13. MQTT Client Identity

Do not rely on MQTT client_id as the canonical Voodoo Device ID.

The MQTT client ID may be stored as connection metadata.

Canonical identity remains:

device_id

⸻

14. Enrollment Security

Problem

Device enrollment creates credentials and therefore must not be exposed as an unauthenticated public administrative operation.

Protect enrollment creation with the existing Voodoo authentication and authorization mechanisms.

Conceptually:

Administrator / authorized service
       ↓
Create enrollment
       ↓
One-time enrollment credential
       ↓
Device

⸻

15. Enrollment Authorization

Only authorized principals may:

create enrollment
list enrollment
revoke enrollment
issue credentials

A Device credential must not be allowed to create arbitrary new Device enrollments unless explicitly designed and authorized.

⸻

16. Enrollment Credential Security

Enrollment credentials must:

* be securely generated;
* never be logged;
* never be stored in plaintext if avoidable;
* have expiration;
* preferably be single-use;
* be revocable;
* be associated with the intended Runtime/tenant scope.

Document the security model.

⸻

17. Device Credential Security

Device credentials must:

never be logged
never appear in traces
never be returned after initial issuance
never be stored as plaintext when avoidable
support rotation
support revocation

The existing hashed credential storage should be preserved.

If the implementation currently stores only a hash, retain that approach.

⸻

18. Secret Redaction

Audit all Edge logging.

Ensure that these are never logged:

device credentials
enrollment keys
MQTT passwords
tokens
authorization headers
API keys
private credentials

Payload logging must support redaction.

Example:

credential: [REDACTED]

not:

credential: vdk_abc123...

⸻

19. Effect Lifecycle Integration

Critical Requirement

Effects must become part of the existing Runtime execution lifecycle.

The desired flow is:

Execution
    ↓
Effect created
    ↓
Effect persisted
    ↓
Device Gateway
    ↓
HTTP / MQTT
    ↓
Device
    ↓
ACK
    ↓
Effect status updated
    ↓
Execution lifecycle updated

The Gateway must not be the authoritative creator of an isolated Effect lifecycle.

⸻

20. Effect Ownership

An Effect must be associated with its originating Execution wherever applicable.

Minimum relationship:

execution_id
    ↓
effect_id
    ↓
device_id

The Runtime must be able to answer:

Which Execution produced this Effect?
Which Device was targeted?
Was the Effect delivered?
Was it acknowledged?
Did it complete?
Did it fail?

⸻

21. Effect State Machine

Define a clear Effect lifecycle.

Recommended initial model:

CREATED
   ↓
PENDING
   ↓
DELIVERING
   ↓
DELIVERED
   ↓
ACKNOWLEDGED
   ↓
COMPLETED

Failure paths:

DELIVERING
   ↓
DELIVERY_FAILED

or:

ACKNOWLEDGED
   ↓
FAILED

Unknown network state must not automatically become FAILED.

⸻

22. Unknown Delivery State

Handle:

Effect sent
   ↓
network failure
   ↓
ACK unknown

The Runtime must represent this explicitly.

Do not assume:

network failure = device did not execute

and do not assume:

network failure = device executed

This distinction is fundamental to reliable physical-world execution.

⸻

23. Retry Policy

Define retry behavior for Effects.

Retries must be:

bounded
observable
idempotent
configurable

Do not retry indefinitely.

Do not automatically retry non-idempotent Effects without explicit semantics.

⸻

24. Effect Idempotency

Every Effect must have a stable:

effect_id

A Device receiving:

effect_id = effect_123

multiple times must be able to recognize the same logical Effect.

The protocol must document:

at-least-once delivery
+
application-level idempotency

Do not claim exactly-once delivery.

⸻

25. Idempotent Response Replay

Improve duplicate message handling.

Current behavior may identify:

message_id already processed

but simply return:

duplicate

Prefer storing enough information to replay the original semantic response.

Conceptually:

message_id
    ↓
original response

When the same message arrives again:

same message_id
    ↓
same response

This is particularly important for HTTP retries.

If full response replay is not appropriate for a specific message type, document the exception.

⸻

26. Event Idempotency

Every externally generated Event must have a stable identifier.

Example:

event_id
message_id

The Runtime must distinguish:

transport retry

from:

new semantic Event

Duplicate delivery must not create duplicate semantic Events unless explicitly documented.

⸻

27. State Versioning

Device State must remain versioned.

Every State synchronization operation must have:

state_version

The Runtime must reject or safely handle:

older version
same version
newer version
conflicting version

Do not blindly overwrite newer Runtime state with stale Device state.

⸻

28. State Reconciliation

Complete the State reconciliation protocol.

Required scenarios:

Device behind Runtime

Device = version 41
Runtime = version 42
       ↓
SYNC
       ↓
Device receives version 42

Runtime behind Device

Device = version 43
Runtime = version 42
       ↓
SYNC
       ↓
Runtime evaluates and accepts version 43

The exact authority rules must be documented.

⸻

29. Source of Truth

Explicitly define ownership for Device State fields.

Possible model:

Sensor measurements
    → Device authoritative
Actuator desired state
    → Runtime authoritative
Actuator actual state
    → Device authoritative

Do not assume one global authority for every state field.

The implementation should support clear field/domain ownership where necessary.

⸻

30. Reconnect Semantics

Define:

disconnect
reconnect
resynchronization

A reconnect must NOT create a duplicate Device.

Correct:

Device A
   ↓
disconnect
   ↓
Device A
   ↓
reconnect
   ↓
same Device A

Incorrect:

Device A
Device A-2
Device A-3

⸻

31. Reconnect State Machine

Document and test:

CONNECTED
    ↓
DISCONNECTED
    ↓
RECONNECTING
    ↓
AUTHENTICATING
    ↓
CONNECTED
    ↓
STATE_RECONCILIATION

The exact internal status model may differ, but behavior must be deterministic.

⸻

32. Last Seen

last_seen_at must be updated only by valid authenticated Device activity.

Invalid requests must not make a Device appear online.

Heartbeat must update:

last_seen_at

without generating unnecessary Events or Executions.

⸻

33. Device Status

Separate:

Entity lifecycle

from:

connection status

A disconnected Device still exists.

Example:

Device:
  status = registered
  connection = disconnected

Revocation is different:

Device:
  status = revoked

⸻

34. Protocol Version Handling

Current protocol:

voodoo-edge/v1

must be explicitly versioned.

Unsupported versions must produce a machine-readable error.

Do not silently interpret an unknown protocol version.

Document compatibility policy.

⸻

35. Protocol Validation

Validate all incoming messages before entering Runtime logic.

Validation order should be conceptually:

transport
   ↓
protocol decode
   ↓
schema validation
   ↓
authentication
   ↓
identity binding
   ↓
authorization
   ↓
idempotency
   ↓
Runtime processing

Do not process payloads before validation.

⸻

36. Error Contract

Define stable machine-readable Edge errors.

Minimum:

AUTHENTICATION_FAILED
AUTHORIZATION_FAILED
DEVICE_NOT_FOUND
DEVICE_REVOKED
INVALID_MESSAGE
INVALID_PROTOCOL_VERSION
INVALID_CAPABILITY
INVALID_STATE_VERSION
DUPLICATE_MESSAGE
DEVICE_ID_MISMATCH
SESSION_REQUIRED
SESSION_INVALID
EFFECT_NOT_FOUND
EFFECT_EXPIRED
DELIVERY_FAILED
TRANSPORT_ERROR

Use existing Voodoo error conventions where possible.

⸻

37. HTTP/MQTT Semantic Equivalence

The same logical message must have the same Runtime semantics regardless of transport.

Example:

EVENT temperature.changed

via:

HTTP

and:

MQTT

must result in equivalent Runtime behavior.

Likewise:

STATE_SYNC
EFFECT_ACK
HEARTBEAT

must behave equivalently.

⸻

38. Transport-Specific Responsibilities

HTTP owns:

HTTP request parsing
HTTP authentication transport
HTTP response
HTTP status code

MQTT owns:

connection
subscription
publication
MQTT session
MQTT QoS

The Gateway owns:

protocol
identity
authorization
event/state/effect semantics

The Runtime owns:

Entity
State
Execution
Capability
Effect
Event
persistence

⸻

39. MQTT QoS

Document the selected QoS level for each topic.

Example policy may be:

Events        QoS 1
State         QoS 1
Effects       QoS 1
ACK           QoS 1
Heartbeat     QoS 0 or 1

The exact choice must be based on the implementation and reliability requirements.

Do not rely on MQTT QoS as a replacement for application-level idempotency.

⸻

40. MQTT Retained Messages

Define whether each topic supports retained messages.

Do not retain transient:

EVENT
EFFECT
ACK

unless there is a clear reason.

Retained State may be appropriate, but must not bypass Runtime state/version validation.

Document the policy.

⸻

41. MQTT Last Will

Consider using MQTT Last Will to improve disconnect detection.

If implemented:

unexpected disconnect
    ↓
Device status update

must remain consistent with the Runtime’s last_seen_at semantics.

Do not generate duplicate lifecycle Events unnecessarily.

⸻

42. HTTP Effect Delivery Model

Because HTTP is request/response, define how a Device receives Effects.

Possible model:

GET /effects

with:

effect_id

and acknowledgement afterward.

If this is the current model, harden it rather than inventing a second delivery mechanism.

The implementation must guarantee that:

poll
 ↓
effect
 ↓
ack

uses the same Effect lifecycle as MQTT delivery.

⸻

43. Effect Claiming

If multiple HTTP requests can poll Effects concurrently, ensure that two consumers cannot accidentally claim the same Effect as two independent executions.

Use existing persistence locking/claiming mechanisms.

Test concurrent polling.

⸻

44. Concurrent MQTT/HTTP Delivery

The same Device may potentially be connected through both transports.

Define behavior.

Example:

Device A
 ├── HTTP
 └── MQTT

The Runtime must not accidentally deliver the same Effect twice as two independent deliveries.

The canonical Effect ID and delivery state must remain authoritative.

⸻

45. Device Simulator Improvements

The simulator must support:

authentication
HTTP
MQTT
HELLO
STATE_SYNC
EVENT
EFFECT
EFFECT_ACK
HEARTBEAT
disconnect
reconnect
duplicate messages
stale state

The simulator should intentionally support failure injection:

drop ACK
duplicate Event
duplicate Effect
disconnect after Effect
send stale state
invalid credential
wrong device ID

This becomes the primary integration testing tool before ESP32.

⸻

46. Security Test Matrix

Add tests for:

unauthenticated Event
unauthenticated State
unauthenticated ACK
invalid credential
expired credential
revoked credential
wrong device ID
wrong MQTT topic
topic/device mismatch
message/device mismatch
cross-device access
cross-tenant access
unauthorized capability
credential leakage
enrollment abuse
protocol version abuse
replay/duplicate messages

⸻

47. Device Isolation Tests

Create at least:

Device A
Device B

Verify:

A cannot publish to B
A cannot modify B state
A cannot ACK B effects
A cannot execute B capabilities
A cannot retrieve B effects

⸻

48. Enrollment Security Tests

Test:

unauthorized user → create enrollment

must fail.

Test:

authorized user → create enrollment

must succeed.

Test:

same enrollment key → second use

must fail if enrollment is single-use.

Test:

expired enrollment → use

must fail.

⸻

49. Credential Rotation

Implement or validate Device credential rotation.

Desired flow:

Credential A
    ↓
issue Credential B
    ↓
Device transitions
    ↓
Credential A revoked

Avoid unnecessary device downtime where possible.

Document the exact behavior.

⸻

50. Observability

Every Edge operation must propagate identifiers where available:

device_id
session_id
message_id
event_id
effect_id
execution_id
correlation_id
trace_id

The following trace must be reconstructable:

Device
 ↓
Message
 ↓
Event
 ↓
Execution
 ↓
Effect
 ↓
Transport
 ↓
Device
 ↓
ACK

⸻

51. Metrics

Add useful Edge metrics if the Runtime already supports metrics.

Recommended:

edge_messages_total
edge_messages_rejected_total
edge_auth_failures_total
edge_events_total
edge_state_updates_total
edge_effects_total
edge_effect_delivery_failures_total
edge_effect_ack_total
edge_duplicate_messages_total
edge_devices_connected
edge_devices_disconnected
edge_mqtt_connections
edge_http_requests

Do not add a new metrics system.

⸻

52. Logging

Logs should make debugging possible without exposing secrets.

Example:

device_id=...
message_id=...
event_id=...
effect_id=...
transport=mqtt

Never:

credential=...
password=...
token=...

⸻

53. Persistence Audit

Review all new Edge persistence.

Verify:

Devices
Credentials
Enrollments
State
State versions
Messages
Effects
Delivery metadata

use the existing persistence abstraction.

Do not create a separate Edge database.

⸻

54. SQLite

All Edge functionality must work with the existing SQLite Runtime configuration.

Test:

fresh database
migration
restart
reconnect
duplicate messages
pending Effects

⸻

55. Postgres

If Postgres is supported by the current Voodoo Runtime, repeat the critical persistence tests.

Pay special attention to:

concurrent Effect claiming
idempotency
State version updates
Device registration
credential rotation

⸻

56. Restart Recovery

Test:

Runtime
 ↓
pending Effect
 ↓
Runtime restart
 ↓
Device reconnect
 ↓
Effect still recoverable

The system must not lose persisted Effects merely because the process restarted.

⸻

57. Crash Safety

Test failures at important boundaries:

after Effect persistence
before delivery
after delivery before ACK
after ACK before persistence

The system must recover according to the documented at-least-once model.

Do not claim transactional guarantees that do not exist.

⸻

58. Execution Integration Test

Create the definitive Runtime integration test:

Device Event
     ↓
Runtime Event
     ↓
Execution
     ↓
Execution produces Effect
     ↓
Effect persisted
     ↓
Device Gateway
     ↓
transport
     ↓
Device
     ↓
ACK
     ↓
Effect completed
     ↓
Execution reflects completion

This test must use the real Runtime ExecutionEngine.

Do not mock the central ExecutionEngine in the primary E2E test.

⸻

59. HTTP E2E

Test:

Simulator
   ↓
HTTP
   ↓
Gateway
   ↓
Runtime
   ↓
Execution
   ↓
Effect
   ↓
HTTP delivery
   ↓
ACK

⸻

60. MQTT E2E

Test:

Simulator
   ↓
MQTT
   ↓
Gateway
   ↓
Runtime
   ↓
Execution
   ↓
Effect
   ↓
MQTT delivery
   ↓
ACK

⸻

61. Transport Equivalence Test

Given the same logical input:

temperature.changed

execute it through:

HTTP

and:

MQTT

Verify:

same Event semantics
same Execution semantics
same Capability behavior
same Effect semantics
same ACK semantics

Transport-specific metadata may differ.

Runtime semantics must not.

⸻

62. Duplicate Event E2E

Scenario:

Device
 ↓
EVENT #123
 ↓
Runtime
EVENT #123
 ↓
Runtime

Expected:

one semantic Event

unless explicitly documented otherwise.

⸻

63. Duplicate Effect E2E

Scenario:

Effect #123
 ↓
Device
Effect #123
 ↓
Device

Expected:

same logical Effect

and no unintended duplicate physical action where the protocol expects idempotency.

⸻

64. Reconnect E2E

Scenario:

Device
 ↓
AUTH
 ↓
EVENT
 ↓
disconnect
 ↓
Runtime restart
 ↓
reconnect
 ↓
AUTH
 ↓
STATE_SYNC
 ↓
continue

Verify all persistent information survives.

⸻

65. Capability E2E

Device advertises:

relay.control

Runtime attempts:

relay.control

must succeed if authorized.

Runtime attempts:

motor.control

must fail.

⸻

66. Documentation Updates

Update all relevant documentation.

At minimum:

README.md
CHANGELOG.md
SPRINT_PLAN.md
docs/runtime-contract.md
docs/architecture.md
docs/edge/overview.md
docs/edge/protocol.md
docs/edge/http.md
docs/edge/mqtt.md
docs/edge/security.md
docs/edge/device-lifecycle.md
docs/edge/state-synchronization.md
docs/edge/reliability.md
docs/edge/device-simulator.md

If some files do not exist, create them only where appropriate.

⸻

67. Runtime Contract Documentation

Update the Runtime Contract to explicitly state:

Device is an Entity.
Device Events enter the canonical Event system.
Device-triggered work enters the canonical Execution system.
Device Effects are canonical Effects.
Device capabilities use the canonical Capability system.
Device State uses canonical State semantics.

Also document:

Edge Protocol = external integration contract
HTTP/MQTT = transports
Device Gateway = boundary adapter

⸻

68. Edge Architecture Documentation

Document the final architecture:

                       Voodoo Runtime
                              │
                       Device Gateway
                              │
                 ┌────────────┴────────────┐
                 │                         │
                HTTP                      MQTT
                 │                         │
                 └────────────┬────────────┘
                              │
                         Edge Protocol
                              │
                           Device

Explicitly state that the Edge Gateway is not an execution engine.

⸻

69. Protocol Documentation

For every V1 message document:

HELLO
AUTH
STATE_SYNC
EVENT
EFFECT
EFFECT_ACK
HEARTBEAT

For each include:

* direction;
* authentication requirements;
* required fields;
* optional fields;
* validation;
* idempotency;
* errors;
* retry behavior;
* examples.

⸻

70. Reliability Documentation

Explicitly document:

at-least-once delivery
idempotency
duplicate Events
duplicate Effects
unknown delivery state
retry behavior
reconnect
State reconciliation
Runtime restart behavior

Do not claim exactly-once execution.

⸻

71. Security Documentation

Document:

Device identity
Device credentials
Enrollment
Credential rotation
Credential revocation
MQTT TLS
HTTP TLS expectations
Capability authorization
Topic authorization
Secret redaction
Replay/idempotency
Cross-device isolation

⸻

72. MQTT Documentation

Document:

broker configuration
TLS
authentication
topic structure
QoS
retained messages
connection lifecycle
authentication lifecycle
topic/device binding
reconnect

Provide a complete example.

⸻

73. HTTP Documentation

Document:

authentication
endpoint semantics
request schemas
response schemas
errors
idempotency
retry
Effect polling/delivery
ACK

Provide curl examples.

⸻

74. Device Simulator Documentation

Provide a quick-start:

1. Start Voodoo Runtime
2. Start MQTT broker
3. Create Device
4. Authenticate simulator
5. Connect simulator
6. Send Event
7. Observe Execution
8. Observe Effect
9. ACK Effect
10. Inspect final State

Provide both HTTP and MQTT workflows.

⸻

75. README Update

The README should include a concise section:

## Voodoo Edge

Explain that Voodoo can connect external Devices to the Runtime using:

HTTP
MQTT

and that an official ESP32 client is planned for the next sprint.

Do not claim that the ESP32 SDK already exists.

⸻

76. CHANGELOG

Add a release entry for Sprint 23.1.

Include:

Edge hardening
HTTP authentication/session fixes
MQTT session fixes
MQTT topic identity binding
Enrollment security
Execution/Effect integration
State reconciliation
Idempotency improvements
Security tests
Documentation

Use the project’s actual versioning conventions.

Do not invent a version number if the repository has an established version source.

⸻

77. SPRINT_PLAN

Update the roadmap to reflect the actual repository state.

Sprint 23 must be marked complete only if its implementation remains complete.

Add:

Sprint 23.1 — Edge Hardening & Runtime Integration

Mark the next milestone as:

Sprint 24 — Voodoo Edge ESP32 Reference Implementation

Do not leave the roadmap claiming TypeScript SDK is the next milestone if the architecture has intentionally prioritized ESP32 Edge.

⸻

78. Documentation Consistency Audit

Search the entire repository for outdated references such as:

Sprint 17
Sprint 22
Sprint 23
2.3.0
2.5.1
2.5.2
TypeScript SDK

where these references are supposed to describe the current state.

Correct stale documentation.

Do not modify historical changelog entries merely because they are old.

⸻

79. Protocol Schema Audit

Review all protocol schemas and confirm:

runtime model
protocol model
HTTP model
MQTT model

do not unnecessarily duplicate semantic definitions.

Where conversion is necessary, keep conversion logic explicit and tested.

The external protocol remains stable and language-neutral.

⸻

80. API Contract Stability

Do not break existing APIs unnecessarily.

If a breaking change is required:

1. document it;
2. version it;
3. add migration guidance;
4. update tests.

Prefer additive changes.

⸻

81. Code Quality

Before completion:

* remove dead Edge code;
* remove unused imports;
* remove duplicate logic;
* remove temporary compatibility hacks;
* simplify duplicated authentication logic;
* centralize identity validation;
* centralize protocol validation;
* ensure transport adapters remain thin;
* add type annotations consistent with the project;
* follow existing formatting/linting conventions.

⸻

82. Dependency Audit

Review dependencies added for Sprint 23.

Verify:

actively maintained
compatible with project Python version
async compatible
license compatible
not redundant

Do not add another MQTT or messaging abstraction if one already exists.

⸻

83. Performance Audit

Verify that:

heartbeat
state updates
MQTT messages
HTTP requests
Effect polling

do not create:

unbounded memory
unbounded sessions
unbounded database rows
blocking event loop operations

Where necessary, add limits.

⸻

84. Resource Limits

Define reasonable configurable limits for:

message size
payload size
State size
Event rate
heartbeat rate
pending Effects
connections

Reject abusive requests cleanly.

⸻

85. Final Security Review

Before declaring Sprint 23.1 complete, manually review:

Authentication
Authorization
Device identity
MQTT topic binding
Enrollment
Credential storage
Credential logging
State isolation
Effect isolation
Tenant isolation
Replay
Idempotency
Transport security

Document any known limitations.

⸻

86. Full Regression

Run:

all existing tests
+
all Edge unit tests
+
all Edge integration tests
+
all security tests
+
HTTP E2E
+
MQTT E2E

No existing Voodoo functionality may regress.

⸻

87. Definition of Done

Sprint 23.1 is complete only when:

[ ] HTTP does not create unnecessary persistent sessions
[ ] HTTP authentication context is correct
[ ] HTTP device identity is enforced
[ ] MQTT AUTH establishes a persistent connection context
[ ] MQTT subsequent messages use authenticated context
[ ] MQTT topic device_id is bound to authenticated device_id
[ ] MQTT message device_id is validated
[ ] Enrollment creation is protected
[ ] Enrollment credentials are secure
[ ] Device credentials are secure
[ ] Secrets are redacted from logs
[ ] Effects are integrated with Execution lifecycle
[ ] Effect state machine is explicit
[ ] Unknown delivery state is represented
[ ] Effect retries are bounded
[ ] Effect idempotency works
[ ] Event idempotency works
[ ] Duplicate responses are handled correctly
[ ] State versioning works
[ ] State reconciliation works
[ ] Reconnect works
[ ] Runtime restart recovery works
[ ] Device isolation works
[ ] Capability authorization works
[ ] HTTP E2E passes
[ ] MQTT E2E passes
[ ] HTTP/MQTT semantic equivalence passes
[ ] Duplicate Event test passes
[ ] Duplicate Effect test passes
[ ] Stale State test passes
[ ] Revoked Device test passes
[ ] Wrong MQTT topic test passes
[ ] Cross-device access tests pass
[ ] Enrollment security tests pass
[ ] Full regression suite passes
[ ] SQLite tests pass
[ ] Postgres tests pass where supported
[ ] Documentation is updated
[ ] Runtime Contract is updated
[ ] README is updated
[ ] CHANGELOG is updated
[ ] SPRINT_PLAN is updated
[ ] Sprint 24 ESP32 scope is documented

⸻

88. Final Acceptance Scenario

The following scenario must work end-to-end:

                     DEVICE
                       │
                       │ AUTH
                       ▼
                Device Gateway
                       │
                       ▼
                    Runtime
                       │
                       │
               Device registered
                       │
                       ▼
                 Device Event
                       │
                       ▼
                  Event System
                       │
                       ▼
                 ExecutionEngine
                       │
                       ▼
                    Execution
                       │
                       ▼
                     Effect
                       │
                       ▼
                Device Gateway
                       │
                 ┌─────┴─────┐
                 │           │
                HTTP        MQTT
                 │           │
                 └─────┬─────┘
                       │
                       ▼
                     DEVICE
                       │
                       │ execute
                       ▼
                      ACK
                       │
                       ▼
                Device Gateway
                       │
                       ▼
                 Effect update
                       │
                       ▼
               Execution update

Then intentionally:

network failure

must occur.

The Device reconnects:

Device
 ↓
AUTH
 ↓
STATE_SYNC
 ↓
reconciliation
 ↓
continue

without:

duplicate Device
duplicate Execution
duplicate semantic Event
duplicate physical Effect

where the protocol’s idempotency contract applies.

⸻

89. Architectural Acceptance Criteria

At the end of Sprint 23.1, the following statements must be true:

Statement 1

A Device is a first-class Voodoo Entity.

Statement 2

A Device Event is a normal Voodoo Event.

Statement 3

A Device-triggered operation uses the normal Voodoo ExecutionEngine.

Statement 4

A Device Effect is a normal Voodoo Effect.

Statement 5

Device capabilities use the existing Capability system.

Statement 6

Device State uses the existing State model.

Statement 7

HTTP and MQTT are only transports.

Statement 8

The Edge Gateway is an integration boundary, not another Runtime.

Statement 9

The Edge Protocol is language-neutral and can be implemented in C++.

Statement 10

The Runtime remains authoritative.

⸻

90. Expected Result

After Sprint 23.1:

                     VOODOO
                         │
          ┌──────────────┼──────────────┐
          │              │              │
        Agent          Human          Device
          │              │              │
          └──────────────┼──────────────┘
                         │
                    Execution
                         │
                    Capability
                         │
                       Effect
                         │
                 ┌───────┴────────┐
                 │                │
             Software          Hardware

The Edge layer becomes:

                     VOODOO RUNTIME
                           │
                      Edge Gateway
                           │
                  Voodoo Edge Protocol
                           │
                    ┌──────┴──────┐
                    │             │
                   HTTP          MQTT
                    │             │
                    └──────┬──────┘
                           │
                         Device

This is the foundation required for the next phase.

⸻

91. Next Sprint

After Sprint 23.1 passes all acceptance criteria:

Sprint 24 — Voodoo Edge ESP32 Reference Implementation

The next project should be:

voodoo-edge-esp32

The ESP32 client must consume:

voodoo-edge/v1

without changing the Runtime semantics.

Initial demonstration:

ESP32 Button
      │
      ▼
EVENT
      │
      ▼
Voodoo Runtime
      │
      ▼
Execution
      │
      ▼
Effect
      │
      ▼
ESP32 LED
      │
      ▼
ACK

Both:

HTTP
MQTT

must eventually be supported by the ESP32 client.

⸻

92. Final Principle

Sprint 23 created the Edge surface.

Sprint 23.1 must make that surface trustworthy.

The goal is not simply:

"MQTT works"

or:

"ESP32 can connect"

The goal is:

A physical Device can participate in Voodoo’s existing Entity → Event → Execution → Capability → Effect model with the same identity, authorization, persistence, reliability, and observability guarantees as the rest of the Runtime.

When this sprint is complete, Voodoo should be ready to cross the boundary from:

software-only Runtime

to:

software + physical world Runtime

without requiring a second architecture.