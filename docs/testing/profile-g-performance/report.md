# Profile G throughput, fairness, and recovery report

Published 2026-07-12 for workload `profile-g-three-peer-exclusive-v1`. **Overall: PASS.**

## Baseline comparison

| Scheduler | Parallelism | Scheduled makespan | Scheduled throughput |
| --- | ---: | ---: | ---: |
| single-owner-fifo | 1 | 3000 ms | 10.0 tasks/s |
| Profile G | 3 | 1090 ms | 27.522936 tasks/s |

The deterministic scheduled-capacity gain is **2.752294x**, against a pre-agreed minimum of 2.5x. The durable harness processed 30 tasks at 28.137657 tasks/s on the publication host; this wall-clock diagnostic is not used for the gain claim.

## Fairness and starvation

| Peer | Completed tasks | Scheduled service (ms) |
| --- | ---: | ---: |
| `did:web:peer-a.example` | 10 | 920 |
| `did:web:peer-b.example` | 10 | 990 |
| `did:web:peer-c.example` | 10 | 1090 |

Jain's completion fairness index is **1.0** and service-allocation fairness is **0.995157**. Maximum queue wait is **980 ms** and starved task count is **0**.

## Fault recovery and safety

All 3 injected lease-holder isolations recovered. Maximum successor-fence time was **5001 ms**. The run recorded 3 fail-closed majority denials, **0 policy bypasses**, 60 duplicate attempts, and **0 duplicate completion events**. Event frontiers converged: **true**.

## Acceptance gate

| Check | Result |
| --- | --- |
| throughput gain | PASS |
| fairness | PASS |
| bounded wait | PASS |
| no starvation | PASS |
| bounded recovery | PASS |
| all faults recovered | PASS |
| no policy bypass | PASS |
| bounded duplicates | PASS |
| converged | PASS |

## Measurement contract

- Scheduled capacity is task count divided by the declared service-time makespan. It is deterministic and is the only value used for the throughput-gain gate.
- Harness rate measures JSON persistence, canonical hashing, replication, fencing, and reconciliation on the current host. It is diagnostic and must not be presented as the baseline gain.
- Recovery time uses the deterministic protocol clock from isolation through expiry to the majority-issued successor fence.
