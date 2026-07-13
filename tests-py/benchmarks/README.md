# Profile G performance benchmark

`profile_g_workload.json` is the versioned, published SVD-090 workload. It
defines the single-owner FIFO baseline, heterogeneous task service times,
three fault injections, and all acceptance thresholds before execution.

`ProfileGBenchmark` drives the SVD-089 durable harness through claims,
resolution, partitions, expiry, successor fencing, stale completion attempts,
duplicate completion retries, duplicate event delivery, and convergence. The
suite reports two deliberately separate kinds of throughput:

- scheduled capacity is deterministic and supports the baseline gain gate;
- wall-clock harness rate measures the current host's JSON persistence,
  canonical hashing, replication, and reconciliation overhead.

Run and publish the default workload from `tests-py`:

```bash
python benchmarks/run_profile_g_benchmark.py
```

The command exits nonzero if any gate fails and writes `results.json`,
`report.md`, and `dashboard.html` under
`docs/testing/profile-g-performance/`. Use `--output-dir` for an isolated run
or `--store-dir` to retain the peer stores for forensic inspection.
