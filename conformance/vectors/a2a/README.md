# A2A execution extension vectors (MCPP-055)

Interface: **`A2AExtensionSchema@1`**  
Wire URI: `https://mcplusplus.io/extensions/execution/v1`  
Alias (non-wire): `io.mcplusplus.execution@1`  
Spec: `ipfs_accelerate_py/mcplusplus/docs/spec/a2a-extension.md`  
Schemas: `ipfs_accelerate_py/mcplusplus/schemas/a2a/`

## Suites

| File | Kind | Expected |
| --- | --- | --- |
| `well-formed.json` | positive | All cases validate (`valid: true`) |
| `malformed.json` | negative | Malformed extension URIs/fields — **expected failures** |
| `unsupported-profile.json` | negative | Unknown or non-advertised profiles — **expected failures** |
| `manifest.json` | index | Suite map, error codes, CID catalog |

## Validation model

1. Load the JSON Schema named by each case’s `schema_file` under `schemas/a2a/`.
2. Validate `payload` with Draft 2020-12.
3. For cases with `semantic_rules: ["requested_subset_of_advertised"]`, also require  
   `set(requested_profiles) ⊆ set(advertised_profiles)`.
4. Negative suites: overall case `valid` is `false`. When `schema_valid` is
   true and `semantic_valid` is false, structural schema may pass but the
   semantic rule must still fail closed.

## Acceptance (MCPP-055)

- Malformed extension vectors are expected failures.
- Unsupported profile vectors are expected failures.
- Well-formed extension, activation, metadata, and portable terminal evidence validate.
