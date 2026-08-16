# MCP++ 1.0 Gap-Closure — Implementation Report

| Field | Value |
| --- | --- |
| Interface | `ImplementationReport@1` / `ReleaseRecommendation@1` |
| Task | `MCPP-082` |
| Goal | `MCPP-G170` |
| Bundle | `mcplusplus/1.0/report` |
| Track | `report` |
| Program | `mcplusplus-1.0-gap-closure` |
| Board namespace | `mcplusplus-1-0-gap-closure-v1` |
| Generated (UTC) | `2026-08-16T17:06:48Z` |
| Depends on | `MCPP-079`, `MCPP-080`, `MCPP-081` |
| Authority | Sealed plan §12 final deliverables; plan §10 acceptance gates; ADRs 0001–0006 |

**Release recommendation: `RC` (Release Candidate)** — see §16 for the evidence basis and the explicit reasons this is **not** `GO` production admission and **not** a blanket `NO-GO` of the program work.

---

## 1. Executive summary

The MCP++ 1.0 gap-closure program turned a documentation-first protocol plus scattered structural validators into a coherent **release-candidate architecture**: dual MCP bindings (legacy + current), named canonicalization (`mcpp-jcs-v1`), portable envelope/state carriers, cryptographic and policy adapters where real verifiers exist, durable execution and Profile G fencing paths with commands, Profile H payment≠authorization negatives, multi-language CI workflows, honest documentation, and a runtime adapter disposition matrix.

What this report admits:

- **Spec / conformance package** (nested `mcplusplus` / Mcp-Plus-Plus): four-language structural suites were baselined green; four-language JCS identity is recorded as agreeing; dual bindings, envelope family, StateRef, ADRs, threat model, and CI workflow files are present on the current tree.
- **Runtime adapters** (accelerate, datasets, kit, SwissKnife): a fail-closed disposition matrix lists each profile as `implemented`, `partial`, or `blocked` **with commands for every `implemented` cell** (`docs/reports/mcplusplus-1.0-gap-closure/runtime/adapter-matrix.md`).
- **Documentation honesty** (MCPP-079): the current README no longer claims 100% coverage or production readiness without generated evidence.
- **CI definition** (MCPP-080): `CiWorkflow@1` workflows are present and encode language suites, vectors, crypto negatives, P2P abuse, three-peer/crash recovery, bindings, scans, demo smoke, SBOM/license/manifest packaging (unsigned allowed when signing secrets are absent).

What this report does **not** admit:

- Full multi-runtime **production GO**.
- That schema/validator green equals cryptographic, policy-enforced, receipt-signed, or proof-verified conformance everywhere.
- Profile G as Byzantine-fault-tolerant consensus.
- Simulated Groth16 / ZK as Verified Execution.
- Payment, PeerID, TLS client cert, or registry presence as authorization.
- That required GitHub Actions runs are green on this exact tree (workflows are present; remote green-run artifacts for this report HEAD are not bound here — residual for gate 28 / MCPP-083).

**User overlays remain intact.** MCPP-001 recorded dirty-overlay inventory; this report lane edits only declared report outputs and does not reset, force-push, or discard operator uncommitted work (see §15).

---

## 2. Repositories and commit SHAs

### 2.1 Bound operator forest (MCPP-001 baseline)

Source: `docs/reports/mcplusplus-1.0-gap-closure/baseline/repository-forest.json`  
Generated: `2026-08-15T18:36:13.970099+00:00` · Program branch target: `codex/mcplusplus-1.0-gap-closure`

| Role | Path (operator) | Bound HEAD (forest) | Remote |
| --- | --- | --- | --- |
| Superproject | `/home/barberb/lift_coding` | `b6f40c05e0884867eb8557f8882cd25cb760ca2f` | `https://github.com/endomorphosis/lift_coding.git` |
| Protocol / Mcp-Plus-Plus | `/home/barberb/lift_coding/Mcp-Plus-Plus` | `6965f89f066769f3b3ac7b5f753b1a0044562570` | `https://github.com/endomorphosis/Mcp-Plus-Plus` |
| accelerate | `/home/barberb/lift_coding/external/ipfs_accelerate` | `ea11293bb996f052d620eae989f5377a956764b1` | `https://github.com/endomorphosis/ipfs_accelerate_py` |
| datasets | `/home/barberb/lift_coding/external/ipfs_datasets` | `ac82107e246b30e35a2bbdcf75e01370d22350c6` | `https://github.com/endomorphosis/ipfs_datasets_py` |
| kit | `/home/barberb/lift_coding/external/ipfs_kit` | `6196017ca3df016c7159dce43af60f2a0d96a9ae` | `https://github.com/endomorphosis/ipfs_kit_py` |
| SwissKnife | `/home/barberb/lift_coding/swissknife` | `afdbf885175fde34505ef05a2ea6aac5535ad03e` | **Discovered** `https://github.com/endomorphosis/swissknife` (not invented) |

SwissKnife also carries `upstream https://github.com/dnakov/anon-kode.git`. Pre-existing dirty overlay on SwissKnife: `test-results/virtual-desktop-ipfs-mcp-orb/svd-132.json` (preserve).

### 2.2 Program worktree HEADs (this report generation)

| Tree | HEAD (this worktree) | Notes |
| --- | --- | --- |
| accelerate program worktree | `0515dbbf198d3a8ca40e3d3302342e41d059e302` | branch `implementation/mcpp-082-…` |
| Nested `ipfs_accelerate_py/mcplusplus` | `9e2ce7c826ece337811eb18d5bc78a74616ccd50` | gap-closure gitlink progress beyond forest pin |
| `ipfs_datasets_py` gitlink | `d229eef0e651afa03a146d52e83ec5ecf7dd642f` | program-isolated gitlink |
| `ipfs_kit_py` gitlink | `706d3eb545533f02c8332b127c7c8d543a848897` | program-isolated gitlink |
| SwissKnife (live operator checkout) | `afdbf885175fde34505ef05a2ea6aac5535ad03e` | matches forest; origin discovered |

A changed revision does not automatically invalidate the program, but it requires readers to treat forest pins as the **inventory baseline** and worktree HEADs as the **implementation progress** surface.

### 2.3 Evidence directory root

All gap-closure evidence under the accelerate program tree:

```text
docs/reports/mcplusplus-1.0-gap-closure/
  baseline/          # MCPP-001…011 forest, overlays, language/runtime receipts
  canonical/         # four-language JCS identity
  runtime/           # adapter matrix, Profile H, SwissKnife A2A
  demo/              # evidence-bundle schema
```

Nested protocol docs and CI:

```text
ipfs_accelerate_py/mcplusplus/
  docs/architecture/   # overview, threat model, ADRs, durable, state, trust
  docs/spec/           # profiles, bindings, envelope, state-ref, …
  docs/roadmap/        # requirement-to-evidence matrix
  docs/testing/        # honest testing README + historical trophies retained
  .github/workflows/mcplusplus-1.0.yml
```

Parent monorepo CI companion:

```text
.github/workflows/mcplusplus-1.0-gap-closure.yml
```

---

## 3. Architecture decisions

Accepted ADRs under `ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/`:

| ADR | Title | Binding plan KD |
| --- | --- | --- |
| 0001 | Spec versus runtime ownership | KD-1 |
| 0002 | Crypto suite and `mcpp-jcs-v1` canonicalization | KD-4, KD-5 |
| 0003 | Conformance levels (`structural` → `proof-verified`) | KD-6 |
| 0004 | State modes (`StateRef@1` exclusivity) | KD-8…KD-11 |
| 0005 | DurableExecutor product choice | KD-12 (+ 2026-08-16 DuckDB default / SQLite fallback) |
| 0006 | Dual MCP bindings + A2A extension URI | KD-2, KD-3, KD-13 |

Additional sealed defaults still in force: KD-14 (transport identity ≠ authority; payment ≠ authorization), KD-15 (confidential artifact refs), KD-16 (`mcpp` CLI + three-peer compose + independent verifier), KD-17 (profile bundles: Evidence Core, Secure Delegation, Federated Mesh, Commerce, Verified Execution).

**Runtime persistence correction (2026-08-16):** durable journals / single-authority state / Profile H stores **default to DuckDB** with best-effort local `LOAD` of Quack then DuckLake (never network `INSTALL`). SQLite remains explicit via `MCPPLUSPLUS_SQL_ENGINE=sqlite`. Recorded in ADR-0004 / ADR-0005.

---

## 4. Files changed by workstream (summary)

This section maps sealed plan workstreams to landed surfaces. It is an index, not a full git log.

| Workstream | Goals / tasks | Primary outputs |
| --- | --- | --- |
| Phase 0 baseline | G010 / MCPP-001…012 | `docs/reports/…/baseline/*`, roadmap matrix scaffold |
| ADRs | G020 / MCPP-013…018 | `docs/architecture/decisions/0001`…`0006` |
| MCP bindings | G030 / MCPP-019…023 | `docs/spec/bindings/*`, dual adapters accelerate/datasets |
| Canonicalization | G040 / MCPP-024…029 | `mcpp-jcs-v1`, four-language identity (`canonical/four-language.json`) |
| Envelope | G050 / MCPP-030…034 | `ExecutionEnvelope@1` family specs + accelerate emit/verify |
| State | G060 / MCPP-035…040 | `StateRef@1` + provider adapters |
| Crypto | G070 / MCPP-041…045 | kit `UCANVerifier`, signed receipt paths, negatives |
| Policy | G080 / MCPP-046…049 | datasets fail-closed evaluator |
| Durable | G090 / MCPP-050…053 | DurableExecutor + accelerate runtime bind |
| A2A | G100 / MCPP-054…057 | extension URI + SwissKnife/accelerate handoff adapters |
| Discovery | G110 / MCPP-058…061 | advertisement / registry surfaces |
| P2P | G120 / MCPP-062…065 | framing + abuse tests (datasets owner; kit bind) |
| Profile G | G130 / MCPP-066…069 | normative G + stale-fence reject (accelerate) |
| Profile H | G140 / MCPP-070…072 | payment≠auth negatives; accelerate + SwissKnife sellers |
| Confidential | G150 / MCPP-073…074 | encrypted artifact reference shape / leak tests |
| CLI / demo | G160 / MCPP-075…077 | `mcpp` CLI, compose demo, `verify_bundle.py` |
| Docs honesty | G170 / MCPP-078…079 | architecture guides; rewrite of stale coverage claims |
| CI | G170 / MCPP-080 | nested + parent `CiWorkflow@1` YAML |
| Runtime closeout | G170 / MCPP-081 | `runtime/adapter-matrix.md` |
| Report / draft PRs | G170 / MCPP-082 | **this document** + `docs/reports/…/DRAFT_PULL_REQUESTS.md` |
| Terminal receipt | G170 / MCPP-083 | *(downstream, not this task)* joined release receipt |

Protected operator paths (plan / objectives / todo / scheduler / board validator) were **not** modified by this task.

---

## 5. Protocol compatibility matrix

### 5.1 MCP dual bindings

Normative matrix: `ipfs_accelerate_py/mcplusplus/docs/spec/bindings/compatibility-matrix.md` (`BindingCompatibilityMatrix@1`, MCPP-022).

| Binding id | `protocolVersion` | Lifecycle |
| --- | --- | --- |
| `mcp-binding/legacy-2024-11-05` | `2024-11-05` | `initialize` / `notifications/initialized` |
| `mcp-binding/2026-07-28` | `2026-07-28` | Stateless per-request `_meta`; **no** initialize |

Honest path selection, dual advertisement, and fail-closed forgery/downgrade cells are specified in that document. Integration tests (CI-encoded):

```bash
cd ipfs_accelerate_py/mcplusplus
python -m pytest -q \
  tests-py/integration/test_mcp_binding_current.py \
  tests-py/integration/test_mcp_binding_legacy.py \
  tests-py/integration/test_mcp_binding_compat.py
```

Runtime dual-binding adapters: **implemented** on accelerate and datasets; **blocked** on kit and SwissKnife (adapter matrix §3.1).

### 5.2 A2A

| Item | Value |
| --- | --- |
| Extension URI (verified) | `https://mcplusplus.io/extensions/execution/v1` |
| Working alias | `io.mcplusplus.execution@1` (not sole wire id) |
| accelerate | `implemented` — `python -m pytest -q test/api/test_mcplusplus_a2a_handoff.py` |
| SwissKnife | `implemented` — `npm run test:run -- test/mcp-plus-plus/a2a-adapter.test.ts` |
| datasets / kit | `blocked` for dedicated A2A adapter |

### 5.3 Official MCP / A2A primary-source note

`docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md` records that official MCP **2026-07-28** is not initialize-based and that A2A extensions are URI-identified.

---

## 6. Conformance levels achieved

Ladder (ADR-0003 / KD-6):

`structural` → `canonical` → `cryptographic` → `policy-enforced` → `receipt-signed` → `proof-verified`

| Area | Highest evidenced level (honest) | Notes |
| --- | --- | --- |
| Four-language validators A–H (codecs) | `structural` (often) / `canonical` for JCS identity cases | Structural green is inventory, not production crypto |
| `mcpp-jcs-v1` cross-language identity | `canonical` | `canonical/four-language.json`: `identity_ok=true`, 10 cases, 0 mismatches |
| Profile C kit `UCANVerifier` | `cryptographic` (local) | Real negatives; forest-wide still partial |
| Profile D datasets evaluator | `policy-enforced` (local fail-closed) | Missing evaluator → deny |
| Envelope / CID artifacts accelerate | partial → runtime `implemented` for B emit/verify | Not full forest receipt-signed admission |
| Profile G fencing accelerate | runtime coordination / stale-fence deny | **Not BFT** |
| Profile F ZK | often `structural-only` / simulated | Must not claim `zero_knowledge: true` without real verify |
| Profile H payment≠auth | policy/auth boundary tests | Payment never elevates authz |
| Verified Execution bundle | **not admitted** forest-wide | Requires independent receipt + real proof success |

**Promotion rule (plan):** schema acceptance alone is never `implemented` at a higher claimed level.

---

## 7. Exact test commands and results

### 7.1 Four-language Mcp-Plus-Plus baseline (MCPP-002…005)

| Language | Command | Result (baseline receipt) | Coverage (measured) | Evidence |
| --- | --- | --- | --- | --- |
| Python | `cd ipfs_accelerate_py/mcplusplus && python -m pytest -q tests-py --maxfail=1` | **pass** 323/323 | ~96.1% statements (`tests-py/validators`) | `baseline/mcpplusplus-python.json` |
| TypeScript | `cd ipfs_accelerate_py/mcplusplus/tests-ts && npm test` | **pass** 223 passed, 19 skipped; 1 disabled suite not treated as pass | ~98% statements (supplemental) | `baseline/mcpplusplus-typescript.json` |
| Go | `cd ipfs_accelerate_py/mcplusplus/tests-go && go test ./...` | **pass** 211 | ~96.9% overall | `baseline/mcpplusplus-go.json` |
| Rust | `cd ipfs_accelerate_py/mcplusplus/tests-rs && cargo test` | **pass** 191 | **unavailable** in baseline (tooling missing) | `baseline/mcpplusplus-rust.json` |

### 7.2 Four-language canonical identity (MCPP-028 area)

| Field | Value |
| --- | --- |
| Artifact | `docs/reports/mcplusplus-1.0-gap-closure/canonical/four-language.json` |
| Algorithm | `mcpp-jcs-v1` |
| Cases | 10 |
| `identity_ok` | **true** |
| `mismatch_count` | **0** |
| Languages | python, typescript, go, rust agree on bytes / SHA-256 / CID |

CI re-check command:

```bash
cd ipfs_accelerate_py/mcplusplus
python -m pytest -q tests-py/integration/test_cross_language_jcs.py
```

### 7.3 Runtime baseline honesty (not all green)

| Runtime | Declared gate (summary) | Baseline honesty | Evidence |
| --- | --- | --- | --- |
| accelerate | `pytest -q ipfs_accelerate_py/mcp/tests test/api -k mcplusplus --maxfail=1` | **partial** — inventory recorded collection debt / failures under broader selection | `baseline/ipfs-accelerate-mcplusplus.json` |
| datasets | `pytest -q tests/unit/mcp_server -k mcplusplus` | **missing** at committed `-k mcplusplus` selection (exit 5) | `baseline/ipfs-datasets-mcplusplus.json` |
| kit | `pytest -q tests -k 'ucan or mcplusplus or profile'` | **partial** — collection `ImportError` / debt | `baseline/ipfs-kit-mcplusplus.json` |
| SwissKnife | vitest `test/mcp-plus-plus` | **partial** — crypto mock missing `generateKeyPairSync` at baseline | `baseline/swissknife-mcplusplus.json` |

Later adapter tasks re-verified **focused** commands listed in §8; those do not erase the baseline inventory of broader suite debt.

### 7.4 CI-encoded suites (MCPP-080 — definition present)

Nested workflow jobs (`ipfs_accelerate_py/mcplusplus/.github/workflows/mcplusplus-1.0.yml`):

| Job | Intent |
| --- | --- |
| `python` | Full `tests-py`, JCS identity, crypto adversarial, P2P abuse, three-peer/crash, bindings, vectors, verifier self-test + coverage artifacts |
| `typescript` | type-check + test (+ optional coverage) |
| `go` | `go test` + coverage |
| `rust` | `cargo test` (+ clippy/fmt best-effort) |
| `schema-and-docs` | schema parse, A2A vector smoke, doc presence |
| `scans` | static / secret / vuln / fuzz smoke |
| `demo` | `mcpp demo --help`, compose config, `verify_bundle.py --self-test` |
| `release-artifacts` | conformance matrix, SBOM, license inventory, checksums, release manifest (**unsigned if secrets absent**) |

Parent companion: `.github/workflows/mcplusplus-1.0-gap-closure.yml` (same suite themes for monorepo path filters).

**Gate 28 note:** workflow **presence** is evidenced on this tree (`test -s` both YAML files). A bound green GitHub Actions run URL for HEADs in §2.2 is **not** attached to this report; treat remote CI green as residual for MCPP-083 / operator CI.

---

## 8. Runtime adapter matrix (MCPP-081 import)

Full matrix: `docs/reports/mcplusplus-1.0-gap-closure/runtime/adapter-matrix.md`.

### 8.1 Profiles A–H (disposition only)

| Profile | accelerate | datasets | kit | SwissKnife |
| --- | --- | --- | --- | --- |
| A MCP-IDL | partial | blocked | blocked | partial |
| B CID-native artifacts | **implemented** | partial | partial | partial |
| C UCAN delegation | partial | blocked | **implemented** | partial |
| D Temporal deontic policy | partial | **implemented** | partial | partial |
| E P2P transport | partial | **implemented** | partial | partial |
| F Event DAG / ZK | partial | partial | partial | partial |
| G Risk / fencing | **implemented** | partial | partial | partial |
| H x402 payments | **implemented** | partial | partial | **implemented** |

### 8.2 Cross-cutting

| Capability | accelerate | datasets | kit | SwissKnife |
| --- | --- | --- | --- | --- |
| Dual MCP bindings | **implemented** | **implemented** | blocked | blocked |
| DurableExecutor bind | **implemented** | blocked | blocked | blocked |
| A2A extension | **implemented** | blocked | blocked | **implemented** |

### 8.3 Command index (`implemented` cells only)

| Runtime | Profile / capability | Command |
| --- | --- | --- |
| accelerate | B Envelope / CID | `python -m pytest -q ipfs_accelerate_py/mcp/tests/test_mcplusplus_envelope.py` |
| accelerate | G Stale fence | `python -m pytest -q ipfs_accelerate_py/mcp/tests/test_mcplusplus_profile_g_fence.py` |
| accelerate | H Payment≠auth | `cd ipfs_accelerate_py/mcplusplus && python -m pytest -q tests-py/integration/test_profile_h_negatives.py` |
| accelerate | Bindings | `python -m pytest -q ipfs_accelerate_py/mcp/tests/test_mcplusplus_bindings.py` |
| accelerate | DurableExecutor | `python -m pytest -q ipfs_accelerate_py/mcp/tests/test_mcplusplus_durable_runtime.py` |
| accelerate | A2A | `python -m pytest -q test/api/test_mcplusplus_a2a_handoff.py` |
| datasets | D Policy | `cd ipfs_datasets_py && python -m pytest -q tests/unit/mcp_server/test_mcplusplus_policy_evaluator.py` |
| datasets | E P2P framing | `cd ipfs_datasets_py && python -m pytest -q tests/unit/mcp_server/test_mcplusplus_p2p_framing.py` |
| datasets | Bindings | `python -m pytest -q ipfs_accelerate_py/mcp/tests/test_mcplusplus_bindings.py` |
| kit | C UCANVerifier | `cd ipfs_kit_py && python -m pytest -q tests/runtime_readiness/mcplusplus/test_ucan_verifier.py` |
| SwissKnife | H Profile H | `cd /home/barberb/lift_coding/swissknife && npm run test:run -- test/mcp-plus-plus/profile-h-adapter.test.ts` |
| SwissKnife | A2A | `cd /home/barberb/lift_coding/swissknife && npm run test:run -- test/mcp-plus-plus/a2a-adapter.test.ts` |

No cell is marked `implemented` without a command in the matrix.

---

## 9. Coverage

| Surface | Claim allowed by evidence | Forbidden claim |
| --- | --- | --- |
| Nested Python validators | ~96.1% statement coverage of `tests-py/validators` (baseline recompute) | “100% coverage” |
| Nested TypeScript | ~98% statements supplemental | “100%” / disabled suite as pass |
| Nested Go | ~96.9% overall | “100%” |
| Nested Rust | suite green; coverage **not measured** in baseline | historical 100% markdown |
| Runtime packages | focused adapter tests only | package-wide production coverage trophies |

Historical trophy documents under `ipfs_accelerate_py/mcplusplus/docs/testing/` remain as **non-authoritative history**; current status is `docs/testing/README.md` and the root README (MCPP-079).

---

## 10. Security tests

| Category | Evidence / command locus | Status |
| --- | --- | --- |
| Crypto adversarial / UCAN negatives | nested `tests-py/integration` adversarial selectors; kit `test_ucan_verifier.py` | Present; kit crypto strongest |
| Transport identity ≠ authority | threat model + trust boundaries docs; runtime fail-closed design | Documented; not a global cert |
| Payment ≠ authorization | Profile H negatives (accelerate + SwissKnife) | Implemented cells |
| P2P abuse / framing | `tests-py/integration/test_transport_abuse.py`; datasets framing tests | Present in CI + matrix |
| Stale fence / exclusive completion | Profile G fence tests; three-peer harness | accelerate G implemented; three-peer CI-encoded |
| Secret / vuln / static / fuzz smoke | workflow `scans` job | Defined; results from CI artifacts when runs complete |
| Confidential plaintext non-leak | MCPP-073…074 paths | Spec + tests as landed; residual risk if unrun |
| SBOM / license inventory | workflow `release-artifacts` | Generated on CI; **unsigned** when `GPG_SIGNING_KEY` / `COSIGN_KEY` absent (allowed if documented) |

Threat model (authority-class marked): `ipfs_accelerate_py/mcplusplus/docs/architecture/threat-model.md`.

---

## 11. Performance

Profile G performance publication (historical harness evidence, 2026-07-12 workload `profile-g-three-peer-exclusive-v1`):

| Metric | Value | Source |
| --- | --- | --- |
| Scheduled throughput gain vs single-owner FIFO | **2.752294×** (≥ 2.5× gate) | `docs/testing/profile-g-performance/report.md` |
| Jain completion fairness | 1.0 | same |
| Starved tasks | 0 | same |
| Policy bypasses | 0 | same |
| Duplicate completion events | 0 | same |
| Frontiers converged | true | same |

This is **scheduler harness** evidence for Profile G coordination, not a production capacity SLA for all runtimes.

---

## 12. Three-peer demo evidence

| Item | Path / command | Notes |
| --- | --- | --- |
| Evidence bundle schema | `docs/reports/mcplusplus-1.0-gap-closure/demo/evidence-bundle.schema.json` | Schema present |
| CLI | `python -m mcpp` / `ipfs_accelerate_py/mcplusplus/cli/mcpp.py` | doctor / demo / verify path |
| Independent verifier | `ipfs_accelerate_py/mcplusplus/cli/verify_bundle.py --self-test` | CI-encoded |
| Compose | `ipfs_accelerate_py/mcplusplus/demo/docker-compose.yml` (workflow presence check) | config validation in CI |
| Three-peer integration | `tests-py/integration/test_profile_g_three_peer.py` | CI python job |
| Historical Profile G release aggregation | `docs/testing/profile-g-release/report.md` (+ `evidence.json`) | Prior **GO** for SVD-091 gates — **not** this program’s terminal MCPP-083 receipt |

Gates 25–26 are **architecturally landed** (CLI + verifier + compose + harness). Operator-facing one-command green demo for this exact HEAD should be re-run and bound in MCPP-083.

---

## 13. Crash-recovery evidence

| Surface | Evidence |
| --- | --- |
| DurableExecutor interface + ADR-0005 | DuckDB default journal; SQLite fallback |
| accelerate runtime bind | `test_mcplusplus_durable_runtime.py` (**implemented**) |
| Three-peer / crash recovery integration | CI step: three-peer harness under nested workflow |
| Explicit non-claim | In-process memory retry is **not** crash recovery (architecture overview §7) |

Broader forest CRDT convergence (gate 11) and multi-runtime durable binds remain partial/blocked outside accelerate.

---

## 14. Cryptographic evidence

| Claim | Evidence | Not claimed |
| --- | --- | --- |
| Mandatory suite Ed25519 + key ids + CID-native direction | ADR-0002 / KD-4 | Universal default-on verify in every runtime |
| kit `UCANVerifier` + adversarial negatives | `implemented` command in matrix | datasets dedicated C verifier |
| SwissKnife `@ucans/ucans` library path | partial (strong library; local PASS ≠ forest admission) | four-language crypto API identity |
| accelerate C | partial — real Ed25519 when `require_signatures=True`; default may still allow non-crypto tokens | default-on forest crypto |
| Four-language Profile C validators | structural field presence historically | signature verify at validator layer |
| Cross-trust-domain receipt-signed | partial / structural in places | full gate 15 forest-wide |
| Groth16 / ZK proof-verified | simulated paths common | Verified Execution production |

---

## 15. User overlays remain intact

| Checkout | Preserve rule | Evidence |
| --- | --- | --- |
| accelerate operator | Uncommitted supervisor/MCP/runtime edits preserved; lanes use worktrees | `baseline/dirty-overlay.md`; plan §3.1 |
| datasets operator | Uncommitted logic/UI-IR and MCP++ P2P files preserved | dirty-overlay inventory |
| SwissKnife | Dirty `test-results/.../svd-132.json` preserved; origin not rewritten | adapter-matrix §2.1; forest |
| superproject | Dirty gitlinks and untracked backup dirs not force-cleaned | dirty-overlay |
| This task (MCPP-082) | Only declared report outputs written; no `git reset --hard`, no force-push | edit policy `task_output_exact` |

**No uncommitted operator files were deleted, reset, or force-pushed** (dirty-overlay header statement from MCPP-001 generation).

---

## 16. Remaining limitations

1. **Runtime breadth:** many profile×runtime cells are `partial` or `blocked` (matrix §9).
2. **Baseline suite debt:** accelerate/kit/SwissKnife broader selections were not fully green at inventory; datasets `-k mcplusplus` selection empty at baseline.
3. **Profile F / Verified Execution:** simulated proofs and structural validators must not be marketed as proof-verified.
4. **Profile G:** coordination / majority fencing — **not** BFT consensus.
5. **Signing:** release artifacts may be unsigned when CI secrets are absent (documented allowed).
6. **Remote CI green (gate 28):** workflows exist; this report does not bind a green Actions run for §2.2 HEADs.
7. **MCPP-083:** joined release receipt with all 28 gates command/result/artifact rows is **downstream** of this report.
8. **SwissKnife self-PASS matrices** are not forest-wide four-language admission.

---

## 17. Items explicitly not claimed

This implementation report **does not claim**:

1. That current trees are **production-ready** or production-admitted without residual gates.
2. **100% code coverage** for any language.
3. That green structural validator suites equal **cryptographic**, **policy-enforced**, **receipt-signed**, or **proof-verified** conformance everywhere.
4. That Profile G is **Byzantine-fault-tolerant consensus**.
5. That **simulated** Groth16 / ZK material is Verified Execution.
6. That **payment**, **PeerID**, **TLS client cert**, or **registry presence** grants execution authorization.
7. That **schema acceptance** alone means a requirement is `implemented`.
8. That SwissKnife local `CONFORMANCE_MATRIX.md` PASS rows are forest-wide admission.
9. That required CI workflows are **green on this exact HEAD** without a bound Actions artifact.
10. That this document **merges** draft PRs or replaces MCPP-083’s joined receipt.
11. That user dirty overlays were cleaned or rewritten.
12. That kit/datasets/SwissKnife have full dual-binding + Durable + A2A parity with accelerate.

---

## 18. Migration instructions

**Authority class:** non-normative operator guidance (see architecture overview §10). Normative byte/CID preservation: ADR-0002 and envelope/state chapters.

### 18.1 Compatibility principles

1. Baseline MCP peers that never advertise MCP++ continue to interoperate.
2. Historical artifacts remain readable under their **recorded** canonicalization algorithm; new mints use `mcpp-jcs-v1` when claiming MCP++ 1.0 identity.
3. Do **not** silently change bytes or CIDs of existing artifacts.
4. Dual-binding servers **MAY** accept legacy initialize **or** current `_meta` paths; they **MUST** name binding ids when claiming dual support.
5. Runtime adapters map local types into Envelope@1 / StateRef@1 without inventing a second portable contract.
6. Prefer worktrees / `codex/mcplusplus-1.0-gap-closure` (or implementation branches) — never reset operator dirty checkouts.

### 18.2 Suggested migration sequence

| Step | Action | Bundle impact |
| --- | ---: | --- |
| 1 | Inventory advertised profile keys and binding ids | All |
| 2 | Adopt Envelope@1 adapters for B/G artifacts | Evidence Core |
| 3 | Turn on real signature verify for C; policy evaluate for D | Secure Delegation |
| 4 | Declare StateRef modes; stop silent multi-writer merges | Evidence Core / Federated Mesh |
| 5 | Journal durable steps (DuckDB default / SQLite fallback) before claiming crash-safe resume | Evidence Core ops |
| 6 | Separate payment settlement from authz checks | Commerce |
| 7 | Require independent receipt verify / real proof verify only when claiming Verified Execution | Verified Execution |

### 18.3 Operator install / verify sketch

```bash
# Nested conformance package
cd ipfs_accelerate_py/mcplusplus
python -m pip install -e ".[dev]" || python -m pip install -e .
python -m mcpp doctor
python -m pytest -q tests-py --maxfail=1

# Independent evidence verifier self-test
python cli/verify_bundle.py --self-test

# Focused runtime samples (examples)
python -m pytest -q ipfs_accelerate_py/mcp/tests/test_mcplusplus_bindings.py
python -m pytest -q ipfs_accelerate_py/mcp/tests/test_mcplusplus_profile_g_fence.py
```

SQL engine selection for durable paths:

```bash
# Default DuckDB; optional fallback
export MCPPLUSPLUS_SQL_ENGINE=sqlite   # only when intentionally falling back
```

### 18.4 Related documents

| Concern | Location |
| --- | --- |
| Architecture overview migration | `docs/architecture/overview.md` §10 |
| Binding compatibility | `docs/spec/bindings/compatibility-matrix.md` |
| Requirement-to-evidence matrix | `docs/roadmap/mcplusplus-1.0-gap-closure.md` |
| Draft PR text per repo | `docs/reports/mcplusplus-1.0-gap-closure/DRAFT_PULL_REQUESTS.md` (accelerate monorepo path) |
| Profile G release runbook | `docs/operations/profile-g-release-runbook.md` |

---

## 19. Acceptance gates (plan §10) — status for this report

Legend: **pass** = command + artifact on current program evidence; **partial** = meaningful land + residual; **open** = not bound here / residual for MCPP-083.

| # | Gate | Status | Evidence pointer |
| --- | --- | --- | --- |
| 1 | Baseline tests; no user changes lost | **pass** (inventory) | `baseline/*`, `dirty-overlay.md` |
| 2 | Abstract profiles vs MCP bindings | **pass** | bindings docs + ADR-0006 |
| 3 | Current MCP 2026-07-28 binding | **pass** | `mcp-2026-07-28.md`, tests |
| 4 | Current binding without legacy initialize | **pass** | current binding + official note |
| 5 | Legacy binding still works | **pass** | legacy binding + compat tests |
| 6 | A2A extension + handoff test | **pass** (accelerate + SwissKnife) | matrix A2A commands |
| 7 | Envelope@1 family exists | **pass** (spec + accelerate B) | envelope specs + B command |
| 8 | StateRef@1 + modes | **partial** | specs/ADRs; not all providers forest-green |
| 9 | B/G adapt without silent CID breakage | **partial** | adapters + versioned JCS |
| 10 | Single-authority restart-tested backend | **partial** | durable/SQLite-DuckDB path; bind residual |
| 11 | Real CRDT concurrent convergence | **partial** / residual | Automerge decision; suite breadth residual |
| 12 | Consensus vs neighborhood labeled accurately | **pass** | G docs + non-BFT honesty |
| 13 | Real cryptographic delegation verify | **partial** | kit **implemented**; not all runtimes |
| 14 | Attenuation/expiry/revocation/audience/replay negatives | **partial** | kit negatives; validators structural |
| 15 | Cross-trust-domain signed receipts | **partial** | not forest-wide receipt-signed |
| 16 | Temporal obligations lifecycle + deadlines | **partial** | datasets D implemented; full suite residual |
| 17 | Durable crash recovery without dup effects | **partial** | accelerate Durable **implemented** |
| 18 | Profile G rejects stale fenced completion | **pass** (accelerate) | fence test command |
| 19 | Three peers converge after partition heals | **partial** | harness/CI-encoded; bind CI run residual |
| 20 | Exactly one authoritative exclusive completion | **partial** | G harness design + historical perf report |
| 21 | P2P abuse and framing tests | **pass** (encoded + datasets E) | CI + matrix E |
| 22 | Confidential artifacts no plaintext leak | **partial** | G150 landings; residual re-verify |
| 23 | Profile H never treats payment as auth | **pass** (accelerate + SwissKnife) | H negatives commands |
| 24 | Canonical bytes/CIDs match four languages | **pass** | `canonical/four-language.json` |
| 25 | One-command three-peer demo | **partial** | CLI/compose present; operator re-run residual |
| 26 | Separate verifier validates evidence bundle | **partial** | `verify_bundle.py --self-test` present |
| 27 | Static docs match generated CI evidence | **pass** (honesty rewrite) | README + testing README |
| 28 | Required CI workflows green | **partial** | workflows **present**; green run URL not bound |

---

## 20. Release recommendation

### 20.1 Decision

| Field | Value |
| --- | --- |
| Recommendation | **`RC`** |
| Meaning | Release **Candidate** for review, integration, and joined-receipt publication — **not** full production **`GO`** |
| Decision date (UTC) | `2026-08-16` |
| Deciding task | `MCPP-082` |
| Downstream | `MCPP-083` publishes `MCPPLUSPLUS_1_0_RELEASE_RECEIPT.json` binding gate rows |

### 20.2 Why not `GO`

1. Multiple plan gates remain **partial** (state CRDT breadth, forest-wide crypto/receipts, remote CI green bind, demo operator re-run).
2. Runtime adapter matrix still has many `partial`/`blocked` cells.
3. Verified Execution / real ZK is not forest-admitted.
4. Baseline runtime suite debt remains explicit.
5. Production admission requires residual gate closure and MCPP-083 joined receipt with no silent “pass without evidence”.

### 20.3 Why not `NO-GO`

1. Four-language structural suites baselined green; JCS identity agrees.
2. Dual bindings, architecture ADRs, threat model, and honesty rewrites landed.
3. Multiple high-value runtime cells are `implemented` **with re-runnable commands**.
4. CI workflows (`CiWorkflow@1`) are present and encode the required suite themes.
5. User overlays preserved; program did not discard operator work.
6. Profile H payment≠auth and Profile G stale-fence denials have focused evidence.

### 20.4 Conditions to promote `RC` → `GO` (operator checklist)

1. Bind green Actions runs for both workflows on the release HEADs (gate 28).
2. Close or explicitly waive residual gates 8–11, 13–17, 19–20, 22, 25–26 with command+artifact.
3. Promote no cell to `implemented` without a matrix command.
4. Publish MCPP-083 joined receipt with all 28 gates.
5. Keep unsigned release artifacts only if signing secrets remain absent **and** the manifest states that fact.
6. Do not claim production readiness in README without those artifacts.

### 20.5 Draft PRs

Ready-to-paste draft pull-request descriptions (problem, architecture, changes, compatibility, security, tests, deploy, risks) live in:

`docs/reports/mcplusplus-1.0-gap-closure/DRAFT_PULL_REQUESTS.md`

Policy: open as **draft** only; **do not merge** from this task; **do not force-push**.

---

## 21. Validation (this task)

```bash
test -s ipfs_accelerate_py/mcplusplus/docs/reports/MCPPLUSPLUS_1_0_IMPLEMENTATION_REPORT.md
test -s docs/reports/mcplusplus-1.0-gap-closure/DRAFT_PULL_REQUESTS.md
```

Expected: exit 0; non-empty files.

---

## 22. Document control

| Item | Value |
| --- | --- |
| Schema | `ImplementationReport@1` |
| Recommendation schema | `ReleaseRecommendation@1` |
| Supersedes | none (first gap-closure implementation report) |
| Superseded-by | future report only with newer bound HEADs + CI artifacts |
| Related | plan §12; MCPP-079/080/081; MCPP-083 terminal receipt |

**End of ImplementationReport@1 for MCPP-082.**
