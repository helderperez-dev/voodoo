# Workflow persistence boundary

Runtime `WorkflowStore` checkpoints use native Store workflows. Runtime workflow
IDs remain human-readable strings and checkpoints contain orchestration
projections (`task_results`, execution IDs, iteration state, and error metadata),
while the native Store workflow primitive uses generated 16-byte IDs and a
state/history model. A durable mapping in `runtime:workflows:native-id:` bridges
those identities.

The checkpoint codec is schema version **1**. Native workflow state preserves
the rich checkpoint payload, native status transitions are authoritative for
terminal state, and records written before native migration remain readable
through the legacy KV namespace. Unknown future versions are rejected before
they can influence orchestration. Native workflow history remains Store-owned;
Runtime consumes the checkpoint projection and does not duplicate history.
