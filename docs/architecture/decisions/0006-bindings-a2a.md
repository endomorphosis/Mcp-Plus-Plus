# ADR-0006: Dual MCP bindings and A2A extension identifier

- **Status:** Accepted
- **Date:** 2026-08-15
- **Last verified:** 2026-08-15
- **Deciders:** MCP++ 1.0 gap-closure program (MCPP-G020); sealed plan Key Decisions KD-2, KD-3, and KD-13
- **Scope:** Dual MCP protocol bindings for MCP++ 1.0 (`mcp-binding/legacy-2024-11-05` and `mcp-binding/2026-07-28`); the rule that Profiles A–H stay transport- and MCP-version-independent; the verified A2A execution extension URI from MCPP-010; the working alias vs wire-identifier split; and the ban on a competing public task lifecycle.
- **Non-goals:** Full binding module prose and dual-binding peer tests (MCPP-019…023); A2A extension schemas, adapter, and handoff tests (MCPP-054…057); SwissKnife adapter wiring (MCPP-057); Profile A–H content beyond independence from MCP revision and transport; DurableExecutor choice (ADR-0005); crypto suite (ADR-0002); package ownership of schemas vs adapters beyond restating that binding docs live in the spec tree (ADR-0001 / MCPP-013).
- **Supersedes:** none
- **Superseded-by:** none
- **Related guides:**
  - Sealed plan: `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` (§5 KD-2, KD-3, KD-13; gates 2–6; PR-05, PR-12)
  - Official MCP / A2A verification note (MCPP-010): `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md`
  - Traceability matrix: `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` (REQ-BIND-01…03, REQ-A2A-01…02)
  - Goal tree: MCPP-G030 abstract bindings; MCPP-G100 A2A interoperability extension
  - Future binding specs: `ipfs_accelerate_py/mcplusplus/docs/spec/bindings/mcp-legacy-2024-11-05.md` (MCPP-020); `ipfs_accelerate_py/mcplusplus/docs/spec/bindings/mcp-2026-07-28.md` (MCPP-021)
  - Future A2A extension chapter: MCPP-054 family
  - Durable execution (related, not the same lifecycle): `ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0005-durable-executor.md`
- **Source anchors:**
  - `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` — KD-2, KD-3, KD-13; gates 2–6
  - `docs/architecture/mcplusplus_1_0_gap_closure.objectives.md` — MCPP-G030, MCPP-G100
  - `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md` — verified MCP 2026-07-28 lifecycle; A2A URI rule; confirmed URI
  - `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` — REQ-BIND-*, REQ-A2A-*
  - Conformance pin (legacy only today): `ipfs_accelerate_py/mcplusplus/conformance/vectors/initialize_result.json`
  - Downstream tasks MCPP-019…023, MCPP-054…057

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

This ADR is **Accepted** as the binding dual-MCP and A2A-identifier choice for
MCP++ 1.0 design and implementation tasks. It does **not** claim that binding
modules, dual-binding peer tests, or the A2A execution adapter already exist
in-tree; those land in MCPP-019…023 and MCPP-054…057. Documentation alone does
not close gates 2–6.

## Context

MCP++ must remain usable on both installed fleets that still speak the
initialize-era MCP revision and modern peers that speak the current
stateless MCP revision. Separately, multi-agent handoff requires an official
A2A extension identifier so Agent Cards and request activation stay
interoperable without inventing a second public task model.

Without an explicit decision:

1. **Draft profile text treats `initialize` / `2024-11-05` as current**, so new
   peers implement a removed handshake and fail against MCP 2026-07-28 clients.
2. **Profiles A–H embed a single MCP version or transport**, so each protocol
   revision forks the entire profile surface instead of versioned binding modules.
3. **A2A extension ids are spelled as reverse-DNS tokens** (e.g.
   `io.mcplusplus.execution@1`) on the Agent Card or in `A2A-Extensions`,
   which violates the official A2A URI identifier rule verified in MCPP-010.
4. **A private “MCP++ task lifecycle” competes with A2A Task**, so status,
   cancel, streaming, and artifacts diverge across SwissKnife, accelerate, and
   third-party A2A agents.

Current-tree forces:

| Force | Evidence |
| --- | --- |
| Sealed plan requires version-independent profiles and dual named bindings | KD-2, KD-3; gates 2–5; MCPP-G030 |
| Installed vectors and accelerate/datasets still legacy-shaped | `initialize_result.json` pins `2024-11-05`; inventory / REQ-BIND-02 `partial` |
| Official MCP 2026-07-28 is **not** initialize-based; per-request `_meta` | MCPP-010 note §2; primary changelog / versioning pages |
| Dual-era servers may accept modern `_meta` **or** legacy `initialize` | MCPP-010 §2.3 item 6 (official versioning “Backward Compatibility”) |
| Official A2A extensions are **URIs** on the Agent Card and in `A2A-Extensions` | MCPP-010 §3; A2A extensions topic |
| Confirmed MCP++ execution extension URI | `https://mcplusplus.io/extensions/execution/v1` (MCPP-010 §4.1; REQ-A2A-02) |
| Alias `io.mcplusplus.execution@1` is human/internal only, not the wire id | MCPP-010 §4.3; G100 evidence source policy |
| A2A already owns Agent Card, Task, Message, Part, Artifact, status, cancel, streaming | KD-13; G100 gap task; REQ-A2A-01 |
| DurableExecutor is step-commit recovery, not a public multi-agent task API | ADR-0005; must not become a competing public lifecycle |

If this decision is deferred, binding and A2A lanes invent incompatible module
names, treat initialize as current, advertise reverse-DNS-only A2A ids, or ship
a parallel task status machine. Gates 2–6 cannot close; MCPP-019…023 and
MCPP-054…057 lack stable identifiers and lifecycle ownership rules.

Who is affected: binding authors (MCPP-019…023), A2A extension and adapter
authors (MCPP-054…057), SwissKnife and accelerate integration owners, operators
reading capability advertisements, and any peer that must fail closed on
version forgery, downgrade, or undeclared lifecycle competition.

## Decision

**MCP++ 1.0 ships two named MCP bindings—legacy `2024-11-05` (initialize) and
current `2026-07-28` (not initialize-based)—keeps Profiles A–H independent of
MCP revision and transport, and uses the MCPP-010-verified A2A extension URI
`https://mcplusplus.io/extensions/execution/v1`.** MCP++ MUST NOT define a
competing public task lifecycle; it extends A2A Task semantics with envelope,
state, and receipt mappings. Implementations MUST fail closed on protocol
version forgery, silent downgrade, and reverse-DNS-only A2A wire identifiers.

### 1. Profiles A–H are binding-independent (KD-2)

| Rule | Normative statement |
| --- | --- |
| Independence | Profiles **A–H** describe execution semantics (IDL, CID artifacts, UCAN, policy, Event DAG, risk/scheduling, transport profile options, adversarial controls) **without** requiring a specific MCP protocol revision or a specific carriage transport. |
| Binding locus | MCP version and handshake/stateless mechanics live in **versioned binding documents/modules**, not inside profile normative cores. |
| Transport locus | Optional transports (e.g. `mcp+p2p`) are profile-or-transport bindings; they MUST NOT rewrite profile A–F object models per MCP revision. |
| Refactor mandate | Existing draft language that treats `initialize` / `protocolVersion` `2024-11-05` as the only normative MCP path is **legacy-binding content**, not abstract profile law (MCPP-019). |

### 2. Dual MCP bindings (KD-3)

| Binding id | MCP revision | Lifecycle shape | Normative role |
| --- | --- | --- | --- |
| `mcp-binding/legacy-2024-11-05` | `2024-11-05` (initialize-era family through `2025-11-25` semantics as documented in the legacy binding) | `initialize` / `notifications/initialized` session handshake | **Legacy.** Supported for installed fleets and historical vectors. MUST be advertised by name when offered. |
| `mcp-binding/2026-07-28` | `2026-07-28` | Stateless per-request `_meta`; **no** initialize handshake | **Current.** Official MCP revision for new normative work and current-binding conformance. |

| Rule | Normative statement |
| --- | --- |
| Both allowed | A peer **MAY** support both bindings. Dual support is the intended migration path. |
| Explicit naming | Capability / binding advertisement MUST use the binding ids above (or equivalent documented aliases that expand to them). Supporting initialize without naming the legacy binding is non-conformant for MCP++ 1.0 claims. |
| Current is not initialize | The current binding **MUST NOT** depend on the removed `initialize` / `notifications/initialized` exchange. Version, client capabilities, and identity ride per-request metadata per official MCP 2026-07-28 (`io.modelcontextprotocol/protocolVersion`, `io.modelcontextprotocol/clientCapabilities`, related `_meta` / headers as specified in the binding). |
| Legacy remains initialize | The legacy binding **MUST** document and test the initialize handshake, including `protocolVersion` `2024-11-05` acceptance on that path. |
| Discovery on current | Current binding discovery follows official MCP (`server/discover` and related mechanics). Discovery is not a substitute initialize handshake. |
| Downgrade rejection | A peer that has negotiated or declared a binding **MUST** reject silent downgrade to a weaker or different binding without re-advertisement. Forged or mismatched `protocolVersion` / binding id pairs fail closed. |
| Forgery rejection | Accepting a forged `protocolVersion`, forged binding id, or initialize-shaped messages on a path that claims only the current binding is non-conformant. |
| Vector continuity | Existing `2024-11-05` vectors remain readable under the legacy binding; they do **not** prove the current binding. |

Detail prose, request shapes, and dual-binding peer tests land in MCPP-019…023.
This ADR freezes the **names, revision pairing, and fail-closed rules**.

### 3. A2A execution extension identifier (KD-13 + MCPP-010)

| Role | Value | Normative? |
| --- | --- | --- |
| **Wire / Agent Card / `A2A-Extensions` identifier** | `https://mcplusplus.io/extensions/execution/v1` | **Yes — mandatory** for A2A interop claims |
| **Working alias (human / internal only)** | `io.mcplusplus.execution@1` | Documented synonym only; **not** a wire substitute |

| Rule | Normative statement |
| --- | --- |
| Official form | A2A extensions are identified by **URI**, advertised on the Agent Card (`AgentExtension.uri`), and activated via the `A2A-Extensions` service parameter (comma-separated URIs). Reverse-DNS tokens without a URI scheme are **not** valid A2A extension identifiers. |
| Confirmed URI | MCP++ 1.0 uses **`https://mcplusplus.io/extensions/execution/v1`**, confirmed by MCPP-010 against primary A2A sources. No substitute URI is required for 1.0. |
| Breaking changes | A breaking change to the extension’s logic, data structures, or required parameters **MUST** introduce a **new URI** (e.g. `…/v2`), not silently redefine `/v1`. |
| Alias use | Schemas, adapters, interoperability tests, and Agent Cards that speak A2A **MUST** use the HTTPS URI. Text **MAY** mention `io.mcplusplus.execution@1` as a non-normative short name. |
| Namespace | The URI is project-controlled under `mcplusplus.io`. Implementations MUST NOT claim the reserved A2A-org prefix `https://a2a-protocol.org/extensions/` for this extension. |
| Identifier vs HTTP | Extension URIs are identifiers. Temporary DNS/hosting unavailability for `mcplusplus.io` does **not** rename the identifier (MCPP-010 §4.2). Spec hosting remains an ops follow-on. |

### 4. No competing public task lifecycle (KD-13)

| Rule | Normative statement |
| --- | --- |
| A2A owns the public agent-task model | A2A already provides **Agent Card**, **Task**, **Message**, **Part**, **Artifact**, **status**, **cancel**, **streaming**, and related auth/push patterns. MCP++ **extends** that model; it does **not** replace it. |
| Extension maps, does not fork status | The execution extension maps MCP-IDL and MCP++ envelope / state / receipt / event objects onto A2A Task and Artifact surfaces. Implementations MUST NOT invent a second public status vocabulary that peers must learn instead of A2A Task status names. |
| Final results | Terminal A2A results under this extension MUST be able to carry MCP++ evidence references (at minimum `receipt_cid`, `event_cid`, and proof references as specified in MCPP-054+), without defining a parallel terminal-state machine. |
| DurableExecutor is not public task API | `DurableExecutor` (ADR-0005) is the crash-recovery / journal contract for step commit. It MUST NOT be advertised as a competing multi-agent public task lifecycle that displaces A2A Task. |
| MCP Tasks extension is distinct | Official MCP Tasks (`io.modelcontextprotocol/tasks`) is an MCP-side capability family. It is **not** the A2A extension identifier and does **not** replace A2A Task for cross-agent handoff. Binding docs may reference both without merging their id spaces. |
| Fail closed | Adapters that claim A2A interop while exposing only a private MCP++ task lifecycle (no Agent Card extension URI, no Task mapping) are non-conformant for gates that require A2A handoff. |

### 5. Decision checklist (`BindingAndA2ADecision@1`)

A reader may treat the following as the interface label **`BindingAndA2ADecision@1`**:

1. Profiles A–H are transport- and MCP-version-independent; MCP revision mechanics live in versioned bindings.
2. Legacy binding id is **`mcp-binding/legacy-2024-11-05`** (initialize-era; `2024-11-05`).
3. Current binding id is **`mcp-binding/2026-07-28`** (stateless; **not** initialize-based).
4. Dual support is allowed; downgrade and version forgery fail closed.
5. A2A wire identifier is **`https://mcplusplus.io/extensions/execution/v1`** (MCPP-010 confirmed).
6. `io.mcplusplus.execution@1` is an alias only; not valid alone on Agent Card / `A2A-Extensions`.
7. No competing public task lifecycle; A2A Task remains the public multi-agent lifecycle; DurableExecutor stays journal authority only.

## Alternatives

### Alternative A: Single current binding only (`2026-07-28`)

- **Summary:** Drop legacy initialize support; all MCP++ 1.0 peers speak only modern per-request `_meta`.
- **Expected benefits:** Smaller matrix; no dual-era code paths.
- **Why not chosen:** Installed fleets and existing vectors still speak `2024-11-05`. KD-3 requires dual bindings and explicit legacy naming. Legacy remains a first-class, named binding.

### Alternative B: Treat initialize / `2024-11-05` as current

- **Summary:** Keep draft initialize-centric text as the only normative MCP path.
- **Expected benefits:** Matches today’s accelerate/datasets/vector shapes with less rewrite.
- **Why not chosen:** Official MCP 2026-07-28 removed initialize as modern behavior (MCPP-010). Gates 3–4 require a current binding that is not initialize-based.

### Alternative C: Reverse-DNS-only A2A identifier (`io.mcplusplus.execution@1` on the wire)

- **Summary:** Use the working alias as `AgentExtension.uri` and `A2A-Extensions` value.
- **Expected benefits:** Short strings; matches some MCP capability key habits.
- **Why not chosen:** Official A2A identifiers are **URIs**. MCPP-010 and REQ-A2A-02 reject reverse-DNS-only as the wire id. Alias stays human/internal.

### Alternative D: Competing MCP++ public task lifecycle

- **Summary:** Define MCP++-native Task/status/cancel/stream types as the public multi-agent API; treat A2A as optional translation.
- **Expected benefits:** Full control of status vocabulary and evidence fields.
- **Why not chosen:** KD-13 and G100 require extending A2A, not replacing it. A second public lifecycle fragments SwissKnife and third-party A2A agents.

### Alternative E: Fold binding choice into Profile G/H or transport only

- **Summary:** Encode MCP revision inside transport or adversarial profiles instead of versioned binding modules.
- **Expected benefits:** Fewer top-level documents.
- **Why not chosen:** KD-2 requires abstract profiles; revision mechanics must not fork A–F object models. Bindings are versioned modules (MCPP-019…021).

### Alternative F: Do nothing / status quo

- **Summary:** Defer names and URI until adapter implementation starts.
- **Why not chosen:** Wave 3 ADRs exist so binding and A2A work (MCPP-G030, MCPP-G100) share one identifier and lifecycle rule set. Plan KD-2, KD-3, and KD-13 already decide; this ADR records them with MCPP-010 evidence.

## Consequences

### Positive

- Parallel lanes share fixed binding ids and a single A2A URI; no re-litigation per PR.
- Legacy initialize work continues under an honest name; current MCP work cannot claim initialize is modern.
- A2A Agent Card and `A2A-Extensions` activation use the verified HTTPS URI.
- Public multi-agent lifecycle stays A2A Task; DurableExecutor and MCP Tasks remain correctly scoped.
- Clear fail-closed rules for downgrade, forgery, and reverse-DNS-only A2A ids.

### Negative

- Dual-binding test matrix and advertisement surface are larger (MCPP-020…023).
- Adapter authors must map A2A Task fields without inventing parallel status names (discipline cost in MCPP-054…057).
- Operators must learn both binding ids and the URI vs alias distinction.
- Spec hosting for `https://mcplusplus.io/extensions/execution/v1` remains an ops item until the domain serves the extension document.

### Neutral / residual risks

- Exact `_meta` key tables, HTTP header bindings, and dual-era selection algorithms are specified in MCPP-020…021, not frozen here beyond the lifecycle shape.
- Mapping tables from A2A Task/Artifact to envelope/state/receipt CIDs are MCPP-054 acceptance detail.
- MCP Tasks extension (`io.modelcontextprotocol/tasks`) coexistence with A2A Task needs careful dual-stack demos so neither id space is mislabeled.
- A future Accepted ADR may add further named MCP bindings for later revisions; until then only the two ids above are MCP++ 1.0 dual-binding law.
- Temporary DNS failure for `mcplusplus.io` must not trigger an unauthorized URI rename.

## Evidence

| Claim in Decision | Evidence (path, test, or operational check) | Notes |
| --- | --- | --- |
| Profiles independent of MCP version / transport | Plan KD-2; gate 2; REQ-BIND-01; MCPP-G030 | Abstract refactor still `missing` (MCPP-019) |
| Dual bindings `legacy-2024-11-05` and `2026-07-28` | Plan KD-3; gates 2–5; REQ-BIND-02 | Legacy partial; current binding missing |
| Current MCP not initialize-based | MCPP-010 §2; official MCP 2026-07-28 changelog / versioning | Primary HTTPS sources |
| Legacy initialize still valid under named legacy binding | MCPP-010 §2.2–2.3; vector `initialize_result.json` | Pin is legacy, not current proof |
| A2A extensions identified by URI | MCPP-010 §3; A2A extensions topic | Agent Card + `A2A-Extensions` |
| Wire URI `https://mcplusplus.io/extensions/execution/v1` | MCPP-010 §4.1; REQ-A2A-02 `implemented` (identifier decision) | Extension implementation still missing |
| Alias not wire id | MCPP-010 §4.3; G100 evidence source policy | Human/internal only |
| No competing public task lifecycle | Plan KD-13; G100 gap task; REQ-A2A-01 | Handoff tests in MCPP-056 |
| DurableExecutor ≠ public task lifecycle | ADR-0005; this ADR §4 | Journal vs A2A Task |

Evidence classes used: sealed plan key decisions (design authority for this
wave), MCPP-010 primary-source verification note, objectives evidence policy,
traceability matrix (gap status). Binding modules, dual-peer tests, and A2A
adapter artifacts are **not** claimed complete by this ADR.

## Verification

How a future reader confirms this ADR still holds:

1. **Document presence (this task):**
   ```text
   test -s ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0006-bindings-a2a.md
   ```
2. **A2A URI still MCPP-010 confirmed:** inspect Decision §3 and
   `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md` §4.1
   for `https://mcplusplus.io/extensions/execution/v1`.
3. **Dual binding ids present in binding specs (later):**  
   `ipfs_accelerate_py/mcplusplus/docs/spec/bindings/mcp-legacy-2024-11-05.md`  
   `ipfs_accelerate_py/mcplusplus/docs/spec/bindings/mcp-2026-07-28.md`
4. **Legacy initialize tests (later):**  
   `cd ipfs_accelerate_py && python -m pytest -q tests-py/integration/test_mcp_binding_legacy.py`
5. **Current non-initialize tests (later):**  
   `cd ipfs_accelerate_py && python -m pytest -q tests-py/integration/test_mcp_binding_current.py`
6. **A2A handoff (later / gate 6):**  
   extension schemas + adapter tests under MCPP-054…056 use the HTTPS URI and
   A2A Task status names.
7. **Staleness signals:** initialize treated as current; reverse-DNS-only on
   Agent Card / `A2A-Extensions`; second public task status machine; URI rename
   without superseding ADR; dual binding ids dropped while claiming KD-3.

## Review triggers

- [ ] Source anchors no longer match the Decision statement
- [ ] A recorded negative consequence becomes unacceptable
- [ ] Official MCP publishes a successor revision that requires a third named binding
- [ ] Official A2A changes the extension identifier rule (URI form, activation header, or Agent Card field)
- [ ] MCPP-010 substitute URI is recorded (would require superseding or amending §3)
- [ ] A rejected alternative (single-binding-only, reverse-DNS wire id, competing lifecycle) is forced by external standards
- [ ] Security or trust-boundary changes touch binding advertisement, version forgery, or task-lifecycle ownership
- [ ] Superseding design is Accepted under a new ADR number

When superseding: create a new ADR number; set this file to **Superseded** with
`Superseded-by`; set the successor’s `Supersedes`; do not delete this file.

## Notes (optional)

### Downstream task map

| Concern | Follow-on |
| --- | --- |
| Abstract Profiles A–H (version/transport independent) | MCPP-019 |
| Legacy MCP 2024-11-05 binding + tests | MCPP-020 |
| Current MCP 2026-07-28 binding + tests | MCPP-021 |
| Dual-binding peer / downgrade-forgery proofs | MCPP-022…023 |
| A2A execution extension spec + mappings | MCPP-054 |
| A2A schemas and vectors | MCPP-055 |
| A2A reference adapter + two-agent handoff | MCPP-056 |
| SwissKnife A2A adapter | MCPP-057 |

### Interface label

Task interface id: **`BindingAndA2ADecision@1`** — the normative checklist in
Decision §5.

### Sealed defaults preserved

This ADR records plan KD-2, KD-3, and KD-13 without reopening them. Dual
bindings remain `mcp-binding/legacy-2024-11-05` and `mcp-binding/2026-07-28`;
the A2A wire identifier remains the MCPP-010-confirmed URI
`https://mcplusplus.io/extensions/execution/v1`; and MCP++ does not invent a
competing public task lifecycle. Refinements (binding independence rules,
forgery/downgrade fail-closed, alias vs wire split, DurableExecutor
non-competition) stay inside those defaults and cite current-tree evidence.
