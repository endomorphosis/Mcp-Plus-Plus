# Profile C: Capability Delegation (UCAN)

**Status:** Draft

This document expands the MCP++ delegation profile based on UCAN-style capability chains.

## 1. Goals

- Make authority **explicit, delegable, and attenuable** across multi-hop agent workflows.
- Bind authority to **interfaces and content** (CIDs), not vague strings.
- Ensure authorization is checked **at execution time**.

## 2. Conceptual Model

A typical chain looks like:

User → Planner model → Worker model → Tool peer

Each hop delegates a subset of authority, potentially with time bounds and caveats.

## 3. What Gets Delegated?

MCP++ delegation SHOULD be able to express:

- **Interface/method invocation**: “may invoke interface CID X, method Y”.
- **Content-scoped rights** (CID-native):
  - “may read CID X”
  - “may write under CID-prefix Y”
  - “may derive output CID only from allowed input CIDs”
- **Operational constraints**:
  - time windows
  - rate limits / budgets
  - environment constraints (e.g., only within a given peer group)

## 4. Proof Bundles (`proof_cid`)

Delegation proofs SHOULD be represented as a canonicalized proof bundle and content-addressed as `proof_cid`.

At minimum, evaluators must be able to verify:
- issuer and audience bindings,
- signature validity,
- attenuation across the chain,
- caveats and expiry.

## 5. Invocation Shape (MCP++ Integration)

At execution time, an invocation SHOULD include:

- `intent_cid`
- `ucan_proofs[]` (or a single `proof_cid` referencing the proof bundle)
- `policy_cid` (if richer constraints are evaluated via deontic policy)
- `context_cids[]` (state snapshots / relevant prior events)

## 6. Execution-Time Validation (Normative)

Implementations MUST validate delegation proofs at execution time.

Validation MUST include:
- cryptographic proof verification
- capability matching (interface/method/content constraints)
- caveat checks (time bounds, budgets, revocations)

## 7. Relationship to Temporal Deontic Policy

UCAN covers the cryptographic authorization chain (“who can do what”).

Temporal deontic policy evaluation can cover richer norms (“when/under what conditions/what obligations are spawned”).

See: [docs/spec/temporal-deontic-policy.md](temporal-deontic-policy.md)

## 8. Receipts

Receipts SHOULD bind to the proofs checked so that later auditors can verify that:
- the action was authorized,
- under which delegation chain,
- under which policy version.

See: [docs/spec/cid-native-artifacts.md](cid-native-artifacts.md)

## 9. Open Questions

- Standard capability vocabulary for interface vs CID-prefix constraints.
- Revocation representation and propagation in a CID-first world.
- How to encode budget constraints for toolset slicing and execution.
