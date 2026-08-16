# mcpp-jcs-v1 golden vectors

Cross-language golden vectors for MCP++ algorithm id `mcpp-jcs-v1` (RFC 8785 JCS).

## Layout

| File | Category |
| --- | --- |
| `numbers.json` | Number serialization & NaN/Infinity rejection |
| `unicode.json` | UTF-8 strings, escapes, UTF-16 key sort, lone surrogates |
| `null.json` | Present `null` vs absent keys |
| `empty-object.json` | `{}` and non-canonical whitespace |
| `nested-keys.json` | Recursive key sort, unsorted claims, cycles |
| `duplicate-keys.json` | Unique keys vs fail-closed duplicate rejection |
| `manifest.json` | Index + coverage matrix |

## Vector shape (`GoldenVector@1`)

Each case includes:

- `source` and/or `source_json` — logical value or raw JSON text under test
- For **positive** cases: `canonical_utf8`, `canonical_bytes_hex`, `canonical_bytes_base64`, `sha256`, `cid` (CIDv1 raw+sha2-256 base32)
- `signature_input` — the UTF-8 JCS bytes (hex) that Ed25519 would sign
- `signature` / `signature_placeholder` — null placeholder until suite signing tasks
- `expected_validator_result.accept` — true/false plus `reason_code` on reject

## Coverage (acceptance MCPP-025)

Every listed category has **≥1 positive** and **≥1 negative** case.

## Normative refs

- `docs/spec/canonicalization-mcpp-jcs-v1.md`
- `schemas/canonicalization/mcpp-jcs-v1.schema.json`
- RFC 8785
