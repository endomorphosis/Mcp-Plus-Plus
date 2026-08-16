# Adversarial cryptographic negative vectors (AdversarialVector@1)

Shared fail-closed UCAN / Profile C vectors for MCP++ 1.0 gap-closure (**MCPP-044**).

## Acceptance

Every listed case **fails closed** in Python, TypeScript, Go, and Rust.

| Case id | Layer | Primary reason codes |
| --- | --- | --- |
| `forged_signature` | cryptographic | `invalid_signature` |
| `altered_bytes` | cryptographic | `invalid_signature` |
| `wrong_audience` | attenuation | `audience_mismatch` |
| `expanded_capabilities` | attenuation | `method_attenuation_failed` |
| `expanded_resources` | attenuation | `resource_attenuation_failed` |
| `expired` | attenuation | `expired` |
| `future_nbf` | attenuation | `not_yet_valid` |
| `revoked` | revocation | `revoked` |
| `missing_proof` | invocation | `missing_proof_cid` |
| `replay` | attenuation | `replayed` |
| `wrong_executor` | attenuation | `executor_binding_failed` |
| `wrong_policy_cid` | attenuation | `policy_cid_mismatch` |
| `valid_peerid_invalid_ucan` | authority | `peerid_not_authority` |

## Layout

| Path | Role |
| --- | --- |
| `manifest.json` | Case index (`AdversarialVector@1`) |
| `recipes.json` | Compact recipe index (no bulk golden dumps) |
| `fixtures/` | Deterministic signed inputs + requests |
| `generate_fixtures.py` | Regenerates fixtures from fixed test seeds |
| `evaluate.py` | Authoritative Python evaluator (real verifiers, no mocks) |
| `runners/evaluate.ts` | TypeScript runner |
| `runners/evaluate.go` | Go runner |
| `runners/evaluate.rs` | Rust runner |

## Vector shape

Each negative fixture includes:

- `id`, `polarity: "negative"`, `layer`
- Input material (`token` / `chain` / `invocation` / `revocation_record` / peer fields)
- `request` context when attenuation is exercised
- `issuer_public_keys` for cryptographic verification
- `expected_reason_codes`
- `languages`: `python`, `typescript`, `go`, `rust`

Keys under `fixtures/keys.json` use **test-only** fixed Ed25519 seeds.

## How to run

```bash
# Authoritative Python suite (validation gate)
cd ipfs_accelerate_py/mcplusplus
python -m pytest -q tests-py/integration -k adversarial_ucan

# Direct evaluator
python conformance/vectors/crypto/adversarial/evaluate.py

# Regenerate fixtures
python conformance/vectors/crypto/adversarial/generate_fixtures.py
```

Language runners under `runners/` load the same fixtures and assert fail-closed outcomes.

## Normative refs

- `docs/spec/ucan-delegation.md`
- ADR-0002 (Ed25519 / mcpp-jcs-v1)
- ADR-0003 (conformance levels)
- Interfaces: `DelegationProof@1`, `AttenuationPolicy@1`, `RevocationRecord@1`, `AdversarialVector@1`
