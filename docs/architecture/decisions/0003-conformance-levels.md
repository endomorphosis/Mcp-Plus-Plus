# ADR-0003: Conformance levels and fail-closed promotion

- **Status:** Accepted
- **Date:** 2026-08-15
- **Last verified:** 2026-08-15
- **Deciders:** MCP++ 1.0 gap-closure program (MCPP-G020); sealed plan Key Decision KD-6
- **Scope:** The mandatory ordered ladder of MCP++ 1.0 conformance levels; the rule that each level is distinct and independently evidenced; the rule that schema or codec acceptance is never “implemented”; and the promotion rule that a claim may rise to a level only when tests at that level pass (positive and negative).
- **Non-goals:** Which package owns schemas vs adapters (ADR-0001 / MCPP-013); mandatory crypto suite and `mcpp-jcs-v1` naming (ADR-0002 / MCPP-014); state modes and CRDT backend (ADR-0004 / MCPP-016); DurableExecutor choice (ADR-0005 / MCPP-017); A2A extension URI and dual MCP bindings (ADR-0006 / MCPP-018); concrete golden vectors, verifiers, policy engines, receipt signers, or proof verifiers (later waves implement evidence under these levels).
- **Supersedes:** none
- **Superseded-by:** none
- **Related guides:**
  - Sealed plan: `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` (§4 rule on structural vs crypto; §5 KD-6; §11 non-claims; §12 deliverables)
  - Traceability matrix: `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` (§0.1–0.2 status vocabulary and ladder)
  - Profile inventory: `docs/reports/mcplusplus-1.0-gap-closure/baseline/profiles-a-h-inventory.md`
  - Official MCP / A2A note: `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md`
  - Crypto suite (what “cryptographic” must verify): `ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0002-crypto-canonical.md`
- **Source anchors:**
  - `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` — KD-6; Profile C/D structural-only observation; §11–12
  - `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` — §0.1 fail-closed promotion; §0.2 level ladder; matrix rows scored by claimed level
  - Four-language structural validators under `ipfs_accelerate_py/mcplusplus/tests-{py,ts,go,rs}/`
  - Shared vectors under `ipfs_accelerate_py/mcplusplus/conformance/vectors/`
  - Kit real UCAN verifier (local cryptographic evidence): `ipfs_kit_py/ipfs_kit_py/mcp_server/mcplusplus/ucan.py`

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

This ADR is **Accepted** as the binding conformance-level vocabulary and
promotion policy for MCP++ 1.0 design, matrix scoring, and implementation
tasks. It does **not** claim that forest-wide cryptographic, policy, receipt,
or proof suites already pass; those remain later-wave obligations. A green
structural suite is **not** suite compliance at any higher level.

## Context

MCP++ spans Profiles A–H, four conformance languages, and multiple runtime
adapters (accelerate, datasets, kit, SwissKnife). Without distinct
conformance levels:

1. **Schema or field-presence green becomes “implemented”**, overstating
   security and interop (Profile C signature strings accepted without verify;
   Profile D policy fields accepted without deontic evaluation).
2. **Line-coverage trophies and “validation complete / 100%” docs** are cited
   as production evidence (inventory §10; plan §11).
3. **Runtime-local PASS matrices** are treated as four-language or forest-wide
   admission.
4. **Higher security claims** (signed receipts, ZK proofs) ride on
   proof-shaped JSON or signature field presence alone.

Current-tree forces:

| Force | Evidence |
| --- | --- |
| Sealed plan requires six distinct levels; schema acceptance is never “implemented” | KD-6; plan §12 |
| Traceability matrix already scores rows against the ladder and forbids structural promotion | matrix §0.1–0.2 (MCPP-012) |
| Profile C/D four-language validators are structural field presence | plan §3.2; inventory C/D; REQ-CRY-01 / REQ-POL-01 |
| Kit has real Ed25519 UCAN verification locally; forest validators do not | `ucan.py`; `test_ucan_verifier.py`; REQ-CRY-02 `partial` |
| Profile B receipt validators treat signature **presence** as signed | inventory B; REQ-CRY-04 / REQ-B-02 `structural-only` |
| Profile F / datasets ZK material is simulated or statement-request, not verified proof | plan §11; REQ-F-02; REQ-D-05 |
| Coverage “100%” documents contradict measured receipts | matrix REQ-BASE-*; inventory §10 |

If this decision is deferred, parallel lanes invent different “done” meanings,
promote crypto claims from structural suites, or mark matrix rows `implemented`
from JSON Schema acceptance. Gates 13–16, 24, and Verified Execution packaging
cannot close honestly.

Who is affected: conformance authors, matrix maintainers, runtime adapter
owners, operators reading evidence bundles and the implementation report,
and any peer that must fail closed on overstated security claims.

## Decision

**MCP++ 1.0 uses exactly six ordered, distinct conformance levels.** Every
normative claim, matrix row, gate, profile completeness statement, and
implementation-report assertion MUST be scored against the **highest** level
the claim requires. Schema or codec acceptance alone is **never**
`implemented`. **Promotion** of a claim, row, or artifact family to a level
**requires tests at that level** (positive evidence and adversarial negatives
appropriate to the level). A green lower-level suite does **not** promote a
higher-level claim.

### 1. Mandatory levels (ordered ladder)

The levels, in ascending strength, are **exactly**:

```text
structural → canonical → cryptographic → policy-enforced → receipt-signed → proof-verified
```

| Level | Identifier (wire / matrix) | Normative meaning | Typical positive evidence | Typical negative evidence (required for promotion) |
| --- | --- | --- | --- | --- |
| Structural | `structural` | Required fields, types, enums, size limits, and shape constraints hold. No security semantics. | Schema or hand model accepts valid vectors; field-presence validators green | Malformed types, missing required fields, wrong enums rejected |
| Canonical | `canonical` | Same logical object yields identical **canonical bytes**, digest, and CID (under the declared algorithm, e.g. `mcpp-jcs-v1`) across languages / peers. | Cross-language golden bytes, SHA-256, CID match; Kubo identity where claimed | Non-canonical serialization, key-order drift, number/Unicode edge cases change digest |
| Cryptographic | `cryptographic` | Signatures and key material are **verified** under the mandatory suite (ADR-0002): Ed25519/EdDSA, explicit `kid`, DID-compatible iss/aud, sig over canonical bytes. | Valid tokens/attestations verify; cross-lang verify where claimed | Tampered payload, `alg: none`, missing `kid`, wrong audience, expired/revoked/forged material **fail closed** |
| Policy-enforced | `policy-enforced` | Temporal deontic (or profile-declared) **evaluation** runs: permissions, prohibitions, obligations, deadlines; decisions are not field-presence alone. | Policy engine admits allowed cases and records decisions | Stale/revoked policy, conflict, obligation breach, missing deadline, revoked proof still allowed → reject |
| Receipt-signed | `receipt-signed` | Execution or cross-trust-domain **receipts** are signed and **independently verifiable** by a third party without trusting the executor’s transport identity. | Receipt verifies under issuer key; binds outputs/CIDs/intent as profile requires | Unsigned receipt, forged signature, executor PeerID as sole authority, broken binding → reject |
| Proof-verified | `proof-verified` | Zero-knowledge, attestation, or other **proof objects** are checked by a real verifier on current vectors (not simulated proof-shaped JSON). | Verifier accepts valid proofs; binds public inputs / statements as declared | Simulated/mocked proof claiming verified; missing keys; invalid proof; statement-request labeled as proof → reject |

Rules:

| Rule | Normative statement |
| --- | --- |
| Exhaustive set | For MCP++ 1.0, conformance levels are **exactly** these six identifiers. No aliases that collapse levels (e.g. “secure” for cryptographic+policy). No free-text levels in normative matrices. |
| Ordered ladder | Higher levels **presuppose** the lower levels they depend on for the same artifact family. A `cryptographic` claim without structural shape and declared canonical signing input is invalid scoring. A `receipt-signed` claim requires cryptographic verify of the receipt, not only a signature string field. |
| Distinct | Levels are **not interchangeable**. Field presence is not verification. Canonical hash helpers are not signature verify. Signature verify is not policy evaluation. A signed receipt is not a ZK proof. |
| Highest-claim scoring | A row or gate is scored against the **highest** level its requirement claims. If only lower-level evidence exists, status is `structural-only` or `partial` (or `missing` / `blocked`), **never** `implemented` at the higher claim. |
| Schema ≠ implemented | JSON Schema acceptance, hand-model field presence, or regex CID form is **at most** `structural` (or partial format work). It is **never** alone sufficient for status `implemented` on a security, policy, receipt, or proof claim (KD-6; plan §12). |

### 2. Promotion requires tests at that level

**Promotion** means raising a claim’s recorded conformance level, marking a
matrix row `implemented` for a level-bearing requirement, asserting a profile
or gate “closed” at a level, or shipping an implementation-report statement
that a level was achieved.

| Promotion rule | Normative statement |
| --- | --- |
| Same-level tests | Promotion to level *L* requires **tests that exercise *L***: automated cases that pass only if *L*’s semantics hold, not merely lower levels. |
| Positive and negative | Evidence MUST include **positive** (valid material accepted / verifies) and **negative** (adversarial or malformed material rejected) coverage appropriate to *L*. Positives alone never promote security levels. |
| Current-tree command | Evidence MUST name a **reproducible current-tree command** (and, when applicable, artifact path) that demonstrates *L*. Documentation prose, outdated coverage trophies, and historical green CI without the level’s checks do **not** promote. |
| No structural leap | A green **structural** suite MUST NOT promote `canonical`, `cryptographic`, `policy-enforced`, `receipt-signed`, or `proof-verified` claims. |
| No canonical leap | Canonical / CID identity alone MUST NOT promote cryptographic, policy, receipt, or proof claims. |
| No crypto leap | Signature verification alone MUST NOT promote policy-enforced, receipt-signed (unless the claim is only signature verify), or proof-verified claims. Receipt-signed requires signed **receipt** objects independently verifiable as such. |
| No simulation leap | Simulated Groth16, proof-shaped JSON, or statement-request certificates MUST NOT promote `proof-verified` (plan §11; inventory F/D). |
| Local ≠ forest | Runtime-local PASS (e.g. kit-only UCAN, SwissKnife matrix) MAY evidence a **local** path at a level; forest-wide or four-language claims require evidence at that scope. Local crypto does not auto-promote structural four-language validators. |
| Downgrade honesty | If higher-level tests fail or are removed, recorded level and matrix status MUST drop; they MUST NOT remain `implemented` on stale evidence. |

### 3. Relationship to matrix status vocabulary

The five **status** values in the traceability matrix (`implemented`,
`partial`, `structural-only`, `missing`, `blocked`) are **not** the same
thing as the six **conformance levels**. Status answers “how far is this
requirement relative to its claim?”; level answers “what class of evidence is
claimed or achieved?”

| Status | How it relates to levels |
| --- | --- |
| `implemented` | Behavior is enforced at the **claimed** level with positive **and** negative evidence at that level. Schema field presence alone never qualifies. |
| `partial` | Meaningful work exists below or incompletely at the claimed level (e.g. local crypto, incomplete negatives, draft-only). |
| `structural-only` | Evidence stops at shape/field acceptance while the claim requires higher semantics. |
| `missing` | No implementation, schema, validator, vector, or runtime found for the claim. |
| `blocked` | Path exists only behind unavailable deps, flags, or authority; blocker recorded. |

Scoring formula (normative intent):

1. Determine the **claimed level** of the requirement (from plan gate, profile
   draft, or explicit security wording).
2. Determine the **highest level with current positive+negative evidence**.
3. If evidence level ≥ claimed level and scope matches → may be `implemented`.
4. If evidence level is only `structural` while claim is higher →
   `structural-only` (or `partial` if some higher work exists but incomplete).
5. Never write `implemented` because a schema accepts fields.

### 4. Fail-closed defaults (KD-6 restated)

| Rule | Normative statement |
| --- | --- |
| Schema never “implemented” | Acceptance of fields, types, or CID **shape** is not production conformance at cryptographic or higher levels. |
| Coverage trophies are not evidence | Line-coverage or “validation complete / 100%” docs do not promote any level (plan §11; inventory §10). |
| Structural green ≠ higher claim | Four-language structural suites (e.g. Profile C/D field presence) remain structural until higher-level tests land. |
| Transport ≠ authority | PeerID, TLS client cert, registry presence, or payment settlement never substitute for cryptographic / receipt authority (KD-14; restated for level scoring). |
| Honest non-claims | Implementation reports and matrices MUST list levels **not** achieved. Profile G is not BFT; simulated ZK is not `proof-verified`; payment is not authorization. |

### 5. Normative checklist (ConformanceLevelDecision@1)

An artifact family, matrix row, gate, or report claim is **level-honest** only
when all of the following hold:

1. Levels used are exactly: `structural`, `canonical`, `cryptographic`,
   `policy-enforced`, `receipt-signed`, `proof-verified`.
2. The claim states (or can be derived from the requirement) which level it
   asserts.
3. Status `implemented` is used only when tests at that level (positive and
   negative) pass under a named current-tree command.
4. Schema or codec acceptance alone never yields `implemented` for a
   higher-than-structural claim.
5. Lower-level green suites are not used as evidence for higher-level
   promotion.
6. Simulated proofs, signature field presence, and transport identity are not
   scored as `proof-verified`, `cryptographic`/`receipt-signed`, or
   execution authority respectively.
7. Local runtime evidence is labeled local unless four-language / forest scope
   is also evidenced.

## Alternatives

### Alternative A: Binary pass/fail per profile

- **Summary:** Each profile is simply “conforming” or not once any validator is green.
- **Expected benefits:** Simpler dashboards; fewer matrix columns.
- **Why not chosen:** Collapses security depth; Profile C structural green would read as full UCAN security. KD-6 exists precisely because current validators are structural-only for C/D.

### Alternative B: Schema acceptance equals implemented

- **Summary:** Versioned JSON Schema green → row `implemented`.
- **Expected benefits:** Fast matrix completion when schemas land.
- **Why not chosen:** Explicitly forbidden by KD-6 and plan §12. Schemas do not verify signatures, evaluate policy, sign receipts, or check proofs.

### Alternative C: Continuous “maturity score” without named levels

- **Summary:** 0–100 scores or coverage percentages as the only ladder.
- **Expected benefits:** Fine-grained progress tracking.
- **Why not chosen:** Non-comparable across profiles; coverage trophies already mislead (inventory §10). Named semantic levels force honest security language.

### Alternative D: Promote automatically when lower levels are green

- **Summary:** Structural + some CID helper auto-promotes to cryptographic.
- **Expected benefits:** Less bookkeeping.
- **Why not chosen:** Creates false security claims. Promotion requires same-level tests; structural suites must not leap.

### Alternative E: Do nothing / status quo labels only in the plan

- **Summary:** Keep KD-6 in the sealed plan only; no ADR.
- **Why not chosen:** Wave 3 ADRs exist so Waves 4–7 (G040–G080 and packaging) share one vocabulary (MCPP-G020). Matrix MCPP-012 already depends on the ladder; this ADR freezes it as Accepted design authority.

## Consequences

### Positive

- Parallel lanes share one vocabulary: six levels, ordered, non-collapsible.
- Matrix scoring and implementation reports have an unambiguous promotion bar:
  tests at the claimed level.
- Prevents structural validators and schema acceptance from being marketed as
  cryptographic or Verified Execution readiness.
- Aligns with existing MCPP-012 matrix §0.1–0.2 and plan KD-6 without reopening
  either.
- Gives crypto (MCPP-041…045), policy (MCPP-046…049), receipt, and proof tracks
  a clear “done” definition distinct from field presence.

### Negative

- Authors must maintain level tags and same-level negative suites; more
  bookkeeping than a single green checkmark.
- Some currently “green” suites must be **relabeled** downward (structural-only)
  rather than celebrated as complete.
- Forest-wide claims take longer: local kit crypto does not close four-language
  cryptographic gates until validators and shared vectors catch up.
- Simulated ZK and signature-presence paths require explicit demotion language,
  which can block packaging claims until real verifiers land.

### Neutral / residual risks

- Exact command names for later gates may change as tests are added; the
  promotion **rule** (same-level positive+negative, current-tree) does not.
- ADR-0002 defines **what** cryptographic verify means; this ADR defines **when**
  a claim may say it achieved that level.
- Profile-specific extras (lease fencing, P2P abuse, commerce settlement) still
  map onto these levels or remain non-claims; they do not invent a seventh
  default level without a superseding ADR.
- Status vocabulary remains five values; do not merge status and level into one
  enum in matrices.

## Evidence

| Claim in Decision | Evidence (path, test, or operational check) | Notes |
| --- | --- | --- |
| Six distinct levels named as above | Plan KD-6; matrix §0.2 | Exact identifier set |
| Schema acceptance never “implemented” | Plan KD-6; plan §12; matrix §0.1 rule 1 | Normative for matrices and reports |
| Structural green does not promote higher claims | Matrix §0.1 rules 3–4; plan §3.2 C/D structural | Current four-lang C/D suites |
| Promotion needs same-level tests | This ADR Decision §2; matrix §0.1 rule 5 | Positive + negative + command |
| Structural-only C/D validators today | plan §3.2; inventory C/D; REQ-CRY-01 / REQ-POL-01 | Motivation for KD-6 |
| Local cryptographic evidence exists (kit) | `ucan.py`; `test_ucan_verifier.py`; REQ-CRY-02 `partial` | Local ≠ forest-wide promotion |
| Receipt signature presence is structural | inventory B; REQ-B-02 / REQ-CRY-04 | Not `receipt-signed` |
| Simulated ZK is not proof-verified | plan §11; REQ-F-02; REQ-D-05 | Fail-closed non-claim |
| Coverage trophies are not evidence | inventory §10; matrix REQ-BASE-* vs doc 100% | Measured receipts win |

Evidence classes used: sealed plan key decision (design authority for this
wave), traceability matrix (MCPP-012 scoring rules), baseline inventory and
receipts (tree reality). This ADR does **not** claim higher-level forest
conformance is complete.

## Verification

How a future reader confirms this ADR still holds:

1. **Document presence (this task):**
   ```text
   test -s ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0003-conformance-levels.md
   ```
2. **Level set still closed:** inspect Decision §1 for exactly the six
   identifiers and the ordered ladder matching plan KD-6 and matrix §0.2.
3. **Matrix still uses the ladder:**  
   `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md`
   §0.1–0.2 still forbids schema-only `implemented` and structural leapfrogging.
4. **Structural ≠ cryptographic (spot check):** four-language Profile C
   validators still fail to verify signatures until MCPP-041…044 land; kit
   `test_ucan_verifier.py` remains local crypto evidence only.
5. **Staleness signals:** a seventh default level without a superseding ADR;
   matrix rows marked `implemented` from schema alone; structural suite green
   cited as cryptographic / policy / receipt / proof closure; simulated proofs
   labeled `proof-verified`; collapse of levels into a single “secure” flag.

## Review triggers

- [ ] Source anchors no longer match the Decision statement
- [ ] A recorded negative consequence becomes unacceptable
- [ ] A rejected alternative (binary pass/fail, schema-as-implemented, auto-promotion) becomes viable without those costs
- [ ] Security or trust-boundary changes require a new distinct level (only via superseding ADR)
- [ ] Matrix status vocabulary is redesigned in a way that conflicts with highest-claim scoring
- [ ] Superseding design is Accepted under a new ADR number

When superseding: create a new ADR number; set this file to **Superseded** with
`Superseded-by`; set the successor’s `Supersedes`; do not delete this file.

## Notes (optional)

### Downstream task map

| Concern | Follow-on |
| --- | --- |
| Cross-language canonical identity | MCPP-024…028 (gate 24; level `canonical`) |
| Real Ed25519 delegation verify forest-wide | MCPP-041…044 (gates 13–14; level `cryptographic`) |
| Signed cross-trust receipts | MCPP-045 (gate 15; level `receipt-signed`) |
| Temporal deontic policy enforcement | MCPP-046…049 (gate 16; level `policy-enforced`) |
| Real proof verification (ZK / attestations) | Profile F / Verified Execution tracks (level `proof-verified`) |
| Matrix row upgrades | Only with same-level command + artifacts (MCPP-012 rules) |
| Implementation report conformance section | plan §12 final deliverables |

### Interface label

Task interface id: **`ConformanceLevelDecision@1`** — the normative checklist in
Decision §5.

### Sealed defaults preserved

This ADR records plan KD-6 without reopening it. Refinements (promotion test
requirements, matrix status mapping, local-vs-forest scope, fail-closed
non-claims for simulated proofs and transport identity) stay inside that
default and cite current-tree evidence from MCPP-012 and the baseline
inventory.
