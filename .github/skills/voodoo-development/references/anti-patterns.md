# Application Anti-patterns

Avoid:

- Events encoded manually into KV when native Topics exist.
- Object storage represented as arbitrary KV blobs when native Objects exist.
- Custom queue tables when native Jobs/Queue exists.
- Opening a second `.vstore` writer inside an adapter.
- Automatically indexing every Model field.
- Treating UUIDv7 as a business/customer-facing sequence.
- Using UUID embedded time instead of explicit domain timestamps.
- A giant ORM-style `field(...)` argument bag.
- Claiming global exactly-once, consensus, or global serializable transactions without implementation proof.

Always ask first: does Voodoo already have a native primitive or architectural rule for this problem?
