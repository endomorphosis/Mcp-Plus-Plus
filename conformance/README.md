# Cross-language conformance vectors

Canonical MCP++ wire payloads captured from the live `ipfs_accelerate_py` and
`ipfs_datasets_py` servers. Every spec validator (Python, TypeScript, Rust, Go)
loads these same `vectors/*.json` files and validates each `payload` against the
named `model`. A new third-party implementation is interoperable iff it accepts
all vectors.

Each vector: `{"model": "<CanonicalModelName>", "payload": { ... }}`.

Models: `InitializeResult`, `PolicyDecision`, `P2PMessage`, `Delegation`,
`DAGEvent`, `ExecutionReceipt`. Adding a vector here forces all four validators
to agree on it, preventing silent drift between the mirrors.
