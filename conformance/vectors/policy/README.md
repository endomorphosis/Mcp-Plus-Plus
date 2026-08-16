# Policy vectors (PolicyVector@1)

Shared Profile D / `PolicyEvaluator@1` cases for MCP++ 1.0 gap-closure (**MCPP-048**).

## Acceptance

Every listed case has an **expected decision**. Conflicting policies resolve by a
**documented deterministic rule** (below).

| Case id | Layer | Expected decision | Primary reason / note |
| --- | --- | --- | --- |
| `policy_version_mismatch` | gate | `deny` | `policy_version_mismatch` |
| `missing_context` | gate | `deny` | `missing_context` |
| `stale_root` | gate | `deny` | `stale_root` |
| `deadline` | temporal | `deny` | `no_matching_permission` (permission window elapsed) |
| `revoked_before_execution` | revocation | `deny` | `revoked_before_execution` |
| `allow_with_obligations` | deontic | `allow_with_obligations` | obligation spawned |
| `unsatisfied_obligation` | obligation | `allow_with_obligations` | obligation `status=overdue` |
| `compensating_action` | obligation | `allow_with_obligations` | `compensation[]` recorded |
| `conflicting_policies` | conflict | `deny` | `prohibition_matched` |

## Deterministic conflict resolution (normative)

When multiple policy documents are supplied to `PolicyEvaluator@1`:

1. **Any matching prohibition across the entire set wins** (most restrictive).
2. Permissions and obligations are **unioned**.
3. Clause iteration order is stable: sort by
   `(clause_id, clause_type, action, source_index)`.

This is the same rule as `docs/spec/temporal-deontic-policy.md` §6.4. The
`conflicting_policies` vector encodes permission in policy A and a matching
prohibition in policy B; the expected decision is always `deny` with
`reason_code=prohibition_matched`.

## Fail-closed gates (order)

Before deontic matching, gates fire in this order (first hit wins):

1. invalid intent / logical_time → `invalid_input`
2. invalid delegation → `delegation_invalid`
3. missing required context root → `missing_context`
4. stale context root CID → `stale_root`
5. policy version mismatch → `policy_version_mismatch`
6. prior-event revocation before execution → `revoked_before_execution`

## Layout

| Path | Role |
| --- | --- |
| `manifest.json` | Case index (`PolicyVector@1`) |
| `recipes.json` | Compact recipe index (source of truth for inputs + expected) |
| `fixtures/` | Materialized case envelopes (generated from recipes) |
| `generate_fixtures.py` | Regenerates fixtures from recipes |
| `evaluate.py` | Authoritative Python evaluator (real `PolicyEvaluator@1`, no mocks) |

## Vector shape

Each fixture includes:

- `id`, `polarity`, `layer`, `interface: PolicyVector@1`
- `inputs` — kwargs-shaped payload for `PolicyEvaluator.evaluate`
- `expected` — required `decision` / `granted` / optional `reason_code` and obligation checks
- `languages`: `python`, `typescript`, `go`, `rust`

## How to run

```bash
# Authoritative Python suite (validation gate)
cd ipfs_accelerate_py/mcplusplus
python -m pytest -q tests-py/integration -k policy_negative

# Direct evaluator
python conformance/vectors/policy/evaluate.py

# Regenerate fixtures from recipes
python conformance/vectors/policy/generate_fixtures.py
```

## Normative refs

- `docs/spec/temporal-deontic-policy.md` (§6 PolicyEvaluator@1, §6.3 gates, §6.4 deontic matching)
- Interfaces: `PolicyEvaluator@1`, `PolicyDecision@1`, `PolicyVector@1`
- Obligation lifecycle: `schemas/policy/obligation-event-1.schema.json` (MCPP-047)
