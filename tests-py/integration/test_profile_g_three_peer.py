"""SVD-089 three-peer Profile G scheduling conformance proof."""
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
