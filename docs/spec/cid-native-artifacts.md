# Profile B: CID-Native Execution Artifacts

**Status:** Draft

This document specifies the CID-native artifacts used by MCP++ profiles: inputs, outputs, intents, decisions, receipts, and events.

## 1. Why CID-native artifacts?

- **Immutability & replay:** same CID → same bytes → same artifact.
- **Provenance:** Merkle-style links let you prove “this output came from these inputs under these proofs/policies.”
- **Auditability:** disputes, rollbacks, and credit assignment become DAG walking.

## 2. Canonicalization (Normative)

Implementations MUST define deterministic canonicalization for any content that is turned into a CID.

A canonicalization pipeline SHOULD include:
- stable encoding (canonical JSON or CBOR family; archive phrasing: “Canonical JSON / CBOR encoding”)
- sorted keys and normalized numeric representations
- explicit schema/version markers

## 3. Artifact Types

The following identifiers are used throughout MCP++:

- `input_cid`: canonicalized request input
- `output_cid`: canonicalized output/result
- `intent_cid`: canonicalized plan-to-act object (what will be attempted)
- `policy_cid`: canonicalized policy (permissions/prohibitions/obligations + temporal constraints)
- `proof_cid`: canonicalized proof bundle (e.g., UCAN chain)
- `decision_cid`: canonicalized policy evaluation result
- `receipt_cid`: canonicalized execution receipt/attestation
- `event_cid`: canonicalized event node that links the above into an append-only DAG

## 4. Intent Object (CID’d)

The intent object is the minimal, immutable “what I plan to do” description used for policy evaluation and later replay.

### 4.1 Suggested Fields

```json
{
  "interface_cid": "bafy...",
  "tool": "repo.status",
  "input_cid": "bafy...",
  "expected_output_schema_cid": "bafy...",
  "constraints_policy_cid": "bafy...",
  "correlation_id": "uuid-or-nonce",
  "declared_side_effects": ["bafy...", "capability:write"]
}
```

- `constraints_policy_cid` MAY equal the active `policy_cid`, or refer to a narrower policy for the specific action.
- `correlation_id` is a non-normative correlation hook described in the archive as `nonce / correlation_id`.

## 5. Decision Object (CID’d)

A decision is produced by evaluators after verifying proofs and evaluating policy at execution time.

### 5.1 Suggested Fields

```json
{
  "decision": "allow" ,
  "intent_cid": "bafy...",
  "policy_cid": "bafy...",
  "proofs_checked": ["bafy..."],
  "evaluation_witness_cid": "bafy...",
  "justification": "human-readable or structured",
  "obligations": [
    {"type": "produce_receipt", "deadline": "2026-02-04T12:00:00Z"}
  ],
  "policy_version": "v1",
  "evaluator_dids": ["did:key:..."],
  "signatures": ["...optional..."]
}
```

- `decision` SHOULD support at least: `allow`, `deny`, `allow_with_obligations`.

`evaluation_witness_cid` is OPTIONAL. When present, it SHOULD commit to a deterministic, replayable “why” record (e.g., evaluator inputs, rule IDs fired, or a policy-evaluation transcript) without requiring the ecosystem to standardize one proof format immediately.

Alias note: the archived notes refer to the signature array as `signatures[]`.

## 6. Receipt Object (CID’d)

Receipts are the immutable outcome record, suitable for audit, disputes, and risk scoring.

### 6.1 Suggested Fields

```json
{
  "intent_cid": "bafy...",
  "output_cid": "bafy...",
  "observed_side_effects": ["bafy..."],
  "proofs_checked": ["bafy..."],
  "decision_cid": "bafy...",
  "correlation_id": "uuid-or-nonce",
  "time_observed": "2026-02-04T12:34:56Z",
  "signatures": ["..."]
}
```

Receipts MUST be content-addressed and MAY be signed.

## 6.2 Observability and Correlation (Non-Normative)

The archived design thread emphasizes “mandatory observability hooks (trace IDs, provenance metadata) baked into every call/reply/exception”. MCP++ supports this without changing baseline MCP semantics by treating immutable artifacts as the correlation substrate:

- `intent_cid` and/or `event_cid` are stable, content-addressed identifiers suitable for trace correlation across components.
- `correlation_id` remains useful for ephemeral/UI correlation (and SHOULD be carried from intent into receipts when available).
- Alias note: the archive also describes “transactional grouping for “multi-step tasks as a single reliable operation””; MCP++ can model this by carrying a common `correlation_id` across the related intents/receipts/events.

## 7. Event Node (CID’d)

Events connect intents/decisions/receipts into a provenance and concurrency structure.

### 7.1 Suggested Fields

```json
{
  "parents": ["bafy..."],
  "interface_cid": "bafy...",
  "intent_cid": "bafy...",
  "proof_cid": "bafy...",
  "decision_cid": "bafy...",
  "output_cid": "bafy...",
  "receipt_cid": "bafy...",
  "peer_did": "did:key:...",
  "timestamps": {"created": "...", "observed": "..."}
}
```

## 8. Security Considerations

- Canonicalization MUST be specified tightly enough to avoid ambiguity attacks.
- Evaluator signatures (on `decision_cid` and/or `receipt_cid`) SHOULD be supported for cross-peer trust.
