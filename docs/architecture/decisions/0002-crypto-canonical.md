# ADR-0002: Mandatory crypto suite and mcpp-jcs-v1 canonicalization

- **Status:** Accepted
- **Date:** 2026-08-15
- **Last verified:** 2026-08-15
- **Deciders:** MCP++ 1.0 gap-closure program (MCPP-G020); sealed plan Key Decisions KD-4 and KD-5
- **Scope:** The mandatory cryptographic and content-addressing suite for MCP++ 1.0 normative artifacts, delegation proofs, receipts, and cross-language conformance: signature algorithm, key identifiers, DID-compatible identities, signature input construction, CID multicodec defaults, named canonicalization algorithm `mcpp-jcs-v1`, and the rule that historical algorithms stay readable.
- **Non-goals:** Full UCAN attenuation/revocation semantics (later crypto tasks); Profile H payment non-authorization policy (KD-14 / Profile H ADR scope); confidential ciphertext envelopes (KD-15); CRDT/consensus backends; which runtime package hosts adapters (ADR-0001 / MCPP-013); conformance-level ladder definitions (ADR-0003 / MCPP-015); complete RFC 8785 edge-case catalog and golden vectors (MCPP-024…029 implement the named algorithm).
- **Supersedes:** none
- **Superseded-by:** none
- **Related guides:**
  - Sealed plan: `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` (§4 rules 6–7; §5 KD-4, KD-5)
  - Traceability matrix: `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` (REQ-CAN-01…03, REQ-CRY-01…04)
  - Profile B: `ipfs_accelerate_py/mcplusplus/docs/spec/cid-native-artifacts.md`
  - Profile C: `ipfs_accelerate_py/mcplusplus/docs/spec/ucan-delegation.md`
  - Future normative detail: `ipfs_accelerate_py/mcplusplus/docs/spec/canonicalization-mcpp-jcs-v1.md` (MCPP-024)
- **Source anchors:**
  - `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` — KD-4, KD-5
  - `ipfs_accelerate_py/mcplusplus/docs/spec/cid-native-artifacts.md` — CIDv1 preferred form
  - `ipfs_kit_py/ipfs_kit_py/mcp_server/mcplusplus/ucan.py` — EdDSA / Ed25519, explicit `kid`, DID-shaped `iss`/`aud`
  - `ipfs_kit_py/tests/runtime_readiness/mcplusplus/test_ucan_verifier.py` — fail-closed signature negatives
  - Profile G/H codecs under `ipfs_accelerate_py/mcplusplus/tests-{py,ts,go,rs}/` — local CIDv1 + sha2-256 helpers (pre-JCS naming)
  - Four-language Profile C validators (structural only today) under `ipfs_accelerate_py/mcplusplus/tests-*/**/ucan*`

## Status meanings (do not invent new values)

| Value | Use when |
| --- | --- |
| Proposed | Decision is under review; **not** yet evidenced current design |
| Accepted | Decision is normative for Scope (sealed defaults refined with tree evidence) |
| Deprecated | Still historical; prefer another practice for new work |
| Superseded | Replaced by the ADR in Superseded-by |
| Rejected | Considered and not adopted; retained to document the negative choice |

Only **Accepted** records are current design authority. **Proposed** records
must not be treated as implemented system law.

This ADR is **Accepted** as the binding suite for MCP++ 1.0 design and
implementation tasks. It does **not** claim that every language validator
already performs cryptographic verification; forest-wide enforcement remains
a later-wave obligation (MCPP-041…045). Structural-only green tests do not
satisfy the suite’s security claims.

## Context

MCP++ content-addresses intents, decisions, receipts, proofs, and events, and
binds multi-hop authority with UCAN-style delegation. Cross-language
conformance (Python, TypeScript, Go, Rust) and multi-runtime adapters
(accelerate, datasets, kit, SwissKnife) only interoperate if:

1. **Signatures verify the same message bytes** on every peer.
2. **CIDs of the same logical object match** (or declare a different, versioned algorithm explicitly).
3. **Identity and key material are unambiguous** across issuers, audiences, and key rotation.

Current-tree forces:

| Force | Evidence |
| --- | --- |
| Draft specs require deterministic canonicalization before CID computation, but do not name a single algorithm id | `cid-native-artifacts.md` §2; archive phrasing “Canonical JSON / CBOR” |
| Profile G/H codecs already hash local canonical JSON to CIDv1 sha2-256, with profile-local multicodec choices | `profile_g` / `profile_h` multi-language codecs |
| Kit `UCANVerifier` already issues and verifies Ed25519 (EdDSA) tokens with explicit `kid` and DID-shaped issuers/audiences | `ucan.py`, `test_ucan_verifier.py` |
| Four-language Mcp-Plus-Plus Profile C validators remain structural-only (field shape, not crypto) | inventory §4; REQ-CRY-01 status `partial` |
| Silent re-canonicalization would rewrite historical artifact CIDs and break provenance DAGs | plan §4 rules 6–7; REQ-CAN-03 |

If this decision is deferred, parallel lanes invent incompatible suites
(different signature curves, implicit “first key”, ad-hoc key sorting, mixed
CIDv0, silent JCS upgrades). Cross-language gate 24 and cryptographic gates
13–15 cannot close.

Who is affected: Mcp-Plus-Plus conformance authors, runtime adapter owners,
operators verifying evidence bundles, and any peer that must fail closed on
forged or algorithm-downgraded material.

## Decision

**MCP++ 1.0 uses one mandatory cryptographic and content-addressing suite for
new normative work.** Historical artifacts remain readable under the algorithm
recorded at mint time. Implementations MUST fail closed when required suite
fields are missing, algorithms are downgraded, or signatures do not verify
over the declared canonical bytes.

### 1. Signature algorithm: Ed25519 (EdDSA)

| Rule | Normative statement |
| --- | --- |
| Curve / scheme | **Ed25519** pure EdDSA (RFC 8032). Wire algorithm name for UCAN-style headers is **`EdDSA`** when a JOSE/UCAN header is used. |
| Signature encoding | 64-byte Ed25519 signature; transport encoding is base64url (no padding) unless a profile’s declared wire form specifies otherwise. |
| Forbidden for new normative tokens | `alg: none`, HMAC-as-delegation, RSA/ECDSA suites as the default MCP++ suite, and any path that accepts unsigned material when a signature is required. |
| Optional algorithms | MAY be specified later under a **new named algorithm identifier** and ADR; they MUST NOT silently replace Ed25519 for existing profile versions. |

Rationale alignment: kit `UCANVerifier` already requires `alg == "EdDSA"` and
verifies with `Ed25519PublicKey`; Profile H artifact schemas already pin
`signatureAlg: Ed25519` for signed commerce objects.

### 2. Explicit key identifiers

| Rule | Normative statement |
| --- | --- |
| Key id required | Every signature verification path MUST carry an **explicit key id** (`kid` in UCAN/JOSE headers, or the profile’s declared equivalent field). |
| Resolution | Public keys are resolved by `(issuer, kid)` (or equivalent ledger lookup), never by “the only key on file” or peer transport identity. |
| Rotation | Multiple concurrent `kid` values for one issuer are allowed; verifiers MUST NOT assume a single global key per DID. |
| Downgrade | Omitting `kid`, or accepting a token whose header set differs from the profile’s fixed required set in a way that drops `kid`, is a fail-closed error. |

### 3. DID-compatible identities

| Rule | Normative statement |
| --- | --- |
| Issuers and audiences | Delegation and receipt **issuer** and **audience** fields MUST be **DID-compatible strings** (e.g. `did:key:…`, `did:web:…`, or other DID method URIs accepted by the profile). |
| Transport ≠ authority | libp2p PeerID, TLS client certificate identity, registry membership, and payment settlement **never** substitute for a DID-compatible issuer/audience on a verified proof (KD-14; restated here for suite completeness). |
| Wire aliases | Full-name records (`issuer` / `audience`) and UCAN shorthand (`iss` / `aud`) are both acceptable shapes when a profile declares both; identity semantics are the same. |

### 4. Signatures over canonical bytes

| Rule | Normative statement |
| --- | --- |
| Message construction | A signature MUST cover **canonical bytes** of the signed payload (or the profile’s declared signing input built from those bytes—for example UCAN `base64url(header).base64url(payload)` where header and payload were each JCS-canonicalized before encoding). |
| Forbidden | Signing pretty-printed JSON, language-local `json.dumps` without a named algorithm, non-deterministic map iteration, or floating “display form” text. |
| Verify equals mint | Verifiers reconstruct the **same** canonical signing input; any encoding drift is a hard failure. |
| Detached signatures | When a profile stores a signature beside a CID’d object, the signature still binds the **canonical bytes** (or the content digest of those bytes) of the object, not a peer-local re-serialization. |

### 5. Content identifiers: CIDv1, raw, sha2-256 (default)

| Rule | Normative statement |
| --- | --- |
| Version | **CIDv1** is required for new normative MCP++ artifacts. |
| Multicodec (default) | **`raw` (0x55)** over the canonical payload bytes unless a profile **explicitly** declares another multicodec for that artifact family. |
| Multihash (default) | **`sha2-256` (0x12)** with 32-byte digest. |
| Multibase (preferred string form) | Lowercase base32 (`b` prefix), matching Kubo `ipfs add --cid-version=1 --raw-leaves` for the same bytes when the codec is `raw` + `sha2-256`. |
| Legacy readability | **CIDv0** (`Qm…`) and non-default multicodecs (for example historical profile codecs that used other DAG codecs) remain **readable** when already recorded on existing artifacts; new mint paths MUST NOT silently rewrite them. |
| Exception clause (KD-4) | “Unless an existing artifact already uses another **declared** multicodec” — declaration is mandatory; undeclared codec drift is forbidden. |

Note: some current Profile G/H helpers emit CIDv1 with profile-local codecs
during the structural era. MCPP-024…031 must publish the named algorithm and
adapters so new portable envelopes use the defaults above without breaking
recorded historical CIDs.

### 6. Canonicalization identifier: `mcpp-jcs-v1` = RFC 8785 JCS

| Rule | Normative statement |
| --- | --- |
| Name | The MCP++ 1.0 canonicalization algorithm identifier is **`mcpp-jcs-v1`**. |
| Definition | **`mcpp-jcs-v1` is RFC 8785 JSON Canonicalization Scheme (JCS)** applied to the JSON data model of the artifact. |
| Output | UTF-8 encoding of the JCS result is the **canonical byte sequence** used for hashing, CID computation, and signature input construction (unless a profile builds a multi-segment signing string from already-JCS pieces, as in UCAN header/payload). |
| Versioning | Future JCS profile changes, CBOR alternatives, or encoding fixes require a **new algorithm id** (for example `mcpp-jcs-v2`) and a migration path. The string `mcpp-jcs-v1` MUST NOT be reused for incompatible behavior. |
| Publication | Normative prose and schema land in MCPP-024 (`canonicalization-mcpp-jcs-v1.md` + schema); golden vectors in MCPP-025; four-language implementations in MCPP-026…027. This ADR **names and freezes** the choice so those tasks do not reopen the algorithm. |

### 7. Historical algorithms remain readable

| Rule | Normative statement |
| --- | --- |
| No silent CID change | Implementations MUST NOT re-encode existing artifacts under `mcpp-jcs-v1` (or any new suite) in a way that **changes** a stored CID without an explicit migration record. |
| Read path | Readers MUST accept artifacts that declare (or are known by fixture/profile era to use) a **historical** canonicalization or multicodec, and verify against **that** algorithm. |
| Write path | New normative MCP++ 1.0 artifacts, vectors, and envelopes MUST mint under **this ADR’s suite** and label algorithm fields accordingly (`mcpp-jcs-v1`, Ed25519/EdDSA, explicit `kid`, DID-compatible iss/aud, CIDv1 defaults). |
| Dual-stack | A peer MAY speak both historical and `mcpp-jcs-v1` paths; promotion is adapter-mediated (MCPP-031), never silent rewrite. |

### 8. Normative checklist (CryptoSuiteDecision@1)

An implementation claims the mandatory suite only when all of the following hold
for its **new** normative paths:

1. Ed25519 signatures (EdDSA where headers apply).
2. Explicit key ids on signed material.
3. DID-compatible issuer and audience (or equivalent identity fields).
4. Signature verification over `mcpp-jcs-v1` canonical bytes (or declared composition thereof).
5. Default CIDv1 with `raw` + `sha2-256` for new portable content-addressed payloads.
6. Algorithm id `mcpp-jcs-v1` published and used for new canonical digests.
7. Historical algorithm/CID pairs remain readable without silent mutation.

## Alternatives

### Alternative A: Leave canonicalization unnamed; keep per-profile hand codecs

- **Summary:** Continue Profile G/H local “sort keys + JSON.stringify” helpers without a shared algorithm id.
- **Expected benefits:** No migration work; existing vectors keep working unchanged.
- **Why not chosen:** Cross-language identity (gate 24) is not guaranteed; agents invent divergent codecs; REQ-CAN-01 stays `missing`; silent drift rewrites CIDs when someone “fixes” Unicode or number handling.

### Alternative B: DAG-CBOR as the sole canonical form

- **Summary:** Require DAG-CBOR for all signed and CID’d objects; drop JSON JCS.
- **Expected benefits:** Binary determinism; good IPFS ecosystem fit for some DAG types.
- **Why not chosen:** Existing draft artifacts, Profile H x402 headers, and multi-language validators are JSON-first; forcing CBOR rewrites historical CIDs and raises four-language cost. CBOR remains available as a **declared** multicodec for specific artifact families, not the mandatory default for the portable suite.

### Alternative C: Multiple signature algorithms (RSA/ECDSA/Ed25519) as first-class equals

- **Summary:** Accept any common WebCrypto suite; negotiate per peer.
- **Expected benefits:** Broader HSM / enterprise key support.
- **Why not chosen:** Explodes negative-test matrix; weakens fail-closed defaults; kit and Profile H already center Ed25519. Additional algorithms require a later ADR and named identifiers, not silent multi-alg acceptance.

### Alternative D: Implicit keys from DID documents without `kid`

- **Summary:** Resolve “the” verification method from a DID document alone.
- **Expected benefits:** Shorter tokens.
- **Why not chosen:** Rotation and multi-key DIDs become ambiguous; kit already requires explicit `kid`; fail-closed verification needs a stable key handle independent of remote document fetch races.

### Alternative E: Do nothing / status quo

- **Summary:** Defer suite choice until crypto tasks land.
- **Why not chosen:** Wave 3 ADRs exist specifically so Waves 4–5 do not invent incompatible suites (MCPP-G020). Plan KD-4/KD-5 already decide; this ADR records them with evidence and consequences.

## Consequences

### Positive

- Parallel lanes share one suite: Ed25519, explicit `kid`, DID-compatible identities, signatures over `mcpp-jcs-v1` bytes, CIDv1 `raw`+`sha2-256`.
- Named algorithm `mcpp-jcs-v1` enables versioned migration without silent CID breakage.
- Aligns with existing kit UCAN verifier and CID-native draft direction.
- Clear fail-closed rules for `alg: none`, missing `kid`, and transport-as-authority mistakes.
- Gives MCPP-024…029 and MCPP-041…045 an unambiguous implementation target.

### Negative

- Implementations that used ad-hoc JSON dumps must migrate mint paths to JCS and re-pin golden vectors (cost in MCPP-025…028).
- Profile codecs that chose non-`raw` multicodecs need explicit declaration and adapters (MCPP-031) rather than silent unification.
- Four-language structural validators must grow real crypto verify paths; temporary dual-stack complexity increases until historical eras age out.
- Operators must store and publish key ids and algorithm metadata with artifacts; “just the DID” is insufficient.

### Neutral / residual risks

- RFC 8785 edge cases (numbers, Unicode, null, duplicate keys) need golden negatives (MCPP-025); this ADR does not replace that suite.
- DID method resolution policy (offline `did:key` vs network `did:web`) is profile-specific; suite only requires DID-compatible string form and explicit `kid`.
- Real cryptographic enforcement forest-wide remains `partial` until MCPP-041…045 close; structural green is not suite compliance.
- Optional stronger multicodecs (e.g. dag-cbor for large binaries) may be added later only as **declared** exceptions, not default rewrites.

## Evidence

| Claim in Decision | Evidence (path, test, or operational check) | Notes |
| --- | --- | --- |
| Ed25519 / EdDSA is the tree-aligned suite | `ipfs_kit_py/ipfs_kit_py/mcp_server/mcplusplus/ucan.py` (`alg: EdDSA`, Ed25519 verify); Profile H `signatureAlg: Ed25519` | Forest-wide Mcp-Plus-Plus validators still structural-only for C |
| Explicit key ids | `ucan.py` header requires `kid`; `test_ucan_verifier.py` uses `kid="root-v1"` | Normative for new tokens |
| DID-compatible iss/aud | Fixtures and kit tests use `did:key:…`; `ucan-delegation.md` issuer/audience fields | Transport identity remains non-authorizing (KD-14) |
| Sign over canonical bytes | `issue_ucan` signs base64url of `_canonical_json` header/payload; plan KD-4 | JCS naming arrives with MCPP-024 |
| CIDv1 + sha2-256 direction | `cid-native-artifacts.md` §2.1; profile G/H CIDv1 helpers | Default multicodec `raw` (0x55) per KD-4; declare exceptions |
| `mcpp-jcs-v1` = RFC 8785 JCS | Plan KD-5; REQ-CAN-01 | Spec file + schema = MCPP-024 |
| Historical algorithms stay readable | Plan §4 rules 6–7; REQ-CAN-03 | No silent CID rewrite |

Evidence classes used: sealed plan key decisions (design authority for this
wave), source layout and runtime verifiers (tree reality), traceability matrix
(gap status). Full cryptographic conformance is **not** claimed complete.

## Verification

How a future reader confirms this ADR still holds:

1. **Document presence (this task):**
   ```text
   test -s ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0002-crypto-canonical.md
   ```
2. **Named algorithm still equals JCS:** inspect this ADR §6 and, once landed,
   `ipfs_accelerate_py/mcplusplus/docs/spec/canonicalization-mcpp-jcs-v1.md`
   for identifier `mcpp-jcs-v1` and RFC 8785 reference.
3. **Ed25519 + kid fail-closed:**  
   `cd ipfs_kit_py && python -m pytest -q tests/runtime_readiness/mcplusplus/test_ucan_verifier.py`
4. **Cross-language canonical identity (later waves):** golden vectors under
   `ipfs_accelerate_py/mcplusplus/conformance/vectors/mcpp-jcs-v1` and
   four-language JCS tests (MCPP-025…028).
5. **Staleness signals:** a new default curve without a superseding ADR; reuse
   of the string `mcpp-jcs-v1` for non-JCS bytes; mint paths that change
   historical CIDs without adapters; acceptance of `alg: none` or missing
   `kid` on required signatures.

## Review triggers

- [ ] Source anchors no longer match the Decision statement
- [ ] A recorded negative consequence becomes unacceptable
- [ ] A rejected alternative (e.g. DAG-CBOR default, multi-alg suite) becomes viable without those costs
- [ ] Security or trust-boundary changes touch identity, signatures, or CID defaults
- [ ] RFC 8785 errata or a deliberate encoding fix requires `mcpp-jcs-v2`
- [ ] Superseding design is Accepted under a new ADR number

When superseding: create a new ADR number; set this file to **Superseded** with
`Superseded-by`; set the successor’s `Supersedes`; do not delete this file.

## Notes (optional)

### Downstream task map

| Concern | Follow-on |
| --- | --- |
| Full JCS normative text + schema | MCPP-024 |
| Golden vectors (bytes, SHA-256, CID, sig input) | MCPP-025 |
| Python/TS/Go/Rust `mcpp-jcs-v1` | MCPP-026, MCPP-027 |
| Shared identity tests | MCPP-028 |
| Real Ed25519 delegation verify over canonical bytes | MCPP-041 |
| Receipt signing / cross-domain verify | MCPP-045 |
| Historical B/G CID adapters | MCPP-031 |

### Interface label

Task interface id: **`CryptoSuiteDecision@1`** — the normative checklist in
Decision §8.

### Sealed defaults preserved

This ADR records plan KD-4 and KD-5 without reopening them. Refinements
(explicit `kid` resolution model, default multicodec wording, historical-read
rules) stay inside those defaults and cite current-tree evidence.
