# Profile H 1.0 generated schema reference

This reference is generated from the closed schemas in
`schemas/profile-h/1.0`. The schemas and codecs, not this summary, are
normative.

| Artifact | Schema marker | Profile H commitment |
|---|---|---|
| `PaidCapability` | `mcp++/profile-h/paid-capability@1.0` | operation, seller, authority, price, validity, signature |
| `PaymentQuote` | `mcp++/profile-h/payment-quote@1.0` | capability/catalog/descriptor/request, requirements, nonce, expiry, idempotency |
| `PaymentAuthorization` | `mcp++/profile-h/payment-authorization@1.0` | quote/request and redacted payload/signature commitments |
| `PaymentVerification` | `mcp++/profile-h/payment-verification@1.0` | authorization, verifier decision, freshness, evidence |
| `SettlementReceipt` | `mcp++/profile-h/settlement-receipt@1.0` | verification, outcome, amount/network and response commitments |
| `PaidEntitlement` | `mcp++/profile-h/paid-entitlement@1.0` | settlement, subject/capability scope, quota, consumption, expiry |
| `UsageRecord` | `mcp++/profile-h/usage-record@1.0` | entitlement, unit, input/output commitments and units |
| `RefundRecord` | `mcp++/profile-h/refund-record@1.0` | settlement/request, decision/outcome and evidence |
| `AccessReceipt` | `mcp++/profile-h/access-receipt@1.0` | request, C/D/G/commercial decisions, allow/deny and result |

Canonical blocks are UTF-8 JSON with object keys sorted by UTF-8 bytes, no
insignificant whitespace, duplicate keys, floats, non-safe integers, or unknown
artifact fields. CIDs are CIDv1, `dag-json` (`0x0129`), sha2-256, lower-case
base32. The default bounds are 1 MiB per artifact, 32 KiB per decoded x402
object, eight requirements, depth 16, 8 KiB strings, 32 parents, and a five
minute quote lifetime. Hard maxima match section 15 of the Profile H spec.

The artifact schemas deliberately contain commitments rather than wallet
addresses, transaction hashes, request arguments, raw x402 payloads, or raw
signatures. x402 transport payloads are described separately by
`x402-v2.schema.json` and must be redacted before logging or artifact creation.
