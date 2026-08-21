# Proof-context v0.1 interoperability

MCP++ owns the **wire contracts** for Proof-Carrying Context Engine v0.1.
Datasets, kit, and accelerator remain the canonical producers. MCP++ has no
production runtime, persistence, or model authority.

## Contracts

Closed JSON Schema drafts live under `schemas/proof-context/v0.1/`. Version
`0.1` is immutable after admission. Incompatible changes require a new version
and a migration record.

Canonical bytes use `mcpp-jcs-v1` (RFC 8785 JCS). New CIDs are CIDv1, codec
`raw`, multihash `sha2-256`, base32 (`b…`). Pseudo-CIDs (`sha256:…`, bare hex,
`Qm` new mints) are rejected.

## Status and provenance

Statuses are closed: `succeeded`, `rejected`, `verification_failed`,
`proof_failed`, `assurance_failed`, `context_insufficient`,
`model_escalation_required`, `human_review_required`, `unavailable`,
`timeout`, `cancelled`, `invalid`, `stale`, `simulated`,
`infrastructure_failure`, `partial_effect`, `repair_required`.

Provenance is `live`, `replayed`, or `simulated`. Simulated results cannot be
promoted as live `succeeded` identities. Stale roots are not live success.

## Vectors

`conformance/vectors/proof-context-v0.1.json` freezes positive canonical
UTF-8 + CID pairs and negative cases (unknown fields, malformed/pseudo CIDs,
wrong schema markers, missing required fields, simulated promotion, stale
live success).

## Compatibility

The four-repository producer/consumer matrix is admitted on the control
checkout at `artifacts/proof_carrying_context_engine/contracts/compatibility_matrix.json`.
Schema support on datasets/kit/accelerate is **consumer pending** until
PCCE-008 through PCCE-010 remove integration blockers. MCP++ is the schema
producer at gitlink `feat/pcce-006-proof-context-v0.1` (PCCE-006/007).
