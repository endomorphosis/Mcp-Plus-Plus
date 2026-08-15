# MCP++ 1.0 Gap-Closure — Requirement-to-Evidence Traceability Matrix

**Schema:** `RequirementTraceRow@1` (tabular rows in this document)  
**Task:** MCPP-012  
**Goal:** MCPP-G010  
**Track:** baseline-matrix  
**Generated:** 2026-08-15  
**Authority:** Mcp-Plus-Plus nested checkout bound by MCPP-001 / baseline forest  
**Depends on evidence from:** MCPP-002, MCPP-003, MCPP-004, MCPP-005, MCPP-006, MCPP-007, MCPP-008, MCPP-009, MCPP-010, MCPP-011  

Companion sources (read-only for this task):

| Source | Path |
| --- | --- |
| Sealed plan | `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` |
| Profile inventory | `docs/reports/mcplusplus-1.0-gap-closure/baseline/profiles-a-h-inventory.md` |
| Official MCP / A2A note | `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md` |
| Forest / overlays | `docs/reports/mcplusplus-1.0-gap-closure/baseline/repository-forest.json`, `dirty-overlay.md` |
| Language / runtime receipts | `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-{python,typescript,go,rust}.json`, `ipfs-{accelerate,datasets,kit}-mcplusplus.json`, `swissknife-mcplusplus.json` |

---

## 0. How to read this matrix

### 0.1 Status vocabulary (exact)

Every row uses **exactly one** of:

| Status | Meaning |
| --- | --- |
| `implemented` | Behavior exists and is enforced at the claimed conformance level with positive **and** negative evidence. Schema field presence alone never qualifies. |
| `partial` | Meaningful implementation exists, but gaps remain relative to normative / draft claims (missing negatives, incomplete cross-runtime parity, optional crypto, draft-only text, etc.). |
| `structural-only` | Validators/schemas accept shapes (fields, types, regex CID form) without enforcing the security, policy, crypto, proof, lease, or fencing semantics the claim requires. |
| `missing` | No readable implementation, schema, validator, vector, or runtime for the claim was found in the bound forest. |
| `blocked` | Implementation or verification exists only behind unavailable external deps, flags, toolchains, or unresolvable authority (recorded as such). |

**Fail-closed promotion rule (KD-6 / plan §12):**

1. Schema or codec acceptance is **never** `implemented`.
2. Line-coverage trophies and “validation complete / 100%” docs are **not** evidence (inventory §10).
3. A green structural suite does **not** promote cryptographic, policy-enforced, receipt-signed, or proof-verified claims.
4. Runtime-local PASS matrices (for example SwissKnife `CONFORMANCE_MATRIX.md`) are not four-language or forest-wide admission.
5. Later waves **may** upgrade a row only with a current-tree command, artifact path, and conformance level that matches the claim.

### 0.2 Conformance levels (plan KD-6)

`structural` → `canonical` → `cryptographic` → `policy-enforced` → `receipt-signed` → `proof-verified`

A row’s `status` is scored against the **highest** level the requirement claims. If only lower levels have evidence, status is `structural-only` or `partial`, never `implemented` at the higher claim.

### 0.3 Row schema (`RequirementTraceRow@1`)

Each matrix row maps one normative (or sealed-plan) requirement to:

| Column | Description |
| --- | --- |
| `req_id` | Stable identifier (`REQ-…`) |
| `requirement` | Short normative claim |
| `spec` | Spec section / plan gate / inventory section |
| `schema` | Versioned JSON Schema or hand model path; `—` if none |
| `validator` | Conformance validator path(s) |
| `pos_vector` | Positive vector / fixture |
| `neg_vector` | Negative / adversarial vector |
| `runtime` | Runtime surface(s) |
| `integration` | Integration or cross-language test |
| `status` | One of the five exact values above |
| `evidence` | Baseline receipt, inventory section, or primary-source note |
| `next` | Owning follow-on task(s) when not terminal |

### 0.4 Bound revisions (from baseline forest + receipts)

| Role | Bound SHA (short) | Receipt / source |
| --- | --- | --- |
| Mcp-Plus-Plus / nested `mcplusplus` | `6965f89f` | MCPP-002…005, MCPP-011 |
| accelerate operator | `ea11293b` (forest); live runtime worktree varies | MCPP-001, MCPP-006 |
| datasets | `ac82107e` | MCPP-007 |
| kit | `6196017c` (live; plan freeze `5a7a2df8` ancestor) | MCPP-008 |
| SwissKnife | `afdbf885` (live; plan freeze `26f06277` ancestor) | MCPP-009 |
| Official MCP | revision `2026-07-28` | MCPP-010 primary URLs |
| Official A2A | `1.0.0` extension-by-URI | MCPP-010 |

---

## 1. Baseline evidence index (MCPP-002…011)

These rows are **measurement** requirements of G010. They are not production conformance claims for Profiles A–H.

| req_id | requirement | command (board / receipt) | result (honest) | status | evidence |
| --- | --- | --- | --- | --- | --- |
| REQ-BASE-PY | Recompute Mcp-Plus-Plus Python suite | `cd ipfs_accelerate_py/mcplusplus && python -m pytest -q tests-py --maxfail=1` | **pass** 323/323; validators stmt coverage **~96.1%** (recomputed; not doc 100%) | `implemented` | `baseline/mcpplusplus-python.json` |
| REQ-BASE-TS | Recompute Mcp-Plus-Plus TypeScript suite | `cd ipfs_accelerate_py/mcplusplus/tests-ts && npm test` | **pass** 223 passed, 19 skipped, **1 disabled suite** (`comprehensive.test.ts.disabled`) not treated as pass; coverage ~98% statements (supplemental) | `implemented` | `baseline/mcpplusplus-typescript.json` |
| REQ-BASE-GO | Recompute Mcp-Plus-Plus Go suite | `cd ipfs_accelerate_py/mcplusplus/tests-go && go test ./...` | **pass** 211; cover **~96.9%** (validators package ~97.6%); historical coverage.html not used as current evidence | `implemented` | `baseline/mcpplusplus-go.json` |
| REQ-BASE-RS | Recompute Mcp-Plus-Plus Rust suite | `cd ipfs_accelerate_py/mcplusplus/tests-rs && cargo test` | **pass** 191; coverage **unavailable** this run (tooling missing); stale 100% docs not cited as measured | `implemented` | `baseline/mcpplusplus-rust.json` |
| REQ-BASE-ACC | Baseline accelerate MCP++ tests | `python -m pytest -q ipfs_accelerate_py/mcp/tests test/api -k mcplusplus --maxfail=1` | **fail** / inventory: 239 passed, 3 failed, 63 collection errors under broader inventory; official maxfail gate fails on collection debt | `partial` | `baseline/ipfs-accelerate-mcplusplus.json` |
| REQ-BASE-DS | Baseline datasets MCP++ tests | `cd ipfs_datasets_py && python -m pytest -q tests/unit/mcp_server -k mcplusplus --maxfail=1` | **no tests selected** (exit 5); 116 collected, 116 deselected; untracked operator files not promoted | `missing` (committed `-k mcplusplus` suite) | `baseline/ipfs-datasets-mcplusplus.json` |
| REQ-BASE-KIT | Baseline kit UCAN/MCP++/profile tests | `cd ipfs_kit_py && python -m pytest -q tests -k 'ucan or mcplusplus or profile' --maxfail=1` | **fail** at collection (`ImportError` `CallbackFacilitator` from `mcplusplus_profile_h`; reverify also hits duplicate-basename collection debt) | `partial` (code present; suite not green) | `baseline/ipfs-kit-mcplusplus.json` |
| REQ-BASE-SK | Baseline SwissKnife MCP++ tests | SwissKnife `test/mcp-plus-plus` vitest (see receipt) | **fail** 6 passed / 39 failed (crypto mock missing `generateKeyPairSync`); remote discovered not invented | `partial` | `baseline/swissknife-mcplusplus.json` |
| REQ-BASE-OFF | Verify official MCP 2026-07-28 + A2A from primary sources | primary HTTPS sources only | **recorded**; current MCP not initialize-based; A2A extensions are URIs; confirmed MCP++ URI `https://mcplusplus.io/extensions/execution/v1` | `implemented` (verification note) | `baseline/official-mcp-a2a.md` |
| REQ-BASE-INV | Inventory Profiles A–H with fail-closed statuses | forest-bound tree walk | **complete** ProfileInventory@1; C crypto not structural-only overall because real verifiers found | `implemented` (inventory artifact) | `baseline/profiles-a-h-inventory.md` |

**Baseline interpretation:** four-language Mcp-Plus-Plus validator suites are currently green at the **structural / codec** layer. That is necessary inventory, not cryptographic or production admission.

---

## 2. Cross-cutting program requirements (plan gates + key decisions)

### 2.1 Ownership, bindings, and trust boundaries

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-OWN-01 | Spec repo owns schemas, vectors, validators, matrices; runtimes own adapters | plan KD-1 | — | — | — | — | Mcp-Plus-Plus vs accelerate/datasets/kit/SwissKnife | — | `partial` | inventory §0.3; forest | MCPP-013 |
| REQ-BIND-01 | Profiles A–H are transport- and MCP-version-independent | plan KD-2, G030 | — | — | — | — | draft chapters still mix initialize language | — | `missing` (refactor not done) | inventory §0.3 #5; official-mcp-a2a | MCPP-019…023 |
| REQ-BIND-02 | Dual bindings: `mcp-binding/legacy-2024-11-05` and `mcp-binding/2026-07-28` | plan KD-3, gate 2–5 | — | — | `conformance/vectors/initialize_result.json` (legacy pin only) | forged/downgraded `protocolVersion` | accelerate/datasets still legacy-shaped | — | `partial` (legacy present; current binding missing) | official-mcp-a2a §2; vector `initialize_result.json` | MCPP-020…023 |
| REQ-BIND-03 | Current MCP binding does not depend on removed initialize exchange | plan gate 3–4; MCP 2026-07-28 | — | — | — | reject initialize-as-current | — | — | `missing` | official-mcp-a2a §2.2 | MCPP-021 |
| REQ-BIND-04 | Legacy clients still work under explicit legacy binding name | plan gate 5 | — | — | initialize_result | — | runtimes using 2024-11-05 | — | `partial` | vector + inventory | MCPP-020 |
| REQ-TRUST-01 | Transport identity ≠ execution authority (PeerID/TLS ≠ UCAN) | plan KD-14 | — | transport validators structural | — | peerId grants capability (must fail) | SwissKnife cross-profile notes | — | `partial` | inventory E/C; plan KD-14 | MCPP-062…065, MCPP-041… |
| REQ-TRUST-02 | Payment never grants authorization | plan KD-14, gate 23, Profile H | `schemas/profile-h/1.0/*` | `profile_h` codecs | H valid vectors | payment success + C/D deny | accelerate/kit/datasets seller paths | planned adversarial suite | `partial` | inventory §9; codec disclaims crypto | MCPP-070…072 |

### 2.2 Canonicalization, schemas, and portable envelope

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-CAN-01 | Named algorithm `mcpp-jcs-v1` = RFC 8785 JCS | plan KD-5, G040 | — | hand codecs partial | G/H DAG-JSON vectors | numeric/Unicode/null/dup-key negatives incomplete as shared suite | multi-lang codecs | four-language identity tests planned | `missing` (named id not published) | plan KD-5; inventory cross-cutting | MCPP-024…029 |
| REQ-CAN-02 | Same object → identical canonical bytes, digest, CID in Py/TS/Go/Rust | plan gate 24 | — | language-local | profile_g/h valid | — | — | `test_conformance_vectors` structural | `partial` | receipts show suites green; not proven Kubo-byte identity | MCPP-026…028 |
| REQ-CAN-03 | Historical artifact CIDs remain readable under recorded algorithm | plan §4 rule 6–7 | adapters planned | — | existing B/G vectors | silent CID rewrite (forbidden) | accelerate/kit/SwissKnife artifacts | planned adapter tests | `partial` | inventory B/G; no Envelope@1 yet | MCPP-031 |
| REQ-SCH-01 | Single-source schema generation for all profiles | plan G040 | only `schemas/profile-h/1.0/` versioned | hand models A–G | H schemas | — | — | — | `partial` (H only) | inventory §0.3 #2 | MCPP-029 |
| REQ-ENV-01 | `ExecutionEnvelope@1` exists | plan KD-7, gate 7 | **missing** | B field validators only | `execution_receipt.json` (legacy shape) | — | accelerate `artifacts` / SwissKnife envelope | — | `missing` | inventory B §3.7 | MCPP-030 |
| REQ-ENV-02 | `ExecutionResult@1` exists | plan gate 7 | **missing** | — | — | — | — | — | `missing` | inventory B | MCPP-030 |
| REQ-ENV-03 | `ExecutionReceipt@1` exists | plan gate 7 | **missing** | `cid_artifacts` structural | `execution_receipt.json` | signature verify negatives | accelerate/SwissKnife | — | `structural-only` (legacy receipt shape) | inventory B §3.4 | MCPP-030, MCPP-045 |
| REQ-ENV-04 | `PortableError@1` exists | plan gate 7 | **missing** | `session_error.json` sample only | `session_error.json` | — | — | — | `missing` | vectors list | MCPP-030 |
| REQ-ENV-05 | Existing B and G artifacts adapt without silent CID breakage | plan gate 9 | adapters planned | G codec + B validators | profile_g_* / execution_receipt | CID mutation | accelerate, kit | planned MCPP-031 | `partial` | inventory B/G | MCPP-031 |

### 2.3 State, durable execution, and Event DAG

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-ST-01 | `StateRef@1` with exactly one consistency mode | plan KD-8, gate 8 | **missing** | — | — | multi-mode / silent merge | — | — | `missing` | plan G060 | MCPP-035…040 |
| REQ-ST-02 | Single-authority backend: SQLite WAL CAS restart-tested | plan KD-9, gate 10 | — | — | — | lost update after restart | accelerate/datasets candidate paths | restart tests planned | `missing` | plan; no gate evidence artifact | MCPP-037, MCPP-052 |
| REQ-ST-03 | Real CRDT backend (Automerge), not informal LWW | plan KD-10, gate 11 | — | — | — | divergence without merge evidence | — | concurrent-update tests planned | `missing` | plan KD-10 | MCPP-038 |
| REQ-ST-04 | Consensus vs neighborhood coordination labeled accurately (not BFT for G) | plan KD-11, gate 12 | G codecs | `profile_g` | profile_g vectors | labeling G as BFT | accelerate/kit G transport | three-peer harness | `partial` | inventory G §8.3; chapter non-normative | MCPP-066…069 |
| REQ-DUR-01 | `DurableExecutor` interface + crash recovery without duplicate effects | plan KD-12, gates 17 | **missing** | — | — | duplicate side effects after crash | SQLite journaled adapter planned | crash-recovery tests | `missing` | plan G090 | MCPP-050…053 |
| REQ-F-01 | Event DAG reconstructs causal history; parents required | Profile F draft | — | `event_dag` structural | `dag_event_*.json` | missing parents | accelerate/kit event_dag | integration suites structural | `structural-only` (validators) / `partial` (runtimes) | inventory §7 | MCPP-F / G050 overlap |
| REQ-F-02 | Compaction `zero_knowledge: true` only with real verifiable ZK | Profile F draft; plan §11 | — | structural event validator | `zkp_proof_artifact.json` | simulated proof claiming ZK | accelerate `dag_compaction` defaults `simulated_groth16` | — | `structural-only` / often `blocked` for real Groth16 | inventory §7.5 | later F/ZK tasks |
| REQ-F-03 | Verified Execution requires real verifier success on current vectors | plan §11 | — | — | — | simulated digest as proof | opt-in `IPFS_DATASETS_ENABLE_GROTH16` | — | `blocked` (or missing default-on path) | inventory §7.5–7.7 | G150/F follow-ons |

### 2.4 Crypto, policy, discovery, A2A, CLI

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-CRY-01 | Mandatory suite: Ed25519, key ids, DID-compatible iss/aud, sig over canonical bytes, CIDv1 | plan KD-4 | — | 4-lang C validators structural | `delegation.json` | tampered/unsigned/alg-none | kit `UCANVerifier`; SwissKnife `@ucans/ucans`; accelerate optional | kit readiness tests | `partial` | inventory C; kit tests `implemented` locally | MCPP-041…045 |
| REQ-CRY-02 | Real cryptographic delegation verification (forest-wide) | plan gate 13 | — | structural in Mcp-Plus-Plus | kit valid tokens | kit adversarial suite | kit **implemented**; SwissKnife partial; accelerate partial | kit `test_ucan_verifier.py` | `partial` | inventory §4.5 | MCPP-041…044 |
| REQ-CRY-03 | Attenuation, expiration, revocation, audience, replay tested negatively | plan gate 14 | — | 4-lang **do not** check | kit negatives | kit negatives present | kit ledger + SwissKnife revocation | kit readiness | `partial` (kit); `structural-only` (validators) | inventory C | MCPP-042…044 |
| REQ-CRY-04 | Cross-trust-domain receipts signed and independently verifiable | plan gate 15 | Envelope/Receipt@1 missing | `cid_artifacts` marks signed if field exists | execution_receipt | verify failure paths | SwissKnife optional sign; accelerate modules | — | `structural-only` | inventory B §3.4–3.5 | MCPP-045 |
| REQ-POL-01 | Temporal deontic evaluate permissions/prohibitions/obligations + deadlines | Profile D; gates 16 | **missing** versioned | `policy_evaluation` structural | `policy_decision.json` | stale/revoked/conflict | accelerate/datasets/SwissKnife engines | planned obligation suite | `partial` | inventory D | MCPP-046…049 |
| REQ-A2A-01 | A2A extension URI verified; no competing public task lifecycle | plan KD-13, gate 6 | — | — | official A2A docs | reverse-DNS-only as wire id | planned SwissKnife adapter | handoff tests planned | `partial` (URI verified; extension implementation missing) | official-mcp-a2a §3 | MCPP-054…057 |
| REQ-A2A-02 | Wire identifier is URI `https://mcplusplus.io/extensions/execution/v1` | MCPP-010 | — | — | — | use `io.mcplusplus.execution@1` as sole wire id | — | — | `implemented` (identifier decision recorded) | official-mcp-a2a §1, §3.3 | MCPP-054 |
| REQ-DISC-01 | Agent advertisement / capability discovery for MCP++ profiles | plan G110 | **missing** | initialize_result legacy caps | — | — | accelerate peer modules | — | `missing` | plan G110 | MCPP-058…061 |
| REQ-P2P-01 | P2P abuse and framing tests pass (oversize, replay, flood) | plan gate 21 | — | transport structural | `p2p_message.json` | shared abuse suite missing | datasets/accelerate/SwissKnife/kit | planned MCPP-063…065 | `partial` | inventory E | MCPP-062…065 |
| REQ-CONF-01 | Confidential artifacts do not leak plaintext in tested paths | plan KD-15, gate 22 | **missing** | — | — | plaintext in logs/DAG/cache | kit planned | leak tests planned | `missing` | plan G150 | MCPP-073…074 |
| REQ-CLI-01 | Installable `mcpp` CLI + three-peer Docker Compose demo | plan KD-16, gates 25–26 | — | — | — | — | SwissKnife has related CLI pieces; unified `mcpp` missing | three-peer G harness partial | `missing` | plan G160; inventory G harness | MCPP-075…077 |
| REQ-CI-01 | Static docs match generated CI evidence; required workflows green | plan gates 27–28 | — | — | — | coverage trophy docs | — | — | `missing` | inventory §10 contradictory docs | MCPP-078…083 |

---

## 3. Profile A–H requirement matrix

Paths below are relative to `ipfs_accelerate_py/mcplusplus/` unless noted. Runtime paths use repo roots (`ipfs_accelerate_py/…`, `ipfs_datasets_py/…`, `ipfs_kit_py/…`, SwissKnife checkout).

### 3.1 Profile A — MCP-IDL (`mcp++/idl` / `interfaces/*`)

**Overall status:** `partial`  
**Dominant conformance today:** structural (+ partial canonical CID helper)

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-A-01 | Interface descriptor required fields (`name`, `namespace`, `version`, `methods[]`, `errors[]`, `compatibility`, `requires[]`) | `docs/spec/mcp-idl.md`; registry §4 | **missing** versioned | `tests-py/validators/mcp_idl.py` (+ TS/Go/Rust) | IDL fixtures under tests-*/fixtures | missing-field cases in unit tests | accelerate `idl_registry.py`, `interface_descriptor.py`; SwissKnife `mcp-idl` | TS/Go/Rust validator suites | `partial` | inventory §2; BASE-PY/TS/GO/RS green | schema gen |
| REQ-A-02 | Repository APIs `interfaces/list|get|compat` | mcp-idl.md | — | structural | — | unknown CID | SwissKnife IDL CLI/repo; accelerate registry | SwissKnife tests (local) | `partial` | inventory §2.3 | runtime parity |
| REQ-A-03 | `interface_cid` content-addressed and Kubo-identical for same canonical bytes | mcp-idl.md | — | `compute_interface_cid` simplified | — | cross-lang CID mismatch | accelerate CID helpers | four-language golden missing | `structural-only` / `partial` | inventory §2.4 | MCPP-024…028 |
| REQ-A-04 | Optional `interfaces/select` + streaming/event semantics | mcp-idl.md optional | — | — | — | — | incomplete | — | `missing` | inventory §2.1 optional | later |
| REQ-A-05 | Production claim of Profile A completeness from coverage docs | testing trophies §10 | — | line coverage of structural validator | — | — | — | — | `structural-only` | inventory §10 (not promotion evidence) | never promote from §10 |

### 3.2 Profile B — CID-native artifacts

**Overall status:** `partial`  
**Dominant conformance today:** structural (validators); partial runtime helpers

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-B-01 | Envelope fields `interface_cid`, `input_cid`, optional intent/policy/proof, `parents[]` | `cid-native-artifacts.md`; registry §5 | **missing** versioned | `cid_artifacts.py` (+ peers) | `conformance/vectors/execution_receipt.json` | bad CID form (regex only) | accelerate `artifacts.py`, `cid_ucan.py`; kit artifacts; SwissKnife `mcp-envelope` | multi-lang validator tests | `structural-only` (security) / `partial` (format) | inventory §3 | MCPP-030 |
| REQ-B-02 | Outputs `output_cid` / `receipt_cid`; receipts MAY be signed | cid-native-artifacts.md | — | signature **presence** only | execution_receipt | tampered signature must fail (missing at validator) | SwissKnife optional sign; accelerate modules | — | `structural-only` | inventory §3.4–3.5 | MCPP-045 |
| REQ-B-03 | Deterministic canonicalization; CIDs match Kubo | chapter claim | — | regex CID, not multihash/content verify | — | non-Kubo CID accepted if shape matches | accelerate `kubo_cid.py` partial | cross-lang golden missing | `partial` | inventory §3.4 | MCPP-024…028 |
| REQ-B-04 | Shared ExecutionEnvelope@1 family supersedes overlapping B/G carriers | plan KD-7 | **missing** | — | — | — | — | — | `missing` | inventory §3.7 | MCPP-030…034 |

### 3.3 Profile C — UCAN delegation

**Overall status:** `partial` (validators `structural-only`; forest crypto `partial` with **real verifiers found**)  
**Acceptance import from MCPP-011:** do **not** classify overall crypto enforcement as structural-only.

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-C-01 | Execution-time validation of delegation chains REQUIRED | `ucan-delegation.md`; registry §6 | **missing** versioned | 4-lang field presence only | `delegation.json` | invalid chain shape (structural) | kit `UCANVerifier`; SwissKnife ucans; accelerate optional Ed25519 | kit `test_ucan_verifier.py` | `partial` | inventory §4 | MCPP-041…044 |
| REQ-C-02 | Verify signatures (EdDSA / Ed25519) | KD-4 + C draft | — | **no** in Mcp-Plus-Plus validators | kit valid | kit tampered/unsigned/alg-none/wrong key | **kit `implemented`**; SwissKnife `partial`; accelerate `partial` (default may allow non-crypto) | kit negatives | `partial` (forest); kit-local `implemented` | inventory §4.3–4.5 | MCPP-041 |
| REQ-C-03 | Capability attenuation subset enforced | C draft | — | **no** in 4-lang validators | kit | over-scope capability | kit attenuation | kit tests | `partial` | inventory §4.3 | MCPP-042 |
| REQ-C-04 | Audience continuity enforced | C draft | — | **no** in 4-lang validators | kit | wrong audience | kit + SwissKnife | kit tests | `partial` | inventory §4.3 | MCPP-042 |
| REQ-C-05 | Expiration / time windows enforced | C draft | — | **no** in 4-lang validators | kit | expired token | kit + SwissKnife | kit tests | `partial` | inventory §4.3 | MCPP-042 |
| REQ-C-06 | Revocation fail-closed with durable ledger | C draft; gate 14 | — | **no** in 4-lang validators | kit ledger | revoked still accepted | kit `RevocationLedger`; SwissKnife registry | kit tests | `partial` | inventory §4.3 | MCPP-043 |
| REQ-C-07 | Four-language cryptographic conformance API + shared adversarial vectors | plan G070 | — | structural only today | — | shared crypto negatives missing | — | — | `missing` | inventory §4.7 | MCPP-041…044 |
| REQ-C-08 | Mcp-Plus-Plus validator “success” on unsigned/forged tokens | (anti-requirement) | — | currently would accept shape-valid unsigned | — | must become expected **failure** | — | — | `structural-only` (current defect class) | inventory §4.4 | MCPP-041 |

### 3.4 Profile D — Temporal deontic policy

**Overall status:** `partial`  
**Validators:** `structural-only`  
**Runtimes:** partial policy-enforced

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-D-01 | Content-addressed `policy_cid` with permissions/prohibitions/obligations/temporal constraints | `temporal-deontic-policy.md`; registry §7 | **missing** | `policy_evaluation.py` structural | `policy_decision.json` | — | accelerate `policy_engine.py`; datasets `profile_d_policy.py`; SwissKnife `mcp-policy` | unit/integration partial | `partial` | inventory §5 | MCPP-046…049 |
| REQ-D-02 | Evaluate policy at execution; emit `decision_cid` | D draft | — | type enum + field presence | policy_decision | deny paths incomplete in validators | accelerate/datasets evaluate paths | — | `partial` | inventory §5.3 | MCPP-047 |
| REQ-D-03 | Obligations MAY have deadlines; lifecycle events | plan gate 16 | — | temporal ISO checks stubbed/`pass` in Python validator | — | missed deadline | runtime engines partial | six-event suite planned | `partial` / near `missing` for shared suite | inventory §5.4, §5.7 | MCPP-048…049 |
| REQ-D-04 | Validate delegation proofs before policy (depends on C) | D draft | — | structural | — | revoked proof still allowed | mixed wiring | — | `partial` | inventory §5.5 | MCPP-046 + C track |
| REQ-D-05 | datasets `zkp_certificate` as verified ZK proof | (claimed only if asserted) | — | — | — | — | datasets header: **statement request, not proof** | — | `structural-only` (must not claim proof-verified) | inventory §5.5 | never promote without verifier |
| REQ-D-06 | Four-language adversarial policy negatives (stale/revoked/conflict) | plan G080 | — | missing | — | — | — | — | `missing` | inventory §5.7 | MCPP-049 |

### 3.5 Profile E — `mcp+p2p` transport

**Overall status:** `partial`  
**Carriage-only; not execution authority**

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-E-01 | Carry MCP JSON-RPC over libp2p without redefining MCP methods | `transport-mcp-p2p.md`; registry §8 | **missing** versioned framing | `transport.py` shape checks | `p2p_message.json`, `bus_message.json` | — | datasets P2P engines; accelerate `p2p_framing`; SwissKnife session; kit readiness | multi-repo partial | `partial` | inventory §6 | MCPP-062 |
| REQ-E-02 | Frame length / session phase discipline | E draft | — | structural field checks | p2p vectors | oversize/flood incomplete in 4-lang alone | SwissKnife rate limits partial | abuse suite planned | `structural-only` / `partial` | inventory §6.4 | MCPP-063…065 |
| REQ-E-03 | Split transport negotiation vs MCP app semantics vs authority | plan G120 | — | — | — | — | still coupled to initialize in draft | — | `missing` | inventory §6.4, §6.7 | MCPP-062 |
| REQ-E-04 | PeerID never grants UCAN capabilities | KD-14 | — | — | — | peer-only auth success | SwissKnife peer-id UCAN checks cross-profile | planned negatives | `partial` | inventory §6.5 | MCPP-065 |

### 3.6 Profile F — Event DAG + compaction / ZK

**Overall status:** `partial`  
**ZK:** simulated default; real path opt-in / often blocked

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-F-10 | Event commits bind intent/interface/proofs/decision/outputs/parents | `event-dag-ordering.md`; registry §9 | — | `event_dag.py` structural | `dag_event_epoch.json`, `dag_event_iso.json` | incomplete parent sets (limited) | accelerate/kit `event_dag.py` | multi-lang structural | `structural-only` (validators) / `partial` (runtime) | inventory §7 | later F |
| REQ-F-11 | Compaction certificate fields (`certificate_cid`, `archive_cid`, `merkle_root`, …) | F draft | — | presence-level | `zkp_proof_artifact.json`, wasm fixture | Merkle not recomputed in validator | accelerate `dag_compaction.py` | — | `structural-only` | inventory §7.4 | later F |
| REQ-F-12 | `zero_knowledge: true` only with real verifiable ZK | F draft; plan §11 | — | not enforced | — | simulated_groth16 with ZK true | default `proof_type: simulated_groth16` | — | `partial` (text) / enforcement uneven | inventory §7.5 | later F |
| REQ-F-13 | Groth16 MPC ceremony + always-on verify path | `groth16-mpc-ceremony.md` | ceremony fixture structural | — | fixture JSON | missing keys fail closed | opt-in flag path | — | `blocked` / `missing` default | inventory §7.5–7.7 | later F |

### 3.7 Profile G — Risk / neighborhood / scheduling

**Overall status:** `partial`  
**Tension:** chapter mostly non-normative; codecs stricter

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-G-01 | Canonical G artifact field sets + CIDv1 sha2-256 + size limits | codecs; `risk-scheduling.md` weak | **missing** versioned JSON Schema | `profile_g.py` (+ TS/Go/Rust) | `profile_g_artifacts_valid.json`, `profile_g_protocol_valid.json` | `profile_g_*_invalid.json` | accelerate `risk_scheduler`, `profile_g_transport`; kit coordination | `test_profile_g_codec.py`, multi-lang codec tests | `partial` (canonical + structural) | inventory §8; BASE suites green | MCPP-066 |
| REQ-G-02 | Signature / signature_alg on RiskEvidence / Neighborhood* **verified** | codec fields exist | — | **strings only; no verify** | valid vectors | forged attestation | — | — | `structural-only` | inventory §8.3–8.4 | MCPP-067… |
| REQ-G-03 | Neighborhood agreement is coordination / majority approval, **not BFT** | plan KD-11; chapter | — | — | — | BFT labeling | accelerate/kit | three-peer docs | `partial` (documented) | inventory §8.3 | MCPP-066 |
| REQ-G-04 | Stale fenced completion rejected | plan gate 18 | — | — | — | stale fence accepted | planned | three-peer | `missing` forest-wide | inventory §8.6 | MCPP-069 |
| REQ-G-05 | Three peers converge after partition heals; exactly one exclusive completion | plan gates 19–20 | — | — | `profile_g_three_peer.json` | split-brain dual complete | accelerate three-peer harness | `test_profile_g_three_peer.py` | `partial` | inventory §8.2 | MCPP-068…069 |
| REQ-G-06 | One normative Profile G reconciling registry, chapter, codecs, harness | plan G130 | — | — | — | — | — | — | `missing` | inventory §8.1 | MCPP-066 |

### 3.8 Profile H — x402 payments (payment ≠ authorization)

**Overall status:** `partial` (strongest schema/codec maturity)  
**Critical boundary:** payment authority must not become execution authority

| req_id | requirement | spec | schema | validator | pos_vector | neg_vector | runtime | integration | status | evidence | next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-H-01 | Versioned Profile H schemas + canonical codec (DAG-JSON, CID, amount canonicity) | `x402-payments.md` | `schemas/profile-h/1.0/{artifacts,common,x402-v2}.schema.json` | `profile_h.py` / TS `profileH.ts` | `profile_h_artifacts_valid.json`, `profile_h_transport_valid.json` | `profile_h_invalid.json` | accelerate/datasets/kit/SwissKnife profile_h modules | `test_profile_h_codec.py` | `partial` | inventory §9; BASE green | MCPP-070 |
| REQ-H-02 | Codec does **not** claim wallet/crypto verify | H codec docstring | H schemas | explicit non-crypto | valid wire | — | seller-side deferred | — | `structural-only` at crypto level (honest) | inventory §9.4–9.5 | keep honest |
| REQ-H-03 | Payment success MUST NOT authorize execution when C/D deny | plan gate 23; H normative | H schemas | — | paid + authorized | **paid + denied** must fail closed | accelerate seller dispatch separates payment from effect | adversarial suite planned | `partial` | inventory §9.7 | MCPP-070…072 |
| REQ-H-04 | Full upstream x402 HTTP v2 interop certification | guidance | x402-v2 schema | — | — | — | kit `profile_h_http` partial | — | `partial` / external | inventory §9.7 | optional |
| REQ-H-05 | Four-language complete H codec parity | G040 style | H schemas | Py/TS strong; Go/Rust weaker | H vectors | H invalid | — | BASE-GO/RS still exercise validators broadly | `partial` | inventory §9.7 | MCPP-028/H lane |
| REQ-H-06 | kit Profile H test suite collectable and green | runtime readiness | — | — | — | — | kit profile_h import broken at baseline (`CallbackFacilitator`) | MCPP-008 fail | `blocked` (collection ImportError) | `baseline/ipfs-kit-mcplusplus.json` | kit repair before H admission |

---

## 4. Acceptance-gate rollup (plan §10)

Status here is the **current-tree** disposition imported from baseline + inventory. None of these gates are release-complete.

| Gate | Claim (abbreviated) | status | evidence | blocking work |
| --- | --- | --- | --- | --- |
| 1 | Tests baselined; no user changes lost | `partial` | MCPP-001 overlay; MCPP-002…009 receipts (several red) | repair runtime suites without discarding overlays |
| 2 | Abstract profiles separated from MCP bindings | `missing` | inventory + plan G030 | MCPP-019…023 |
| 3 | Current binding follows MCP 2026-07-28 | `missing` | official-mcp-a2a (verified text only) | MCPP-021 |
| 4 | Current binding not initialize-based | `missing` | official-mcp-a2a §2.2 | MCPP-021 |
| 5 | Legacy binding still passes | `partial` | `initialize_result.json` + legacy runtimes | MCPP-020 |
| 6 | A2A extension + E2E handoff | `missing` | URI only in MCPP-010 | MCPP-054…057 |
| 7 | Envelope@1 family | `missing` | inventory B | MCPP-030 |
| 8 | StateRef@1 modes | `missing` | plan G060 | MCPP-035 |
| 9 | B/G adapt without CID breakage | `partial` | no Envelope adapters yet | MCPP-031 |
| 10 | Single-authority restart tests | `missing` | — | MCPP-037, MCPP-052 |
| 11 | CRDT convergence tests | `missing` | — | MCPP-038 |
| 12 | Consensus labeling accurate | `partial` | inventory G + KD-11 | MCPP-066 |
| 13 | Real crypto delegation verification | `partial` | kit implemented; 4-lang structural | MCPP-041…044 |
| 14 | Attenuation/exp/revocation/audience/replay negatives | `partial` | kit; not 4-lang | MCPP-042…044 |
| 15 | Signed cross-trust receipts independently verifiable | `structural-only` | B validators presence-only | MCPP-045 |
| 16 | Temporal obligations lifecycle + deadlines | `partial` | engines partial; suite missing | MCPP-048…049 |
| 17 | Durable executor crash recovery | `missing` | — | MCPP-050…053 |
| 18 | Profile G rejects stale fenced completion | `missing` | inventory §8.6 | MCPP-069 |
| 19 | Three peers converge after partition | `partial` | harness exists | MCPP-068…069 |
| 20 | Exactly one exclusive completion | `partial` | not forest-proven | MCPP-069 |
| 21 | P2P abuse/framing tests | `partial` | structural + some runtime | MCPP-063…065 |
| 22 | Confidential artifacts no plaintext leak | `missing` | — | MCPP-073…074 |
| 23 | Profile H payment ≠ authorization | `partial` | spec+codec honest; adversarial incomplete | MCPP-070…072 |
| 24 | Cross-language canonical bytes/CID/sig match | `partial` | suites green; JCS id + Kubo identity incomplete | MCPP-024…028 |
| 25 | One-command three-peer demo | `missing` | — | MCPP-075…077 |
| 26 | Separate verifier process on evidence bundle | `missing` | — | MCPP-076…077 |
| 27 | Static docs match CI evidence | `missing` | inventory §10 contradictions | MCPP-078…080 |
| 28 | Required CI workflows green | `missing` | not yet in program evidence | MCPP-079…080 |

---

## 5. Explicit non-promotions (schema / coverage are not implementation)

The following **must not** be read as `implemented` for security or production claims:

| Observation | Correct status | Why |
| --- | --- | --- |
| Profile C/D four-language validators green (323/223/211/191) | `structural-only` at crypto/policy levels | Field presence ≠ signatures / deontic evaluation |
| Profile H JSON Schema accepts payment objects | `partial` / structural for crypto | Schema acceptance ≠ settlement or authorization |
| `cid_artifacts` sets `signed=True` when signature field exists | `structural-only` | No cryptographic verify |
| Profile G codec requires `signature` string | `structural-only` | No attestation verify |
| `simulated_groth16` proof-shaped JSON | not `proof-verified` | Plan §11; inventory §7.5 |
| Docs under `docs/testing/*100*`, `COVERAGE_100*`, SwissKnife PASS matrix | **not evidence** | inventory §10 |
| datasets `-k mcplusplus` empty selection | `missing` committed suite | MCPP-007 |
| kit collection ImportError | `blocked` / `partial` suite | MCPP-008 |
| SwissKnife 39 UCAN test failures under crypto mock | `partial` | MCPP-009 |

---

## 6. Profile overall status summary

| Profile | Overall status | Dominant level today | Highest honest crypto/policy note |
| --- | --- | --- | --- |
| A MCP-IDL | `partial` | structural / partial canonical | N/A (integrity, not authority crypto) |
| B CID-native | `partial` | structural | receipt-signed **not** achieved |
| C UCAN | `partial` | validators structural-only; kit crypto **implemented** locally | forest cryptographic enforcement **partial** (real verifiers found) |
| D Policy | `partial` | validators structural-only; runtimes partial policy-enforced | not policy-enforced forest-wide |
| E P2P | `partial` | structural + partial framing | peer identity ≠ authority |
| F Event DAG / ZK | `partial` | structural; ZK simulated | proof-verified **blocked**/missing default |
| G Risk / neighborhood | `partial` | structural + partial canonical codec | signatures structural-only; not BFT |
| H x402 | `partial` | structural + canonical + versioned schema | payment≠auth needs adversarial suite; kit H suite blocked |

---

## 7. Downstream update protocol

When a later task changes a requirement’s evidence:

1. Re-run the task’s validation command on the bound worktree.
2. Record the command, SHA, and artifact under `docs/reports/mcplusplus-1.0-gap-closure/`.
3. Update the corresponding `REQ-*` row status using the §0.1 vocabulary only.
4. Never upgrade solely because a schema, fixture, or coverage percentage improved.
5. Prefer `partial`, `structural-only`, `missing`, or `blocked` over an unearned `implemented`.

Suggested first consumers: MCPP-013…018 (ADRs), MCPP-019…029 (bindings + JCS), MCPP-030…045 (envelope/state/crypto), MCPP-070…072 (H adversarial), MCPP-078…083 (report/RC).

---

## 8. Acceptance for MCPP-012

| Criterion | Result |
| --- | --- |
| Every normative requirement maps to spec, schema, validator, positive vector, negative vector, runtime, integration test, status, evidence path | **Yes** — §§2–4 rows use `RequirementTraceRow@1` columns (absent artifacts listed as `—` / `missing`, not invented) |
| Status values are exactly `implemented`, `partial`, `structural-only`, `missing`, or `blocked` | **Yes** |
| No row is `implemented` merely because a schema accepts its fields | **Yes** — H schemas remain non-implemented for crypto/auth; C/D validators structural-only; B signature presence structural-only |
| Baseline receipts + profile inventory + official MCP/A2A imported | **Yes** — §1 and evidence columns |
| Contradictory 100% coverage docs not used as promotion evidence | **Yes** — §5 and inventory §10 |

**End of RequirementTraceRow@1 matrix for MCPP-012.**
