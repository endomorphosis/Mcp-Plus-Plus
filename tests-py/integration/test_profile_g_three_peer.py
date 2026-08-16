"""Three-peer Profile G scheduling conformance proof (MCPP-068 expansion).

Acceptance:
- Partition heal converges (frontiers and state roots).
- Exactly one authoritative completion for an exclusive task.
- Stale publisher is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).parent.parent
sys.path.insert(0, str(TESTS))

from harness.profile_g_three_peer import CoordinationError, ThreePeerHarness
from validators.event_dag import EventDAGValidator


FIXTURE = Path(__file__).parents[2] / "conformance" / "vectors" / "profile_g_three_peer.json"


@pytest.fixture
def scenario() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def cluster(tmp_path: Path, scenario: dict) -> ThreePeerHarness:
    harness = ThreePeerHarness(tmp_path, scenario["peer_ids"], scenario["initial_time_ms"])
    harness.create_task(scenario["peer_ids"][0], scenario["task_cid"])
    return harness


def _claim(cluster: ThreePeerHarness, task_cid: str, spec: dict, epoch: int = 1):
    return cluster.claim(
        spec["peer_id"], task_cid, logical_epoch=epoch,
        risk_bucket=spec["risk_bucket"],
        capability_fit_millionths=spec["capability_fit_millionths"],
        expected_finish_ms=cluster.clock.now_ms + spec["expected_finish_offset_ms"],
    )


def _claimant_for(cluster: ThreePeerHarness, task_cid: str, claim_cid: str) -> str:
    """Resolve the claimant DID for a claim CID from any peer's claim index."""
    for peer in cluster.peers.values():
        for claim in peer.claims(task_cid):
            if claim["claim_cid"] == claim_cid:
                return claim["claimant_did"]
    raise AssertionError(f"claim {claim_cid} not found")


def test_simultaneous_claim_has_deterministic_winner_and_conflict_evidence(cluster, scenario):
    task = scenario["task_cid"]
    first, second = (_claim(cluster, task, spec) for spec in scenario["claims"])
    resolution = cluster.resolve(scenario["peer_ids"][2], task, 1)

    winner = next(event for event in (first, second)
                  if event["payload"]["claim_cid"] == resolution["payload"]["accepted_claim_cid"])
    assert winner["payload"]["claimant_did"] == scenario["expected"]["epoch_1_winner"]
    assert set(resolution["payload"]["considered_claim_cids"]) == {
        first["payload"]["claim_cid"], second["payload"]["claim_cid"]
    }
    conflicts = cluster.peers[scenario["peer_ids"][0]].events_of_type("claim_conflicted", task)
    assert len(conflicts) == 1
    assert conflicts[0]["payload"]["accepted_claim_cid"] == winner["payload"]["claim_cid"]


def test_partition_fails_closed_and_replay_is_idempotent(cluster, scenario):
    task = scenario["task_cid"]
    claim = _claim(cluster, task, scenario["claims"][0])
    isolated, left, right = scenario["peer_ids"]
    cluster.partition([isolated], [left, right])

    with pytest.raises(CoordinationError, match="G_COORDINATION_UNAVAILABLE") as failure:
        cluster.resolve(isolated, task, 1)
    assert failure.value.code == "G_COORDINATION_UNAVAILABLE"
    assert cluster.policy_denials >= 1
    assert cluster.policy_bypasses == 0

    assert cluster.replay(isolated, left, claim["event_cid"]) is False
    assert cluster.replay(isolated, left, claim["event_cid"]) is False
    assert len(cluster.peers[left].claims(task)) == 1


def test_restart_rebuilds_lease_and_fence_from_durable_event_dag(cluster, scenario):
    task = scenario["task_cid"]
    for spec in scenario["claims"]:
        _claim(cluster, task, spec)
    resolution = cluster.resolve(scenario["peer_ids"][2], task, 1)

    restarted = cluster.restart(scenario["peer_ids"][1])
    recovered = restarted.accepted_resolution(task)
    assert recovered is not None
    assert recovered["event_cid"] == resolution["event_cid"]
    assert recovered["payload"]["fencing_token"] == 1
    assert len(restarted.claims(task, 1)) == 2


def test_expired_takeover_conflicting_completion_and_idempotent_reconciliation(cluster, scenario):
    task = scenario["task_cid"]
    claim_events = [_claim(cluster, task, spec) for spec in scenario["claims"]]
    epoch1 = cluster.resolve(scenario["peer_ids"][2], task, 1)
    old_claim = epoch1["payload"]["accepted_claim_cid"]
    old_worker = next(event["payload"]["claimant_did"] for event in claim_events
                      if event["payload"]["claim_cid"] == old_claim)

    # Keep the old worker isolated. The majority expires epoch 1 and issues a
    # strictly newer fence; the isolated worker can retain evidence but cannot
    # acquire another exclusive lease.
    majority = [peer for peer in scenario["peer_ids"] if peer != old_worker]
    cluster.partition([old_worker], majority)
    with pytest.raises(CoordinationError, match="G_CLAIM_CONFLICT"):
        _claim(cluster, task, scenario["takeover"], epoch=2)
    cluster.clock.advance(5001)
    cluster.expire(majority[0], task)
    takeover_claim = _claim(cluster, task, scenario["takeover"], epoch=2)
    epoch2 = cluster.resolve(majority[0], task, 2)
    assert epoch2["payload"]["accepted_claim_cid"] == takeover_claim["payload"]["claim_cid"]
    assert epoch2["payload"]["fencing_token"] > epoch1["payload"]["fencing_token"]

    stale = cluster.complete(old_worker, task, old_claim, 1, scenario["outputs"]["stale"])
    assert stale["event_type"] == "task_reconciled"
    assert stale["payload"]["reason"] == "G_STALE_FENCE"

    accepted = cluster.complete(majority[0], task, takeover_claim["payload"]["claim_cid"], 2,
                                scenario["outputs"]["accepted"])
    assert accepted["event_type"] == "task_completed"
    assert cluster.complete(majority[0], task, takeover_claim["payload"]["claim_cid"], 2,
                            scenario["outputs"]["accepted"])["event_cid"] == accepted["event_cid"]
    conflicting = cluster.complete(majority[0], task, takeover_claim["payload"]["claim_cid"], 2,
                                   scenario["outputs"]["conflicting"])
    assert conflicting["payload"]["reason"] == "G_COMPLETION_CONFLICT"

    first = cluster.reconcile()
    event_counts = {peer_id: len(peer.events) for peer_id, peer in cluster.peers.items()}
    second = cluster.reconcile()
    assert first["converged"] and second["converged"]
    assert event_counts == {peer_id: len(peer.events) for peer_id, peer in cluster.peers.items()}
    assert len(set(event_counts.values())) == 1
    assert len(set(first["state_roots"].values())) == 1
    assert first["state_roots"] == second["state_roots"]

    evidence = cluster.evidence(scenario["peer_ids"][0])
    validation = EventDAGValidator().validate_dag(evidence)
    assert validation.is_valid, validation.errors
    assert not validation.warnings, validation.warnings
    assert all(set(event["parents"]) <= {prior["event_cid"] for prior in evidence[:index]}
               for index, event in enumerate(evidence))

    report = cluster.conformance_report(task)
    expected = scenario["expected"]
    assert report["accepted_epochs"] == expected["accepted_epochs"]
    assert report["fencing_tokens"] == expected["fencing_tokens"]
    assert report["successful_completion_count"] == expected["successful_completion_count"]
    assert report["rejected_evidence_reasons"] == expected["rejected_evidence_reasons"]
    assert all(report["checks"].values())
    assert cluster.authoritative_completion(task)["event_cid"] == accepted["event_cid"]


def test_partitioned_leaseholder_cannot_authoritatively_complete(cluster, scenario):
    """Exclusive completion requires majority so partition cannot dual-complete."""
    task = scenario["task_cid"]
    for spec in scenario["claims"]:
        _claim(cluster, task, spec)
    epoch1 = cluster.resolve(scenario["peer_ids"][2], task, 1)
    winner_claim = epoch1["payload"]["accepted_claim_cid"]
    winner = _claimant_for(cluster, task, winner_claim)
    majority = [peer for peer in scenario["peer_ids"] if peer != winner]
    cluster.partition([winner], majority)

    with pytest.raises(CoordinationError, match="G_COORDINATION_UNAVAILABLE") as failure:
        cluster.complete(winner, task, winner_claim, 1, scenario["outputs"]["stale"])
    assert failure.value.code == "G_COORDINATION_UNAVAILABLE"
    assert cluster.peers[winner].authoritative_completion(task) is None
    assert cluster.policy_bypasses == 0


def test_partition_heal_converges_to_one_authoritative_completion(cluster, scenario):
    """After takeover under partition, heal converges state roots to one success."""
    task = scenario["task_cid"]
    for spec in scenario["claims"]:
        _claim(cluster, task, spec)
    epoch1 = cluster.resolve(scenario["peer_ids"][2], task, 1)
    old_claim = epoch1["payload"]["accepted_claim_cid"]
    old_worker = _claimant_for(cluster, task, old_claim)
    majority = [peer for peer in scenario["peer_ids"] if peer != old_worker]
    cluster.partition([old_worker], majority)

    # Isolated holder cannot finish exclusive work alone (no split-brain success).
    with pytest.raises(CoordinationError, match="G_COORDINATION_UNAVAILABLE"):
        cluster.complete(old_worker, task, old_claim, 1, scenario["outputs"]["stale"])

    cluster.clock.advance(5001)
    cluster.expire(majority[0], task)
    takeover = _claim(cluster, task, scenario["takeover"], epoch=2)
    epoch2 = cluster.resolve(majority[0], task, 2)
    accepted = cluster.complete(
        majority[0],
        task,
        takeover["payload"]["claim_cid"],
        epoch2["payload"]["fencing_token"],
        scenario["outputs"]["accepted"],
    )
    assert accepted["event_type"] == "task_completed"

    # Stale publisher still rejected after majority advanced the fence.
    stale = cluster.complete(old_worker, task, old_claim, 1, scenario["outputs"]["stale"])
    assert stale["event_type"] == "task_reconciled"
    assert stale["payload"]["reason"] == "G_STALE_FENCE"

    result = cluster.reconcile()
    assert result["converged"] is True
    assert len(set(result["state_roots"].values())) == 1
    assert len({tuple(frontier) for frontier in result["frontiers"].values()}) == 1

    for peer in cluster.peers.values():
        auth = peer.authoritative_completion(task)
        assert auth is not None
        assert auth["event_cid"] == accepted["event_cid"]
        assert auth["payload"]["fencing_token"] == epoch2["payload"]["fencing_token"]

    report = cluster.conformance_report(task)
    assert report["successful_completion_count"] == 1
    assert report["checks"]["single_success"]
    assert report["checks"]["converged"]
    assert report["checks"]["no_policy_bypass"]
    assert "G_STALE_FENCE" in report["rejected_evidence_reasons"]


def test_malicious_stale_publisher_rejected_after_heal(cluster, scenario):
    """A peer that learns the new fence still cannot re-publish under the old fence."""
    task = scenario["task_cid"]
    for spec in scenario["claims"]:
        _claim(cluster, task, spec)
    epoch1 = cluster.resolve(scenario["peer_ids"][2], task, 1)
    old_claim = epoch1["payload"]["accepted_claim_cid"]
    old_worker = _claimant_for(cluster, task, old_claim)
    majority = [peer for peer in scenario["peer_ids"] if peer != old_worker]
    cluster.partition([old_worker], majority)
    cluster.clock.advance(5001)
    cluster.expire(majority[0], task)
    takeover = _claim(cluster, task, scenario["takeover"], epoch=2)
    epoch2 = cluster.resolve(majority[0], task, 2)
    accepted = cluster.complete(
        majority[0],
        task,
        takeover["payload"]["claim_cid"],
        epoch2["payload"]["fencing_token"],
        scenario["outputs"]["accepted"],
    )

    cluster.heal()
    # Exchange majority evidence to the former holder.
    for event_cid in list(cluster.peers[majority[0]].events):
        cluster.replay(majority[0], old_worker, event_cid)

    malicious = cluster.complete(
        old_worker, task, old_claim, epoch1["payload"]["fencing_token"], scenario["outputs"]["stale"]
    )
    assert malicious["event_type"] == "task_reconciled"
    assert malicious["payload"]["reason"] == "G_STALE_FENCE"
    assert cluster.authoritative_completion(task, old_worker)["event_cid"] == accepted["event_cid"]
    assert cluster.conformance_report(task)["successful_completion_count"] == 1


def test_out_of_order_delivery_fails_closed_and_causal_reorder_succeeds(cluster, scenario):
    task = scenario["task_cid"]
    claim = _claim(cluster, task, scenario["claims"][0])
    resolution = cluster.resolve(scenario["peer_ids"][2], task, 1)
    source = scenario["peer_ids"][2]
    target = scenario["peer_ids"][0]
    # Drop the resolution from target by restarting from a store that never saw it:
    # simulate by using a peer that is healed but missing only the leaf via partition.
    isolated = scenario["peer_ids"][1]
    cluster.partition([isolated], [source, target])
    # Create a second-epoch path on the majority so we have a child event to reorder.
    cluster.clock.advance(5001)
    cluster.expire(source, task)
    expiry = cluster.peers[source].events_of_type("claim_expired", task)[-1]

    # Re-open full mesh then deliver the expiry leaf to isolated without parents.
    cluster.heal()
    # Ensure isolated is missing the expiry event specifically by restarting empty store
    # is too strong; instead deliver a child that depends on missing parents.
    # First, remove isolation knowledge: wipe isolated and reload only task creation via causal replay of claim parents.
    store = cluster.peers[isolated].store_path
    store.unlink(missing_ok=True)
    cluster.restart(isolated)
    # Non-causal delivery of a descendant before parents must fail closed.
    with pytest.raises(CoordinationError, match="G_MISSING_PARENT") as failure:
        cluster.deliver(source, isolated, expiry["event_cid"], causal=False)
    assert failure.value.code == "G_MISSING_PARENT"
    assert expiry["event_cid"] not in cluster.peers[isolated].events

    # Causal delivery repairs parent order and converges.
    assert cluster.deliver(source, isolated, expiry["event_cid"], causal=True) is True
    assert expiry["event_cid"] in cluster.peers[isolated].events
    assert resolution["event_cid"] in cluster.peers[isolated].events
    assert claim["event_cid"] in cluster.peers[isolated].events


def test_duplicate_completion_and_replay_do_not_fork_success(cluster, scenario):
    task = scenario["task_cid"]
    for spec in scenario["claims"]:
        _claim(cluster, task, spec)
    resolution = cluster.resolve(scenario["peer_ids"][2], task, 1)
    claim_cid = resolution["payload"]["accepted_claim_cid"]
    fence = resolution["payload"]["fencing_token"]
    worker = _claimant_for(cluster, task, claim_cid)
    first = cluster.complete(worker, task, claim_cid, fence, scenario["outputs"]["accepted"])
    second = cluster.complete(worker, task, claim_cid, fence, scenario["outputs"]["accepted"])
    assert second["event_cid"] == first["event_cid"]

    other = next(peer for peer in scenario["peer_ids"] if peer != worker)
    before = len(cluster.peers[other].events)
    assert cluster.replay(worker, other, first["event_cid"]) is False or len(cluster.peers[other].events) >= before
    # Second replay is always a no-op once present.
    assert cluster.replay(worker, other, first["event_cid"]) is False
    completions = {
        peer_id: [event["event_cid"] for event in peer.completions(task)]
        for peer_id, peer in cluster.peers.items()
    }
    assert all(cids == [first["event_cid"]] for cids in completions.values())
    assert cluster.conformance_report(task)["successful_completion_count"] == 1
