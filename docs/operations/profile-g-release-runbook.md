# Profile G release and incident runbook

This runbook is for operators promoting MCP++ Profiles A-G with the optional
Profile G risk-scheduling capability. The gate is deliberately fail-closed:
`GO` means every profile dependency, every configured service transport, the
durable three-peer scenario, the published performance workload, the desktop
mapping, and the bounded glasses handoff passed together.

## Run the gate

From the integration-workspace root:

```bash
python scripts/run_mcplusplus_release_gate.py
```

The command runs canonical Profiles A-F tests, Profile G valid/invalid vector
tests, the accelerator/datasets/kit HTTP and Profile E transport tests, the
three-peer failure harness, the fixed benchmark, and the SwissKnife connector
and policy-mapping tests. It then verifies the required virtual-desktop and
glasses captures and writes:

- `Mcp-Plus-Plus/docs/testing/profile-g-release/evidence.json`
- `Mcp-Plus-Plus/docs/testing/profile-g-release/report.md`
- `Mcp-Plus-Plus/docs/testing/profile-g-release/meta-glasses-summary.json`

Do not promote a release from `--evidence-only`; that diagnostic mode marks all
unexecuted gates failed and always publishes `NO_GO`.

## Promotion checklist

1. Confirm `evidence.json` has schema `mcp++/release-evidence@1`, task
   `SVD-091`, decision `GO`, profiles A through G, and both `jsonrpc-http` and
   `mcp+p2p` transports.
2. Confirm every gate row is `pass`. A missing row is a failure, not a waiver.
3. Confirm the multi-peer rows report at least three peers and the benchmark
   reports zero policy bypasses, duplicate completion events, and starved
   tasks, with converged frontiers.
4. Open the committed Agent Supervisor and MCP++ Explorer screenshots. Verify
   the health, peer, frontier, claim/lease, fencing, risk, receipt, and fallback
   labels are legible. Screenshots are supporting UX evidence; they never
   override a failed protocol gate.
5. Inspect `meta-glasses-summary.json`. It must say `read-only`,
   `mutation_authority: false`, list redacted fields, and forbid claim, renew,
   release, resolve, reconcile, plan selection, and steering.

## State triage

| Visible state | Meaning | Operator action |
| --- | --- | --- |
| `degraded` | A backend or transport is impaired while bounded evidence remains available. | Inspect the named peer/transport and receipt. Do not hide it with cached healthy data. |
| `denied` | Profile C authority or Profile D policy rejected the operation. | Inspect reason and decision CID. Do not retry with broader authority automatically. |
| `conflicted` | More than one valid claim exists and one deterministic winner was selected. | Verify accepted/losing claim CIDs and fence; a loser must not execute. |
| `expired` | The accepted lease passed its bound. | Verify the expiry event precedes a higher-epoch takeover. |
| `stale_fence` | An old claimant attempted execution/completion. | Confirm rejection and current fencing token; treat acceptance as a release blocker. |
| `partitioned` | The policy-required neighborhood cannot attest a safe placement. | Keep exclusive work stopped until quorum/reachability returns. |
| `blocked` | Dependencies, authority, risk action, or capacity prevent readiness. | Resolve the displayed cause; never relabel it as ready. |
| `unavailable` | A capability has no usable live transport/evidence. | Use correlation ID and owner to diagnose. A missing required capability is `NO_GO`. |

## Incident and rollback rules

Immediately withdraw `mcp++/risk-scheduling` from initialize metadata when a
required operation differs across transports, a stale fence executes, a claim
bypasses Profile C/D, a terminal task lacks its Profile B/F receipt chain, or a
denied/conflicted/degraded state becomes invisible. Existing artifacts remain
immutable and retrievable; do not delete or rewrite the Event DAG during
rollback.

Stop new claims, allow only safe bounded reads and artifact retrieval, retain
the last accepted fence for each task, and capture the failing gate report.
After repair, rerun the entire gate—never only the previously failing command—
because transport, policy, reconciliation, and UI evidence are coupled.

## Meta glasses handoff

The glasses payload is a summary, not a control plane. It may display release
decision, aggregate counts, bounded risk action, redacted denial/conflict
reason, peer DID, claim/receipt/event CID, fencing token, and expiry. It must
redact raw task input/output, delegation tokens, policy bodies, raw health/risk
telemetry, private addresses, and operator prompts.

Any voice, touch, or display action that would mutate scheduling leaves the
summary surface and opens the desktop/mobile confirmed Profile C/D path. A
device or display-webapp outage falls back to the read-only mobile card or
audio summary and remains visibly degraded; it never silently grants control.
