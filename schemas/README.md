# MCP++ schemas (SchemaId@1)

Versioned JSON Schema documents for the MCP++ 1.0 conformance package live
here.  **One canonical source** owns schema identity and generation:

| Role | Path |
| --- | --- |
| Canonical source | `ipfs_accelerate_py/mcplusplus/scripts/generate_schemas.py` |
| Generated / checked outputs | this tree (`schemas/`) |
| Drift gate | `python ipfs_accelerate_py/mcplusplus/scripts/generate_schemas.py --check` |

Language-local models (Python, TypeScript, and any later Go/Rust Profile H
maps) are **not** authorities.  If a language model disagrees with the
canonical source, the drift check fails.

## Authority rules

1. Edit the **canonical IR** in `scripts/generate_schemas.py` (catalog,
   Profile H artifact kinds, markers, fields).
2. Run the generator to refresh managed JSON Schema files.
3. Align language codecs to the same IR (field order and schema markers).
4. **Do not hand-edit** managed generated schema JSON after this task lands.
5. Schema acceptance is never “implemented” (ADR-0003).  Codecs and vectors
   still provide structural, canonical, and higher conformance levels.

## Tree layout

```text
schemas/
  README.md                          # this file
  canonicalization/
    mcpp-jcs-v1.schema.json          # McppJcsV1@1 (frozen; MCPP-024)
  profile-h/
    1.0/
      common.schema.json             # managed — shared primitives
      artifacts.schema.json          # managed — closed H artifact kinds
      x402-v2.schema.json            # managed — transport objects
```

New families (execution envelope, StateRef, confidential refs, …) add a
versioned subdirectory and a `SchemaId` catalog entry plus builder in the
generator.  Follow the Profile H pattern: closed kinds, explicit markers,
and a language-model drift check.

## SchemaId@1

Each catalog entry has:

- `schema_id` — stable logical id (e.g. `mcp++/profile-h/1.0/artifacts@1`)
- `relative_path` — path under this directory
- `$id` URL — `https://mcp-plus-plus.dev/schemas/<relative_path>`
- optional plan `interface` label (`McppJcsV1@1`, `SchemaId@1`, …)

List the catalog:

```bash
python ipfs_accelerate_py/mcplusplus/scripts/generate_schemas.py --list
```

## Profile H generation pattern

Profile H 1.0 is the reference pattern for single-source generation:

| Kind | Schema marker |
| --- | --- |
| `PaidCapability` | `mcp++/profile-h/paid-capability@1.0` |
| `PaymentQuote` | `mcp++/profile-h/payment-quote@1.0` |
| `PaymentAuthorization` | `mcp++/profile-h/payment-authorization@1.0` |
| `PaymentVerification` | `mcp++/profile-h/payment-verification@1.0` |
| `SettlementReceipt` | `mcp++/profile-h/settlement-receipt@1.0` |
| `PaidEntitlement` | `mcp++/profile-h/paid-entitlement@1.0` |
| `UsageRecord` | `mcp++/profile-h/usage-record@1.0` |
| `RefundRecord` | `mcp++/profile-h/refund-record@1.0` |
| `AccessReceipt` | `mcp++/profile-h/access-receipt@1.0` |

Common envelope fields on every artifact: `schema`, `createdAt`, `parents`,
`correlationId`.  Codecs under `tests-py/validators/profile_h.py` and
`tests-ts/src/profileH.ts` must expose the same kind → slug map and field
inventories as the generator IR.

## Commands

```bash
# Regenerate managed JSON Schema files from the canonical source
python ipfs_accelerate_py/mcplusplus/scripts/generate_schemas.py

# Fail if on-disk schemas or language models disagree with the source
python ipfs_accelerate_py/mcplusplus/scripts/generate_schemas.py --check

# Dry-run generate
python ipfs_accelerate_py/mcplusplus/scripts/generate_schemas.py --dry-run

# Canonical IR fingerprint (SHA-256)
python ipfs_accelerate_py/mcplusplus/scripts/generate_schemas.py --fingerprint
```

`--check` verifies:

1. Every catalog entry exists with the expected `$id`.
2. Managed Profile H documents match the closed kind / marker / field IR
   (and common / x402 documents match the builders).
3. Required language models (Python, TypeScript) expose the same Profile H
   `SCHEMAS` and `FIELDS` inventories as the canonical source.
4. Optional Go/Rust models, when they define Profile H markers, must not
   disagree.

Exit status `1` means drift; exit status `0` means agreement.

## Frozen vs managed

| Document | Mode | Notes |
| --- | --- | --- |
| `canonicalization/mcpp-jcs-v1.schema.json` | frozen | Authored with the mcpp-jcs-v1 spec; checked for `$id` / algorithm id only |
| `profile-h/1.0/*.schema.json` | managed | Regenerated from the Profile H IR in the generator |

Frozen files still appear in the SchemaId@1 catalog so identity and path
layout stay single-sourced.

## Related

- ADR-0002 crypto / `mcpp-jcs-v1` — `docs/architecture/decisions/0002-crypto-canonical.md`
- ADR-0003 conformance levels — `docs/architecture/decisions/0003-conformance-levels.md`
- Canonicalization spec — `docs/spec/canonicalization-mcpp-jcs-v1.md`
- Profile H payments — `docs/spec/x402-payments.md`
- Generated H summary — `docs/generated/profile-h-schemas-1.0.md`
- REQ-SCH-01 — single-source schema generation (traceability matrix)
