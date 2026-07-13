# Profile G three-peer conformance (SVD-089)

## Scope

The repeatable integration proof uses three durable peer stores, a simulated
clock, and an explicitly partitionable network. It exercises the normative
Profile G conflict tuple, majority fail-closed behavior for exclusive work,
lease expiry, epoch takeover, fencing at completion, durable restart, replay,
and Event DAG reconciliation. It does not depend on wall-clock timing, random
ports, or an external daemon.

The failure-injection inputs and expected result are fixed in
`conformance/vectors/profile_g_three_peer.json`. Each peer receives only
content-addressed Profile F events. Materialized claims, leases, fences, and
terminal state are rebuilt from those events, including after restart.

## Conformance evidence

| Requirement | Injected condition | Required evidence |
| --- | --- | --- |
| simultaneous claim | peers A and B claim epoch 1 before resolution | peer B wins by capability fit; both claim CIDs are considered; loser emits `claim_conflicted` |
| partition | the epoch-1 worker is isolated from the two-peer majority | isolated resolution fails with `G_COORDINATION_UNAVAILABLE` |
| replay | the same claim event is delivered repeatedly | event count and claim count do not change |
| restart | a peer process is reconstructed from its JSON store | accepted resolution, claims, and fencing token are recovered from the DAG |
| expired takeover | clock advances beyond epoch-1 expiry and the majority claims epoch 2 | an explicit `claim_expired` parent exists and fence 2 supersedes fence 1 |
| conflicting completion | expired worker submits a late result and winner submits two output CIDs | stale result is `G_STALE_FENCE`; alternate result is `G_COMPLETION_CONFLICT`; exactly one `task_completed` exists |
| reconciliation | the partition heals and frontiers are exchanged twice | all stores have identical frontiers and counts; the second pass creates no events |
| Event DAG | all emitted and replayed records are inspected | CIDs commit to canonical event bodies, all parents precede children, no duplicates or missing parents exist |

The harness `conformance_report()` result is machine-readable and asserts:

- exactly three peers and one successful completion;
- accepted epochs and durable fencing tokens are `[1, 2]`;
- fences are strictly increasing;
- rejected evidence retains both conflict reasons;
- all peer frontiers converge after bounded reconciliation.

## Reproduction

```bash
cd Mcp-Plus-Plus/tests-py
pytest -q integration/test_profile_g_three_peer.py
```

The integration suite also passes its final evidence through the shared
`EventDAGValidator`. The fixture retains the compatibility `DAGEvent` carrier,
so the existing Python, TypeScript, Rust, and Go conformance scanners continue
to validate the common vector directory.
