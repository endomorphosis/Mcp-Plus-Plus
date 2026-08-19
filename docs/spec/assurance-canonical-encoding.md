# Assurance Canonical Encoding — DAG-CBOR and CID Profile

**Status:** Normative (Canonical Contract Compiler encoding)
**Release:** `formal-claim-algebra-v1`
**Profile:** `facp/dag-cbor-profile@1`
**Owning task:** FACP-033
**Goal:** FACP-G310 (Canonical Contract Compiler)
**Bundle:** `facp/contracts/encoding`
**Companion:** `Mcp-Plus-Plus/docs/spec/assurance-idl.md` (OperationSpec shape);
`Mcp-Plus-Plus/docs/spec/formal-claim-algebra-v1.md` (EvidenceEnvelope product)

This specification pins **one** deterministic byte representation and **exact**
CID derivation for every Formal Assurance Control Plane (FACP) security-critical
persisted artifact. It closes the encoding fragmentation where Profile A allowed
JSON/DAG-JSON/DAG-CBOR, Profile B left JSON/CBOR open while pinning raw CIDs, and
Profiles G/H pinned DAG-JSON.

Profiles G/H remain DAG-JSON for their own artifacts. This profile is the sole
authority for CCC signed/persisted identity of:

| Artifact family | Schema id |
| --- | --- |
| EvidenceEnvelope@1 | `facp/evidence-envelope@1` |
| OperationSpec@1 | `facp/operation-spec@1` |
| AdmissionToken@1 | `facp/admission-token@1` |
| EffectReceipt@1 | `facp/effect-receipt@1` |

No second security-critical canonical form is permitted for these families.

## 1. Goals

- Guarantee byte-identical canonical DAG-CBOR across Python, TypeScript, Rust,
  and Go for the same logical value.
- Derive CIDs by a fixed, decode-and-recompute procedure — never regex-only
  admission and never fabricated hex/`Qm` identities.
- Reject duplicate keys, indefinite lengths, non-minimal integers, floats,
  unknown CBOR tags, unsorted maps, and malleable encodings as negative vectors.
- Pin exactly one CID family per artifact class (signed DAG-CBOR vs opaque raw).

## 2. Normative references (profiled)

Implementations MUST conform to IPLD DAG-CBOR strictness as profiled here:

- Definite-length encoding only (no indefinite-length strings, bytes, arrays, or maps).
- Map keys MUST be UTF-8 text strings, unique, and sorted by **increasing key
  length**, then by **lexicographic order of UTF-8 bytes**.
- Integers MUST use the shortest CBOR encoding that preserves the value.
- The only allowed CBOR tag is **tag 42** (IPLD CID link).
- Tag 42 payloads MUST be a byte string beginning with the identity multibase
  prefix `0x00`, followed by a binary CIDv1.

Where this profile is stricter than plain CBOR or a non-strict DAG-CBOR encoder,
this profile wins.

## 3. Data model (admitted values)

Logical values admitted before encoding:

| Kind | Rule |
| --- | --- |
| `null` | CBOR simple `null` |
| `bool` | CBOR `true` / `false` |
| `int` | Arbitrary-precision signed integer encoded in minimal CBOR major type 0/1 form; JSON/transport floats are forbidden |
| `text` | UTF-8 NFC text; no unpaired surrogates |
| `bytes` | Finite byte string |
| `list` | Ordered sequence of admitted values |
| `map` | String-keyed map; keys unique; order for encoding is the sort order above |
| `link` | IPLD CID carried only as tag 42 (never as a plain text CID string inside signed DAG-CBOR identity bytes) |

**Forbidden** in security-critical identity bytes:

- IEEE floats, including finite floats, `-0.0`, `NaN`, and infinities
- Non-string map keys
- Duplicate map keys
- CBOR tags other than 42
- Indefinite-length items
- Non-minimal integer encodings
- Second encodings of the same logical value (malleability)

Decimal / numeric rule: every security-critical number is an **integer**.
Resource bounds, versions, timestamps-as-unix-seconds, nonces-as-integers, and
counts MUST encode as CBOR integers. Textual decimal strings are not a second
numeric form for identity; if a field is defined as text, it is text, not a float.

## 4. Canonical encode / decode procedure

### 4.1 Encode

1. Validate the logical value against the closed artifact schema (unknown fields
   fail closed at the schema layer with `UNKNOWN_FIELD`).
2. Reject any forbidden data-model construct (`FORBIDDEN_FLOAT`,
   `NON_STRING_MAP_KEY`, …).
3. Emit exactly one DAG-CBOR byte string under §2–§3.
4. Compute the artifact CID under §5.

There is no alternate “pretty”, “DAG-JSON equivalent”, or “canonical JSON”
identity for these families.

### 4.2 Decode (strict)

1. Reject empty or over-bound byte strings.
2. Decode as DAG-CBOR under §2.
3. **Re-encode** the decoded value and require byte-identity with the input.
   Any difference is `MALLEABLE_ENCODING` / non-canonical form.
4. Validate the logical value against the closed schema.

Decode-and-reencode is mandatory. Accepting a CBOR value solely because a
permissive decoder produced a dict is non-conformant.

## 5. CID families (exact derivation)

### 5.1 Family `assurance_signed_dag_cbor` (default for the four artifacts)

For canonical DAG-CBOR bytes `B`:

```text
mh  = sha2-256(B)                         # multihash code 0x12, length 32
cid = CIDv1(version=1, codec=dag-cbor/0x71, multihash=mh)
text = multibase-base32-lower(cid)        # leading 'b', alphabet a-z2-7
```

Binary layout before multibase:

```text
0x01 || 0x71 || 0x12 || 0x20 || <32-byte digest>
```

Rendered identities for this family begin with `bafyrei…`. Implementations MUST
decode the CID, verify version/codec/multihash, recompute from `B`, and require
the textual form to equal the strict lowercase base32 encoding. Regex-only CID
checks are prohibited.

### 5.2 Family `assurance_opaque_raw`

Opaque byte blobs that are not DAG-CBOR maps (signature material, raw digests
retained as bytes, public-key multicodec material) use:

```text
mh  = sha2-256(B)
cid = CIDv1(version=1, codec=raw/0x55, multihash=mh)
text = multibase-base32-lower(cid)        # bafkrei…
```

Binary layout: `0x01 || 0x55 || 0x12 || 0x20 || <32-byte digest>`.

### 5.3 Closed set

| Family id | version | codec | multihash | multibase | Example prefix |
| --- | --- | --- | --- | --- | --- |
| `assurance_signed_dag_cbor` | 1 | `dag-cbor` `0x71` | `sha2-256` `0x12` | base32 lower | `bafyrei` |
| `assurance_opaque_raw` | 1 | `raw` `0x55` | `sha2-256` `0x12` | base32 lower | `bafkrei` |

**Not admitted** as identity for these CCC artifacts:

- CIDv0 (`Qm…`)
- `dag-json` (`0x0129`, `baguqeera…`) for signed CCC artifacts
- Raw hex digests or `sha256:<hex>` aliases
- Truncated or uppercase multibase strings
- A CID whose codec does not match the family of the retained bytes

Each artifact family in the table in the preamble MUST use
`assurance_signed_dag_cbor` for its sealed identity. Cross-links inside those
artifacts MUST be tag-42 CIDs whose target codec matches the target family.

## 6. Link encoding

Inside signed DAG-CBOR identity bytes, every field that names another
content-addressed artifact (`*_cid`, parent lists of artifact CIDs, schema
links when carried as IPLD links) MUST encode as:

```text
tag(42) || bstr( 0x00 || binary_cid )
```

The tag head MUST be the two-byte form `0xd82a`. The byte string MUST include
the identity multibase prefix `0x00`. Plain UTF-8 CID strings MUST NOT appear
in place of links inside identity bytes (transport JSON may still show string
CIDs; the identity encoding is Tag 42).

## 7. Unknown fields and closure

Canonical encoding does not invent schema fields. Closed artifact schemas
(`additionalProperties` / `unevaluatedProperties` false) reject unknown
normative fields before CID sealing. An encoded map that includes an unknown
key is not a valid sealed instance of that artifact family, even if the CBOR
is otherwise strict.

## 8. Stable error codes

| Code | Meaning |
| --- | --- |
| `NON_DEFINITE_LENGTH` | Indefinite-length CBOR item |
| `DUPLICATE_MAP_KEY` | Duplicate key in a CBOR map |
| `UNSORTED_MAP_KEYS` | Map keys not in length-then-lex order |
| `NON_MINIMAL_INTEGER` | Integer not in shortest CBOR form |
| `FORBIDDEN_FLOAT` | Float / NaN / Infinity / `-0.0` present |
| `FORBIDDEN_TAG` | CBOR tag other than 42 |
| `INVALID_CID_LINK` | Tag 42 payload missing `0x00` prefix or not a CIDv1 |
| `NON_STRING_MAP_KEY` | Map key is not UTF-8 text |
| `MALLEABLE_ENCODING` | Decode-and-reencode bytes differ |
| `WRONG_CID_FAMILY` | CID version/codec/multihash/multibase mismatch |
| `NON_CANONICAL_CID_TEXT` | CID text is not the strict lowercase base32 form |
| `PSEUDO_CID` | Hex digest, `Qm…`, or other non-IPLD alias |
| `UNKNOWN_FIELD` | Schema-level unknown property |
| `REGEX_ONLY_CID` | Implementation attempted regex-only CID admission |

## 9. Conformance vectors

Normative vectors:

`Mcp-Plus-Plus/conformance/vectors/assurance-canonical-encoding.json`

The vector file MUST include:

- Positive cases with exact `canonical_hex` and `cid` for each fixture
- Negative cases for duplicate keys, indefinite lengths, unsorted maps,
  non-minimal integers, forbidden floats, forbidden tags, malformed links,
  wrong CID families, and pseudo-CIDs
- Mutation cases that flip a retained byte or substitute an alternate encoding
  of the same logical value and require failure

Passing the vectors is necessary but not sufficient for multi-language parity;
language bindings (later FACP tasks) MUST reproduce the same hex and CID.

## 10. Security considerations

- Ambiguous encodings enable identity confusion and signature bypass. Strict
  decode-and-reencode closes CBOR malleability.
- Regex-only CID checks admit lookalike strings that do not bind bytes.
- Allowing both DAG-JSON and DAG-CBOR for the same security-critical artifact
  creates two authorities; this profile forbids that split for CCC artifacts.
- Floats enable NaN/signaling and cross-language numeric drift; they are banned
  from identity bytes.

## 11. Normative artifacts

| Artifact | Path |
| --- | --- |
| This specification | `Mcp-Plus-Plus/docs/spec/assurance-canonical-encoding.md` |
| Conformance vectors | `Mcp-Plus-Plus/conformance/vectors/assurance-canonical-encoding.json` |
| Spec tests | `Mcp-Plus-Plus/tests-py/integration/test_assurance_canonical_encoding_spec.py` |
