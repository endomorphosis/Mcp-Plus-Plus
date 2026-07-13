"""SVD-090 throughput, fairness, and recovery benchmark for Profile G.

The workload drives the SVD-089 durable three-peer harness. Scheduled capacity
uses declared task service time, making the baseline comparison reproducible
across hosts. Harness execution throughput is reported separately and is never
used to claim a scheduling gain.
"""
from __future__ import annotations

import html
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from harness.profile_g_three_peer import CoordinationError, ThreePeerHarness
from validators.profile_g import profile_g_artifact_cid


SCHEMA = "mcp++/profile-g/performance-report@1"


def _jain(values: list[int]) -> float:
    if not values or not any(values):
        return 0.0
    return sum(values) ** 2 / (len(values) * sum(value * value for value in values))


def _round(value: float) -> float:
    return round(value, 6)


class ProfileGBenchmark:
    """Run the published workload against a fresh durable harness."""

    def __init__(self, workload: Mapping[str, Any], store_root: Path):
        self.workload = dict(workload)
        self.store_root = Path(store_root)
        self._validate_workload()

    @classmethod
    def from_file(cls, workload_path: Path, store_root: Path) -> "ProfileGBenchmark":
        return cls(json.loads(Path(workload_path).read_text(encoding="utf-8")), store_root)

    def _validate_workload(self) -> None:
        workload = self.workload
        if workload.get("schema") != "mcp++/profile-g/performance-workload@1":
            raise ValueError("unsupported Profile G performance workload schema")
        peers = workload.get("peer_ids", [])
        if len(peers) != 3 or len(set(peers)) != 3:
            raise ValueError("performance workload requires three unique peers")
        count = workload.get("task_count")
        cycle = workload.get("service_time_ms_cycle")
        faults = workload.get("fault_task_indexes")
        if not isinstance(count, int) or count < len(peers):
            raise ValueError("task_count must be an integer at least as large as peer_count")
        if not isinstance(cycle, list) or not cycle or any(not isinstance(value, int) or value <= 0 for value in cycle):
            raise ValueError("service_time_ms_cycle must contain positive integers")
        if not isinstance(faults, list) or len(set(faults)) != len(faults) or any(
            not isinstance(index, int) or index < 0 or index >= count for index in faults
        ):
            raise ValueError("fault_task_indexes must be unique valid task indexes")
        if workload.get("lease_ms", 0) < 5000:
            raise ValueError("lease_ms must satisfy the Profile G minimum")
        baseline = workload.get("baseline")
        if not isinstance(baseline, dict) or baseline.get("parallelism") != 1 or not baseline.get("name"):
            raise ValueError("baseline must name a single-owner scheduler with parallelism 1")
        acceptance = workload.get("acceptance")
        required_gates = {
            "minimum_throughput_gain",
            "minimum_jain_fairness",
            "maximum_wait_ms",
            "maximum_recovery_ms",
            "maximum_duplicate_completion_events",
            "maximum_policy_bypasses",
            "maximum_starved_tasks",
        }
        if not isinstance(acceptance, dict) or set(acceptance) != required_gates or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
            for value in acceptance.values()
        ):
            raise ValueError("acceptance must define every non-negative performance and safety gate")
        if acceptance["minimum_throughput_gain"] <= 1 or acceptance["minimum_jain_fairness"] > 1:
            raise ValueError("acceptance throughput gain must exceed 1 and Jain fairness cannot exceed 1")

    def run(self) -> dict[str, Any]:
        workload = self.workload
        peers: list[str] = workload["peer_ids"]
        task_count: int = workload["task_count"]
        cycle: list[int] = workload["service_time_ms_cycle"]
        fault_indexes = set(workload["fault_task_indexes"])
        lease_ms: int = workload["lease_ms"]
        cluster = ThreePeerHarness(self.store_root, peers, workload["initial_time_ms"])

        completions: Counter[str] = Counter()
        lane_load_ms: Counter[str] = Counter()
        waits: list[int] = []
        recoveries: list[dict[str, Any]] = []
        policy_denials = 0
        policy_bypasses = 0
        completion_retry_attempts = 0
        replay_attempts = 0
        duplicate_completion_events = 0
        started = time.perf_counter()

        for index in range(task_count):
            task_cid = profile_g_artifact_cid({"workload": workload["id"], "task_index": index})
            output_cid = profile_g_artifact_cid({"task_cid": task_cid, "output": "accepted"})
            service_ms = cycle[index % len(cycle)]
            preferred_index = index % len(peers)
            preferred = peers[preferred_index]
            cluster.create_task(peers[0], task_cid)

            claims: dict[str, dict[str, Any]] = {}
            for peer_index, peer_id in enumerate(peers):
                distance = (peer_index - preferred_index) % len(peers)
                claims[peer_id] = cluster.claim(
                    peer_id,
                    task_cid,
                    logical_epoch=1,
                    risk_bucket=0,
                    capability_fit_millionths=950_000 - distance * 50_000,
                    expected_finish_ms=cluster.clock.now_ms + service_ms + distance,
                    requested_lease_ms=lease_ms,
                )
            resolution = cluster.resolve(peers[(preferred_index + 1) % len(peers)], task_cid, 1)
            accepted_claim = resolution["payload"]["accepted_claim_cid"]
            winner = next(peer_id for peer_id, claim in claims.items() if claim["payload"]["claim_cid"] == accepted_claim)
            executor = winner

            if index in fault_indexes:
                majority = [peer_id for peer_id in peers if peer_id != winner]
                cluster.partition([winner], majority)
                before = len(cluster.peers[winner].resolutions(task_cid))
                try:
                    cluster.resolve(winner, task_cid, 1)
                except CoordinationError as error:
                    if error.code != "G_COORDINATION_UNAVAILABLE":
                        raise
                    policy_denials += 1
                else:
                    policy_bypasses += 1
                if len(cluster.peers[winner].resolutions(task_cid)) != before:
                    policy_bypasses += 1

                cluster.clock.advance(lease_ms + 1)
                cluster.expire(majority[0], task_cid)
                executor = peers[(preferred_index + 1) % len(peers)]
                takeover = cluster.claim(
                    executor,
                    task_cid,
                    logical_epoch=2,
                    risk_bucket=0,
                    capability_fit_millionths=975_000,
                    expected_finish_ms=cluster.clock.now_ms + service_ms,
                    requested_lease_ms=lease_ms,
                )
                takeover_resolution = cluster.resolve(majority[0], task_cid, 2)
                stale = cluster.complete(winner, task_cid, accepted_claim, 1, profile_g_artifact_cid({"task": task_cid, "stale": True}))
                if stale["payload"].get("reason") != "G_STALE_FENCE":
                    policy_bypasses += 1
                completion = cluster.complete(
                    executor, task_cid, takeover["payload"]["claim_cid"],
                    takeover_resolution["payload"]["fencing_token"], output_cid,
                )
                recoveries.append({
                    "task_index": index,
                    "failed_peer": winner,
                    "takeover_peer": executor,
                    "recovery_ms": lease_ms + 1,
                    "stale_fence_rejected": stale["payload"].get("reason") == "G_STALE_FENCE",
                    "new_fencing_token": takeover_resolution["payload"]["fencing_token"],
                })
                cluster.reconcile()
            else:
                completion = cluster.complete(
                    winner, task_cid, accepted_claim, resolution["payload"]["fencing_token"], output_cid,
                )

            waits.append(lane_load_ms[executor])
            lane_load_ms[executor] += service_ms
            completions[executor] += 1
            before_completion_cids = {
                event["event_cid"]
                for peer in cluster.peers.values()
                for event in peer.events_of_type("task_completed", task_cid)
            }
            repeated = cluster.complete(
                executor,
                task_cid,
                completion["payload"]["claim_cid"],
                completion["payload"]["fencing_token"],
                output_cid,
            )
            completion_retry_attempts += 1
            target = peers[(peers.index(executor) + 1) % len(peers)]
            cluster.replay(executor, target, completion["event_cid"])
            replay_attempts += 1
            after_completion_cids = {
                event["event_cid"]
                for peer in cluster.peers.values()
                for event in peer.events_of_type("task_completed", task_cid)
            }
            duplicate_completion_events += len(after_completion_cids - before_completion_cids)
            if repeated["event_cid"] != completion["event_cid"]:
                duplicate_completion_events += 1

        reconciliation = cluster.reconcile()
        elapsed_seconds = max(time.perf_counter() - started, 1e-9)
        durations = [cycle[index % len(cycle)] for index in range(task_count)]
        baseline_makespan_ms = sum(durations)
        profile_makespan_ms = max(lane_load_ms.values())
        baseline_throughput = task_count * 1000 / baseline_makespan_ms
        profile_throughput = task_count * 1000 / profile_makespan_ms
        completion_values = [completions[peer_id] for peer_id in peers]
        service_values = [lane_load_ms[peer_id] for peer_id in peers]
        max_recovery = max((item["recovery_ms"] for item in recoveries), default=0)
        starvation = task_count - sum(completion_values)

        metrics = {
            "baseline": {
                "name": workload["baseline"]["name"],
                "parallelism": workload["baseline"]["parallelism"],
                "scheduled_makespan_ms": baseline_makespan_ms,
                "scheduled_throughput_tasks_per_second": _round(baseline_throughput),
            },
            "profile_g": {
                "parallelism": len(peers),
                "scheduled_makespan_ms": profile_makespan_ms,
                "scheduled_throughput_tasks_per_second": _round(profile_throughput),
                "throughput_gain": _round(profile_throughput / baseline_throughput),
                "harness_elapsed_seconds": _round(elapsed_seconds),
                "harness_tasks_per_second": _round(task_count / elapsed_seconds),
            },
            "fairness": {
                "completed_by_peer": {peer_id: completions[peer_id] for peer_id in peers},
                "service_ms_by_peer": {peer_id: lane_load_ms[peer_id] for peer_id in peers},
                "jain_index": _round(_jain(completion_values)),
                "service_jain_index": _round(_jain(service_values)),
                "maximum_wait_ms": max(waits, default=0),
                "starved_tasks": starvation,
            },
            "fault_recovery": {
                "injected_faults": len(fault_indexes),
                "recovered_faults": len(recoveries),
                "maximum_recovery_ms": max_recovery,
                "recoveries": recoveries,
            },
            "safety": {
                "policy_denials": policy_denials,
                "policy_bypasses": policy_bypasses,
                "completion_retry_attempts": completion_retry_attempts,
                "replay_attempts": replay_attempts,
                "duplicate_attempts": completion_retry_attempts + replay_attempts,
                "duplicate_completion_events": duplicate_completion_events,
                "frontiers_converged": reconciliation["converged"],
            },
        }
        acceptance = workload["acceptance"]
        checks = {
            "throughput_gain": metrics["profile_g"]["throughput_gain"] >= acceptance["minimum_throughput_gain"],
            "fairness": min(metrics["fairness"]["jain_index"], metrics["fairness"]["service_jain_index"]) >= acceptance["minimum_jain_fairness"],
            "bounded_wait": metrics["fairness"]["maximum_wait_ms"] <= acceptance["maximum_wait_ms"],
            "no_starvation": starvation <= acceptance["maximum_starved_tasks"],
            "bounded_recovery": max_recovery <= acceptance["maximum_recovery_ms"],
            "all_faults_recovered": len(recoveries) == len(fault_indexes),
            "no_policy_bypass": policy_bypasses <= acceptance["maximum_policy_bypasses"],
            "bounded_duplicates": duplicate_completion_events <= acceptance["maximum_duplicate_completion_events"],
            "converged": reconciliation["converged"],
        }
        return {
            "schema": SCHEMA,
            "workload_id": workload["id"],
            "publication_date": workload["publication_date"],
            "task_count": task_count,
            "peer_count": len(peers),
            "measurement_contract": {
                "scheduled_capacity": "task_count / declared service-time makespan; deterministic and used for the gain gate",
                "harness_rate": "wall-clock durable harness rate; diagnostic only and not compared with the baseline",
                "fault_recovery": "deterministic clock from isolation to a majority-issued successor fence",
            },
            "acceptance_thresholds": acceptance,
            "metrics": metrics,
            "checks": checks,
            "accepted": all(checks.values()),
        }


def render_report(result: Mapping[str, Any]) -> str:
    metrics = result["metrics"]
    fairness = metrics["fairness"]
    recovery = metrics["fault_recovery"]
    safety = metrics["safety"]
    status = "PASS" if result["accepted"] else "FAIL"
    peer_rows = "\n".join(
        f"| `{peer}` | {count} | {fairness['service_ms_by_peer'][peer]} |"
        for peer, count in fairness["completed_by_peer"].items()
    )
    check_rows = "\n".join(
        f"| {name.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |"
        for name, passed in result["checks"].items()
    )
    return f"""# Profile G throughput, fairness, and recovery report

Published {result['publication_date']} for workload `{result['workload_id']}`. **Overall: {status}.**

## Baseline comparison

| Scheduler | Parallelism | Scheduled makespan | Scheduled throughput |
| --- | ---: | ---: | ---: |
| {metrics['baseline']['name']} | {metrics['baseline']['parallelism']} | {metrics['baseline']['scheduled_makespan_ms']} ms | {metrics['baseline']['scheduled_throughput_tasks_per_second']} tasks/s |
| Profile G | {metrics['profile_g']['parallelism']} | {metrics['profile_g']['scheduled_makespan_ms']} ms | {metrics['profile_g']['scheduled_throughput_tasks_per_second']} tasks/s |

The deterministic scheduled-capacity gain is **{metrics['profile_g']['throughput_gain']}x**, against a pre-agreed minimum of {result['acceptance_thresholds']['minimum_throughput_gain']}x. The durable harness processed {result['task_count']} tasks at {metrics['profile_g']['harness_tasks_per_second']} tasks/s on the publication host; this wall-clock diagnostic is not used for the gain claim.

## Fairness and starvation

| Peer | Completed tasks | Scheduled service (ms) |
| --- | ---: | ---: |
{peer_rows}

Jain's completion fairness index is **{fairness['jain_index']}** and service-allocation fairness is **{fairness['service_jain_index']}**. Maximum queue wait is **{fairness['maximum_wait_ms']} ms** and starved task count is **{fairness['starved_tasks']}**.

## Fault recovery and safety

All {recovery['injected_faults']} injected lease-holder isolations recovered. Maximum successor-fence time was **{recovery['maximum_recovery_ms']} ms**. The run recorded {safety['policy_denials']} fail-closed majority denials, **{safety['policy_bypasses']} policy bypasses**, {safety['duplicate_attempts']} duplicate attempts, and **{safety['duplicate_completion_events']} duplicate completion events**. Event frontiers converged: **{str(safety['frontiers_converged']).lower()}**.

## Acceptance gate

| Check | Result |
| --- | --- |
{check_rows}

## Measurement contract

- Scheduled capacity is task count divided by the declared service-time makespan. It is deterministic and is the only value used for the throughput-gain gate.
- Harness rate measures JSON persistence, canonical hashing, replication, fencing, and reconciliation on the current host. It is diagnostic and must not be presented as the baseline gain.
- Recovery time uses the deterministic protocol clock from isolation through expiry to the majority-issued successor fence.
"""


def render_dashboard(result: Mapping[str, Any]) -> str:
    data = json.dumps(result, sort_keys=True).replace("</", "<\\/")
    title = html.escape(f"Profile G capacity dashboard — {result['workload_id']}")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font:16px system-ui,sans-serif;margin:0;background:#101827;color:#e8eef8}}main{{max-width:1050px;margin:auto;padding:2rem}}h1{{font-size:1.7rem}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}}.card{{background:#19253a;border:1px solid #34445f;border-radius:10px;padding:1rem}}.value{{font-size:2rem;font-weight:700;color:#73e0b1}}.bar{{height:1rem;background:#24334d;border-radius:1rem;overflow:hidden}}.bar span{{display:block;height:100%;background:#6fa8ff}}table{{width:100%;border-collapse:collapse}}th,td{{padding:.6rem;text-align:left;border-bottom:1px solid #34445f}}.pass{{color:#73e0b1}}.fail{{color:#ff8585}}small{{color:#aebbd0}}
</style></head><body><main><h1>{title}</h1><p id="summary"></p><section class="grid" id="cards"></section><h2>Peer capacity and fairness</h2><section id="peers"></section><h2>Recovery incidents</h2><section id="recovery"></section><h2>Acceptance checks</h2><section id="checks"></section><p><small>Scheduled capacity is deterministic. Host harness rate is diagnostic only.</small></p></main>
<script type="application/json" id="benchmark-data">{data}</script><script>
const r=JSON.parse(document.getElementById('benchmark-data').textContent),m=r.metrics;
document.getElementById('summary').innerHTML=`Published ${{r.publication_date}} — <strong class="${{r.accepted?'pass':'fail'}}">${{r.accepted?'PASS':'FAIL'}}</strong>`;
const cards=[['Throughput gain',m.profile_g.throughput_gain+'x'],['Profile G capacity',m.profile_g.scheduled_throughput_tasks_per_second+' tasks/s'],['Service fairness',m.fairness.service_jain_index],['Max recovery',m.fault_recovery.maximum_recovery_ms+' ms']];
document.getElementById('cards').innerHTML=cards.map(x=>`<article class="card"><div>${{x[0]}}</div><div class="value">${{x[1]}}</div></article>`).join('');
const counts=m.fairness.completed_by_peer,max=Math.max(...Object.values(counts));
document.getElementById('peers').innerHTML=Object.entries(counts).map(([p,n])=>`<p><code>${{p}}</code> — ${{n}} tasks</p><div class="bar"><span style="width:${{100*n/max}}%"></span></div>`).join('');
document.getElementById('recovery').innerHTML='<table><thead><tr><th>Task</th><th>Failed peer</th><th>Takeover peer</th><th>Recovery</th><th>Stale fence</th></tr></thead><tbody>'+m.fault_recovery.recoveries.map(x=>`<tr><td>${{x.task_index}}</td><td>${{x.failed_peer}}</td><td>${{x.takeover_peer}}</td><td>${{x.recovery_ms}} ms</td><td>${{x.stale_fence_rejected?'rejected':'ERROR'}}</td></tr>`).join('')+'</tbody></table>';
document.getElementById('checks').innerHTML='<table><tbody>'+Object.entries(r.checks).map(([k,v])=>`<tr><td>${{k.replaceAll('_',' ')}}</td><td class="${{v?'pass':'fail'}}">${{v?'PASS':'FAIL'}}</td></tr>`).join('')+'</tbody></table>';
</script></body></html>"""


def write_outputs(result: Mapping[str, Any], output_dir: Path) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_report(result), encoding="utf-8")
    (output_dir / "dashboard.html").write_text(render_dashboard(result), encoding="utf-8")
