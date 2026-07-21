# Profile F Groth16 Multi-Party Ceremony

**Status:** Draft

This chapter defines the circuit-specific, independently replayable Groth16
multi-party setup used by Profile F. It supplements [Profile F: Event DAG
Provenance, Archival, and Compaction](event-dag-ordering.md); it does not change
baseline MCP message semantics.

The native protocol identifier is
`arkworks-groth16-bn254-delta-mpc-v1`. Its public transcript has schema version
`1` (also referred to by the Python API as
`mcp++/arkworks-groth16-mpc@1`). The portable MCP++ envelope retains the schema
identifier `mcp++/groth16-mpc-ceremony@1`.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative as
described in RFC 2119.

## 1. Goals and scope

This protocol replaces a setup in which one process supplies all randomness
with a sequence of genuine Groth16 phase-2 `delta` transforms. Each participant
holds fresh entropy locally, changes the current Arkworks proving key, and
publishes only the transformed key and public proof evidence. Every later
participant and every auditor can verify the transform without learning the
participant's scalar.

The protocol provides:

- retention of all preceding contributions in the final key;
- a deterministic, hash-linked public transcript;
- a proof of knowledge for each participant's contribution scalar;
- independent verification against the before and after proving keys;
- canonical Arkworks proving-key and verification-key exports; and
- binding of those exports to the exact Profile F v3 R1CS and to a Profile F
  compaction certificate.

This chapter covers the circuit-specific phase-2 transform. Approval of the
genesis proving key and any preceding phase-1 ceremony remains a separate
trust decision. An implementation MUST NOT describe a locally seeded genesis,
a list of coordinator-selected seeds, a Merkle root, a DID signature, or a
hash-only transcript check as an independently verified MPC ceremony.

## 2. Cryptographic transform

The curve is Arkworks `ark_bn254::Bn254`, named `BN254` in the native
transcript. Let the current Groth16 proving key contain:

- `delta_g1 = delta * G1`;
- `vk.delta_g2 = delta * G2`;
- delta-denominated `h_query[j]` and `l_query[j]`; and
- all other standard Arkworks `ProvingKey<Bn254>` fields.

A participant samples `s` uniformly from the BN254 scalar field using the
operating system cryptographic RNG. The values `0` and `1` MUST be rejected.
The participant computes:

```text
delta_g1'    = s * delta_g1
delta_g2'    = s * delta_g2
h_query'[j]  = s^-1 * h_query[j]   for every j
l_query'[j]  = s^-1 * l_query[j]   for every j
```

Every non-delta field and every query length MUST remain byte-for-byte
equivalent after canonical deserialization. Thus, after contributions
`s1 ... sn`, the delta elements contain the product `s1 * ... * sn`, while
the H and L queries contain its inverse. A later contributor cannot remove an
earlier unknown contribution. Phase-2 security therefore holds if at least
one accepted contributor samples `s` honestly and erases it, subject to the
genesis/phase-1 trust assumptions above.

The contribution also publishes:

```text
S1 = s * G1
S2 = s * G2
R  = r * G1
z  = r + c*s
```

where `r` is a separately sampled non-zero scalar and `c` is the
transcript-bound Fiat-Shamir challenge. `R` MUST NOT be the identity: a zero
nonce would disclose `s` through `z`. Neither `s`, `s^-1`, nor `r` is
serialized.

## 3. Independent verification

A verifier MUST possess the canonical before and after proving keys. Hashes or
signatures alone are insufficient. For each contribution, in sequence, it
MUST:

1. Canonically deserialize both keys with subgroup validation, reject trailing
   bytes, and reserialize them to prove encoding uniqueness.
2. Recompute both key hashes and the public contribution hash.
3. Check the sequence number, prior transcript head, prior key hash, participant
   uniqueness, circuit binding, and expected output-key hash.
4. Reject identity public entropy, an identity transform, or an identity
   Schnorr commitment.
5. Verify the Schnorr relation `z*G1 = R + c*S1`.
6. Verify equal discrete logarithms across groups:
   `e(S1, G2) = e(G1, S2)`.
7. Verify the delta transforms:
   `e(delta_g1, S2) = e(delta_g1', G2)` and
   `e(S1, delta_g2) = e(G1, delta_g2')`.
8. Verify that all non-delta parameters are unchanged.
9. Verify inverse scaling of both H and L queries.

The reference verifier checks each query family with a transcript-derived
random linear combination. For family `K` in `{H,L}`, it derives non-zero
coefficients `a_j` from
`SHA-256("groth16-mpc-query-batch-v1\0" || u64be(len(K)) || K || contribution_hash ||
u64be(j))`, reducing the digest into the scalar field and replacing zero with
one. It then checks:

```text
e(sum(a_j * K'_j), S2) = e(sum(a_j * K_j), G2)
```

H and L have distinct domains. The batching soundness error is at most one
over the scalar-field order per equation. An implementation MAY check every
query individually instead.

An independent full replay starts from an operator-approved genesis key,
applies these checks to every ordered intermediate key, and compares the
resulting transcript and terminal key. A state reconstructed from only a
terminal key and hash transcript MUST NOT export or admit production keys,
because it has not verified historical pairing relations.

## 4. Native public transcript

The native transcript is a closed JSON object. Unknown fields MUST be rejected;
the closed shape prevents an apparently public wrapper from smuggling secret
material. All hashes are lowercase, 64-character SHA-256 hex strings.

| Field | Type | Requirement |
| --- | --- | --- |
| `schema_version` | integer | exactly `1` |
| `protocol` | string | exactly `arkworks-groth16-bn254-delta-mpc-v1` |
| `curve` | string | exactly `BN254` |
| `circuit` | object | immutable circuit binding defined below |
| `genesis_proving_key_hash_hex` | SHA-256 | canonical uncompressed genesis PK |
| `transcript_hash_hex` | SHA-256 | final contribution hash |
| `final_proving_key_hash_hex` | SHA-256 | canonical uncompressed terminal PK |
| `final_verifying_key_hash_hex` | SHA-256 | canonical uncompressed VK embedded in the terminal PK |
| `contributions` | array | non-empty, ordered contribution evidence |

The circuit object contains exactly:

| Field | Type | Profile F v3 value |
| --- | --- | --- |
| `circuit_id` | string | `groth16-bn254-event-dag-v3` |
| `circuit_version` | integer | `3` |
| `circuit_digest_hex` | SHA-256 | `5d0ea5923dc03bc28493264f4a4cb1cbefa0f3d66203b3e2bbebacf6f6840d58` |

The digest fingerprints the exact post-optimization Arkworks R1CS matrices,
not a source label or example witness. Its domain is
`arkworks-r1cs-matrices-bn254-v1\0`; the encoded dimensions, non-zero counts,
A/B/C row boundaries, variable indices, and canonical compressed BN254 scalar
coefficients are hashed in order. A circuit, constraint optimization, or
encoding change requires a new circuit version and digest.

Each contribution contains exactly:

| Field | Type | Meaning |
| --- | --- | --- |
| `sequence` | integer | one-based position |
| `participant_did` | string | unique DID matching `did:<lowercase-method>:<identifier>`, 5–128 ASCII characters from `[A-Za-z0-9._:-]` |
| `previous_transcript_hash_hex` | SHA-256 | genesis hash or preceding contribution hash |
| `previous_proving_key_hash_hex` | SHA-256 | hash of the key being transformed |
| `transformed_proving_key_hash_hex` | SHA-256 | hash of this contribution's output key |
| `public_entropy_g1_hex` | 32-byte hex | canonical compressed `S1` |
| `public_entropy_g2_hex` | 64-byte hex | canonical compressed `S2` |
| `pok_commitment_g1_hex` | 32-byte hex | canonical compressed `R` |
| `pok_response_hex` | 32-byte hex | canonical scalar `z` |
| `contribution_hash_hex` | SHA-256 | evidence hash and next transcript head |

A DID is bound into the transcript but does not, by itself, authenticate its
controller. Cross-organizational deployments SHOULD additionally authenticate
the DID using the signed portable attestation described in Section 7.

## 5. Deterministic hash construction

Integers are unsigned big-endian. `u32be` and `u64be` denote fixed widths.
`LP(x)` is `u64be(byte_length(x)) || x`. Hex fields are decoded before hashing.
Strings are UTF-8. Concatenations below are unambiguous and MUST NOT be
replaced with JSON serialization.

The genesis transcript head is:

```text
SHA-256(
  "groth16-mpc-genesis-v1\0" ||
  LP(protocol) || LP(circuit_id) || u32be(circuit_version) ||
  circuit_digest || genesis_proving_key_hash
)
```

The Fiat-Shamir challenge is the BN254 scalar reduction of:

```text
SHA-256(
  "groth16-mpc-schnorr-pok-v1\0" ||
  LP(circuit_id) || u32be(circuit_version) || circuit_digest ||
  u64be(sequence) || LP(participant_did) ||
  previous_transcript_hash || previous_proving_key_hash ||
  transformed_proving_key_hash ||
  LP(public_entropy_g1) || LP(public_entropy_g2) || LP(pok_commitment_g1)
)
```

The digest is interpreted by `Fr::from_be_bytes_mod_order`; a zero result is
mapped to scalar one.

The contribution hash is:

```text
SHA-256(
  "groth16-mpc-contribution-v1\0" ||
  LP(protocol) || LP(circuit_id) || u32be(circuit_version) || circuit_digest ||
  u64be(sequence) || LP(participant_did) ||
  previous_transcript_hash || previous_proving_key_hash ||
  transformed_proving_key_hash ||
  LP(public_entropy_g1) || LP(public_entropy_g2) ||
  LP(pok_commitment_g1) || LP(pok_response)
)
```

The deterministic hashes make public evidence reproducible across Rust and
Python. Reproducibility applies to evidence for an already-produced
contribution; production entropy MUST remain unpredictable and the transformed
key is not expected to repeat.

## 6. Ceremony lifecycle and artifacts

### 6.1 Genesis

The coordinator publishes the circuit binding and genesis PK hash. An operator
MUST approve the genesis hash out of band. For Profile F v3 the implementation
MUST synthesize the fixed circuit, check key query dimensions, and successfully
prove and verify a fixed compatibility statement before labeling the key as a
Profile F genesis.

### 6.2 Contribution

Each participant MUST obtain the current key, transcript, approved genesis,
and all earlier transformed keys. The participant independently replays the
existing ceremony before contributing. It then uses a local OS RNG, emits the
after key and public evidence atomically, verifies its own result through the
same verifier, and erases `s`, `s^-1`, and `r`.

The reference CLI intentionally has no seed or entropy argument:

```text
groth16 mpc-contribute \
  --current-key CURRENT_PK \
  [--transcript TRANSCRIPT --genesis-key GENESIS_PK \
   --prior-key PK_1 ... --prior-key PK_N] \
  --participant-did DID \
  --out-key NEXT_PK \
  --transcript-out NEXT_TRANSCRIPT \
  --evidence-out EVIDENCE
```

### 6.3 Audit and finalization

Auditors retain an ordered local bundle containing the genesis key and exactly
one transformed key per contribution. An individual check uses a zero-based
transcript index:

```text
groth16 mpc-verify-contribution \
  --transcript TRANSCRIPT --before-key BEFORE_PK --after-key AFTER_PK \
  --index INDEX --json --quiet
```

Finalization MUST replay from genesis and MUST require at least two distinct
participant DIDs. It exports only after the replayed transcript exactly equals
the supplied transcript:

```text
groth16 mpc-finalize \
  --transcript TRANSCRIPT --genesis-key GENESIS_PK \
  --transformed-key PK_1 ... --transformed-key PK_N --out-dir OUTPUT
```

The export consists of:

- `proving_key.bin`: Arkworks canonical uncompressed `ProvingKey<Bn254>`;
- `verifying_key.bin`: Arkworks canonical uncompressed `VerifyingKey<Bn254>`
  embedded in that proving key;
- `mpc_transcript.json`: the replayed public transcript; and
- a JSON export manifest containing the protocol and circuit binding,
  genesis/transcript hashes, contribution count, paths, and SHA-256 values of
  all three files.

Writes MUST be atomic. The final PK and VK hashes MUST match both the transcript
and the actual consumer files. A separately supplied VK with a self-consistent
top-level hash MUST be rejected unless it is the VK embedded in the replayed
terminal PK.

## 7. Portable MCP++ manifest

The portable schema `mcp++/groth16-mpc-ceremony@1` is a transport-safe metadata
envelope. It is useful for discovery, archival, DID attestations, and
content-addressed references. It is not cryptographic proof of an Arkworks
transform.

It contains:

- `schema: "mcp++/groth16-mpc-ceremony@1"`;
- `profile`: `{ "capability": "mcp++/event-dag", "name": "Profile F: Event DAG Provenance, Archival, and Compaction" }`;
- non-empty `ceremonyId` and the versioned `circuitId`;
- `curve: "bn128"` and `keyFormat: "arkworks-canonical"` for this protocol;
- `circuitR1cs`, `phase1Powers`, and `initialZkey` artifact descriptors;
- `minimumIndependentContributors`, which MUST be at least two;
- ordered contributions containing `sequence`, `participantDid`, input/output
  hashes, a signed `attestation` (`algorithm`, `signature`, `signedAt`, and
  `statementCid`), `transcriptVerifier`, and
  `transcriptVerifiedAt`; and
- for `status: "complete"`, `finalZkey`, `provingKey`, `verificationKey`, and
  `finalizedAt`.

An artifact descriptor contains exactly a lowercase SHA-256, a matching
`sha256:<hex>` portable CID, and a positive `sizeBytes`. In an Arkworks
manifest, `finalZkey.sha256` MUST equal `provingKey.sha256` and the terminal
native PK hash. Every contribution MUST declare
`transcriptVerifier: "arkworks-mpc-verifier"` and match the native sequence,
DID, before-key hash, and after-key hash. The initial and final artifact hashes,
native contribution count, circuit identity, and native terminal VK hash MUST
all match.

The portable manifest CID is `sha256:` followed by SHA-256 of recursively
key-sorted JSON encoded as UTF-8 with comma/colon separators, no insignificant
whitespace, and non-ASCII characters represented by JSON Unicode escapes.
JSON keys MUST be strings; floats, NaN, infinity, byte strings, and non-JSON
values are not canonical.

The labels `transcriptVerifier` and `transcriptVerifiedAt` are assertions. A
production admission gate MUST invoke the native verifier against local key
artifacts; it MUST NOT trust those labels or an attestation as a substitute.

## 8. Profile F admission and certificate binding

Strict production mode is selected by
`IPFS_DATASETS_REQUIRE_MPC_CEREMONY` or `GROTH16_REQUIRE_MPC`. Implementations
MUST parse these flags identically and MUST fail closed on invalid or
conflicting values. In strict mode:

- single-process `setup`, including deterministic setup, MUST be disabled;
- only circuit version 3 is permitted;
- the approved genesis hash MUST match both the configured local genesis file
  and `genesis_proving_key_hash_hex`;
- the local audit bundle MUST contain exactly one ordered transformed key per
  contribution;
- every transform MUST be independently replayed;
- at least two unique participant DIDs MUST be present; and
- the local final PK and VK MUST match the transcript and the Profile F v3
  circuit compatibility checks.

`availability()` MUST report production eligibility only after that admission.
Generic Groth16 development operations MAY remain available when strict mode
is off, but the transport-facing Profile F provider MUST NOT issue or accept a
Profile F compaction certificate unless `production_eligible` is true. It MUST
fall back to the non-zero-knowledge hash commitment, or fail if the caller
requires ZK, when an MPC setup has not been admitted.

A Profile F compaction certificate binds the admitted setup using:

- `circuit_id: "groth16-bn254-event-dag-v3"`;
- `circuit_version: 3`;
- `ruleset_id: "MCP++_EventDAG_Compaction_v1"`;
- the fixed `circuit_digest_hex`;
- `verification_key_sha256` and the CIDv1/raw/sha2-256
  `verification_key_cid`; and
- `ceremony_transcript_hash`, equal to the accepted final transcript head.

The verifier independently binds the proof public inputs to the Event-DAG
Merkle root and event count. It MUST reject a certificate if the local admitted
VK hash/CID, circuit identity/digest, or transcript head is absent or stale.
A proof that is otherwise valid under a different key or ceremony is not a
valid Profile F certificate.

## 9. Transport and toxic-waste prohibition

Contribution entropy is participant-held state, not protocol payload. The
following values MUST NOT appear in MCP messages, MCP+p2p streams, HTTP bodies,
URLs, headers, command-line arguments, standard input, environment variables,
logs, manifests, transcripts, attestations, or error text:

- entropy, seed, randomness, or RNG state;
- `s`, `s^-1`, raw delta/trapdoor, or contribution scalars;
- Schnorr nonce `r`;
- private keys or credentials; and
- witness data.

Public transcript evidence (`S1`, `S2`, `R`, and `z`) is not toxic waste. It is
safe only as the closed schema defined above. Serialized PKs are public audit
artifacts but MUST NOT be embedded in the JSON transcript or portable manifest;
the public objects carry their hashes. Local verifier paths and audit-bundle
configuration are operational state and MUST NOT be projected into public
ceremony objects.

The native transcript and its genesis/intermediate key bundle are local audit
inputs. They MUST NOT be accepted by a ceremony contribution method or sent as
MCP, HTTP, or MCP+p2p ceremony payloads. The portable manifest is the only
ceremony object defined for those transports.

The read-only JSON-RPC method `mcp++/zk/ceremony/validate`, where implemented,
accepts only `{ "manifest": <portable public manifest> }` and returns structural
status, reasons, contributor DIDs, and the deterministic manifest CID. It MAY
be carried over HTTP or MCP+p2p after normal capability negotiation because it
does not perform a contribution or accept entropy. Remote peers are validators
and archive providers, never entropy custodians. This specification does not
assert that a handler is deployed. An implementation MUST NOT advertise the
method on a transport until that transport's dispatcher binds it and enforces
the portable-only input contract.

A public transport adapter MUST recursively reject forbidden secret-bearing
field names, opaque byte strings, unknown wrapper fields, and aliases such as
`entropyHex`, `randomness`, `seed`, `nonce`, `toxicWaste`, `deltaScalar`,
`provingKeyBytes`, or `witness`. It MUST fail rather than silently redact: once
a secret reached a boundary, redaction is too late. A local verifier subprocess
SHOULD receive a minimal environment containing only public runtime settings
such as library paths and MUST receive no ceremony secrets.

## 10. Required rejection behavior

Validation and admission are fail closed. The implementation MUST reject:

- malformed JSON, unknown fields, non-canonical hex/point/scalar/key encodings,
  invalid subgroup points, trailing key bytes, or invalid DIDs;
- a missing, empty, identity-delta, wrong-shape, or wrong-circuit key;
- sequence gaps, reordered contributions, a broken transcript link, or a
  transcript whose final head is not the last contribution hash;
- a stale before-key hash, output-key hash mismatch, final PK mismatch, final
  VK mismatch, or a terminal VK not embedded in the replayed terminal PK;
- a repeated participant DID, even when the repeated contribution is otherwise
  valid;
- zero/one contribution entropy, identity public entropy, a zero Schnorr nonce,
  or an output key identical to its input;
- a failed Schnorr equation, G1/G2 discrete-log mismatch, delta mismatch,
  H/L inverse-scaling mismatch, changed non-delta parameter, or changed query
  length;
- a verifier callback that is absent, returns false, throws, reports the wrong
  contribution hash, or does not bind the terminal embedded VK;
- fewer than two independent participants for production admission;
- an unapproved genesis or a resume/export attempt without full replay;
- a circuit ID, version, R1CS digest, ruleset, transcript head, key SHA-256, or
  key CID that differs from the locally admitted Profile F state; and
- any secret-bearing field at an MCP, HTTP, or MCP+p2p boundary.

A one-contribution prefix MAY be reported as structurally and
cryptographically valid for audit, but it MUST have
`production_eligible: false`. A portable `collecting` manifest is likewise not
production eligible.

## 11. Threat model and security considerations

The protocol assumes collision resistance of SHA-256, standard BN254 pairing
and discrete-log hardness, sound canonical Arkworks deserialization, a secure
operating-system RNG, and secure deletion to the extent supported by the
participant host.

The protocol detects a malicious or faulty participant that publishes an
invalid transform, and a coordinator or storage peer that tampers with,
deletes, duplicates, substitutes, or reorders public evidence. Full replay
prevents a coordinator from presenting a plausible hash chain in place of
cryptographic transforms. Circuit and terminal-key binding prevents a valid
ceremony for another circuit or an old key from authorizing Profile F v3.

The protocol does not:

- prove that a DID belongs to a real-world independent person or organization;
- make two DIDs controlled by one adversary independent;
- repair a compromised phase-1/genesis assumption outside this delta phase;
- protect entropy on an already-compromised contributor machine;
- force a participant to erase its scalar;
- provide availability against participants or coordinators that withhold
  intermediate keys; or
- turn portable metadata validation into a cryptographic replay.

Operators SHOULD choose contributors with independent administration and
hardware, authenticate their portable attestations, publish all public
intermediate artifacts for multiple auditors, pin the approved genesis and
final transcript hashes through separate channels, and require at least one
auditor that did not participate in generation.
## 12. Conformance fixture

The portable-manifest conformance fixture is
[`profile_f_groth16_mpc_ceremony.json`](../../tests-py/fixtures/valid/profile_f_groth16_mpc_ceremony.json).
SwissKnife and `ipfs_datasets_py` validators MUST accept it and MUST reject
broken-chain and mismatched-CID mutations. Native Arkworks ceremony admission
still requires the full replay and key-artifact checks defined above.
