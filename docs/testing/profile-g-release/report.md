# MCP++ Profiles A-G release evidence (SVD-091)

**Decision: GO** — published 2026-07-12.

This is a fail-closed aggregation of canonical conformance, each Profile G backend transport, the durable three-peer failure harness, the pre-agreed performance workload, SwissKnife governed mappings, and virtual-desktop/glasses captures. It does not infer a pass from documentation alone.

## Gate matrix

| Gate | Profiles | Transports | Result |
| --- | --- | --- | --- |
| `profiles-a-f-conformance` | A, B, C, D, E, F | jsonrpc-http, mcp+p2p | **PASS** |
| `profile-g-codecs` | G | n/a | **PASS** |
| `accelerator-profile-g-transport` | G | jsonrpc-http, mcp+p2p | **PASS** |
| `datasets-profile-g-transport` | G | jsonrpc-http, mcp+p2p | **PASS** |
| `kit-profile-g-transport` | G | jsonrpc-http, mcp+p2p | **PASS** |
| `profile-g-three-peer` | B, C, D, F, G | jsonrpc-http, mcp+p2p | **PASS** |
| `profile-g-performance` | G | n/a | **PASS** |
| `swissknife-profile-g` | A, B, C, D, E, F, G | jsonrpc-http, mcp+p2p | **PASS** |

## Cross-transport, multi-peer result

- Both `jsonrpc-http` and `/mcp+p2p/1.0.0` retain the same Profile G method and result semantics.
- The proof uses 3 independently persisted peers; simultaneous claims, partition, expiry, takeover, stale completion, conflicting completion, replay, restart, and reconciliation are covered.
- Scheduled throughput gain is 2.752294x; policy bypasses: 0; duplicate completion events: 0; starved tasks: 0; frontiers converged: true.

## Required operator-visible states

| State | Surface | Evidence shown |
| --- | --- | --- |
| `degraded` | backend health and transport fallback | affected peer/transport and receipt |
| `denied` | policy decision | reason, decision CID, and required confirmation |
| `conflicted` | claims and leases | winning/losing claim CIDs and fencing token |
| `expired` | claims and leases | expiry, successor epoch, and takeover receipt |
| `stale_fence` | reconciliation | rejection code and current fence |
| `partitioned` | neighborhood peers | quorum failure and retry state |
| `blocked` | task queue | dependency or authority reason |
| `unavailable` | gateway evidence | capability, owner, reason, and correlation ID |

The Meta glasses artifact is a bounded read-only projection. It cannot claim, renew, release, resolve, reconcile, select a plan, or steer a task; those operations move to the confirmed desktop/mobile Profile C/D flow.
