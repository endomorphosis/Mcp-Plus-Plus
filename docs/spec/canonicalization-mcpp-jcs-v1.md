# Canonicalization Algorithm: `mcpp-jcs-v1`

**Status:** Normative (MCP++ 1.0)  
**Algorithm identifier:** `mcpp-jcs-v1`  
**Interface:** `McppJcsV1@1`  
**Definition:** RFC 8785 JSON Canonicalization Scheme (JCS)  
**Authority:** ADR-0002 (`docs/architecture/decisions/0002-crypto-canonical.md`); sealed plan KD-5  
**Schema:** `ipfs_accelerate_py/mcplusplus/schemas/canonicalization/mcpp-jcs-v1.schema.json`  
**Related:** Profile B CID-native artifacts (`cid-native-artifacts.md`); golden vectors (MCPP-025); four-language implementations (MCPP-026…027)

This document is the normative specification of the MCP++ 1.0 canonicalization
algorithm named **`mcpp-jcs-v1`**. It freezes encoding rules used for hashing,
CID computation, and signature input construction for new normative artifacts.
It also defines the **migration path** and the absolute ban on **silent CID
changes** for historical artifacts.

---

## 1. Purpose and non-goals

### 1.1 Purpose

- Give every language runtime (Python, TypeScript, Go, Rust, and adapters) one
  shared algorithm identifier for deterministic JSON → bytes.
- Ensure that the same logical JSON value produces **byte-identical** UTF-8
  canonical form, and therefore the same digest and CID, across implementations.
- Provide a versioned handle so future encoding fixes require a **new** id
  (`mcpp-jcs-v2`, …) rather than mutating `mcpp-jcs-v1`.

### 1.2 Non-goals

- This document does **not** reimplement RFC 8785 edge-case catalogs as golden
  vectors; those land under `conformance/vectors/mcpp-jcs-v1` (MCPP-025).
- This document does **not** define signature algorithms, key ids, or DID
  methods (see ADR-0002).
- This document does **not** force historical Profile G/H hand codecs or
  legacy multicodecs to re-mint under `mcpp-jcs-v1` without an explicit
  migration record (see §8).

---

## 2. Algorithm identity (normative)

| Field | Value |
| --- | --- |
| Algorithm id | `mcpp-jcs-v1` |
| Standard | [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) — JSON Canonicalization Scheme (JCS) |
| Output | UTF-8 encoded canonical JSON text (no trailing newline) |
| Versioning rule | The string `mcpp-jcs-v1` MUST NOT be reused for behavior incompatible with this document and RFC 8785 |

Implementations MUST use the exact string `mcpp-jcs-v1` when declaring this
algorithm on wire fields, envelopes, vector metadata, and conformance reports.
Aliases, abbreviations, or silent “just sort the keys” implementations that
are not RFC 8785-conformant MUST NOT claim the id `mcpp-jcs-v1`.

If JCS cannot represent a needed value (see §6.7), implementations MUST
**document the exclusion** or reject the value—never invent a silent fork of
the algorithm under the same name.

---

## 3. Input data model (normative)

`mcpp-jcs-v1` operates on the **JSON data model** as refined by RFC 8785:

| JSON type | Representation notes |
| --- | --- |
| Object | Unordered map of string keys to JSON values; key order on input is irrelevant |
| Array | Ordered sequence of JSON values |
| String | Unicode string (see §6.3) |
| Number | IEEE-754 double semantics as constrained by JCS (see §6.4) |
| Boolean | `true` / `false` |
| Null | `null` |

Inputs MAY arrive as language-native structures that map cleanly onto this
model (e.g. Python `dict`/`list`, TypeScript plain objects/arrays). Inputs that
cannot be mapped without loss (cycles, non-JSON types) MUST be rejected before
canonicalization (see §6.7).

---

## 4. Output form (normative)

Let `JCS(value)` be the canonical JSON text produced by RFC 8785 for `value`.

1. **Text form:** `JCS(value)` is a single JSON text with **no** insignificant
   whitespace: no spaces after `:` or `,`, no newlines, no indentation, and no
   trailing newline.
2. **Byte form:** The **canonical byte sequence** is the **UTF-8** encoding of
   `JCS(value)`. That byte sequence is the sole input to:
   - content digests (default `sha2-256`),
   - CID construction for new portable payloads (default CIDv1, multicodec
     `raw` `0x55`, multihash `sha2-256` `0x12` — ADR-0002 §5),
   - signature message construction when a profile signs “the canonical bytes”
     of a JSON object (or when a profile composes signing strings from already
     JCS-canonicalized segments).
3. **Idempotency:** `JCS(parse(JCS(value)))` MUST equal `JCS(value)` for any
   value that is representable under this algorithm.

Implementations MUST NOT use pretty-printed JSON, language-local
`json.dumps` without JCS rules, or non-deterministic map iteration as the
canonical form while claiming `mcpp-jcs-v1`.

---

## 5. Pipeline for new normative artifacts (normative)

For any JSON-shaped content that MCP++ 1.0 mints as a portable CID’d artifact
under this algorithm:

```text
logical value
    → validate JSON data model (§3, §6.7)
    → JCS text per RFC 8785 (§6)
    → UTF-8 bytes (§4)
    → optional: sign over those bytes / declared composition (ADR-0002 §4)
    → digest (sha2-256 default)
    → CID (CIDv1 raw+sha2-256 default unless profile declares another multicodec)
    → store algorithm id "mcpp-jcs-v1" with the artifact metadata
```

Readers that verify a CID or signature MUST reconstruct the same canonical
bytes using the **algorithm recorded at mint time**. For new mint paths that
is `mcpp-jcs-v1`. For historical material, see §8.

---

## 6. Encoding rules (normative, RFC 8785 summary + MCP++ markers)

The following subsections are normative for MCP++ implementations of
`mcpp-jcs-v1`. Where this document summarizes RFC 8785, the RFC is
authoritative for any ambiguity not resolved here. Where this document adds
MCP++ version markers, migration, and fail-closed rules, this document is
authoritative for MCP++ conformance.

### 6.1 UTF-8

- Canonical text is encoded as **UTF-8** without a byte-order mark (BOM).
- A BOM MUST NOT appear in the canonical byte sequence.
- Invalid UTF-8 sequences MUST NOT be produced; string values are Unicode
  scalar sequences serialized per §6.3.

### 6.2 Object key order

- Object members MUST be serialized in **lexicographic order of the UTF-16
  code units** of their member names, as required by RFC 8785.
- Implementations MUST NOT rely on insertion order, hash iteration order, or
  locale-specific collation.
- Empty objects serialize as `{}`.

Note: lexicographic order of UTF-16 code units is **not** the same as
code-point order for all Unicode strings. Implementations MUST follow RFC 8785
exactly so that surrogate-bearing names sort identically across languages.

### 6.3 Unicode strings

- Strings are serialized as JSON strings with double quotes.
- Characters that require JSON escaping (quotation mark U+0022, reverse solidus
  U+005C, and control characters U+0000–U+001F) MUST use the escapes defined by
  RFC 8785 / JSON (RFC 8259).
- Characters outside the escapes required by JCS MUST be emitted as UTF-8 in
  the JSON text (not `\uXXXX` for ordinary printable characters), matching
  RFC 8785.
- Lone surrogates and other non-scalar sequences that cannot appear in valid
  Unicode strings for the implementation’s JSON model MUST be rejected
  (fail closed), not silently replaced.

### 6.4 Numbers

- Numbers MUST be serialized according to RFC 8785 number rules (ES6 / ECMAScript
  `Number.toString` style as specified by JCS).
- Implementations MUST preserve the JCS treatment of:
  - integers vs fractional values,
  - scientific notation thresholds,
  - **negative zero** (`-0` / `-0.0`): JCS serializes negative zero as `0`
    (there is no distinct `-0` token in the JCS number grammar for that case—
    follow RFC 8785 exactly).
- JSON numbers that cannot be represented losslessly as IEEE-754 binary64
  (for example integers outside the safe integer range when the platform
  only carries doubles) MUST be rejected or pre-encoded as **strings** by the
  artifact schema—not rounded silently under `mcpp-jcs-v1`.
- `NaN` and `±Infinity` are **not** JSON numbers and MUST be rejected (§6.7).

Profiles that need exact arbitrary-precision integers (e.g. amounts) MUST use
string or other schema-declared forms, not bare JSON numbers that lose
precision.

### 6.5 Null and booleans

- `null` serializes as the four characters `null`.
- Booleans serialize as `true` or `false`.
- Absence of a property is **not** the same as a property present with value
  `null`. Only present members appear in the object serialization.

### 6.6 Arrays

- Arrays preserve element order.
- Empty arrays serialize as `[]`.
- Elements are each JCS-serialized and joined with `,` without whitespace.

### 6.7 Duplicate keys, unsupported values, and fail-closed rejections

| Condition | Required behavior |
| --- | --- |
| Duplicate object keys on parse | Fail closed. RFC 8259 recommends unique keys; MCP++ parsers for `mcpp-jcs-v1` inputs MUST reject duplicate keys rather than last-key-wins or first-key-wins. |
| Non-JSON types (functions, symbols, class instances without declared mapping) | Fail closed before canonicalization. |
| Cycles / recursive structures | Fail closed. |
| `NaN`, `±Infinity` | Fail closed. |
| Binary blobs without a schema-defined encoding | Fail closed or encode as schema-declared base64/multibase strings first; never embed raw platform buffers as opaque JSON numbers. |
| Undefined / missing optional language values | Treat as **absent** (omit the member), not as `null`, unless a profile schema explicitly requires `null`. |

Silent coercion (e.g. converting `undefined` to `null`, or dropping unknown
types) while still labeling the result `mcpp-jcs-v1` is **forbidden**.

### 6.8 Version markers on artifacts

New normative MCP++ artifacts that use this algorithm SHOULD carry an explicit
algorithm or schema marker so verifiers do not guess:

| Mechanism | Example | Notes |
| --- | --- | --- |
| Algorithm field | `"canonicalization": "mcpp-jcs-v1"` | Preferred when a free-form object carries algorithm metadata |
| Schema marker | `"schema": "mcp++/…@1.0"` combined with suite policy that pins JCS | Profile-local schemas may pin the suite via ADR-0002 |
| Envelope / vector metadata | `"algorithm": "mcpp-jcs-v1"` in conformance vectors | Required for shared vectors (MCPP-025) |

The machine-readable schema for algorithm metadata is published at
`schemas/canonicalization/mcpp-jcs-v1.schema.json` and uses the interface
label **`McppJcsV1@1`**.

---

## 7. Relationship to CID construction (normative)

For new portable content-addressed payloads under ADR-0002 defaults:

1. `bytes = UTF-8(JCS(value))` under algorithm id `mcpp-jcs-v1`.
2. `digest = sha2-256(bytes)`.
3. `cid = CIDv1(multicodec=raw 0x55, multihash=sha2-256 0x12, digest)`.
4. Preferred string form: lowercase multibase base32 (`b…`), matching Kubo
   `ipfs add --cid-version=1 --raw-leaves` for the same bytes.

Profiles MAY declare a different multicodec for a specific artifact family.
That declaration MUST be explicit. Undeclared multicodec drift is forbidden.

A CID is **not** an algorithm identifier. Changing canonicalization without
changing the stored algorithm metadata is a **silent CID change** and is
forbidden (§8).

---

## 8. Migration and historical readability (normative)

### 8.1 Absolute rule: no silent CID changes

Implementations **MUST NOT** re-encode an existing stored artifact under
`mcpp-jcs-v1` (or any other algorithm) in a way that **changes** a previously
published or persisted CID **without** an explicit migration record.

Silent re-canonicalization is a protocol violation even when the new bytes
are “more correct.” Historical provenance DAGs, receipts, and proofs bind the
**recorded** CID and the **recorded** algorithm.

This restates sealed plan KD-5 and ADR-0002 §7 (REQ-CAN-03).

### 8.2 Read path (historical algorithms remain readable)

Readers MUST:

1. Detect the algorithm used at mint time from artifact metadata, fixture/profile
   era, or an explicit adapter table.
2. Verify digests, CIDs, and signatures against **that** algorithm’s bytes.
3. Accept historical Profile G/H hand codecs, legacy CIDv0, and non-default
   multicodecs when already recorded—without rewriting them.

Readers MUST NOT assume every CID’d JSON blob is `mcpp-jcs-v1` solely because
the peer is a 1.0 implementation.

### 8.3 Write path (new mint)

Writers of **new** normative MCP++ 1.0 artifacts, golden vectors, and portable
envelopes MUST:

1. Canonicalize with **`mcpp-jcs-v1`**.
2. Label the algorithm explicitly where the artifact or envelope has an
   algorithm field.
3. Use ADR-0002 CID and signature defaults unless the profile declares a
   versioned exception.

### 8.4 Dual-stack and promotion

A peer MAY implement both historical codecs and `mcpp-jcs-v1` concurrently
(**dual-stack**). Promotion of historical content to `mcpp-jcs-v1` MUST be
**adapter-mediated** (see planned historical adapters, MCPP-031):

| Step | Requirement |
| --- | --- |
| Identify source | Record source CID, source algorithm id, and source multicodec |
| Re-canonicalize | Produce `mcpp-jcs-v1` bytes only when the logical value is known losslessly |
| New CID | Mint a **new** CID for the new bytes; never overwrite the historical CID in place |
| Linkage | Persist a migration record linking `source_cid` → `target_cid` with both algorithm ids |
| Signatures | Re-sign only under explicit policy; historical signatures remain valid for historical bytes |

Promotion without a migration record, or replacing a stored CID string while
leaving dependents unaware, is a silent CID change and is forbidden.

### 8.5 Migration record (minimum fields)

When an operator or adapter promotes content, the migration record SHOULD
include at least:

```json
{
  "schema": "mcp++/canonicalization/migration@1",
  "source_cid": "bafkrei…",
  "source_algorithm": "profile-g-dag-json-local",
  "target_cid": "bafkrei…",
  "target_algorithm": "mcpp-jcs-v1",
  "reason": "promote-to-mcpplusplus-1.0-suite",
  "migrated_at": "2026-08-15T00:00:00Z"
}
```

The concrete schema name may be refined by adapter tasks; the **semantic**
requirements (source/target CID and algorithm, no in-place rewrite) are
normative here.

### 8.6 Version bumps

If RFC 8785 errata, a deliberate encoding fix, or an MCP++ profile change would
produce different bytes for the same logical value:

1. Publish a **new** algorithm id (e.g. `mcpp-jcs-v2`).
2. Keep `mcpp-jcs-v1` immutable and readable forever for existing CIDs.
3. Document a migration path analogous to §8.4–§8.5.

Reusing the string `mcpp-jcs-v1` for incompatible behavior is forbidden.

---

## 9. Conformance checklist (`McppJcsV1@1`)

An implementation claims `McppJcsV1@1` only when all of the following hold:

1. **Named algorithm:** Exposes and records the id `mcpp-jcs-v1`.
2. **RFC 8785 JCS:** Canonical text matches JCS for representable JSON values.
3. **UTF-8 bytes:** Canonical byte sequence is UTF-8 of that text without BOM
   or trailing newline.
4. **Key order:** Object members ordered per RFC 8785 (UTF-16 code unit order).
5. **Unicode:** String escaping matches JCS; invalid scalars fail closed.
6. **Numbers:** JCS number formatting including negative-zero handling; no
   silent precision loss; reject `NaN` / `±Infinity`.
7. **Null / bool / arrays:** Serialize exactly as JSON tokens without extra
   whitespace; array order preserved.
8. **Duplicate keys:** Rejected on parse of untrusted input.
9. **Unsupported values:** Rejected; no silent coercion under this algorithm id.
10. **Version markers:** New mint paths label `mcpp-jcs-v1` where algorithm
    fields exist.
11. **No silent CID changes:** Historical CIDs remain readable under their
    recorded algorithms; promotion uses explicit migration records only.
12. **Cross-language identity (when vectors present):** Same vector input yields
    identical canonical bytes, sha2-256 digests, and CIDs across supported
    languages (enforced by MCPP-025…028).

Structural schema acceptance alone is **not** `McppJcsV1@1` conformance.

---

## 10. Test and vector expectations (informative for this task)

Downstream tasks own fixtures; this section fixes the expected coverage so
implementations and vector authors share one matrix:

| Class | Examples | Expectation |
| --- | --- | --- |
| Empty / simple | `{}`, `[]`, scalars | Pinned UTF-8 bytes |
| Key order | Unsorted input keys | Output keys sorted per JCS |
| Unicode | Non-ASCII, escapes, edge code points | Byte-identical across languages |
| Numbers | Integers, fractions, large magnitudes, `-0` | JCS form; no platform drift |
| Null | Present `null` vs absent key | Distinct encodings |
| Arrays | Nested order sensitivity | Order preserved |
| Negatives | Duplicate keys, `NaN`, cycles | Fail closed |
| Identity | Same object in Py/TS/Go/Rust | Identical digest and CID |
| Historical | Pre-`mcpp-jcs-v1` fixtures | Still verify under recorded algorithm |

Golden vectors belong under:

```text
ipfs_accelerate_py/mcplusplus/conformance/vectors/mcpp-jcs-v1/
```

---

## 11. References

| Reference | Role |
| --- | --- |
| RFC 8785 — JSON Canonicalization Scheme (JCS) | Byte-level encoding rules |
| RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format | JSON data model |
| ADR-0002 — Mandatory crypto suite and `mcpp-jcs-v1` | Suite decision, historical readability |
| Sealed plan KD-5 | Algorithm name and no silent CID change |
| `cid-native-artifacts.md` | CID string form and artifact roles |
| `schemas/canonicalization/mcpp-jcs-v1.schema.json` | Machine-readable algorithm metadata |

---

## 12. Change control

| Change type | Required action |
| --- | --- |
| Clarification that does not alter any canonical bytes | Amend this document; keep id `mcpp-jcs-v1` |
| Behavior that would alter canonical bytes for any previously valid input | New algorithm id; migration path; do not redefine `mcpp-jcs-v1` |
| Historical codec support | Adapter + migration record; never silent rewrite |

**Document version:** 1.0  
**Last updated:** 2026-08-15  
**Task:** MCPP-024
