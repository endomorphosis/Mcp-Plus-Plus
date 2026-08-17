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

### 2.1 CID Format (Normative)

CIDs MUST be valid IPFS Content Identifiers and MUST be byte-identical to the
output of Kubo (`ipfs add --cid-version=1 --raw-leaves`) for the same canonical
bytes. Two forms are accepted:

- **CIDv1 (preferred):** lowercase multibase base32 (`b` prefix). For 32-byte
  sha2-256 raw artifacts the string is the multibase encoding of
  `0x01 0x55 0x12 0x20 <sha256>` and renders as `bafkrei…` (59 chars total).
- **CIDv0 (legacy):** `Qm…` base58btc, 46 chars.

Conformant validators MUST accept exactly:

```
^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$
```

`bafkrei…` examples in this document are abbreviated; real values contain only
base32 alphabet characters (`a-z2-7`), never `0`, `1`, `8`, or `9`.

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
  "interface_cid": "bafkrei...",
  "tool": "repo.status",
  "input_cid": "bafkrei...",
  "expected_output_schema_cid": "bafkrei...",
  "constraints_policy_cid": "bafkrei...",
  "correlation_id": "uuid-or-nonce",
  "declared_side_effects": ["bafkrei...", "capability:write"]
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
  "intent_cid": "bafkrei...",
  "policy_cid": "bafkrei...",
  "proofs_checked": ["bafkrei..."],
  "evaluation_witness_cid": "bafkrei...",
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

Receipts are the immutable outcome record, suitable for audit, disputes, risk
scoring, and **cross-trust-domain independent verification**.

New portable work uses **ExecutionReceipt@1**
(`schema: mcp++/execution/receipt@1`; see
[execution-envelope.md](execution-envelope.md) §6 and
`schemas/execution/execution-receipt-1.schema.json`). Profile B field names
below remain readable historical shapes; adapters map them without rewriting
historical CIDs (MCPP-031).

### 6.1 Suggested Fields (Profile B historical)

```json
{
  "intent_cid": "bafkrei...",
  "output_cid": "bafkrei...",
  "observed_side_effects": ["bafkrei..."],
  "proofs_checked": ["bafkrei..."],
  "decision_cid": "bafkrei...",
  "correlation_id": "uuid-or-nonce",
  "time_observed": "2026-02-04T12:34:56Z",
  "signatures": ["..."]
}
```

Receipts **MUST** be content-addressed. Same-trust-domain receipts **MAY** be
unsigned. Cross-trust-domain receipts **MUST** be signed (plan gate 15).

### 6.2 Cross-trust-domain signed receipts (Normative, MCPP-045 / gate 15)

**Interface:** `ReceiptVerifier@1`  
**Conformance level:** `receipt-signed` (ADR-0003)  
**Crypto:** ADR-0002 — Ed25519 over `mcpp-jcs-v1` canonical bytes

When an execution crosses trust domains (requester trust domain ≠ executor
trust domain, or any portable claim of cross-domain authority):

1. The executor **MUST** mint an **ExecutionReceipt@1** (or an adapter-equivalent
   receipt) that is content-addressed under `mcpp-jcs-v1`.
2. The receipt **MUST** carry a non-null `signature` and `signature_alg` of
   `Ed25519` (EdDSA wire alias accepted for verification).
3. The signature **MUST** cover the detached receipt body under `mcpp-jcs-v1`:
   all fields **except** `signature`, `signature_alg`, and `receipt_cid` (the
   self-address is assigned after signing).
4. Verifiers **MUST** fail closed on:
   - missing / null / empty signature on a cross-domain receipt
     (`unsigned_cross_domain_receipt`);
   - undecodable or non-verifying signature (`invalid_signature`);
   - CID mismatch when loading by `receipt_cid` (`cid_mismatch`).
5. Same-trust-domain receipts **MAY** set `signature` / `signature_alg` to
   `null`. Such receipts **MUST NOT** be scored as `receipt-signed`.
6. Presence of a `signature` string field is **structural only**. A green
   structural validator is **not** `receipt-signed` (ADR-0003; KD-6).

#### 6.2.1 Transport identity is never execution authority (KD-14)

| Layer | Identifies | Grants execution authority? |
| --- | --- | --- |
| TLS client certificate | Transport peer | **No** |
| libp2p / P2P PeerID | Transport peer | **No** |
| `executor.peer_id` on a receipt | Optional transport hint | **No** |
| UCAN / `DelegationProof@1` / `delegation_cid` | Capability authority | **Yes** (when cryptographically verified) |
| Receipt Ed25519 signature | Executor attestation of outcomes | Attests outcomes; does **not** replace UCAN |

Normative rules:

1. A valid TLS session or authenticated PeerID **MUST NOT** admit cross-domain
   execution or receipt acceptance when the UCAN / delegation proof is missing,
   expired, revoked, forged, or otherwise invalid.
2. The deny reason set for “transport looks fine, authority does not” **MUST**
   include `peerid_not_authority` (and typically `invalid_ucan` or
   `missing_authority_proof`). This aligns with adversarial vector
   `valid_peerid_invalid_ucan` (MCPP-044).
3. Cross-domain receipts **SHOULD** bind a non-null `delegation_cid` (or
   equivalent proof CID list on `proofs` / envelope `authority.proof_cids`).
   `delegation_cid: null` is reserved for same-trust local receipts.
4. Payment, PeerID, and TLS **MUST NOT** be treated as substitutes for Profile C
   authority checks at execution time or at receipt admission.

#### 6.2.2 Independent verification by CID

A third party that did **not** observe the executor’s transport session **MUST**
be able to validate a cross-domain receipt using only:

1. The receipt bytes (or a content store lookup keyed by `receipt_cid`);
2. The executor’s public key (resolved from `executor.did` / `key_id`, never from
   PeerID alone);
3. Optional authority material referenced by `delegation_cid` / `proofs`.

**Interface obligations for `ReceiptVerifier@1`:**

- `verify_receipt(receipt, trust_context)` — admit/deny with conformance levels
  `structural`, `cryptographic`, and `receipt-signed`.
- `verify_by_cid(receipt_cid, store, trust_context)` — load bytes by CID,
  recompute the content CID under `mcpp-jcs-v1`, fail closed on mismatch, then
  verify the signature and authority rules above.

An **independent verifier process** (separate OS process / language runtime)
that is given only the store, the CID, and public key material **MUST** reach
the same admit/deny decision as an in-process verifier. Transport session state
**MUST NOT** be required for `receipt-signed` verification.

Evidence for this requirement lives in
`tests-py/integration/test_signed_receipts.py` (MCPP-045).

### 6.3 Observability and Correlation (Non-Normative)

The archived design thread emphasizes “mandatory observability hooks (trace IDs, provenance metadata) baked into every call/reply/exception”. MCP++ supports this without changing baseline MCP semantics by treating immutable artifacts as the correlation substrate:

- `intent_cid` and/or `event_cid` are stable, content-addressed identifiers suitable for trace correlation across components.
- `correlation_id` remains useful for ephemeral/UI correlation (and SHOULD be carried from intent into receipts when available).
- Alias note: the archive also describes “transactional grouping for “multi-step tasks as a single reliable operation””; MCP++ can model this by carrying a common `correlation_id` across the related intents/receipts/events.

## 7. Event Node (CID’d)

Events connect intents/decisions/receipts into a provenance and concurrency structure.

### 7.1 Suggested Fields

```json
{
  "parents": ["bafkrei..."],
  "interface_cid": "bafkrei...",
  "intent_cid": "bafkrei...",
  "proof_cid": "bafkrei...",
  "decision_cid": "bafkrei...",
  "output_cid": "bafkrei...",
  "receipt_cid": "bafkrei...",
  "peer_did": "did:key:...",
  "timestamps": {"created": "...", "observed": "..."}
}
```

## 8. EncryptedArtifactRef@1 and KeyEnvelope@1 (Normative, KD-15)

**Interfaces:** `EncryptedArtifactRef@1`, `KeyEnvelope@1`  
**Schema marker:** `mcp++/confidential/encrypted-artifact-ref@1`  
**Nested envelope marker:** `mcp++/confidential/key-envelope@1`  
**Schema document:** `ipfs_accelerate_py/mcplusplus/schemas/confidential/encrypted-artifact-ref-1.schema.json`

Content addressing is **not** publication. A CID may address ciphertext that
most peers can fetch yet only authorized recipients can decrypt. MCP++ models
that boundary with a portable **encrypted artifact reference**: a public,
content-addressable handle that points at ciphertext and carries enough
metadata to verify integrity and authorize unwrap — without carrying plaintext.

Schema acceptance of these shapes is **structural only** (ADR-0003). Decrypt
success, capability checks, and AEAD verification are higher conformance
levels (`cryptographic`, `policy-enforced`).

### 8.1 Why a separate ref type?

| Concern | Public CID artifact | EncryptedArtifactRef |
| --- | --- | --- |
| Integrity | CID of plaintext bytes | CID of **ciphertext** bytes (still verifiable) |
| Confidentiality | Anyone with the CID can read | Only parties who can unwrap the content key |
| Receipts / Event DAG | Often link the artifact CID | Link `ref_cid` / `ciphertext_cid` without disclosure |
| Policy | Optional | Disclosure + retention policy CIDs + redaction metadata |

### 8.2 Required fields (EncryptedArtifactRef@1)

| Field | Role |
| --- | --- |
| `schema` | Const `mcp++/confidential/encrypted-artifact-ref@1` |
| `ciphertext_cid` | CID of AEAD ciphertext bytes (never plaintext) |
| `algorithm` | Closed content AEAD + key-wrap parameters |
| `key_envelope` | `KeyEnvelope@1` with wrapped content keys and recipients |
| `plaintext_schema_cid` | Schema the plaintext MUST satisfy after decrypt |

### 8.3 Optional fields

| Field | Role |
| --- | --- |
| `protected_digest` | Optional hash commitment to (canonical) plaintext |
| `disclosure_policy_cid` | Who may observe plaintext / export digests |
| `retention_policy_cid` | How long ciphertext, keys, and decrypt caches may live |
| `redaction` | Export / projection treatment (`never-export-plaintext`, `commitment-only`, …) |
| `recipients` / `access_caps` | Top-level summaries; envelope remains authoritative for wraps |
| `issuer`, `created_at_ms`, `canonicalization`, `ref_cid`, `parents`, `correlation_id`, `label` | Mint identity and correlation without secrets |
| `metadata` | Non-authoritative annotations; **MUST NOT** hold plaintext or raw DEKs |

### 8.4 Algorithm profile (closed for new mints)

**Content AEAD (authenticated encryption required):**

- `AES-256-GCM`
- `ChaCha20-Poly1305`

**Key wrap:**

- `X25519-HKDF-SHA256-AES-256-GCM`
- `X25519-HKDF-SHA256-ChaCha20-Poly1305`
- `direct-AES-256-GCM` / `direct-ChaCha20-Poly1305` (same-trust or pre-shared DEK wrap only)
- `UCAN-cap-unwrap` (content key released only after capability validation by a designated unwrap service)

Unauthenticated modes, empty algorithm strings, and silent downgrade are
**forbidden**. Implementations **MUST** fail closed on unknown algorithm tokens.

**Ciphertext layout** (bytes addressed by `ciphertext_cid`):

- Preferred: `nonce_prepended_ciphertext_tag`
- Alternatives: `nonce_separate_ciphertext_tag` (nonce on the ref), `raw_ciphertext_tag`

AEAD tag length is **16 bytes** for the closed set. Nonce reuse with the same
content key is a critical security failure; emitters **MUST** use a unique
nonce per encryption under a given DEK.

**AAD binding.** `algorithm.aad_binding` records what is fed as AEAD additional
authenticated data so ciphertext cannot be reassociated under a different
schema or issuer. Recommended for structured payloads:
`plaintext_schema_cid` or `ref_canonical_body`.

### 8.5 KeyEnvelope@1 semantics

```json
{
  "schema": "mcp++/confidential/key-envelope@1",
  "content_key_id": "ck-…",
  "wrapped_keys": [
    {
      "recipient": "did:key:…",
      "recipient_kid": "…",
      "key_wrap": "X25519-HKDF-SHA256-AES-256-GCM",
      "wrapped_key_b64url": "…",
      "ephemeral_public_key_b64url": "…",
      "capability_cid": "bafkrei…",
      "expires_at_ms": 1893456000000
    }
  ],
  "access_caps": [
    {
      "kind": "ucan_proof_cid",
      "cid": "bafkrei…",
      "ability": "mcp++/confidential/decrypt",
      "resource": "bafkrei…"
    }
  ],
  "epoch": 1,
  "revocation_binding": {
    "mode": "delegation_ledger",
    "ledger_or_registry": "mcp++/revocation-default"
  }
}
```

Normative rules:

1. **`wrapped_keys` MUST be non-empty.** A sealed artifact always names at
   least one unwrap path.
2. **Wrapped keys are not content keys.** Fields named `wrapped_key_b64url`
   carry ciphertext of the DEK. Raw DEKs **MUST NOT** appear on the ref, in
   Event DAG metadata, logs, or local fallback caches (KD-15).
3. **Recipient private key possession is necessary but not always sufficient.**
   When `access_caps` or per-wrap `capability_cid` are present, unwrap
   **MUST** also validate those capabilities at decrypt time (fail closed).
   Transport identity (PeerID, TLS client cert) never grants unwrap (KD-14).
4. **`content_key_id`** is an opaque correlation handle for rotation and
   audit. It **MUST NOT** be derivable into key bytes.
5. **`epoch` / `supersedes_content_key_id`** support re-wrap after rotation.
   A higher epoch on a **new** ref does not rewrite historical CIDs or erase
   prior envelopes.
6. **Per-wrap `expires_at_ms`** makes that wrap entry fail closed after expiry
   even if ECDH would still succeed. Expiry is not global ciphertext deletion.

### 8.6 Ciphertext is verifiable without disclosure

Verifiers that **do not** hold unwrap rights can still:

1. Fetch bytes at `ciphertext_cid` (subject to storage availability).
2. Confirm the CID matches the bytes (content-address integrity).
3. Structurally validate the `EncryptedArtifactRef` document.
4. Confirm `algorithm` is in the closed set and `key_envelope` names recipients.
5. Optionally recompute `ref_cid` under `mcpp-jcs-v1` when `canonicalization`
   is declared.

They **cannot** obtain plaintext without a successful AEAD open under an
authorized wrap path. Integrity of ciphertext is therefore separable from
confidentiality of plaintext.

When `protected_digest` is present, authorized decryptors **MUST** verify the
digest after unwrap. Emitters **MUST** omit or null `protected_digest` unless
disclosure policy permits: plaintext digests enable offline guessing of
low-entropy secrets.

### 8.7 Receipts can attest use without disclosure

Receipts, decisions, and Event DAG nodes **MAY** attest that a confidential
artifact was used by linking **non-secret identifiers only**:

| Safe to link in receipts / Event DAG | Forbidden |
| --- | --- |
| `ref_cid` of an `EncryptedArtifactRef@1` | Plaintext bytes or recoverable fragments |
| `ciphertext_cid` | Raw DEK / unwrapped content key |
| `plaintext_schema_cid` | Full `key_envelope.wrapped_keys` material when policy says commitment-only (optional harden) |
| `redaction.mode`, policy CIDs | `protected_digest` when disclosure policy disallows |
| Correlation ids that are not secrets | Decrypt caches written into receipt metadata |

Recommended receipt pattern (Profile B / ExecutionReceipt@1 adapters):

```json
{
  "output_cids": ["bafkrei…EncryptedArtifactRef…"],
  "side_effects": [
    {
      "kind": "confidential_artifact_used",
      "effect_cid": "bafkrei…ciphertext…",
      "description": "decrypt-authorized; plaintext not included"
    }
  ]
}
```

An auditor can prove **which** confidential artifact participated in an
execution by walking CIDs, without learning the plaintext. Attestation of use
**MUST NOT** be implemented by embedding plaintext “for convenience.”

### 8.8 Example EncryptedArtifactRef@1

```json
{
  "schema": "mcp++/confidential/encrypted-artifact-ref@1",
  "ciphertext_cid": "bafkrei…",
  "algorithm": {
    "content_aead": "AES-256-GCM",
    "key_wrap": "X25519-HKDF-SHA256-AES-256-GCM",
    "ciphertext_layout": "nonce_prepended_ciphertext_tag",
    "aead_tag_length": 16,
    "aad_binding": "plaintext_schema_cid",
    "hkdf_info": "mcp++/confidential/content-key@1"
  },
  "key_envelope": {
    "schema": "mcp++/confidential/key-envelope@1",
    "content_key_id": "ck-01",
    "wrapped_keys": [
      {
        "recipient": "did:key:z6Mk…",
        "wrapped_key_b64url": "…",
        "ephemeral_public_key_b64url": "…",
        "capability_cid": "bafkrei…"
      }
    ],
    "access_caps": [],
    "epoch": 1,
    "revocation_binding": { "mode": "delegation_ledger" }
  },
  "plaintext_schema_cid": "bafkrei…",
  "protected_digest": null,
  "disclosure_policy_cid": "bafkrei…",
  "retention_policy_cid": "bafkrei…",
  "redaction": {
    "mode": "never-export-plaintext",
    "public_fields": [
      "schema",
      "ciphertext_cid",
      "ref_cid",
      "plaintext_schema_cid",
      "redaction.mode"
    ]
  },
  "canonicalization": "mcpp-jcs-v1"
}
```

(`bafkrei…` placeholders are abbreviated; real CIDs match §2.1.)

### 8.9 Honest revocation behavior

Revocation in a CID-first system is **access control over future unwrap**, not
cryptographic erasure of history. Implementations and operators **MUST**
document and implement the following without overclaim:

1. **Ciphertext CIDs remain fetchable.** Publishing `ciphertext_cid` into IPFS
   (or any durable content store) is not undone by revoking a UCAN or rotating
   a key. Peers that already mirrored the bytes keep them.

2. **Revoking unwrap rights fails closed at decrypt time.** When
   `revocation_binding.mode` is `delegation_ledger` (or equivalent), validators
   **MUST** consult the authoritative `RevocationRecord@1` sources for
   `access_caps` / `capability_cid` and **MUST** deny unwrap if the
   authorizing delegation is revoked — even when ECDH would still open a wrap.

3. **Already-distributed plaintext is out of band.** Any party that previously
   decrypted retains that plaintext. MCP++ does not claim remote wipe of
   recipient memory, disks, or logs outside this protocol.

4. **Re-wrap ≠ rewrite history.** Emitting a new `EncryptedArtifactRef` with a
   higher `key_envelope.epoch` and a new recipient set creates a **new** CID.
   Historical refs continue to carry their original envelopes. Mitigations:
   stop distributing old refs, expire wraps (`expires_at_ms`), revoke
   capabilities, and apply retention policy to local decrypt caches.

5. **`wrap_expiry_only` is weak.** Mode `wrap_expiry_only` relies on per-wrap
   timestamps without a live ledger. Clocks can skew; offline holders of
   unexpired wraps keep access until expiry. Do not advertise this mode as
   strong multi-party revocation.

6. **`content_key_epoch` rotation** invalidates unwrap for callers that only
   accept the latest epoch **by local policy**. It does not stop holders of old
   DEKs or old plaintext.

7. **Absence of `revocation_binding` is not “irrevocable forever.”** Outer
   UCAN policy, disclosure policy, and operational key destruction may still
   deny access. Conversely, absence of a ledger **MUST NOT** be treated as
   “revocation checked OK.”

8. **Structural schema green ≠ revoked-key enforcement.** A document can be
   schema-valid while a runtime fails to consult a ledger. Cryptographic and
   policy-enforced conformance require negative tests for revoked access
   (see MCPP-074 / MCPP-G150 evidence).

### 8.10 Non-leakage obligations (pointer)

Plaintext and raw content keys **MUST NOT** appear in:

- application logs or traces,
- Event DAG metadata fields,
- portable errors,
- local fallback / offline caches used when encrypted stores are unavailable.

Those runtime obligations are specified for proof under MCPP-G150 / MCPP-074;
this section defines the wire shapes those tests assume.

### 8.11 Structural validation

```bash
python -m json.tool ipfs_accelerate_py/mcplusplus/schemas/confidential/encrypted-artifact-ref-1.schema.json > /dev/null
```

A document is a valid `EncryptedArtifactRef@1` only if it parses as JSON,
matches the schema (`additionalProperties` false at the object layers defined
there), uses the closed algorithm enums, and never places plaintext or raw
DEK fields on the ref. Higher levels still require AEAD open, capability
checks, and disclosure-policy enforcement.

---

## 9. Security Considerations

- Canonicalization MUST be specified tightly enough to avoid ambiguity attacks.
- Evaluator signatures (on `decision_cid` and/or `receipt_cid`) SHOULD be supported for cross-peer trust.
- **Cross-trust-domain receipts MUST be signed** and independently verifiable by
  CID under `ReceiptVerifier@1` at conformance level `receipt-signed` (§6.2;
  plan gate 15; MCPP-045). Unsigned cross-domain receipts are deny.
- **Transport identity ≠ execution authority** (KD-14): valid TLS or PeerID with
  invalid or missing UCAN is deny (`peerid_not_authority`). Payment never
  authorizes execution.
- Signature **presence** on a receipt is structural only; `receipt-signed`
  requires real Ed25519 verification over `mcpp-jcs-v1` bytes (ADR-0002/0003).
- Confidential artifacts use `EncryptedArtifactRef@1` (§8): ciphertext CIDs are
  verifiable; receipts attest use without disclosure; revocation is access
  control over unwrap, not erasure of content-addressed history (KD-15).
  Transport identity never grants unwrap (§8.5 rule 3).
