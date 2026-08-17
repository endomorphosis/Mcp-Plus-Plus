# ADR-0001: Spec versus runtime ownership

- **Status:** Accepted
- **Date:** 2026-08-15
- **Last verified:** 2026-08-15
- **Task:** MCPP-013 (authoritative design record for KD-1 / REQ-OWN-01)
- **Interface:** `SpecRuntimeOwnership@1`
- **Deciders:** MCP++ 1.0 gap-closure program (MCPP-G020); sealed plan Key Decision KD-1 and §2 Repository ownership
- **Scope:** Which package owns normative MCP++ 1.0 schemas, cross-language conformance vectors, validators, compatibility matrices, interoperability tests, and release bundles; which packages own runtime adapters only; the ban on forking a second unofficial protocol inside any single runtime; and the installability of Mcp-Plus-Plus as a standalone conformance package.
- **Non-goals:** Mandatory crypto suite and `mcpp-jcs-v1` (ADR-0002 / MCPP-014); conformance-level ladder (ADR-0003 / MCPP-015); state modes and CRDT/consensus backends (ADR-0004 / MCPP-016); DurableExecutor product choice (ADR-0005 / MCPP-017); dual MCP bindings and A2A extension URI values (ADR-0006 / MCPP-018); concrete adapter implementations, CLI packaging, or three-peer demos (later waves). Binding *documents* and A2A extension *schemas* still land under Mcp-Plus-Plus ownership per this ADR; only the binding/URI *choices* are out of scope here.
- **Supersedes:** none
- **Superseded-by:** none
- **Related guides:**
  - Sealed plan: `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` (§2 Repository ownership; §4 file-disjointness; §5 KD-1; §7 lane assignment)
  - Traceability matrix: `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` (REQ-OWN-01)
  - Official MCP / A2A note (MCPP-010): `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md`
  - Profile inventory: `docs/reports/mcplusplus-1.0-gap-closure/baseline/profiles-a-h-inventory.md`
  - Forest pin: `docs/reports/mcplusplus-1.0-gap-closure/baseline/repository-forest.json`
  - Nested architecture overview: `ipfs_accelerate_py/mcplusplus/docs/architecture/overview.md`
  - Sibling ADRs that rest on this ownership split: `0002-crypto-canonical.md` … `0006-bindings-a2a.md`
- **Source anchors:**
  - `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` — §2; KD-1 (“Spec repo owns schemas, vectors, validators, matrices. Runtimes own adapters.”); KD-17 release-bundle packaging; §7 file-disjointness rules
  - `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` — REQ-OWN-01 → MCPP-013
  - `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md` — official MCP/A2A facts consumed by adapters; normative binding text remains in the spec tree
  - Nested spec tree: `ipfs_accelerate_py/mcplusplus/` (schemas, `conformance/vectors/`, `tests-{py,ts,go,rs}/`, docs)
  - Runtime adapter locations: `ipfs_accelerate_py/mcp_server/`, `ipfs_datasets_py/`, `ipfs_kit_py/`, SwissKnife checkout
  - Remote: https://github.com/endomorphosis/Mcp-Plus-Plus (canonical protocol / conformance home)

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

This ADR is **Accepted** as the binding ownership split for MCP++ 1.0 design
and implementation tasks. It does **not** claim that every runtime adapter is
already complete, that Mcp-Plus-Plus is already published as a release
bundle, or that forest-wide cryptographic conformance is green. Ownership
rules govern **where** work lands; later waves produce the artifacts.

## Context

MCP++ spans one protocol surface (Profiles A–H, four conformance languages)
and multiple runtime homes (accelerate, datasets, kit, SwissKnife). Without an
explicit ownership split:

1. **Each runtime invents its own schemas, vectors, and “validators”**, so
   peers that interoperate only within one product claim “MCP++ compliance”
   while speaking incompatible dialects.
2. **Large implementations are copied into the specification tree**, so the
   conformance package becomes un-installable and un-reviewable as a pure
   protocol/conformance unit.
3. **Normative matrices and release bundles live only in one product repo**,
   so other runtimes cannot depend on a single versioned package.
4. **Lane assignment collapses**: schema, crypto, transport, and runtime work
   fight over the same paths, breaking the plan’s file-disjoint parallelism.

Current-tree forces:

| Force | Evidence |
| --- | --- |
| Sealed plan names Mcp-Plus-Plus as canonical home for specs, schemas, vectors, validators, matrices, interop tests, and release bundles | Plan §2; KD-1 |
| Plan requires runtime-specific implementation in the repo that owns that runtime; ban large implementation duplication in the spec tree | Plan §2 |
| File-disjoint rules already pin path prefixes per role | Plan §7: `ipfs_accelerate_py/mcplusplus/` for spec/schema/vectors; runtime adapters under accelerate / datasets / kit / SwissKnife only |
| Traceability matrix scores REQ-OWN-01 as `partial` pending this ADR | matrix REQ-OWN-01 → MCPP-013 |
| Nested gitlink `ipfs_accelerate_py/mcplusplus` is the worktree-bound Mcp-Plus-Plus tree | forest pin; inventory header |
| Runtime-local UCAN / Profile H / Event DAG code already exists outside the nested tree | inventory §C/D/H; kit `ucan.py`; accelerate `mcp_server/mcplusplus/*` |
| Four-language structural validators and shared vectors already live under the nested tree | `tests-{py,ts,go,rs}/`; `conformance/vectors/` |
| Sibling Wave 3 ADRs (0002–0006) already treat package ownership as ADR-0001 / MCPP-013 scope | Non-goals sections in those ADRs |

If this decision is deferred, parallel lanes reopen “where does the schema
live?”, fork unofficial dialects inside accelerate or kit, or treat a single
runtime’s green matrix as forest law. Gates that depend on a single
conformance package (24, 13–16, installable `mcpp` / release bundles) cannot
close honestly.

Who is affected: Mcp-Plus-Plus conformance authors, every runtime adapter
owner, matrix and release maintainers, operators installing the conformance
package, and any peer that must reject unofficial protocol forks.

## Decision

**Mcp-Plus-Plus owns schemas, vectors, validators, matrices, and release
bundles. Runtimes own adapters only.**

Expanded ownership (same decision, fully stated): Mcp-Plus-Plus also owns
cross-language conformance vectors’ normative home, interoperability test
gates that admit forest claims, and the package identity of KD-17 release
bundles (Evidence Core, Secure Delegation, Federated Mesh, Commerce, Verified
Execution). Runtimes never take ownership of those asset classes.

MCP++ 1.0 treats the Mcp-Plus-Plus repository (nested in this program as
`ipfs_accelerate_py/mcplusplus/`) as the **single normative and conformance
home**. Runtime repositories (accelerate, datasets, kit, SwissKnife) host
**adapters** that consume that package’s schemas, vectors, and validators.
They MUST NOT mint a second unofficial protocol, a second set of normative
schemas, or a second release identity for the same profile version.

Acceptance alignment (MCPP-013): this Decision is satisfied only when the
bold rule above holds for every MCP++ 1.0 profile version under active
design—schemas, vectors, validators, matrices, and release bundles live in
Mcp-Plus-Plus; product code in accelerate/datasets/kit/SwissKnife is adapter
code only.

### 1. Spec / conformance package ownership (Mcp-Plus-Plus)

| Asset class | Normative owner | Tree location (program worktree) | Runtime may |
| --- | --- | --- | --- |
| Normative protocol specifications | Mcp-Plus-Plus | `ipfs_accelerate_py/mcplusplus/docs/spec/` (and architecture ADRs under `docs/architecture/decisions/`) | Cite and implement; not redefine profile object models in a private fork |
| Versioned JSON / other schemas | Mcp-Plus-Plus | `ipfs_accelerate_py/mcplusplus/schemas/` (and profile schema trees) | Import or pin; not ship a conflicting schema id for the same profile version |
| Cross-language conformance vectors | Mcp-Plus-Plus | `ipfs_accelerate_py/mcplusplus/conformance/vectors/` | Consume as golden inputs; not replace with runtime-only “green” fixtures that redefine the wire shape |
| Validators (structural and higher levels) | Mcp-Plus-Plus | `ipfs_accelerate_py/mcplusplus/tests-{py,ts,go,rs}/` and declared validator packages | Call / wrap; not claim a private validator as the forest admission bar |
| Compatibility / traceability matrices | Mcp-Plus-Plus (+ program evidence under accelerate `docs/reports/…` for gap-closure receipts) | Matrix: `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` | Contribute runtime rows only when the claim is scored against Mcp-Plus-Plus levels (ADR-0003) |
| Interoperability tests (four-language / multi-peer gates) | Mcp-Plus-Plus | Nested tree tests and harnesses | Supply runtime adapter harnesses that still assert against shared vectors |
| Dual MCP binding documents and A2A extension schemas | Mcp-Plus-Plus | Nested `docs/spec/` (and future binding chapters); official facts only in program note `official-mcp-a2a.md` | Implement dual bindings and advertise the verified A2A URI; do not relocate normative binding text into a runtime-only tree |
| Release bundles (Evidence Core, Secure Delegation, Federated Mesh, Commerce, Verified Execution) | Mcp-Plus-Plus packaging (KD-17) | Nested tree release artifacts when published | Depend on published bundle versions; not re-brand a runtime slice as the official MCP++ 1.0 bundle |

Rules:

| Rule | Normative statement |
| --- | --- |
| Single protocol home | For MCP++ 1.0, **one** normative protocol and conformance package exists: Mcp-Plus-Plus. Product marketing names must not invent a second protocol identity. |
| Installable conformance | Mcp-Plus-Plus MUST remain installable and reviewable as a **conformance package** (schemas + vectors + validators + matrices + release bundles) without requiring a full accelerate/datasets/kit/SwissKnife monorepo checkout (KD-1 rationale). |
| No large implementation dump | Do **not** duplicate large runtime implementations inside the specification tree (plan §2). Spec-tree code is limited to validators, codecs needed for conformance, harnesses, and thin reference helpers required to exercise vectors. |
| Schema and vector authority | When a runtime adapter and Mcp-Plus-Plus disagree on shape or bytes for a declared profile version, **Mcp-Plus-Plus wins**. The adapter must be fixed or the profile version must be revised through the spec process—not through silent runtime divergence. |

### 2. Runtime ownership (adapters only)

| Runtime | Adapter home (program rules) | Owns | Does **not** own |
| --- | --- | --- | --- |
| accelerate | `ipfs_accelerate_py/mcp_server/` (and declared MCP tests under `ipfs_accelerate_py/mcp/tests/` or `test/api/`) | Wiring MCP tools/resources, product UX, accelerate-specific storage/transport glue, crash-recovery adapters that implement interfaces defined in the spec tree | Normative schemas, shared golden vectors, four-language admission validators, official release bundle identity |
| datasets | `ipfs_datasets_py/` | Dataset pipelines, ZK/statement adapters as product features, datasets MCP surfaces | Same as above |
| kit | `ipfs_kit_py/` | Kit MCP server surfaces, local UCAN verifier product code, kit Profile H HTTP, etc. | Same as above |
| SwissKnife | Bound SwissKnife checkout (sibling forest; not an accelerate submodule) | TypeScript product adapters, A2A card surfaces, SwissKnife CLI pieces | Same as above |

Rules:

| Rule | Normative statement |
| --- | --- |
| Adapters only | Runtimes **own adapters**: code that maps product APIs, transport, persistence, and UX onto the **shared** MCP++ profiles, envelopes, and proofs defined in Mcp-Plus-Plus. |
| No second unofficial protocol | A runtime MUST NOT publish a private “MCP++ dialect” (new required fields, different CID rules, different UCAN header set) under the same profile version without a versioned binding or superseding ADR in the spec tree. |
| Local crypto is not forest law | Runtime-local verification (for example kit `UCANVerifier`) is valuable **product** and **local evidence**. It does **not** by itself promote matrix rows to forest-wide `cryptographic` / `implemented` without Mcp-Plus-Plus four-language tests at that level (ADR-0003). |
| Path discipline | New adapter work lands only under the runtime’s declared paths (plan §7). New normative schemas, vectors, and validators land only under `ipfs_accelerate_py/mcplusplus/`. |

### 3. Evidence and reports (program vs package)

| Artifact | Owner | Notes |
| --- | --- | --- |
| Gap-closure plan, objectives, todo board (accelerate docs) | Program / superproject | Operator-protected for this board; not Mcp-Plus-Plus release content |
| Baseline receipts under `docs/reports/mcplusplus-1.0-gap-closure/` | Program evidence in accelerate | Pins forest revisions and measured suite results; cites Mcp-Plus-Plus gitlink heads |
| Nested-tree ADRs under `ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/` | Mcp-Plus-Plus design authority | This file is one of them |
| Official release bundles and installable package metadata | Mcp-Plus-Plus | Later G160 / G170 packaging |

Program receipts may live in accelerate for the supervisor board, but they
**score** claims against Mcp-Plus-Plus ownership and conformance levels. They
do not relocate schema authority into accelerate.

### 4. Decision checklist (`SpecRuntimeOwnership@1`)

An implementation or PR satisfies **`SpecRuntimeOwnership@1`** only when all
of the following hold:

1. **Normative assets** (schemas, vectors, validators, matrices, interop gates,
   release bundle definitions) for the change land under Mcp-Plus-Plus
   (`ipfs_accelerate_py/mcplusplus/…`) or are pure program evidence receipts
   that do not redefine those assets.
2. **Runtime changes** are adapters (path-prefixed per §2) that consume the
   shared assets; they do not introduce a conflicting schema id or vector set
   for the same profile version.
3. **No second protocol identity** is advertised for the same MCP++ 1.0
   profile version.
4. **Local runtime green** is labeled local unless four-language / forest
   evidence from Mcp-Plus-Plus exists at the claimed conformance level
   (ADR-0003).
5. **Large product implementations** are not relocated into the spec tree to
   “make the package complete.”

## Alternatives

### Alternative A: Accelerate monorepo owns the protocol

- **Summary:** Treat `ipfs_accelerate_py` (or the superproject) as the sole
  home for schemas, vectors, and validators; other runtimes vendor copies.
- **Expected benefits:** One checkout for accelerate developers; fewer
  gitlinks.
- **Why not chosen:** KD-1 and plan §2 require an installable conformance
  package independent of any single runtime. Vendored copies become unofficial
  forks.

### Alternative B: Each runtime owns its own schemas and vectors

- **Summary:** accelerate, datasets, kit, and SwissKnife each ship profile
  schemas and “validators”; interop is best-effort.
- **Expected benefits:** Fast local iteration per product.
- **Why not chosen:** Produces multiple unofficial protocols. Cross-language
  gate 24 and multi-runtime release bundles cannot close.

### Alternative C: Spec tree hosts full runtime implementations

- **Summary:** Move accelerate/kit adapters into Mcp-Plus-Plus so “one repo
  has everything.”
- **Expected benefits:** Single PR for protocol + product.
- **Why not chosen:** Plan §2 forbids large implementation dumps in the
  specification repository and requires runtime code in the repo that owns
  that runtime. The package stops being a conformance unit.

### Alternative D: Shared schemas only; validators live only in runtimes

- **Summary:** Mcp-Plus-Plus publishes JSON Schema; each language runtime
  writes its own validator suite.
- **Expected benefits:** Smaller nested tree.
- **Why not chosen:** KD-1 lists validators and matrices as spec-repo owned.
  Without shared validators and vectors, “schema green” becomes the only
  common bar (forbidden by ADR-0003 / KD-6).

### Alternative E: Do nothing / status quo

- **Summary:** Defer ownership until packaging (G160/G170).
- **Why not chosen:** Wave 3 ADRs and all adapter lanes need a fixed split now.
  REQ-OWN-01 is already tracked to MCPP-013; sibling ADRs already point here.

## Consequences

### Positive

- One protocol home; adapters cannot silently redefine MCP++ 1.0.
- Mcp-Plus-Plus remains an installable conformance package (KD-1).
- File-disjoint lanes stay workable: schema/crypto/spec vs runtime adapters.
- Matrix and release claims score against shared assets and levels, not a
  single product’s green suite.
- Sibling ADRs (0002–0006) share a stable ownership baseline.

### Negative

- Adapter authors must cross a package boundary (dependency or gitlink pin)
  instead of editing schemas next to product code.
- Dual maintenance of gitlink / published package versions until release
  packaging lands.
- Runtime-local crypto or policy engines remain **local** until forest
  validators catch up—honest, but slower “done” narratives.

### Neutral / residual risks

- Nested `ipfs_accelerate_py/mcplusplus` revision can lag the standalone
  Mcp-Plus-Plus remote; pin and inventory refresh rules still apply (plan §3).
- Program evidence under `docs/reports/mcplusplus-1.0-gap-closure/` is not
  itself the conformance package; readers must not treat receipts as schemas.
- SwissKnife remains a sibling forest checkout; binding it does not move schema
  ownership into SwissKnife.
- Exact packaging layout for installable `mcpp` / release bundles is G160/G170
  detail; this ADR freezes **ownership**, not every filename in the tarball.

## Evidence

| Claim in Decision | Evidence (path, test, or operational check) | Notes |
| --- | --- | --- |
| Spec repo owns schemas, vectors, validators, matrices | Plan §2; KD-1; REQ-OWN-01 | Core KD-1 statement |
| Runtimes own adapters only | Plan §2; KD-1; plan §7 path table | accelerate/datasets/kit/SwissKnife prefixes |
| No large implementation dump in spec tree | Plan §2 paragraph after role list | Conformance package integrity |
| Nested tree already holds multi-language validators + vectors | `tests-{py,ts,go,rs}/`; `conformance/vectors/` | Current-tree force |
| Runtime adapter code already lives outside nested tree | inventory; `ipfs_*_py/**/mcplusplus*`; SwissKnife adapters | Adapter homes |
| Matrix tracks ownership as MCPP-013 | REQ-OWN-01 → MCPP-013 | This ADR is the MCPP-013 design record |
| Sibling ADRs defer ownership to ADR-0001 | Non-goals in 0002–0006 | Cross-ADR consistency |
| Official MCP/A2A facts do not move binding ownership into runtimes | `official-mcp-a2a.md` (MCPP-010) | Program note is evidence; normative binding docs stay in Mcp-Plus-Plus |
| Forest / gitlink pin for nested tree | `repository-forest.json`; inventory header | Revision discipline |
| KD-17 names release bundles under the conformance packaging story | Plan KD-17 | Bundle identity is package-owned, not runtime-owned |

Evidence classes used: sealed plan key decision and repository-ownership
section (design authority), official MCP/A2A note (program evidence consumed by
adapters), traceability matrix (MCPP-012), baseline inventory and forest pin
(tree reality). This ADR does **not** claim packaging or forest-wide
higher-level conformance is complete.

## Verification

How a future reader confirms this ADR still holds:

1. **Document presence (this task / MCPP-013 gate):**
   ```text
   test -s ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0001-spec-runtime-ownership.md
   ```
2. **KD-1 still reflected:** Decision §1–2 match plan §2 and KD-1 (spec owns
   schemas/vectors/validators/matrices/bundles; runtimes own adapters).
3. **Path discipline still matches plan §7:** new schemas/vectors under
   `ipfs_accelerate_py/mcplusplus/`; accelerate adapters under
   `ipfs_accelerate_py/mcp_server/`; datasets under `ipfs_datasets_py/`; kit
   under `ipfs_kit_py/`; SwissKnife only in its bound checkout.
4. **Matrix still points here:** REQ-OWN-01 cites MCPP-013 / this ADR for the
   ownership claim.
5. **Staleness signals:** a runtime publishes a conflicting schema id for the
   same profile version; large product engines moved into the nested tree
   “for convenience”; validators deleted from Mcp-Plus-Plus in favor of
   runtime-only suites; second protocol identity advertised as MCP++ 1.0.

## Review triggers

- [ ] Source anchors no longer match the Decision statement
- [ ] A recorded negative consequence becomes unacceptable
- [ ] Mcp-Plus-Plus packaging splits schemas from validators into multiple
      packages (would require a superseding ownership ADR, not silent drift)
- [ ] A new runtime joins the forest and needs a declared adapter path prefix
- [ ] A rejected alternative (monorepo-only protocol, per-runtime schemas) is
      forced by external packaging constraints
- [ ] Security or trust-boundary changes require relocating a validator class
- [ ] Superseding design is Accepted under a new ADR number

When superseding: create a new ADR number; set this file to **Superseded** with
`Superseded-by`; set the successor’s `Supersedes`; do not delete this file.

## Notes (optional)

### Downstream task map

| Concern | Follow-on |
| --- | --- |
| Crypto suite defaults (consume shared suite) | MCPP-014 / ADR-0002 |
| Conformance levels (score shared claims) | MCPP-015 / ADR-0003 |
| State / DurableExecutor / bindings ADRs | MCPP-016…018 |
| Schema and vector publication waves | MCPP-024…040 (and related) |
| Runtime adapters and installable CLI | MCPP-G090…G160 tracks |
| Matrix row REQ-OWN-01 upgrade | Only when packaging + adapter discipline are evidenced (not by this ADR alone) |

### Interface label

Task interface id: **`SpecRuntimeOwnership@1`** — the normative checklist in
Decision §4. MCPP-013 is complete when this Accepted ADR exists at the
declared path and the Decision statement matches the task acceptance rule.

### Sealed defaults preserved

This ADR records plan KD-1 and §2 Repository ownership without reopening
them. Mcp-Plus-Plus remains the sole normative and conformance home; runtimes
remain adapter owners only; large implementations stay out of the
specification tree; and installability of the conformance package remains a
first-class design constraint. Refinements (path table, local-vs-forest
evidence labeling, program receipts vs package assets, official-note
citation) stay inside that default and cite current-tree evidence from
MCPP-010, MCPP-012, and the baseline inventory.

### Recovery provenance

An earlier recovery task (MCPP-091) seeded this path so sibling Wave-3 ADRs
could reference ADR-0001. **MCPP-013** remains the authoritative board task
for the ownership decision; this revision is the MCPP-013 deliverable
(Accepted ADR with rejection of monorepo-only, per-runtime-schema, and
spec-tree-implementation alternatives, plus implementation consequences).
