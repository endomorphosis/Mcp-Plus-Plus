# MCP++ protocol bindings

**Status:** Normative index (MCP++ 1.0 dual-binding surface)  
**Authority:** ADR-0006 (Accepted); plan KD-2, KD-3; MCPP-G030  
**Parent registry:** [../mcp++-profiles-draft.md](../mcp++-profiles-draft.md)

## 1. Purpose

This directory holds **versioned MCP application bindings**. A binding maps
abstract Profiles A–H (capability keys, object models, profile methods) onto a
specific MCP protocol revision’s lifecycle and wire mechanics.

Profiles A–H in the parent registry are **MCP-version-independent** and
**transport-independent**. Binding documents own:

- session vs stateless lifecycle,
- where capability keys are placed on the wire,
- discovery RPCs and headers that are revision-specific,
- fail-closed rules for version forgery and silent downgrade.

They do **not** redefine Profile A–H object models, CID rules, UCAN validation,
policy evaluation, Event DAG structure, or payment objects.

## 2. Binding inventory

| Binding id | Document | MCP revision | Lifecycle | Role |
| --- | --- | --- | --- | --- |
| `mcp-binding/legacy-2024-11-05` | [mcp-legacy-2024-11-05.md](mcp-legacy-2024-11-05.md) | `2024-11-05` (initialize-era family as documented there) | `initialize` / `notifications/initialized` session handshake | **Legacy.** Required name when offering initialize-era behavior. MCPP-020. |
| `mcp-binding/2026-07-28` | [mcp-2026-07-28.md](mcp-2026-07-28.md) | `2026-07-28` | Stateless per-request `_meta`; **no** initialize | **Current.** Official modern MCP revision for new normative work. MCPP-021. |

Binding document files for MCPP-020 and MCPP-021 are authored by those tasks.
Until they land, this index and ADR-0006 freeze **ids, revision pairing, and
lifecycle shape**. Existing legacy vectors (for example
`conformance/vectors/initialize_result.json`) remain readable under the legacy
binding id; they do **not** prove the current binding.

## 3. Normative rules (summary)

These rules restate ADR-0006 for binding implementers. In case of conflict,
ADR-0006 and the sealed plan prevail.

1. **Dual support allowed.** A peer **MAY** advertise and implement both
   bindings. Dual support is the intended migration path.
2. **Explicit naming.** Capability / binding advertisement **MUST** use the
   binding ids in §2 (or documented aliases that expand to them). Offering
   initialize without naming `mcp-binding/legacy-2024-11-05` is non-conformant
   for MCP++ 1.0 claims.
3. **Current is not initialize.** `mcp-binding/2026-07-28` **MUST NOT** depend
   on the removed `initialize` / `notifications/initialized` exchange. Version,
   client capabilities, and identity ride per-request metadata per official MCP
   2026-07-28 (see MCPP-010 note and the current binding document).
4. **Legacy remains initialize.** `mcp-binding/legacy-2024-11-05` **MUST**
   document and test the initialize handshake, including `protocolVersion`
   `2024-11-05` acceptance on that path.
5. **Discovery ≠ initialize.** On the current binding, official discovery
   (for example `server/discover`) is not a substitute initialize handshake.
6. **Fail closed.** Forged or mismatched `protocolVersion` / binding id pairs,
   silent downgrade, and initialize-shaped messages on a path that claims only
   the current binding **MUST** be rejected.

## 4. Abstract profile keys (shared)

Both bindings advertise the same abstract MCP++ profile keys. Placement differs
by binding; identity of the keys does not.

| Key | Profile |
| --- | --- |
| `mcp++/mcp-idl` | A |
| `mcp++/cid-envelope` | B |
| `mcp++/ucan` | C |
| `mcp++/deontic-policy` | D |
| `mcp++/p2p-transport` | E (optional transport) |
| `mcp++/event-dag` | F |
| `mcp++/risk-scheduling` | G |
| `mcp++/x402-payments` | H |

Profile method tables and result fields remain in the parent registry
[Appendix A](../mcp++-profiles-draft.md#appendix-a-httpjson-rpc-method-surface-normative).
That appendix references this directory for lifecycle and **must not** be treated
as reintroducing initialize as the only negotiation path.

## 5. Transport vs MCP application binding

| Concern | Locus |
| --- | --- |
| MCP revision, handshake vs `_meta`, capability placement | This directory (MCP application bindings) |
| libp2p / `mcp+p2p` stream protocol IDs, framing, peer discovery | Profile E chapter [transport-mcp-p2p.md](../transport-mcp-p2p.md) |
| HTTP/JSON-RPC method names for profile operations | Parent registry Appendix A |

libp2p stream negotiation is a **carriage handshake**. It **MUST NOT** be
conflated with the legacy MCP application `initialize` exchange, and it **MUST
NOT** be required as the only way to activate Profiles A–D or F–H.

## 6. Related evidence

| Artifact | Role |
| --- | --- |
| `docs/architecture/decisions/0006-bindings-a2a.md` | Accepted dual-binding and A2A id decision |
| `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md` | MCPP-010 primary-source verification (current MCP not initialize-based) |
| `conformance/vectors/initialize_result.json` | Legacy pin only |
| Parent [mcp++-profiles-draft.md](../mcp++-profiles-draft.md) | Abstract Profiles A–H registry |

## 7. Downstream tasks

| Task | Deliverable |
| --- | --- |
| MCPP-019 (this index + abstract registry refactor) | Profiles A–H independent; bindings referenced |
| MCPP-020 | Full legacy binding prose + tests |
| MCPP-021 | Full current binding prose + tests |
| MCPP-022…023 | Dual-binding peer, downgrade, and forgery proofs |
