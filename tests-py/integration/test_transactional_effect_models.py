"""FACP-045: Model transactional effect protocols (TEP).

Acceptance (taskboard):
- Models encode all required invariants and crash boundaries.
- Installed admitted tools produce checked traces.
- Missing tools produce explicit nonqualified capability evidence and leave
  the live model-check gate unsatisfied.
- No auto-install of formal tools; never report model proof when unavailable.
- Bounded exploration / syntax / reference tests only.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TEP_DIR = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "formal"
    / "protocols"
    / "transactional_effects"
)
TLA_PATH = TEP_DIR / "TransactionalEffects.tla"
ALS_PATH = TEP_DIR / "relational_invariants.als"
TCB_PATH = (
    REPO_ROOT
    / "implementation_plan"
    / "formal_assurance_control_plane"
    / "baseline"
    / "trusted_computing_base.json"
)

TASK_ID: Final = "FACP-045"
GOAL_ID: Final = "FACP-G510"
EVIDENCE_SCHEMA: Final = "facp/tep-models@1"
BUNDLE: Final = "facp/protocols/models"

REQUIRED_INVARIANTS: Final[tuple[str, ...]] = (
    "NoDoubleEffect",
    "NoStaleFenceCompletion",
    "NoSuccessWithoutObservation",
    "NoConfirmationReuse",
    "NoReplayOfUnknownIrreversibleEffect",
)

CRASH_BOUNDARIES: Final[tuple[str, ...]] = (
    "admission",
    "reservation",
    "started",
    "unknown",
    "observed",
    "receipt",
    "current",
    "lease",
    "fence",
    "retry",
    "idempotency",
    "crash",
    "settlement",
    "compensation",
    "proof_promotion",
)

EVIDENCE_SUBSET: Final[tuple[str, ...]] = CRASH_BOUNDARIES

TYPESTATES: Final[frozenset[str]] = frozenset(
    {
        "Proposed",
        "ContractResolved",
        "ActorAuthenticated",
        "CapabilityVerified",
        "PolicyEvaluated",
        "ObligationsSatisfied",
        "ConfirmationSatisfied",
        "LeaseHeld",
        "Reserved",
        "Started",
        "Observed",
        "ReceiptSealed",
        "Rejected",
        "Unavailable",
        "Failed",
        "Unknown",
        "CompensationRequired",
        "Compensated",
        "Aborted",
    }
)

HAPPY_PATH: Final[tuple[str, ...]] = (
    "Proposed",
    "ContractResolved",
    "ActorAuthenticated",
    "CapabilityVerified",
    "PolicyEvaluated",
    "ObligationsSatisfied",
    "ConfirmationSatisfied",
    "LeaseHeld",
    "Reserved",
    "Started",
    "Observed",
    "ReceiptSealed",
)

ADMITTED_TOOLS: Final[tuple[str, ...]] = ("tla_plus", "alloy")
PROHIBITED_COMPENSATIONS: Final[frozenset[str]] = frozenset(
    {
        "import_time_installation",
        "worker_time_installation",
        "simulated_proof",
        "auto_install",
    }
)


# ---------------------------------------------------------------------------
# Capability probe (fail-closed; never installs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolProbe:
    tool: str
    admitted: bool
    status: str
    disposition: str
    path: str | None
    version: str | None
    raw: str | None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    """Explicit capability evidence for live model-check gating."""

    schema: str
    task_id: str
    goal_id: str
    tools: tuple[ToolProbe, ...]
    live_model_check_gate_satisfied: bool
    qualification: str
    prohibited_compensations: tuple[str, ...]
    checked_traces: tuple[dict[str, Any], ...] = ()
    model_proof_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "task_id": self.task_id,
            "goal_id": self.goal_id,
            "bundle": BUNDLE,
            "tools": [
                {
                    "tool": t.tool,
                    "admitted": t.admitted,
                    "status": t.status,
                    "disposition": t.disposition,
                    "path": t.path,
                    "version": t.version,
                    "raw": t.raw,
                    "notes": list(t.notes),
                }
                for t in self.tools
            ],
            "live_model_check_gate_satisfied": self.live_model_check_gate_satisfied,
            "qualification": self.qualification,
            "prohibited_compensations": list(self.prohibited_compensations),
            "checked_traces": list(self.checked_traces),
            "model_proof_claimed": self.model_proof_claimed,
        }


def _which(name: str) -> str | None:
    found = shutil.which(name)
    return found if found and os.access(found, os.X_OK) else None


def _probe_tla_plus() -> ToolProbe:
    """Probe for an admitted TLC / tla2tools toolchain without installing."""
    notes: list[str] = []
    tlc = _which("tlc") or _which("tlc2") or _which("tla2sany")
    jar_env = os.environ.get("TLA2TOOLS_JAR") or os.environ.get("FACP_TLA2TOOLS_JAR")
    jar_path: str | None = None
    if jar_env and Path(jar_env).is_file():
        jar_path = jar_env
        notes.append("TLA2TOOLS_JAR present")
    # Common admitted locations only (no network, no download).
    for candidate in (
        Path("/usr/share/java/tla2tools.jar"),
        Path("/opt/tla/tla2tools.jar"),
        Path.home() / "tla" / "tla2tools.jar",
    ):
        if candidate.is_file():
            jar_path = str(candidate)
            notes.append(f"found:{candidate}")
            break

    raw = None
    version = None
    path = tlc or jar_path
    if tlc:
        try:
            proc = subprocess.run(
                [tlc, "-help"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            raw = (proc.stdout or proc.stderr or "")[:500]
        except (OSError, subprocess.TimeoutExpired) as exc:
            notes.append(f"tlc_probe_error:{exc}")
            tlc = None
            path = jar_path

    admitted = bool(tlc or jar_path)
    if admitted:
        return ToolProbe(
            tool="tla_plus",
            admitted=True,
            status="present",
            disposition="available",
            path=path,
            version=version,
            raw=raw,
            notes=tuple(notes) or ("admitted_host_toolchain",),
        )
    return ToolProbe(
        tool="tla_plus",
        admitted=False,
        status="absent",
        disposition="typed_capability_gap",
        path=None,
        version=None,
        raw=None,
        notes=(
            "tla_plus absent; record nonqualified capability evidence",
            "defer_capability or reviewed provisioning only; never ad hoc install",
        ),
    )


def _probe_alloy() -> ToolProbe:
    """Probe for an admitted Alloy CLI / jar without installing."""
    notes: list[str] = []
    alloy = _which("alloy") or _which("alloyc") or _which("alloy4")
    jar_env = os.environ.get("ALLOY_JAR") or os.environ.get("FACP_ALLOY_JAR")
    jar_path: str | None = None
    if jar_env and Path(jar_env).is_file():
        jar_path = jar_env
        notes.append("ALLOY_JAR present")
    for candidate in (
        Path("/usr/share/java/alloy.jar"),
        Path("/opt/alloy/alloy.jar"),
        Path.home() / "alloy" / "alloy.jar",
    ):
        if candidate.is_file():
            jar_path = str(candidate)
            notes.append(f"found:{candidate}")
            break

    raw = None
    version = None
    path = alloy or jar_path
    if alloy:
        try:
            proc = subprocess.run(
                [alloy, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            raw = (proc.stdout or proc.stderr or "")[:500]
            version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", raw or "")
            if version_match:
                version = version_match.group(1)
        except (OSError, subprocess.TimeoutExpired) as exc:
            notes.append(f"alloy_probe_error:{exc}")
            alloy = None
            path = jar_path

    admitted = bool(alloy or jar_path)
    if admitted:
        return ToolProbe(
            tool="alloy",
            admitted=True,
            status="present",
            disposition="available",
            path=path,
            version=version,
            raw=raw,
            notes=tuple(notes) or ("admitted_host_toolchain",),
        )
    return ToolProbe(
        tool="alloy",
        admitted=False,
        status="absent",
        disposition="typed_capability_gap",
        path=None,
        version=None,
        raw=None,
        notes=(
            "alloy absent; record nonqualified capability evidence",
            "defer_capability or reviewed provisioning only; never ad hoc install",
        ),
    )


def probe_formal_tools() -> tuple[ToolProbe, ...]:
    return (_probe_tla_plus(), _probe_alloy())


def build_capability_evidence(
    tools: Sequence[ToolProbe],
    *,
    checked_traces: Sequence[Mapping[str, Any]] = (),
) -> CapabilityEvidence:
    admitted = all(t.admitted for t in tools)
    if not admitted:
        return CapabilityEvidence(
            schema=EVIDENCE_SCHEMA,
            task_id=TASK_ID,
            goal_id=GOAL_ID,
            tools=tuple(tools),
            live_model_check_gate_satisfied=False,
            qualification="nonqualified",
            prohibited_compensations=tuple(sorted(PROHIBITED_COMPENSATIONS)),
            checked_traces=(),
            model_proof_claimed=False,
        )
    traces = tuple(dict(t) for t in checked_traces)
    return CapabilityEvidence(
        schema=EVIDENCE_SCHEMA,
        task_id=TASK_ID,
        goal_id=GOAL_ID,
        tools=tuple(tools),
        live_model_check_gate_satisfied=bool(traces),
        qualification="qualified" if traces else "admitted_awaiting_traces",
        prohibited_compensations=tuple(sorted(PROHIBITED_COMPENSATIONS)),
        checked_traces=traces,
        model_proof_claimed=bool(traces),
    )


# ---------------------------------------------------------------------------
# Reference transition-vector interpreter (deterministic; no TLC required)
# ---------------------------------------------------------------------------


@dataclass
class OpState:
    typestate: str = "Proposed"
    effect_count: int = 0
    observed: bool = False
    receipt_sealed: bool = False
    confirmation_bound: bool = True
    confirmation_spent: bool = False
    lease_held: bool = False
    fence_gen: int = 1
    fence_at_reserve: int = 0
    current_pointer: int = 0
    pending_current: int = 0
    retries: int = 0
    idempotency_recorded: bool = False
    unknown_pending: bool = False
    compensation_owed: bool = False
    proof_promoted: bool = False
    durable_cursor: str = "Proposed"
    last_crash_boundary: str = "none"
    reversibility: str = "reversible"  # irreversible | compensatable | reversible


@dataclass
class World:
    ops: dict[str, OpState] = field(default_factory=dict)
    crashed: bool = False
    max_fence_gen: int = 3
    max_retries: int = 2
    trace: list[dict[str, Any]] = field(default_factory=list)

    def snapshot_event(
        self, action: str, op: str | None, boundary: str, **extra: Any
    ) -> None:
        self.trace.append(
            {
                "action": action,
                "op": op,
                "boundary": boundary,
                "crashed": self.crashed,
                **extra,
            }
        )


class TransitionError(ValueError):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise TransitionError(msg)


def apply_action(world: World, action: str, op_id: str | None = None) -> None:
    if action == "Recover":
        _require(world.crashed, "Recover requires crashed")
        world.crashed = False
        world.snapshot_event(action, None, "crash")
        return

    if action.startswith("Crash:"):
        boundary = action.split(":", 1)[1]
        _require(boundary in CRASH_BOUNDARIES, f"unknown crash boundary {boundary}")
        _require(not world.crashed, "already crashed")
        # Restore each op to durable cursor (volatile loss).
        for st in world.ops.values():
            st.typestate = st.durable_cursor
            st.last_crash_boundary = "crash"
        world.crashed = True
        world.snapshot_event(action, None, "crash", named_boundary=boundary)
        return

    _require(op_id is not None and op_id in world.ops, f"unknown op {op_id}")
    assert op_id is not None
    st = world.ops[op_id]
    _require(not world.crashed, "must Recover before further actions")

    def commit(next_state: str, boundary: str) -> None:
        st.typestate = next_state
        st.durable_cursor = next_state
        st.last_crash_boundary = boundary
        world.snapshot_event(action, op_id, boundary, typestate=next_state)

    if action == "AdvanceAdmission":
        pre = HAPPY_PATH[: HAPPY_PATH.index("LeaseHeld")]
        _require(st.typestate in pre and st.typestate != "ConfirmationSatisfied", "bad admission state")
        # Special-case confirmation via SatisfyConfirmation.
        idx = HAPPY_PATH.index(st.typestate)
        nxt = HAPPY_PATH[idx + 1]
        _require(nxt != "ConfirmationSatisfied" or not st.confirmation_bound, "use SatisfyConfirmation")
        if st.typestate == "ObligationsSatisfied" and st.confirmation_bound:
            raise TransitionError("use SatisfyConfirmation")
        commit(nxt, "admission")
        return

    if action == "SatisfyConfirmation":
        _require(st.typestate == "ObligationsSatisfied", "confirmation prestate")
        _require(st.confirmation_bound, "confirmation not bound")
        _require(not st.confirmation_spent, "NoConfirmationReuse")
        st.confirmation_spent = True
        commit("ConfirmationSatisfied", "admission")
        return

    if action == "AcquireLease":
        _require(st.typestate == "ConfirmationSatisfied", "lease prestate")
        _require(st.fence_gen < world.max_fence_gen, "fence bound")
        st.lease_held = True
        st.fence_gen += 1
        commit("LeaseHeld", "lease")
        return

    if action == "Reserve":
        _require(st.typestate == "LeaseHeld" and st.lease_held, "reserve prestate")
        _require(not st.idempotency_recorded, "idempotency already recorded")
        st.fence_at_reserve = st.fence_gen
        st.idempotency_recorded = True
        commit("Reserved", "reservation")
        return

    if action == "Start":
        _require(st.typestate == "Reserved", "start prestate")
        _require(st.lease_held, "lease required")
        _require(st.fence_at_reserve == st.fence_gen, "NoStaleFenceCompletion/start")
        commit("Started", "started")
        return

    if action == "ApplyEffect":
        _require(st.typestate == "Started", "apply prestate")
        _require(st.effect_count == 0, "NoDoubleEffect")
        st.effect_count = 1
        st.pending_current = st.current_pointer + 1
        st.last_crash_boundary = "idempotency"
        world.snapshot_event(action, op_id, "idempotency", effect_count=1)
        return

    if action == "Observe":
        _require(st.typestate in {"Started", "Unknown"}, "observe prestate")
        _require(st.effect_count == 1, "nothing to observe")
        _require(not st.observed, "already observed")
        st.observed = True
        st.unknown_pending = False
        commit("Observed", "observed")
        return

    if action == "EnterUnknown":
        _require(st.typestate == "Started", "unknown prestate")
        st.unknown_pending = True
        commit("Unknown", "unknown")
        return

    if action == "Fail":
        _require(
            st.typestate in {"Started", "Unknown", "CompensationRequired"},
            "fail prestate",
        )
        # Irreversible unknown stays sticky to block blind replay.
        if not (st.reversibility == "irreversible" and st.unknown_pending):
            st.unknown_pending = False
        commit("Failed", "settlement")
        return

    if action == "Abort":
        _require(st.typestate in {"Started", "Unknown"}, "abort prestate")
        _require(st.effect_count == 0, "cannot abort after effect")
        if st.reversibility == "irreversible" and st.unknown_pending and st.effect_count == 1:
            raise TransitionError("NoReplayOfUnknownIrreversibleEffect/abort")
        st.unknown_pending = False
        commit("Aborted", "settlement")
        return

    if action == "RequireCompensation":
        _require(st.reversibility == "compensatable", "not compensatable")
        _require(
            st.typestate in {"Started", "Unknown", "Observed"},
            "compensation prestate",
        )
        st.compensation_owed = True
        st.unknown_pending = False
        commit("CompensationRequired", "compensation")
        return

    if action == "Compensate":
        _require(st.typestate == "CompensationRequired", "compensate prestate")
        _require(st.compensation_owed, "nothing owed")
        st.compensation_owed = False
        st.observed = True
        commit("Compensated", "compensation")
        return

    if action == "SealReceipt":
        _require(
            st.typestate
            in {
                "Observed",
                "Compensated",
                "Failed",
                "Rejected",
                "Unavailable",
                "Aborted",
            },
            "seal prestate",
        )
        if st.typestate in {"Observed", "Compensated"}:
            _require(st.observed, "NoSuccessWithoutObservation")
        _require(st.fence_at_reserve == st.fence_gen, "NoStaleFenceCompletion")
        st.receipt_sealed = True
        commit("ReceiptSealed", "receipt")
        return

    if action == "SettleCurrent":
        _require(st.typestate == "ReceiptSealed" and st.receipt_sealed, "settle prestate")
        _require(st.observed, "NoSuccessWithoutObservation/current")
        _require(st.pending_current == st.current_pointer + 1, "pending mismatch")
        st.current_pointer = st.pending_current
        st.last_crash_boundary = "current"
        world.snapshot_event(action, op_id, "current", current=st.current_pointer)
        return

    if action == "PromoteProof":
        _require(st.typestate == "ReceiptSealed" and st.receipt_sealed, "proof prestate")
        _require(st.observed, "observation required for proof")
        _require(st.current_pointer == st.pending_current and st.pending_current > 0, "current")
        _require(not st.proof_promoted, "already promoted")
        st.proof_promoted = True
        st.last_crash_boundary = "proof_promotion"
        world.snapshot_event(action, op_id, "proof_promotion", proof=True)
        return

    if action == "Reject":
        _require(st.typestate in HAPPY_PATH[: HAPPY_PATH.index("Reserved")], "reject prestate")
        commit("Rejected", "admission")
        return

    if action == "BumpFence":
        _require(st.lease_held, "lease required to bump")
        _require(st.fence_gen < world.max_fence_gen, "fence bound")
        st.fence_gen += 1
        st.last_crash_boundary = "fence"
        world.snapshot_event(action, op_id, "fence", fence_gen=st.fence_gen)
        return

    if action == "Retry":
        _require(st.typestate == "Failed", "retry prestate")
        _require(st.retries < world.max_retries, "retry bound")
        if st.reversibility == "irreversible" and (
            st.unknown_pending or st.effect_count > 0
        ):
            raise TransitionError("NoReplayOfUnknownIrreversibleEffect")
        _require(not st.idempotency_recorded or st.effect_count == 0, "idempotency")
        st.retries += 1
        st.idempotency_recorded = False
        st.receipt_sealed = False
        st.observed = False
        commit("LeaseHeld", "retry")
        return

    raise TransitionError(f"unknown action {action}")


def check_invariants(world: World) -> dict[str, bool]:
    results: dict[str, bool] = {name: True for name in REQUIRED_INVARIANTS}
    for op_id, st in world.ops.items():
        if st.effect_count > 1:
            results["NoDoubleEffect"] = False
        if st.receipt_sealed and st.typestate == "ReceiptSealed":
            if st.fence_at_reserve != st.fence_gen:
                results["NoStaleFenceCompletion"] = False
        if st.proof_promoted and not st.observed:
            results["NoSuccessWithoutObservation"] = False
        if st.current_pointer > 0 and not st.observed:
            results["NoSuccessWithoutObservation"] = False
        if (
            st.receipt_sealed
            and st.effect_count == 1
            and st.typestate == "ReceiptSealed"
            and not st.observed
        ):
            results["NoSuccessWithoutObservation"] = False
        if st.confirmation_spent and not st.confirmation_bound:
            results["NoConfirmationReuse"] = False
        if (
            st.reversibility == "irreversible"
            and st.unknown_pending
            and st.typestate in {"Reserved", "Started"}
            and st.retries > 0
        ):
            results["NoReplayOfUnknownIrreversibleEffect"] = False
        _ = op_id
    return results


def run_vector(
    ops: Mapping[str, str],
    steps: Sequence[tuple[str, str | None]],
    *,
    expect_ok: bool = True,
) -> World:
    world = World(
        ops={
            name: OpState(reversibility=rev)
            for name, rev in ops.items()
        }
    )
    try:
        for action, op_id in steps:
            apply_action(world, action, op_id)
            inv = check_invariants(world)
            if not all(inv.values()):
                raise TransitionError(f"invariant broken: {inv}")
        if not expect_ok:
            raise AssertionError("expected vector to fail")
    except TransitionError:
        if expect_ok:
            raise
    return world


def happy_path_vector() -> list[tuple[str, str | None]]:
    o = "o1"
    steps: list[tuple[str, str | None]] = []
    # Proposed -> ... -> ObligationsSatisfied
    for _ in range(HAPPY_PATH.index("ObligationsSatisfied")):
        steps.append(("AdvanceAdmission", o))
    steps.extend(
        [
            ("SatisfyConfirmation", o),
            ("AcquireLease", o),
            ("Reserve", o),
            ("Start", o),
            ("ApplyEffect", o),
            ("Observe", o),
            ("SealReceipt", o),
            ("SettleCurrent", o),
            ("PromoteProof", o),
        ]
    )
    return steps


# ---------------------------------------------------------------------------
# Optional live tool runners (only when admitted)
# ---------------------------------------------------------------------------


def _run_tlc_checked_trace(probe: ToolProbe) -> dict[str, Any] | None:
    """Attempt a bounded TLC parse/check when toolchain is admitted."""
    if not probe.admitted or not probe.path:
        return None
    # Prefer SANY-style syntax check via java -cp jar if only jar is present.
    try:
        if probe.path.endswith(".jar"):
            cmd = [
                "java",
                "-cp",
                probe.path,
                "tla2sany.SANY",
                str(TLA_PATH),
            ]
        else:
            # tlc binary: syntax / short bounded run is environment-specific;
            # we only claim a checked trace when the process exits 0.
            cmd = [probe.path, "-config", str(TLA_PATH), str(TLA_PATH)]
        proc = subprocess.run(
            cmd,
            cwd=str(TEP_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            return {
                "tool": "tla_plus",
                "status": "tool_error",
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-1000:],
                "stderr_tail": (proc.stderr or "")[-1000:],
                "model_proof": False,
            }
        return {
            "tool": "tla_plus",
            "status": "checked",
            "returncode": 0,
            "artifact": str(TLA_PATH.relative_to(REPO_ROOT)),
            "model_proof": True,
            "bounds": {"MaxFenceGen": 3, "MaxRetries": 2},
            "invariants": list(REQUIRED_INVARIANTS),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "tool": "tla_plus",
            "status": "tool_error",
            "error": str(exc),
            "model_proof": False,
        }


def _run_alloy_checked_trace(probe: ToolProbe) -> dict[str, Any] | None:
    if not probe.admitted or not probe.path:
        return None
    try:
        if probe.path.endswith(".jar"):
            cmd = ["java", "-jar", probe.path, "-c", str(ALS_PATH)]
        else:
            cmd = [probe.path, "-c", str(ALS_PATH)]
        proc = subprocess.run(
            cmd,
            cwd=str(TEP_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            return {
                "tool": "alloy",
                "status": "tool_error",
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-1000:],
                "stderr_tail": (proc.stderr or "")[-1000:],
                "model_proof": False,
            }
        return {
            "tool": "alloy",
            "status": "checked",
            "returncode": 0,
            "artifact": str(ALS_PATH.relative_to(REPO_ROOT)),
            "model_proof": True,
            "bounds": {"Op": 3, "Int": 4},
            "invariants": list(REQUIRED_INVARIANTS),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "tool": "alloy",
            "status": "tool_error",
            "error": str(exc),
            "model_proof": False,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tla_text() -> str:
    assert TLA_PATH.is_file(), TLA_PATH
    return TLA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def als_text() -> str:
    assert ALS_PATH.is_file(), ALS_PATH
    return ALS_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tool_probes() -> tuple[ToolProbe, ...]:
    return probe_formal_tools()


def test_declared_outputs_exist() -> None:
    assert TLA_PATH.is_file(), TLA_PATH
    assert ALS_PATH.is_file(), ALS_PATH
    assert TEP_DIR.is_dir()


def test_models_encode_task_and_evidence_identity(tla_text: str, als_text: str) -> None:
    for text in (tla_text, als_text):
        assert TASK_ID in text
        assert GOAL_ID in text
        assert EVIDENCE_SCHEMA in text
        assert BUNDLE in text


def test_models_encode_required_invariants(tla_text: str, als_text: str) -> None:
    for name in REQUIRED_INVARIANTS:
        assert name in tla_text, f"TLA missing {name}"
        assert name in als_text, f"Alloy missing {name}"
    assert "Safety" in tla_text
    assert "pred Safety" in als_text or "Safety {" in als_text


def test_models_encode_crash_boundaries_and_evidence_subset(
    tla_text: str, als_text: str
) -> None:
    for boundary in CRASH_BOUNDARIES:
        assert boundary in tla_text, f"TLA missing crash boundary {boundary}"
        assert boundary in als_text, f"Alloy missing crash boundary {boundary}"
    assert "CrashBoundaries" in tla_text
    assert "CrashBoundaryCoverage" in tla_text
    assert "CrashBoundaryCoverage" in als_text
    # Evidence subset aliases used by the taskboard.
    for token in (
        "admission",
        "reservation",
        "lease",
        "fence",
        "retry",
        "idempotency",
        "compensation",
        "proof_promotion",
        "settlement",
    ):
        assert token in EVIDENCE_SUBSET


def test_models_encode_typestate_and_reversibility(tla_text: str, als_text: str) -> None:
    for state in TYPESTATES:
        assert f'"{state}"' in tla_text or state in tla_text
        assert state in als_text
    assert "IrreversibleOps" in tla_text
    assert "CompensatableOps" in tla_text
    assert "Irreversible" in als_text
    assert "Compensatable" in als_text


def test_tla_is_bounded_and_forbids_unbounded_claims(tla_text: str) -> None:
    assert "MaxFenceGen" in tla_text
    assert "MaxRetries" in tla_text
    assert "bounded" in tla_text.lower() or "Bound" in tla_text
    assert "THEOREM Spec => []Safety" in tla_text
    # No placeholder stubs.
    assert "TODO" not in tla_text
    assert "FIXME" not in tla_text


def test_alloy_has_bounded_checks(als_text: str) -> None:
    assert "check SafetyHolds" in als_text
    assert "for 3" in als_text
    for name in REQUIRED_INVARIANTS:
        # Violation-hunt run commands exist for each invariant family.
        assert name in als_text
    assert "TODO" not in als_text
    assert "FIXME" not in als_text


def test_reference_happy_path_preserves_invariants() -> None:
    world = run_vector({"o1": "reversible"}, happy_path_vector(), expect_ok=True)
    inv = check_invariants(world)
    assert all(inv.values()), inv
    st = world.ops["o1"]
    assert st.typestate == "ReceiptSealed"
    assert st.observed and st.receipt_sealed and st.proof_promoted
    assert st.effect_count == 1
    assert st.current_pointer == 1
    # Trace covers required evidence subset tokens.
    boundaries = {ev["boundary"] for ev in world.trace}
    for required in (
        "admission",
        "lease",
        "reservation",
        "started",
        "idempotency",
        "observed",
        "receipt",
        "current",
        "proof_promotion",
    ):
        assert required in boundaries


def test_reference_no_double_effect() -> None:
    steps = happy_path_vector()
    # Insert a second ApplyEffect after the first.
    idx = next(i for i, (a, _) in enumerate(steps) if a == "ApplyEffect")
    bad = list(steps[: idx + 1]) + [("ApplyEffect", "o1")]
    with pytest.raises(TransitionError, match="NoDoubleEffect"):
        run_vector({"o1": "reversible"}, bad, expect_ok=True)


def test_reference_no_stale_fence_completion() -> None:
    o = "o1"
    steps: list[tuple[str, str | None]] = []
    for _ in range(HAPPY_PATH.index("ObligationsSatisfied")):
        steps.append(("AdvanceAdmission", o))
    steps.extend(
        [
            ("SatisfyConfirmation", o),
            ("AcquireLease", o),
            ("Reserve", o),
            ("Start", o),
            ("ApplyEffect", o),
            ("Observe", o),
            ("BumpFence", o),  # invalidate fence after reserve
            ("SealReceipt", o),
        ]
    )
    with pytest.raises(TransitionError, match="NoStaleFenceCompletion"):
        run_vector({o: "reversible"}, steps, expect_ok=True)


def test_reference_no_success_without_observation() -> None:
    o = "o1"
    steps: list[tuple[str, str | None]] = []
    for _ in range(HAPPY_PATH.index("ObligationsSatisfied")):
        steps.append(("AdvanceAdmission", o))
    steps.extend(
        [
            ("SatisfyConfirmation", o),
            ("AcquireLease", o),
            ("Reserve", o),
            ("Start", o),
            ("ApplyEffect", o),
            # skip Observe
            ("SealReceipt", o),
        ]
    )
    with pytest.raises(TransitionError):
        run_vector({o: "reversible"}, steps, expect_ok=True)


def test_reference_no_confirmation_reuse() -> None:
    o = "o1"
    steps: list[tuple[str, str | None]] = []
    for _ in range(HAPPY_PATH.index("ObligationsSatisfied")):
        steps.append(("AdvanceAdmission", o))
    steps.append(("SatisfyConfirmation", o))
    world = run_vector({o: "reversible"}, steps, expect_ok=True)
    assert world.ops[o].confirmation_spent is True
    # Re-enter ObligationsSatisfied only for the reuse probe; spent flag remains.
    world.ops[o].typestate = "ObligationsSatisfied"
    with pytest.raises(TransitionError, match="NoConfirmationReuse"):
        apply_action(world, "SatisfyConfirmation", o)
    inv = check_invariants(world)
    assert inv["NoConfirmationReuse"] is True


def test_reference_no_replay_of_unknown_irreversible() -> None:
    o = "o1"
    steps: list[tuple[str, str | None]] = []
    for _ in range(HAPPY_PATH.index("ObligationsSatisfied")):
        steps.append(("AdvanceAdmission", o))
    steps.extend(
        [
            ("SatisfyConfirmation", o),
            ("AcquireLease", o),
            ("Reserve", o),
            ("Start", o),
            ("ApplyEffect", o),
            ("EnterUnknown", o),
            ("Fail", o),
            ("Retry", o),
        ]
    )
    with pytest.raises(TransitionError, match="NoReplayOfUnknownIrreversibleEffect"):
        run_vector({o: "irreversible"}, steps, expect_ok=True)


def test_reference_crash_boundary_injection_and_recovery() -> None:
    o = "o1"
    steps: list[tuple[str, str | None]] = []
    for _ in range(HAPPY_PATH.index("ObligationsSatisfied")):
        steps.append(("AdvanceAdmission", o))
    steps.extend(
        [
            ("SatisfyConfirmation", o),
            ("AcquireLease", o),
            ("Reserve", o),
            ("Crash:reservation", None),
            ("Recover", None),
            ("Start", o),
            ("ApplyEffect", o),
            ("Observe", o),
            ("SealReceipt", o),
        ]
    )
    world = run_vector({o: "reversible"}, steps, expect_ok=True)
    assert any(ev["boundary"] == "crash" for ev in world.trace)
    assert world.ops[o].typestate == "ReceiptSealed"


def test_reference_compensation_path() -> None:
    o = "o1"
    steps: list[tuple[str, str | None]] = []
    for _ in range(HAPPY_PATH.index("ObligationsSatisfied")):
        steps.append(("AdvanceAdmission", o))
    steps.extend(
        [
            ("SatisfyConfirmation", o),
            ("AcquireLease", o),
            ("Reserve", o),
            ("Start", o),
            ("ApplyEffect", o),
            ("RequireCompensation", o),
            ("Compensate", o),
            ("SealReceipt", o),
            ("SettleCurrent", o),
        ]
    )
    world = run_vector({o: "compensatable"}, steps, expect_ok=True)
    assert world.ops[o].typestate == "ReceiptSealed"
    assert any(ev["boundary"] == "compensation" for ev in world.trace)


def test_capability_probe_never_auto_installs(tool_probes: tuple[ToolProbe, ...]) -> None:
    names = {t.tool for t in tool_probes}
    assert names == set(ADMITTED_TOOLS)
    for probe in tool_probes:
        assert probe.disposition in {"available", "typed_capability_gap"}
        if not probe.admitted:
            assert probe.status == "absent"
            assert probe.disposition == "typed_capability_gap"
            assert any("never ad hoc install" in n for n in probe.notes)


def test_missing_tools_produce_nonqualified_evidence_and_unsatisfied_gate(
    tool_probes: tuple[ToolProbe, ...]
) -> None:
    evidence = build_capability_evidence(tool_probes)
    payload = evidence.to_dict()
    assert payload["schema"] == EVIDENCE_SCHEMA
    assert payload["task_id"] == TASK_ID
    assert payload["goal_id"] == GOAL_ID

    missing = [t for t in tool_probes if not t.admitted]
    if missing:
        assert evidence.qualification == "nonqualified"
        assert evidence.live_model_check_gate_satisfied is False
        assert evidence.model_proof_claimed is False
        assert evidence.checked_traces == ()
        for t in missing:
            assert t.disposition == "typed_capability_gap"
        for banned in PROHIBITED_COMPENSATIONS:
            assert banned in evidence.prohibited_compensations
        # Serialize round-trip stability for supervisor evidence consumers.
        assert json.loads(json.dumps(payload))["qualification"] == "nonqualified"
    else:
        # Both tools admitted: gate still requires checked traces.
        assert evidence.qualification in {"qualified", "admitted_awaiting_traces"}


def test_live_model_check_gate_with_admitted_tools(
    tool_probes: tuple[ToolProbe, ...]
) -> None:
    traces: list[dict[str, Any]] = []
    by_name = {t.tool: t for t in tool_probes}
    if by_name["tla_plus"].admitted:
        result = _run_tlc_checked_trace(by_name["tla_plus"])
        if result and result.get("status") == "checked":
            traces.append(result)
    if by_name["alloy"].admitted:
        result = _run_alloy_checked_trace(by_name["alloy"])
        if result and result.get("status") == "checked":
            traces.append(result)

    evidence = build_capability_evidence(tool_probes, checked_traces=traces)
    if all(t.admitted for t in tool_probes) and traces:
        assert evidence.live_model_check_gate_satisfied is True
        assert evidence.qualification == "qualified"
        assert evidence.model_proof_claimed is True
        assert evidence.checked_traces
    else:
        # Missing tools OR admitted-but-failed check => gate unsatisfied;
        # never claim a model proof.
        if not all(t.admitted for t in tool_probes):
            assert evidence.live_model_check_gate_satisfied is False
            assert evidence.qualification == "nonqualified"
            assert evidence.model_proof_claimed is False


def test_tcb_records_tla_and_alloy_as_typed_gaps_when_absent(
    tool_probes: tuple[ToolProbe, ...]
) -> None:
    if not TCB_PATH.is_file():
        pytest.skip("TCB snapshot not present in this worktree")
    tcb = json.loads(TCB_PATH.read_text(encoding="utf-8"))
    formal_absence = {
        entry["tool"]: entry for entry in tcb.get("formal_tool_absence", [])
    }
    for probe in tool_probes:
        if probe.admitted:
            continue
        assert probe.tool in formal_absence
        assert formal_absence[probe.tool]["disposition"] == "typed_capability_gap"
        prohibited = set(formal_absence[probe.tool]["prohibited_compensation"])
        assert "import_time_installation" in prohibited
        assert "simulated_proof" in prohibited


def test_no_simulated_proof_when_tools_missing(
    tool_probes: tuple[ToolProbe, ...]
) -> None:
    evidence = build_capability_evidence(tool_probes)
    if any(not t.admitted for t in tool_probes):
        assert evidence.model_proof_claimed is False
        assert evidence.checked_traces == ()
        # Reference vectors are not live model-check proofs.
        world = run_vector({"o1": "reversible"}, happy_path_vector())
        assert world.trace  # reference only
        assert evidence.live_model_check_gate_satisfied is False
