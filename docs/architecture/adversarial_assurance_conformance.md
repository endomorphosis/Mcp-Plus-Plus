# Adversarial Assurance Conformance Decision (AAE-013)

**Interface:** `AdversarialAssuranceConformanceDecision@1`  
**Schema:** `aae/conformance-decision@1`  
**Task:** AAE-013  
**Decision:** `shared_requirement`  
**MCP++ change justified:** `true`  
**Date:** 2026-08-13  

## 1. Decision summary

A **genuine cross-language shared-wire requirement is demonstrated** for two closed artifacts only:

1. **Mutation campaign plan** identity wire (`MutationCampaignPlan@1`)
2. **Assurance campaign receipt** identity wire (`AssuranceCampaignReceipt@1`)

Therefore AAE-013 **admits** the minimal shared MCP++ schemas and flat canonical vectors listed below. No MCP++ profile, runtime, application payload, CID authority, cryptography, or harness model-map rewrite is created or changed.

| Path | Status |
| --- | --- |
| `ipfs_accelerate_py/mcplusplus/docs/architecture/adversarial_assurance_conformance.md` | **mandatory** decision document (this file) |
| `ipfs_accelerate_py/mcplusplus/schemas/adversarial_assurance_campaign.schema.json` | **admitted** minimal shared schema |
| `ipfs_accelerate_py/mcplusplus/schemas/adversarial_assurance_receipt.schema.json` | **admitted** minimal shared schema |
| `ipfs_accelerate_py/mcplusplus/conformance/vectors/adversarial_assurance_campaign_valid.json` | **admitted** flat suite vector |
| `ipfs_accelerate_py/mcplusplus/conformance/vectors/adversarial_assurance_campaign_invalid.json` | **admitted** flat suite vector (fail-closed negatives) |
| `ipfs_accelerate_py/mcplusplus/conformance/vectors/adversarial_assurance_receipt_valid.json` | **admitted** flat suite vector |

## 2. Evidence of a shared cross-language requirement

### 2.1 Multi-language conformance surface already exists

MCP++ already operates a single flat vector directory consumed by four language harnesses:

| Language | Harness root | Vector discovery |
| --- | --- | --- |
| Python | `tests-py/integration/test_conformance_vectors.py` | `conformance/vectors/*.json` |
| Go | `tests-go/conformance_vectors_test.go` | same directory |
| Rust | `tests-rs/tests/conformance_vectors_test.rs` | same directory |
| TypeScript | `tests-ts/src/__tests__/conformance-vectors.test.ts` | same directory |

That surface is the only language-neutral wire/conformance authority for this repository (AAE-004 inventory: `MCPPlusPlusBoundary@1`). Application orchestration remains in accelerate/datasets/kit; shared identity bytes and fail-closed enums belong here when they must be interpreted outside a single language runtime.

### 2.2 Campaign plan and campaign receipt are the shared identity boundary

AAE-008 through AAE-012 froze closed, versioned models in
`ipfs_datasets_py.logic.software_contracts.adversarial_assurance`. Two of those
artifacts are the durable, content-addressed objects other components and
future non-Python verifiers must accept without loading Python:

- **Campaign plan** binds repository state, policy, budget, targets, operators, sandbox/rollback requirements, and plan CID.
- **Campaign receipt** binds admitted sets, outcomes, survivors, vacuity, held-out result, authorization, seal scope/status, signature binding, and receipt CID.

These are not application payloads (no operator implementations, no analysis engines, no promotion orchestration). They are **identity wire** for assurance evidence.

### 2.3 Ownership split (plan §4)

| Owner | Responsibility |
| --- | --- |
| datasets | Canonical Python models, content CID authority, package exports |
| kit | Durable CAS/history over existing coordination primitives |
| accelerate | Campaign composition, workers, CLI, promotion orchestration |
| MCP++ | **Only** demonstrably shared mutation-campaign schema, assurance-receipt schema, and flat vectors |

AAE-013 exercises that MCP++ permission envelope. A new AAE or MCP++ profile remains **forbidden**.

### 2.4 Why the no-change branch does not apply

The no-change branch is reserved for the case where no multi-language consumer of campaign/receipt identity exists. That case is not present:

1. Four harnesses already share one vector directory and fail closed on unknown canonical models.
2. Campaign plan and receipt CIDs are the portable evidence objects of AAE-G020.
3. Language-neutral JSON Schema is the only way a Go/Rust/TS (or external) verifier can fail closed on unknown fields/enums without importing datasets Python models.
4. AAE-013's own validation command is multi-language; the admitted vectors must be discoverable by those harnesses without rewriting them.

## 3. What was admitted (minimal)

### 3.1 Schemas

Both schemas are draft-2020-12 JSON Schema documents with:

- `additionalProperties: false` on every object (unknown fields fail closed)
- closed `enum` / `const` sets for statuses, risk classes, seal scope, signature algorithm/authority
- CIDv1 base32 patterns (`^b[a-z2-7]+$`)
- schema and interface constants identical to the datasets contracts (no parallel vocabulary)

They intentionally **omit** operator implementations, remediation plans, analysis reports, promotion orchestration, and any profile-scoped application payload.

### 3.2 Flat vectors

Vectors use the **suite** shape already used by profile-specific suites:

- top-level `schema`, `suite`, `schema_ref`, `interface_id`, `cases`
- **no** canonical `{model, payload}` envelope

Existing py/go/rs/ts harnesses discover every `conformance/vectors/*.json` file. When both `model` and `payload` are absent, they **skip** the file (same behavior as Profile H suite vectors). That is deliberate:

- unknown AAE model names would otherwise fail closed inside the harness model maps (correct fail-closed behavior)
- harness model maps cannot be extended in AAE-013 (conflict policy: consume harnesses, do not rewrite them)
- suite vectors remain the single flat source of valid/invalid cases for schema-driven validators and future model-map admission

Reproduction proof for AAE-013 is therefore:

1. All four language harnesses still pass on the shared vector directory (task validation command).
2. Suite files are present, language-neutral, and paired with the admitted schemas.
3. Invalid suite cases encode unknown-field and unknown-enum failures.

### 3.3 Explicit non-changes

| Forbidden or out-of-scope item | Status |
| --- | --- |
| New MCP++ profile (AAE or otherwise) | not created |
| MCP++ runtime / codec / transport changes | none |
| Application payloads inside existing profiles | none |
| Harness model-map edits (py/go/rs/ts) | none |
| Datasets contract rewrites | none (consumed only) |
| New CID profile or cryptography | none |
| Local generic envelope | forbidden |

## 4. Fail-closed rules (normative)

1. Unknown object properties under admitted schemas **must** be rejected.
2. Unknown enum members (risk class, terminal status, held-out result, seal scope item, seal status, signature verification status) **must** be rejected.
3. Unsupported `schema` / `interface_id` constants **must** be rejected.
4. Canonical harness model maps continue to reject unknown `model` names; AAE suite vectors therefore omit `{model,payload}` until a later, separately owned harness admission task registers AAE models.
5. Datasets remains the content-addressing and Python model authority; MCP++ schemas do not recompute CIDs and do not authorize promotion.

## 5. Validation

Task validation (must stay green after this change):

```bash
python3 -m pytest -q ipfs_accelerate_py/mcplusplus/tests-py/integration/test_conformance_vectors.py \
  && (cd ipfs_accelerate_py/mcplusplus/tests-go && go test ./...) \
  && cargo test --manifest-path ipfs_accelerate_py/mcplusplus/tests-rs/Cargo.toml \
  && (cd ipfs_accelerate_py/mcplusplus/tests-ts && npm test)
```

Python note: the harness imports `validators` from `tests-py`. When running under a PYTHONPATH that includes only the mcplusplus root (not `tests-py`), add `ipfs_accelerate_py/mcplusplus/tests-py` to `PYTHONPATH`, or use an environment that already exposes that path.

Schema-level checks for the admitted suite (optional local probe; not a harness rewrite):

```bash
python3 - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

root = Path("ipfs_accelerate_py/mcplusplus")
campaign_schema = json.loads((root / "schemas/adversarial_assurance_campaign.schema.json").read_text())
receipt_schema = json.loads((root / "schemas/adversarial_assurance_receipt.schema.json").read_text())
cv = Draft202012Validator(campaign_schema)
rv = Draft202012Validator(receipt_schema)

for name, validator in [
    ("adversarial_assurance_campaign_valid.json", cv),
    ("adversarial_assurance_campaign_invalid.json", cv),
    ("adversarial_assurance_receipt_valid.json", rv),
]:
    suite = json.loads((root / "conformance/vectors" / name).read_text())
    for case in suite["cases"]:
        errors = sorted(validator.iter_errors(case["payload"]), key=lambda e: e.path)
        if case["valid"]:
            assert not errors, (name, case["id"], errors[0].message)
        else:
            assert errors, (name, case["id"], "expected failure")
print("schema suite probe ok")
PY
```

## 6. Machine-readable decision record

```json
{
  "schema": "aae/conformance-decision@1",
  "interface_id": "AdversarialAssuranceConformanceDecision@1",
  "task_id": "AAE-013",
  "decision": "shared_requirement",
  "mcpplusplus_change_justified": true,
  "decision_document": "ipfs_accelerate_py/mcplusplus/docs/architecture/adversarial_assurance_conformance.md",
  "admitted_paths": [
    "ipfs_accelerate_py/mcplusplus/schemas/adversarial_assurance_campaign.schema.json",
    "ipfs_accelerate_py/mcplusplus/schemas/adversarial_assurance_receipt.schema.json",
    "ipfs_accelerate_py/mcplusplus/conformance/vectors/adversarial_assurance_campaign_valid.json",
    "ipfs_accelerate_py/mcplusplus/conformance/vectors/adversarial_assurance_campaign_invalid.json",
    "ipfs_accelerate_py/mcplusplus/conformance/vectors/adversarial_assurance_receipt_valid.json"
  ],
  "forbidden": [
    "new_mcpplusplus_profile",
    "runtime_or_codec_change",
    "application_payload_in_existing_profile",
    "harness_model_map_rewrite",
    "new_cid_or_crypto_authority"
  ],
  "fail_closed": {
    "unknown_fields": true,
    "unknown_enums": true,
    "unknown_canonical_models_in_harness": true
  },
  "vector_shape": "suite_without_model_payload_envelope",
  "datasets_authority": "ipfs_datasets_py.logic.software_contracts.adversarial_assurance",
  "interfaces": [
    "MutationCampaignPlan@1",
    "AssuranceCampaignReceipt@1"
  ]
}
```

## 7. Follow-on (out of scope for AAE-013)

- Register AAE model names in the four harness model maps only when a consumer task owns that rewrite and can keep fail-closed parity.
- Bind kit/accelerate verification paths to the admitted schemas without inventing local envelopes.
- Keep promotion authorization and seal publication outside MCP++ shared wire.
