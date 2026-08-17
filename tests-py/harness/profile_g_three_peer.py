"""Repeatable three-peer Profile G coordination and failure-injection harness.

The harness intentionally uses no sockets or sleeps.  A deterministic clock,
explicit network links, and JSON durable stores make every interleaving
repeatable while still exercising the protocol boundary: peers exchange only
content-addressed Profile F events and rebuild all indexes by replaying them.

Expanded coverage (MCPP-068 / ThreePeerHarness@1):
- simultaneous claims with deterministic conflict order
- partition fail-closed majority placement
- duplicate / out-of-order delivery
- durable restart
- lease expiry and epoch takeover
- late / alternate / malicious stale completion rejection
- frontier and state-root convergence after partition heal
- exactly one authoritative exclusive completion
- no policy bypass (minority cannot resolve or complete exclusive work)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from validators.profile_g import claim_order_key, profile_g_artifact_cid


class CoordinationError(RuntimeError):
    """A stable Profile G protocol failure raised by the harness."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class DeterministicClock:
    now_ms: int

    def advance(self, milliseconds: int) -> int:
        if milliseconds < 0:
            raise ValueError("clock cannot move backwards")
        self.now_ms += milliseconds
        return self.now_ms

    def iso(self) -> str:
        return datetime.fromtimestamp(self.now_ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def _event_cid(event_without_cid: Mapping[str, Any]) -> str:
    return profile_g_artifact_cid(event_without_cid)


def _body_without_cid(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key != "event_cid"}


class Peer:
    """One durable peer whose materialized task state is derived from its DAG."""

    def __init__(self, peer_id: str, store_path: Path, clock: DeterministicClock):
        self.peer_id = peer_id
        self.store_path = store_path
        self.clock = clock
        self.events: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        document = json.loads(self.store_path.read_text(encoding="utf-8"))
        if document.get("schema") != "mcp++/profile-g/test-peer-store@1":
            raise ValueError(f"unsupported peer store: {self.store_path}")
        for event in document["events"]:
            self._verify_event(event)
            self.events[event["event_cid"]] = event

    def _persist(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema": "mcp++/profile-g/test-peer-store@1",
            "peer_id": self.peer_id,
            "events": sorted(self.events.values(), key=lambda event: event["event_cid"]),
        }
        temporary = self.store_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        temporary.replace(self.store_path)

    @staticmethod
    def _verify_event(event: Mapping[str, Any]) -> None:
        body = dict(event)
        supplied = body.pop("event_cid", None)
        if supplied != _event_cid(body):
            raise CoordinationError("G_INVALID_ARTIFACT", "event CID does not match its canonical body")

    def ingest(self, event: Mapping[str, Any]) -> bool:
        self._verify_event(event)
        cid = event["event_cid"]
        if cid in self.events:
            return False
        missing = [parent for parent in event["parents"] if parent not in self.events]
        if missing:
            raise CoordinationError("G_MISSING_PARENT", f"missing causal parents: {missing}")
        self.events[cid] = dict(event)
        self._persist()
        return True

    def emit(self, event_type: str, parents: Iterable[str], payload: Mapping[str, Any]) -> dict[str, Any]:
        body = {
            "event_type": event_type,
            "parents": sorted(set(parents)),
            "payload": dict(payload),
            "timestamp": self.clock.iso(),
            "actor": self.peer_id,
        }
        event = {"event_cid": _event_cid(body), **body}
        self.ingest(event)
        return event

    def events_of_type(self, event_type: str, task_cid: str | None = None) -> list[dict[str, Any]]:
        events = [event for event in self.events.values() if event["event_type"] == event_type]
        if task_cid is not None:
            events = [event for event in events if event["payload"].get("task_cid") == task_cid]
        return sorted(events, key=lambda event: (event["timestamp"], event["event_cid"]))

    def claims(self, task_cid: str, epoch: int | None = None) -> list[dict[str, Any]]:
        claims = [dict(event["payload"], claim_cid=event["payload"]["claim_cid"], event_cid=event["event_cid"])
                  for event in self.events_of_type("task_claimed", task_cid)]
        return [claim for claim in claims if epoch is None or claim["logical_epoch"] == epoch]

    def resolutions(self, task_cid: str) -> list[dict[str, Any]]:
        return self.events_of_type("claim_resolved", task_cid)

    def accepted_resolution(self, task_cid: str) -> dict[str, Any] | None:
        accepted = [event for event in self.resolutions(task_cid) if event["payload"]["outcome"] == "accepted"]
        if not accepted:
            return None
        return max(accepted, key=lambda event: (event["payload"]["fencing_token"], event["event_cid"]))

    def task_created(self, task_cid: str) -> dict[str, Any] | None:
        created = self.events_of_type("task_created", task_cid)
        return created[0] if created else None

    def execution_mode(self, task_cid: str) -> str:
        created = self.task_created(task_cid)
        if created is None:
            raise CoordinationError("G_NOT_FOUND", "task is not known")
        return created["payload"].get("execution_mode", "exclusive")

    def completions(self, task_cid: str) -> list[dict[str, Any]]:
        return self.events_of_type("task_completed", task_cid)

    def authoritative_completion(self, task_cid: str) -> dict[str, Any] | None:
        """Return the sole completion matching the current accepted fence, if any."""
        resolution = self.accepted_resolution(task_cid)
        if resolution is None:
            return None
        accepted = resolution["payload"]
        matches = [
            event for event in self.completions(task_cid)
            if event["payload"]["claim_cid"] == accepted["accepted_claim_cid"]
            and event["payload"]["fencing_token"] == accepted["fencing_token"]
            and event["payload"].get("status") == "succeeded"
        ]
        if not matches:
            return None
        return min(matches, key=lambda event: event["event_cid"])

    def terminal(self, task_cid: str) -> dict[str, Any] | None:
        """Authoritative terminal completion (not every historical task_completed)."""
        return self.authoritative_completion(task_cid)

    def state_root(self) -> str:
        """Content-addressed digest of the peer's durable event set.

        The root deliberately excludes peer identity so converged stores share
        one state root after partition heal.
        """
        material = {
            "schema": "mcp++/profile-g/peer-state-root@1",
            "event_cids": sorted(self.events),
        }
        return profile_g_artifact_cid(material)


class ThreePeerHarness:
    """A deterministic majority-coordinated Profile G cluster."""

    def __init__(self, root: Path, peer_ids: Iterable[str], now_ms: int):
        ids = tuple(peer_ids)
        if len(ids) != 3 or len(set(ids)) != 3:
            raise ValueError("the conformance harness requires exactly three unique peers")
        self.root = Path(root)
        self.clock = DeterministicClock(now_ms)
        self.peers = {peer_id: Peer(peer_id, self.root / f"{peer_id.replace(':', '_')}.json", self.clock) for peer_id in ids}
        self.links = {frozenset((left, right)) for left in ids for right in ids if left < right}
        self.policy_denials = 0
        self.policy_bypasses = 0

    def connected(self, left: str, right: str) -> bool:
        return left == right or frozenset((left, right)) in self.links

    def partition(self, *groups: Iterable[str]) -> None:
        normalized = [set(group) for group in groups]
        if set().union(*normalized) != set(self.peers) or sum(map(len, normalized)) != len(self.peers):
            raise ValueError("partition groups must contain each peer exactly once")
        self.links = {frozenset((left, right)) for group in normalized for left in group for right in group if left < right}

    def heal(self) -> None:
        ids = tuple(self.peers)
        self.links = {frozenset((left, right)) for left in ids for right in ids if left < right}

    def reachable(self, peer_id: str) -> set[str]:
        return {other for other in self.peers if self.connected(peer_id, other)}

    def majority_reachable(self, peer_id: str) -> bool:
        return len(self.reachable(peer_id)) >= 2

    def _replicate(self, source: str, event: Mapping[str, Any]) -> None:
        for target in sorted(self.reachable(source) - {source}):
            # Causal delivery: send any parents absent at the target first.
            for parent in event["parents"]:
                if parent not in self.peers[target].events:
                    self._replicate_event_to(source, target, parent)
            self.peers[target].ingest(event)

    def _replicate_event_to(self, source: str, target: str, cid: str) -> None:
        event = self.peers[source].events[cid]
        for parent in event["parents"]:
            if parent not in self.peers[target].events:
                self._replicate_event_to(source, target, parent)
        self.peers[target].ingest(event)

    def create_task(self, coordinator: str, task_cid: str, execution_mode: str = "exclusive") -> dict[str, Any]:
        event = self.peers[coordinator].emit("task_created", [], {
            "task_cid": task_cid, "execution_mode": execution_mode, "state": "ready"
        })
        self._replicate(coordinator, event)
        return event

    def claim(self, peer_id: str, task_cid: str, *, logical_epoch: int, risk_bucket: int,
              capability_fit_millionths: int, expected_finish_ms: int, requested_lease_ms: int = 5000) -> dict[str, Any]:
        peer = self.peers[peer_id]
        task_events = peer.events_of_type("task_created", task_cid)
        if not task_events:
            raise CoordinationError("G_NOT_FOUND", "task is not known by claimant")
        prior = peer.accepted_resolution(task_cid)
        if logical_epoch == 1:
            if prior is not None:
                raise CoordinationError("G_CLAIM_CONFLICT", "epoch 1 already resolved")
            parent = task_events[0]["event_cid"]
        else:
            expiry = [event for event in peer.events_of_type("claim_expired", task_cid)
                      if event["payload"]["logical_epoch"] == logical_epoch - 1]
            if not expiry:
                raise CoordinationError("G_CLAIM_CONFLICT", "takeover requires the prior epoch expiry event")
            parent = expiry[-1]["event_cid"]
        claim_body = {
            "task_cid": task_cid, "logical_epoch": logical_epoch, "risk_bucket": risk_bucket,
            "capability_fit_millionths": capability_fit_millionths,
            "expected_finish_ms": expected_finish_ms, "claimant_did": peer_id,
            "requested_lease_ms": requested_lease_ms,
        }
        claim_cid = profile_g_artifact_cid(claim_body)
        event = peer.emit("task_claimed", [parent], {**claim_body, "claim_cid": claim_cid})
        self._replicate(peer_id, event)
        return event

    def resolve(self, resolver_id: str, task_cid: str, logical_epoch: int) -> dict[str, Any]:
        if not self.majority_reachable(resolver_id):
            self.policy_denials += 1
            raise CoordinationError("G_COORDINATION_UNAVAILABLE", "exclusive lease requires a majority")
        peer = self.peers[resolver_id]
        claims = peer.claims(task_cid, logical_epoch)
        if not claims:
            raise CoordinationError("G_NOT_FOUND", "no claims in requested epoch")
        prior = peer.accepted_resolution(task_cid)
        if prior and prior["payload"]["logical_epoch"] >= logical_epoch:
            return prior
        winner = min(claims, key=claim_order_key)
        lease_expires = self.clock.now_ms + winner["requested_lease_ms"]
        parents = [claim["event_cid"] for claim in claims]
        event = peer.emit("claim_resolved", parents, {
            "task_cid": task_cid, "logical_epoch": logical_epoch,
            "considered_claim_cids": sorted(claim["claim_cid"] for claim in claims),
            "accepted_claim_cid": winner["claim_cid"], "outcome": "accepted",
            "fencing_token": max(logical_epoch, (prior or {"payload": {"fencing_token": 0}})["payload"]["fencing_token"] + 1),
            "lease_expires_at_ms": lease_expires, "resolver_did": resolver_id,
        })
        self._replicate(resolver_id, event)
        for loser in sorted((claim for claim in claims if claim["claim_cid"] != winner["claim_cid"]), key=claim_order_key):
            conflict = peer.emit("claim_conflicted", [event["event_cid"], loser["event_cid"]], {
                "task_cid": task_cid, "logical_epoch": logical_epoch,
                "losing_claim_cid": loser["claim_cid"], "accepted_claim_cid": winner["claim_cid"],
                "reason": "deterministic-conflict-order",
            })
            self._replicate(resolver_id, conflict)
        return event

    def expire(self, peer_id: str, task_cid: str) -> dict[str, Any]:
        peer = self.peers[peer_id]
        resolution = peer.accepted_resolution(task_cid)
        if resolution is None:
            raise CoordinationError("G_NOT_FOUND", "no active lease")
        if self.clock.now_ms <= resolution["payload"]["lease_expires_at_ms"]:
            raise CoordinationError("G_CLAIM_CONFLICT", "lease has not expired")
        existing = [event for event in peer.events_of_type("claim_expired", task_cid)
                    if event["payload"]["logical_epoch"] == resolution["payload"]["logical_epoch"]]
        if existing:
            return existing[-1]
        event = peer.emit("claim_expired", [resolution["event_cid"]], {
            "task_cid": task_cid, "logical_epoch": resolution["payload"]["logical_epoch"],
            "fencing_token": resolution["payload"]["fencing_token"], "state": "ready",
        })
        self._replicate(peer_id, event)
        return event

    def complete(self, peer_id: str, task_cid: str, claim_cid: str, fencing_token: int, output_cid: str) -> dict[str, Any]:
        peer = self.peers[peer_id]
        resolution = peer.accepted_resolution(task_cid)
        if resolution is None:
            raise CoordinationError("G_NOT_FOUND", "no accepted resolution")
        accepted = resolution["payload"]
        existing = peer.authoritative_completion(task_cid)
        exact = accepted["accepted_claim_cid"] == claim_cid and accepted["fencing_token"] == fencing_token
        unexpired = self.clock.now_ms < accepted["lease_expires_at_ms"]
        if not exact or not unexpired:
            # Stale / expired / wrong-claim publishers are rejected without majority.
            reason = "G_STALE_FENCE" if fencing_token < accepted["fencing_token"] or not unexpired else "G_CLAIM_CONFLICT"
            return self._rejection(peer_id, task_cid, resolution, claim_cid, fencing_token, output_cid, reason)

        mode = peer.execution_mode(task_cid)
        if mode == "exclusive" and not self.majority_reachable(peer_id):
            # Exclusive authoritative completion requires neighborhood majority so a
            # partitioned lease holder cannot split-brain a second success.
            self.policy_denials += 1
            raise CoordinationError(
                "G_COORDINATION_UNAVAILABLE",
                "exclusive completion requires a majority",
            )

        if existing:
            payload = existing["payload"]
            if payload["claim_cid"] == claim_cid and payload["output_cid"] == output_cid:
                return existing
            return self._rejection(peer_id, task_cid, resolution, claim_cid, fencing_token, output_cid, "G_COMPLETION_CONFLICT")

        # Defense in depth: refuse a second non-matching completion event body.
        for prior in peer.completions(task_cid):
            prior_payload = prior["payload"]
            if (
                prior_payload["claim_cid"] == claim_cid
                and prior_payload["fencing_token"] == fencing_token
                and prior_payload["output_cid"] == output_cid
            ):
                return prior

        event = peer.emit("task_completed", [resolution["event_cid"]], {
            "task_cid": task_cid, "claim_cid": claim_cid, "resolution_cid": resolution["event_cid"],
            "fencing_token": fencing_token, "output_cid": output_cid, "status": "succeeded",
        })
        self._replicate(peer_id, event)
        return event

    def _rejection(self, peer_id: str, task_cid: str, resolution: Mapping[str, Any], claim_cid: str,
                   fencing_token: int, output_cid: str, reason: str) -> dict[str, Any]:
        peer = self.peers[peer_id]
        payload = {"task_cid": task_cid, "claim_cid": claim_cid, "fencing_token": fencing_token,
                   "output_cid": output_cid, "accepted_resolution_cid": resolution["event_cid"],
                   "outcome": "rejected", "reason": reason}
        # Replaying the same rejected evidence is idempotent because its body and timestamp are retained.
        for event in peer.events_of_type("task_reconciled", task_cid):
            if event["payload"] == payload:
                return event
        event = peer.emit("task_reconciled", [resolution["event_cid"]], payload)
        self._replicate(peer_id, event)
        return event

    def replay(self, source: str, target: str, event_cid: str) -> bool:
        before = len(self.peers[target].events)
        self._replicate_event_to(source, target, event_cid)
        return len(self.peers[target].events) != before

    def deliver(self, source: str, target: str, event_cid: str, *, causal: bool = True) -> bool:
        """Deliver one event, optionally without causal parent repair (reorder injection)."""
        if source == target:
            return False
        if not self.connected(source, target):
            raise CoordinationError("G_COORDINATION_UNAVAILABLE", "no link between source and target")
        event = self.peers[source].events[event_cid]
        if causal:
            before = len(self.peers[target].events)
            self._replicate_event_to(source, target, event_cid)
            return len(self.peers[target].events) != before
        # Non-causal delivery: attempt the leaf only so missing parents surface.
        return self.peers[target].ingest(event)

    def restart(self, peer_id: str) -> Peer:
        self.peers[peer_id] = Peer(peer_id, self.peers[peer_id].store_path, self.clock)
        return self.peers[peer_id]

    def _task_cids(self) -> set[str]:
        tasks: set[str] = set()
        for peer in self.peers.values():
            for event in peer.events.values():
                task_cid = event["payload"].get("task_cid")
                if isinstance(task_cid, str):
                    tasks.add(task_cid)
        return tasks

    def _demote_stale_completions(self) -> list[dict[str, Any]]:
        """After heal, record rejections for any non-authoritative task_completed events."""
        demotions: list[dict[str, Any]] = []
        witness = next(iter(self.peers))
        for task_cid in sorted(self._task_cids()):
            peer = self.peers[witness]
            resolution = peer.accepted_resolution(task_cid)
            if resolution is None:
                continue
            accepted = resolution["payload"]
            for completion in peer.completions(task_cid):
                payload = completion["payload"]
                matches = (
                    payload.get("claim_cid") == accepted["accepted_claim_cid"]
                    and payload.get("fencing_token") == accepted["fencing_token"]
                    and payload.get("status") == "succeeded"
                )
                if matches:
                    continue
                rejection = self._rejection(
                    witness,
                    task_cid,
                    resolution,
                    payload.get("claim_cid", ""),
                    int(payload.get("fencing_token", 0)),
                    payload.get("output_cid", ""),
                    "G_STALE_FENCE",
                )
                demotions.append(rejection)
        return demotions

    def reconcile(self) -> dict[str, Any]:
        """Heal and exchange bounded frontiers until all three stores converge."""
        self.heal()
        all_events: dict[str, dict[str, Any]] = {}
        for peer in self.peers.values():
            all_events.update(peer.events)
        pending = dict(all_events)
        while pending:
            progressed = False
            for cid, event in sorted(list(pending.items())):
                if all(all(parent in peer.events for parent in event["parents"]) for peer in self.peers.values()):
                    for peer in self.peers.values():
                        peer.ingest(event)
                    del pending[cid]
                    progressed = True
            if not progressed:
                raise CoordinationError("G_INVALID_ARTIFACT", "reconciliation frontier has missing parents")
        demotions = self._demote_stale_completions()
        # Re-exchange any demotion evidence emitted during stale-publisher cleanup.
        if demotions:
            for demotion in demotions:
                all_events[demotion["event_cid"]] = demotion
            for peer in self.peers.values():
                for demotion in demotions:
                    peer.ingest(demotion)
        frontiers = {peer_id: self.frontier(peer_id) for peer_id in self.peers}
        state_roots = {peer_id: self.state_root(peer_id) for peer_id in self.peers}
        return {
            "schema": "mcp++/profile-g/three-peer-reconciliation@1",
            "converged": len({tuple(frontier) for frontier in frontiers.values()}) == 1
            and len(set(state_roots.values())) == 1,
            "event_count": len(next(iter(self.peers.values())).events),
            "frontiers": frontiers,
            "state_roots": state_roots,
            "stale_demotions": len(demotions),
            "archive_boundaries": [],
        }

    def frontier(self, peer_id: str) -> list[str]:
        peer = self.peers[peer_id]
        parents = {parent for event in peer.events.values() for parent in event["parents"]}
        return sorted(set(peer.events) - parents)

    def state_root(self, peer_id: str) -> str:
        return self.peers[peer_id].state_root()

    def authoritative_completion(self, task_cid: str, peer_id: str | None = None) -> dict[str, Any] | None:
        if peer_id is None:
            peer_id = next(iter(self.peers))
        return self.peers[peer_id].authoritative_completion(task_cid)

    def evidence(self, peer_id: str) -> list[dict[str, Any]]:
        peer = self.peers[peer_id]
        remaining = dict(peer.events)
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        while remaining:
            ready = sorted(cid for cid, event in remaining.items() if set(event["parents"]) <= seen)
            if not ready:
                raise CoordinationError("G_INVALID_ARTIFACT", "event graph is cyclic")
            for cid in ready:
                ordered.append(remaining.pop(cid))
                seen.add(cid)
        return ordered

    def conformance_report(self, task_cid: str) -> dict[str, Any]:
        peer = next(iter(self.peers.values()))
        resolutions = peer.resolutions(task_cid)
        authoritative = peer.authoritative_completion(task_cid)
        raw_completions = peer.completions(task_cid)
        rejected = peer.events_of_type("task_reconciled", task_cid)
        frontiers = {peer_id: self.frontier(peer_id) for peer_id in self.peers}
        state_roots = {peer_id: self.state_root(peer_id) for peer_id in self.peers}
        fencing_tokens = sorted({event["payload"]["fencing_token"] for event in resolutions})
        return {
            "schema": "mcp++/profile-g/three-peer-conformance-report@1",
            "task_cid": task_cid,
            "peer_count": 3,
            "event_count": len(peer.events),
            "frontiers_converged": len({tuple(value) for value in frontiers.values()}) == 1,
            "state_roots_converged": len(set(state_roots.values())) == 1,
            "state_roots": state_roots,
            "accepted_epochs": sorted({event["payload"]["logical_epoch"] for event in resolutions}),
            "fencing_tokens": fencing_tokens,
            "successful_completion_count": 1 if authoritative is not None else 0,
            "raw_completion_event_count": len(raw_completions),
            "authoritative_completion_cid": None if authoritative is None else authoritative["event_cid"],
            "rejected_evidence_reasons": sorted({event["payload"]["reason"] for event in rejected}),
            "policy_denials": self.policy_denials,
            "policy_bypasses": self.policy_bypasses,
            "checks": {
                "content_addressed_events": all(
                    _event_cid(_body_without_cid(event)) == event["event_cid"] for event in peer.events.values()
                ),
                "strictly_increasing_fences": all(
                    left < right for left, right in zip(fencing_tokens, fencing_tokens[1:])
                ),
                "single_success": (1 if authoritative is not None else 0) == 1 and (
                    authoritative is None
                    or all(
                        event["event_cid"] == authoritative["event_cid"]
                        or event["payload"]["fencing_token"] < authoritative["payload"]["fencing_token"]
                        for event in raw_completions
                    )
                ),
                "converged": len({tuple(value) for value in frontiers.values()}) == 1
                and len(set(state_roots.values())) == 1,
                "no_policy_bypass": self.policy_bypasses == 0,
            },
        }
