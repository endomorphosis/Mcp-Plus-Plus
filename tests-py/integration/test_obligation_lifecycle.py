"""
Integration tests for ObligationEvent@1 lifecycle (MCPP-047).

Interface: ObligationEvent@1
Schema: schemas/policy/obligation-event-1.schema.json
Spec: docs/spec/temporal-deontic-policy.md §7–§8

Effects:
  Events obligation_created, obligation_satisfied, obligation_violated,
  compensation_required, compensation_completed, compensation_failed are
  emitted and content-addressed under mcpp-jcs-v1.

Acceptance:
  - Each event type has a positive test.
  - Deadline passage emits violated.
  - Compensation paths are tested.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import pytest

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]
    Draft202012Validator = None  # type: ignore[misc, assignment]

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from validators.canonical_jcs import ALGORITHM_ID, artifact_cid, canonicalize_bytes
except Exception:  # pragma: no cover - offline fallback
    ALGORITHM_ID = "mcpp-jcs-v1"

    def canonicalize_bytes(value: Any) -> bytes:  # type: ignore[misc]
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")

    def artifact_cid(value: Any) -> str:  # type: ignore[misc]
        digest = hashlib.sha256(canonicalize_bytes(value)).digest()
        # Minimal CIDv1-shaped id for offline fallback.
        return "b" + digest.hex()[:58]


# ---------------------------------------------------------------------------
# Paths / interface constants
# ---------------------------------------------------------------------------

_TESTS_ROOT = Path(__file__).resolve().parent.parent
_MCPPLUSPLUS_ROOT = _TESTS_ROOT.parent
_SCHEMA_PATH = (
    _MCPPLUSPLUS_ROOT / "schemas" / "policy" / "obligation-event-1.schema.json"
)

INTERFACE = "ObligationEvent@1"
SCHEMA_MARKER = "mcp++/policy/obligation-event@1"
CANONICAL_ALGORITHM = ALGORITHM_ID
TASK_ID = "MCPP-047"

EVENT_TYPES = (
    "obligation_created",
    "obligation_satisfied",
    "obligation_violated",
    "compensation_required",
    "compensation_completed",
    "compensation_failed",
)

# Status after each event type (normative closed map).
EVENT_STATUS = {
    "obligation_created": "pending",
    "obligation_satisfied": "satisfied",
    "obligation_violated": "violated",
    "compensation_required": "compensating",
    "compensation_completed": "compensated",
    "compensation_failed": "compensation_failed",
}

TERMINAL_STATUSES = frozenset(
    {"satisfied", "compensated", "compensation_failed"}
)

CID_RE = re.compile(
    r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,}|b[a-f0-9]{58,}|sha256:[0-9a-fA-F]{64})$"
)

# Stable fixture CIDs matching schema pattern (CIDv1-shaped base32-ish / hex fallback).
CID_DECISION = "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
CID_INTENT = "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti"
CID_POLICY = "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi"
CID_RECEIPT = "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
# Valid CIDv1 base32 (alphabet a-z2-7 only; no 0/1/8/9).
CID_COMP_EVIDENCE = "bafkreifz2gfqykmymz5wygva7tx2q3x4y5z6a7bcdefghijkmnopqrstuvwx"

_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?"
    r"(?:Z|[+-]\d{2}:\d{2})?)?$"
)


# ---------------------------------------------------------------------------
# Schema load / validation
# ---------------------------------------------------------------------------


def load_schema() -> Dict[str, Any]:
    with _SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _event_body_for_cid(event: Mapping[str, Any]) -> Dict[str, Any]:
    """Body used to mint event_cid (excludes event_cid itself)."""
    body = {k: copy.deepcopy(v) for k, v in event.items() if k != "event_cid"}
    return body


def mint_event_cid(event: Mapping[str, Any]) -> str:
    return artifact_cid(_event_body_for_cid(event))


def attach_event_cid(event: MutableMapping[str, Any]) -> Dict[str, Any]:
    out = dict(event)
    out["event_cid"] = mint_event_cid(out)
    return out


def structural_validate(event: Mapping[str, Any]) -> List[str]:
    """Fail-closed structural checks independent of jsonschema availability."""
    errors: List[str] = []
    if not isinstance(event, Mapping):
        return ["event must be an object"]

    if event.get("schema") != SCHEMA_MARKER:
        errors.append(f"schema must be {SCHEMA_MARKER}")
    if event.get("interface") != INTERFACE:
        errors.append(f"interface must be {INTERFACE}")
    if event.get("canonicalization") != CANONICAL_ALGORITHM:
        errors.append(f"canonicalization must be {CANONICAL_ALGORITHM}")

    etype = event.get("event_type")
    if etype not in EVENT_TYPES:
        errors.append(f"event_type must be one of {EVENT_TYPES}")
    else:
        expected_status = EVENT_STATUS[etype]
        if event.get("status") != expected_status:
            errors.append(
                f"status for {etype} must be {expected_status}, got {event.get('status')!r}"
            )

    for field_name in (
        "obligation_id",
        "decision_cid",
        "logical_time",
        "status",
        "parents",
    ):
        if field_name not in event:
            errors.append(f"missing required field {field_name}")

    oid = event.get("obligation_id")
    if not isinstance(oid, str) or not oid.strip():
        errors.append("obligation_id must be a non-empty string")

    for cid_field in ("decision_cid", "event_cid", "intent_cid", "policy_cid", "receipt_cid"):
        val = event.get(cid_field)
        if val is None or val == "":
            continue
        if not isinstance(val, str) or not CID_RE.match(val):
            errors.append(f"{cid_field} is not a valid CID: {val!r}")

    lt = event.get("logical_time")
    if lt is not None and (not isinstance(lt, str) or not _ISO8601_RE.match(lt)):
        errors.append(f"logical_time is not ISO-8601: {lt!r}")

    deadline = event.get("deadline")
    if deadline not in (None, "") and (
        not isinstance(deadline, str) or not _ISO8601_RE.match(deadline)
    ):
        errors.append(f"deadline is not ISO-8601: {deadline!r}")

    parents = event.get("parents")
    if parents is not None:
        if not isinstance(parents, list):
            errors.append("parents must be an array")
        else:
            seen = set()
            for idx, p in enumerate(parents):
                if not isinstance(p, str) or not CID_RE.match(p):
                    errors.append(f"parents[{idx}] is not a valid CID")
                elif p in seen:
                    errors.append(f"parents[{idx}] is duplicate")
                else:
                    seen.add(p)

    if etype in (
        "compensation_required",
        "compensation_completed",
        "compensation_failed",
    ):
        comp = event.get("compensation")
        if not isinstance(comp, Mapping):
            errors.append(f"{etype} requires a compensation object")
        elif not str(comp.get("action") or "").strip():
            errors.append(f"{etype} compensation.action is required")

    # event_cid integrity when present
    cid = event.get("event_cid")
    if isinstance(cid, str) and cid:
        expected = mint_event_cid(event)
        if cid != expected:
            errors.append(
                f"event_cid mismatch: wire={cid!r} expected={expected!r}"
            )

    return errors


def validate_event(event: Mapping[str, Any]) -> Tuple[bool, List[str]]:
    errors = structural_validate(event)
    if jsonschema is not None and Draft202012Validator is not None:
        try:
            schema = load_schema()
            validator = Draft202012Validator(schema)
            for err in sorted(validator.iter_errors(dict(event)), key=lambda e: list(e.path)):
                path = ".".join(str(p) for p in err.path) or "$"
                errors.append(f"jsonschema[{path}]: {err.message}")
        except Exception as exc:  # pragma: no cover
            errors.append(f"jsonschema_error: {exc}")
    # de-dup while preserving order
    seen: set[str] = set()
    uniq: List[str] = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return (len(uniq) == 0, uniq)


def assert_valid_event(event: Mapping[str, Any]) -> None:
    ok, errors = validate_event(event)
    assert ok, "invalid ObligationEvent@1:\n  " + "\n  ".join(errors)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _parse_iso8601(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_iso8601(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# ObligationLifecycle — emit content-addressed ObligationEvent@1 records
# ---------------------------------------------------------------------------


@dataclass
class _ObligationState:
    obligation_id: str
    decision_cid: str
    intent_cid: Optional[str]
    policy_cid: Optional[str]
    clause_id: Optional[str]
    action: Optional[str]
    deadline: Optional[str]
    trigger: Optional[str]
    compensation: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    sequence: int = 0
    parent_cids: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)


class ObligationLifecycle:
    """Deterministic obligation lifecycle emitter (ObligationEvent@1).

    Logical time is supplied by the caller — never wall-clock. Events are
    content-addressed under mcpp-jcs-v1; ``event_cid`` is excluded from the
    hashed body then attached after minting.
    """

    def __init__(self) -> None:
        self._states: Dict[str, _ObligationState] = {}
        self._journal: List[Dict[str, Any]] = []

    # -- public API --------------------------------------------------------

    @property
    def events(self) -> List[Dict[str, Any]]:
        return list(self._journal)

    def get_state(self, obligation_id: str) -> Optional[Dict[str, Any]]:
        st = self._states.get(obligation_id)
        if st is None:
            return None
        return {
            "obligation_id": st.obligation_id,
            "status": st.status,
            "decision_cid": st.decision_cid,
            "deadline": st.deadline,
            "sequence": st.sequence,
            "parent_cids": list(st.parent_cids),
            "event_count": len(st.events),
            "compensation": copy.deepcopy(st.compensation),
        }

    def create_from_decision(
        self,
        decision: Mapping[str, Any],
        *,
        logical_time: str,
    ) -> List[Dict[str, Any]]:
        """Spawn obligation_created events from a PolicyDecision@1 obligations list."""
        obligations = decision.get("obligations") or []
        if not isinstance(obligations, list):
            raise ValueError("decision.obligations must be a list")
        decision_cid = str(decision.get("decision_cid") or "").strip()
        if not decision_cid:
            raise ValueError("decision.decision_cid is required")
        intent_cid = decision.get("intent_cid") or None
        policy_cid = decision.get("policy_cid") or None

        # Decision-level compensation map keyed by clause_id (from evaluator).
        comp_by_clause: Dict[str, Any] = {}
        for item in decision.get("compensation") or []:
            if isinstance(item, Mapping):
                cid = str(item.get("clause_id") or "")
                if cid:
                    comp_by_clause[cid] = item.get("compensation")

        emitted: List[Dict[str, Any]] = []
        for index, raw in enumerate(obligations):
            if not isinstance(raw, Mapping):
                raise ValueError(f"obligations[{index}] must be an object")
            clause_id = (
                str(raw.get("clause_id") or raw.get("id") or f"obl-{index}")
            )
            obligation_id = str(
                raw.get("obligation_id")
                or f"obl:{decision_cid}:{clause_id}"
            )
            if obligation_id in self._states:
                raise ValueError(f"obligation already exists: {obligation_id}")

            deadline = raw.get("deadline")
            if deadline == "":
                deadline = None
            meta = dict(raw.get("metadata") or {})
            compensation = (
                raw.get("compensation")
                or meta.get("compensation")
                or comp_by_clause.get(clause_id)
            )
            comp_block: Optional[Dict[str, Any]] = None
            if compensation is not None:
                if isinstance(compensation, str):
                    comp_block = {
                        "action": compensation,
                        "on": "obligation_violated",
                        "status": "declared",
                    }
                    if clause_id:
                        comp_block["clause_id"] = clause_id
                elif isinstance(compensation, Mapping):
                    comp_block = {
                        "action": str(
                            compensation.get("action")
                            or compensation.get("type")
                            or "compensate"
                        ),
                        "on": "obligation_violated",
                        "status": "declared",
                    }
                    if clause_id:
                        comp_block["clause_id"] = clause_id
                    if compensation.get("deadline"):
                        comp_block["deadline"] = compensation.get("deadline")
                    if compensation.get("detail") is not None:
                        comp_block["detail"] = compensation.get("detail")
                else:
                    raise ValueError(
                        f"obligations[{index}].compensation must be string or object"
                    )

            st = _ObligationState(
                obligation_id=obligation_id,
                decision_cid=decision_cid,
                intent_cid=str(intent_cid) if intent_cid else None,
                policy_cid=str(policy_cid) if policy_cid else None,
                clause_id=clause_id,
                action=str(raw.get("action") or raw.get("type") or "obligation"),
                deadline=str(deadline) if deadline else None,
                trigger=str(raw.get("trigger") or "") or None,
                compensation=comp_block,
                metadata=meta,
            )
            self._states[obligation_id] = st
            event = self._emit(
                st,
                event_type="obligation_created",
                logical_time=logical_time,
                reason="spawned_from_decision",
                reason_code="created",
                compensation=copy.deepcopy(comp_block) if comp_block else None,
            )
            emitted.append(event)
        return emitted

    def create(
        self,
        *,
        obligation_id: str,
        decision_cid: str,
        logical_time: str,
        action: str = "audit/log",
        clause_id: Optional[str] = None,
        deadline: Optional[str] = None,
        intent_cid: Optional[str] = None,
        policy_cid: Optional[str] = None,
        trigger: Optional[str] = None,
        compensation: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if obligation_id in self._states:
            raise ValueError(f"obligation already exists: {obligation_id}")
        comp_block: Optional[Dict[str, Any]] = None
        if compensation is not None:
            comp_block = {
                "action": str(compensation.get("action") or "compensate"),
                "on": "obligation_violated",
                "status": "declared",
            }
            if clause_id:
                comp_block["clause_id"] = clause_id
            if compensation.get("deadline"):
                comp_block["deadline"] = compensation.get("deadline")
            if compensation.get("detail") is not None:
                comp_block["detail"] = compensation.get("detail")
        st = _ObligationState(
            obligation_id=obligation_id,
            decision_cid=decision_cid,
            intent_cid=intent_cid,
            policy_cid=policy_cid,
            clause_id=clause_id,
            action=action,
            deadline=deadline,
            trigger=trigger,
            compensation=comp_block,
            metadata=dict(metadata or {}),
        )
        self._states[obligation_id] = st
        return self._emit(
            st,
            event_type="obligation_created",
            logical_time=logical_time,
            reason="spawned",
            reason_code="created",
            compensation=copy.deepcopy(comp_block) if comp_block else None,
        )

    def satisfy(
        self,
        obligation_id: str,
        *,
        logical_time: str,
        receipt_cid: Optional[str] = None,
        reason: str = "obligation_discharged",
    ) -> Dict[str, Any]:
        st = self._require(obligation_id)
        if st.status != "pending":
            raise ValueError(
                f"cannot satisfy obligation in status={st.status!r} "
                f"(expected pending)"
            )
        # Deadline must not already have passed at logical_time.
        if st.deadline:
            now = _parse_iso8601(logical_time)
            due = _parse_iso8601(st.deadline)
            if now is not None and due is not None and now > due:
                raise ValueError(
                    "cannot satisfy after deadline; advance_time to violate first"
                )
        return self._emit(
            st,
            event_type="obligation_satisfied",
            logical_time=logical_time,
            reason=reason,
            reason_code="satisfied",
            receipt_cid=receipt_cid,
        )

    def advance_time(self, logical_time: str) -> List[Dict[str, Any]]:
        """Advance logical clock; any pending obligation past its deadline is violated.

        When the obligation declares compensation, also emits compensation_required.
        """
        now = _parse_iso8601(logical_time)
        if now is None:
            raise ValueError("logical_time is required for advance_time")

        emitted: List[Dict[str, Any]] = []
        # Stable order by obligation_id for determinism.
        for obligation_id in sorted(self._states.keys()):
            st = self._states[obligation_id]
            if st.status != "pending" or not st.deadline:
                continue
            due = _parse_iso8601(st.deadline)
            if due is None:
                continue
            if now <= due:
                continue
            violated = self._emit(
                st,
                event_type="obligation_violated",
                logical_time=logical_time,
                reason="deadline_passed",
                reason_code="deadline_passed",
            )
            emitted.append(violated)
            if st.compensation is not None:
                comp = copy.deepcopy(st.compensation)
                comp["status"] = "required"
                comp["on"] = "obligation_violated"
                required = self._emit(
                    st,
                    event_type="compensation_required",
                    logical_time=logical_time,
                    reason="compensation_after_violation",
                    reason_code="compensation_required",
                    compensation=comp,
                )
                emitted.append(required)
        return emitted

    def complete_compensation(
        self,
        obligation_id: str,
        *,
        logical_time: str,
        evidence_cid: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        st = self._require(obligation_id)
        if st.status != "compensating":
            raise ValueError(
                f"cannot complete compensation in status={st.status!r} "
                f"(expected compensating)"
            )
        if st.compensation is None:
            raise ValueError("no compensation declared for obligation")
        comp = copy.deepcopy(st.compensation)
        comp["status"] = "completed"
        if evidence_cid:
            comp["evidence_cid"] = evidence_cid
        if detail is not None:
            comp["detail"] = detail
        return self._emit(
            st,
            event_type="compensation_completed",
            logical_time=logical_time,
            reason="compensation_succeeded",
            reason_code="compensation_completed",
            compensation=comp,
            receipt_cid=evidence_cid,
        )

    def fail_compensation(
        self,
        obligation_id: str,
        *,
        logical_time: str,
        detail: Optional[str] = None,
        reason: str = "compensating_action_failed",
    ) -> Dict[str, Any]:
        st = self._require(obligation_id)
        if st.status != "compensating":
            raise ValueError(
                f"cannot fail compensation in status={st.status!r} "
                f"(expected compensating)"
            )
        if st.compensation is None:
            raise ValueError("no compensation declared for obligation")
        comp = copy.deepcopy(st.compensation)
        comp["status"] = "failed"
        if detail is not None:
            comp["detail"] = detail
        return self._emit(
            st,
            event_type="compensation_failed",
            logical_time=logical_time,
            reason=reason,
            reason_code="compensation_failed",
            compensation=comp,
        )

    def events_of_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self._journal if e.get("event_type") == event_type]

    def events_for(self, obligation_id: str) -> List[Dict[str, Any]]:
        st = self._states.get(obligation_id)
        if st is None:
            return []
        return list(st.events)

    # -- internals ---------------------------------------------------------

    def _require(self, obligation_id: str) -> _ObligationState:
        st = self._states.get(obligation_id)
        if st is None:
            raise KeyError(f"unknown obligation_id: {obligation_id}")
        return st

    def _emit(
        self,
        st: _ObligationState,
        *,
        event_type: str,
        logical_time: str,
        reason: Optional[str] = None,
        reason_code: Optional[str] = None,
        compensation: Optional[Mapping[str, Any]] = None,
        receipt_cid: Optional[str] = None,
    ) -> Dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type: {event_type}")
        status = EVENT_STATUS[event_type]
        event: Dict[str, Any] = {
            "schema": SCHEMA_MARKER,
            "interface": INTERFACE,
            "event_type": event_type,
            "obligation_id": st.obligation_id,
            "decision_cid": st.decision_cid,
            "logical_time": logical_time,
            "status": status,
            "parents": list(st.parent_cids),
            "canonicalization": CANONICAL_ALGORITHM,
            "sequence": st.sequence,
        }
        if st.intent_cid:
            event["intent_cid"] = st.intent_cid
        if st.policy_cid:
            event["policy_cid"] = st.policy_cid
        if st.clause_id:
            event["clause_id"] = st.clause_id
        if st.action:
            event["action"] = st.action
        if st.deadline:
            event["deadline"] = st.deadline
        if st.trigger:
            event["trigger"] = st.trigger
        if reason is not None:
            event["reason"] = reason
        if reason_code is not None:
            event["reason_code"] = reason_code
        if compensation is not None:
            event["compensation"] = dict(compensation)
            st.compensation = dict(compensation)
        if receipt_cid is not None:
            event["receipt_cid"] = receipt_cid
        if st.metadata:
            event["metadata"] = copy.deepcopy(st.metadata)

        minted = attach_event_cid(event)
        assert_valid_event(minted)

        st.status = status
        st.sequence += 1
        st.parent_cids = [minted["event_cid"]]
        st.events.append(minted)
        self._journal.append(minted)
        return minted


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def sample_decision_with_obligation(
    *,
    with_compensation: bool = False,
    deadline: str = "2026-01-01T13:00:00Z",
    clause_id: str = "audit-1",
    action: str = "audit/log",
) -> Dict[str, Any]:
    """Minimal PolicyDecision@1-shaped object with one obligation."""
    obligation: Dict[str, Any] = {
        "type": "obligation",
        "clause_id": clause_id,
        "action": action,
        "deadline": deadline,
        "trigger": "after_execution",
        "status": "pending",
        "metadata": {},
    }
    compensation_list: List[Dict[str, Any]] = []
    if with_compensation:
        obligation["metadata"] = {
            "compensation": {
                "action": "secrets/rotate",
                "deadline": "2026-01-01T14:00:00Z",
            }
        }
        compensation_list.append(
            {
                "clause_id": clause_id,
                "compensation": {
                    "action": "secrets/rotate",
                    "deadline": "2026-01-01T14:00:00Z",
                },
                "on": "obligation_violated",
            }
        )
    return {
        "schema": "mcp++/profile-d-policy-decision@1",
        "interface": "PolicyDecision@1",
        "decision": "allow_with_obligations",
        "granted": True,
        "allowed": True,
        "decision_cid": CID_DECISION,
        "intent_cid": CID_INTENT,
        "policy_cid": CID_POLICY,
        "evaluated_at": "2026-01-01T12:00:00Z",
        "justification": "Permitted with 1 obligation(s)",
        "obligations": [obligation],
        "compensation": compensation_list,
        "fired_rules": [],
        "facts": [],
        "deadlines": (
            [{"clause_id": clause_id, "deadline": deadline, "status": "pending"}]
            if deadline
            else []
        ),
    }


@pytest.fixture
def lifecycle() -> ObligationLifecycle:
    return ObligationLifecycle()


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------


class TestObligationEventSchemaContract:
    def test_schema_file_exists_and_loads(self):
        assert _SCHEMA_PATH.is_file(), f"missing schema at {_SCHEMA_PATH}"
        schema = load_schema()
        assert schema["$id"].endswith("obligation-event-1.schema.json")
        assert schema["title"] == "MCP++ ObligationEvent@1"
        assert "ObligationEvent@1" in schema["description"] or schema.get(
            "$comment", ""
        )

    def test_schema_documents_six_event_types(self):
        schema = load_schema()
        enum = schema["$defs"]["eventType"]["enum"]
        assert set(enum) == set(EVENT_TYPES)
        assert list(enum) == list(EVENT_TYPES)

    def test_schema_marker_and_interface_consts(self):
        schema = load_schema()
        assert schema["properties"]["schema"]["const"] == SCHEMA_MARKER
        assert schema["properties"]["interface"]["const"] == INTERFACE
        assert schema["properties"]["canonicalization"]["const"] == CANONICAL_ALGORITHM

    def test_schema_required_fields(self):
        schema = load_schema()
        required = set(schema["required"])
        for name in (
            "schema",
            "interface",
            "event_type",
            "obligation_id",
            "decision_cid",
            "logical_time",
            "status",
            "parents",
            "canonicalization",
        ):
            assert name in required, name

    def test_interface_constants(self):
        assert INTERFACE == "ObligationEvent@1"
        assert SCHEMA_MARKER == "mcp++/policy/obligation-event@1"
        assert TASK_ID == "MCPP-047"


# ---------------------------------------------------------------------------
# Positive tests — one per event type
# ---------------------------------------------------------------------------


class TestEachEventTypePositive:
    """Acceptance: each event type has a positive test."""

    def test_obligation_created_positive(self, lifecycle: ObligationLifecycle):
        event = lifecycle.create(
            obligation_id="obl:created-1",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            action="audit/log",
            clause_id="c-created",
            deadline="2026-01-01T13:00:00Z",
            intent_cid=CID_INTENT,
            policy_cid=CID_POLICY,
        )
        assert event["event_type"] == "obligation_created"
        assert event["status"] == "pending"
        assert event["event_cid"]
        assert CID_RE.match(event["event_cid"])
        assert event["parents"] == []
        assert_valid_event(event)
        assert lifecycle.get_state("obl:created-1")["status"] == "pending"

    def test_obligation_satisfied_positive(self, lifecycle: ObligationLifecycle):
        lifecycle.create(
            obligation_id="obl:sat-1",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            action="audit/log",
        )
        event = lifecycle.satisfy(
            "obl:sat-1",
            logical_time="2026-01-01T12:30:00Z",
            receipt_cid=CID_RECEIPT,
        )
        assert event["event_type"] == "obligation_satisfied"
        assert event["status"] == "satisfied"
        assert event["receipt_cid"] == CID_RECEIPT
        assert len(event["parents"]) == 1
        assert_valid_event(event)
        assert lifecycle.get_state("obl:sat-1")["status"] == "satisfied"

    def test_obligation_violated_positive(self, lifecycle: ObligationLifecycle):
        lifecycle.create(
            obligation_id="obl:viol-1",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            action="audit/log",
        )
        events = lifecycle.advance_time("2026-01-01T13:00:01Z")
        violated = [e for e in events if e["event_type"] == "obligation_violated"]
        assert len(violated) == 1
        event = violated[0]
        assert event["status"] == "violated"
        assert event["reason_code"] == "deadline_passed"
        assert event["obligation_id"] == "obl:viol-1"
        assert_valid_event(event)

    def test_compensation_required_positive(self, lifecycle: ObligationLifecycle):
        lifecycle.create(
            obligation_id="obl:comp-req-1",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            action="audit/log",
            compensation={
                "action": "secrets/rotate",
                "deadline": "2026-01-01T14:00:00Z",
            },
        )
        events = lifecycle.advance_time("2026-01-01T13:00:01Z")
        required = [e for e in events if e["event_type"] == "compensation_required"]
        assert len(required) == 1
        event = required[0]
        assert event["status"] == "compensating"
        assert event["compensation"]["action"] == "secrets/rotate"
        assert event["compensation"]["status"] == "required"
        assert event["compensation"]["on"] == "obligation_violated"
        assert_valid_event(event)

    def test_compensation_completed_positive(self, lifecycle: ObligationLifecycle):
        lifecycle.create(
            obligation_id="obl:comp-ok-1",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            compensation={"action": "notify/security"},
        )
        lifecycle.advance_time("2026-01-01T13:00:01Z")
        event = lifecycle.complete_compensation(
            "obl:comp-ok-1",
            logical_time="2026-01-01T13:15:00Z",
            evidence_cid=CID_COMP_EVIDENCE,
            detail="rotated and notified",
        )
        assert event["event_type"] == "compensation_completed"
        assert event["status"] == "compensated"
        assert event["compensation"]["status"] == "completed"
        assert event["compensation"]["evidence_cid"] == CID_COMP_EVIDENCE
        assert_valid_event(event)
        assert lifecycle.get_state("obl:comp-ok-1")["status"] == "compensated"

    def test_compensation_failed_positive(self, lifecycle: ObligationLifecycle):
        lifecycle.create(
            obligation_id="obl:comp-fail-1",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            compensation={"action": "notify/security"},
        )
        lifecycle.advance_time("2026-01-01T13:00:01Z")
        event = lifecycle.fail_compensation(
            "obl:comp-fail-1",
            logical_time="2026-01-01T13:20:00Z",
            detail="notify endpoint unavailable",
        )
        assert event["event_type"] == "compensation_failed"
        assert event["status"] == "compensation_failed"
        assert event["compensation"]["status"] == "failed"
        assert event["reason_code"] == "compensation_failed"
        assert_valid_event(event)
        assert lifecycle.get_state("obl:comp-fail-1")["status"] == "compensation_failed"


# ---------------------------------------------------------------------------
# Deadline passage → violated
# ---------------------------------------------------------------------------


class TestDeadlinePassageEmitsViolated:
    """Acceptance: deadline passage emits violated."""

    def test_deadline_passage_emits_violated(self, lifecycle: ObligationLifecycle):
        created = lifecycle.create(
            obligation_id="obl:deadline-1",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            action="produce/receipt",
        )
        assert created["status"] == "pending"

        # Before / at deadline: no violation.
        assert lifecycle.advance_time("2026-01-01T12:59:59Z") == []
        assert lifecycle.advance_time("2026-01-01T13:00:00Z") == []
        assert lifecycle.get_state("obl:deadline-1")["status"] == "pending"

        # Past deadline: obligation_violated.
        events = lifecycle.advance_time("2026-01-01T13:00:01Z")
        assert len(events) == 1
        assert events[0]["event_type"] == "obligation_violated"
        assert events[0]["reason_code"] == "deadline_passed"
        assert events[0]["deadline"] == "2026-01-01T13:00:00Z"
        assert events[0]["logical_time"] == "2026-01-01T13:00:01Z"
        assert_valid_event(events[0])

    def test_satisfied_before_deadline_is_not_violated(
        self, lifecycle: ObligationLifecycle
    ):
        lifecycle.create(
            obligation_id="obl:deadline-sat",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
        )
        lifecycle.satisfy(
            "obl:deadline-sat",
            logical_time="2026-01-01T12:45:00Z",
            receipt_cid=CID_RECEIPT,
        )
        events = lifecycle.advance_time("2026-01-01T14:00:00Z")
        assert events == []
        assert lifecycle.get_state("obl:deadline-sat")["status"] == "satisfied"
        assert lifecycle.events_of_type("obligation_violated") == []

    def test_no_deadline_is_never_auto_violated(self, lifecycle: ObligationLifecycle):
        lifecycle.create(
            obligation_id="obl:no-deadline",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline=None,
        )
        assert lifecycle.advance_time("2099-01-01T00:00:00Z") == []
        assert lifecycle.get_state("obl:no-deadline")["status"] == "pending"

    def test_multiple_obligations_deadline_scan_is_deterministic(
        self, lifecycle: ObligationLifecycle
    ):
        for i, clause in enumerate(("z-last", "a-first", "m-mid")):
            lifecycle.create(
                obligation_id=f"obl:multi-{clause}",
                decision_cid=CID_DECISION,
                logical_time="2026-01-01T12:00:00Z",
                deadline="2026-01-01T13:00:00Z",
                clause_id=clause,
            )
        events = lifecycle.advance_time("2026-01-01T13:00:01Z")
        violated_ids = [
            e["obligation_id"]
            for e in events
            if e["event_type"] == "obligation_violated"
        ]
        assert violated_ids == sorted(violated_ids)
        assert len(violated_ids) == 3


# ---------------------------------------------------------------------------
# Compensation paths
# ---------------------------------------------------------------------------


class TestCompensationPaths:
    """Acceptance: compensation paths are tested."""

    def test_full_compensation_success_path(self, lifecycle: ObligationLifecycle):
        decision = sample_decision_with_obligation(with_compensation=True)
        created = lifecycle.create_from_decision(
            decision, logical_time="2026-01-01T12:00:00Z"
        )
        assert len(created) == 1
        assert created[0]["event_type"] == "obligation_created"
        oid = created[0]["obligation_id"]

        advanced = lifecycle.advance_time("2026-01-01T13:00:01Z")
        types = [e["event_type"] for e in advanced]
        assert types == ["obligation_violated", "compensation_required"]

        completed = lifecycle.complete_compensation(
            oid,
            logical_time="2026-01-01T13:30:00Z",
            evidence_cid=CID_COMP_EVIDENCE,
        )
        assert completed["event_type"] == "compensation_completed"
        assert completed["status"] == "compensated"

        chain = [e["event_type"] for e in lifecycle.events_for(oid)]
        assert chain == [
            "obligation_created",
            "obligation_violated",
            "compensation_required",
            "compensation_completed",
        ]
        for event in lifecycle.events_for(oid):
            assert_valid_event(event)

    def test_full_compensation_failure_path(self, lifecycle: ObligationLifecycle):
        decision = sample_decision_with_obligation(with_compensation=True)
        created = lifecycle.create_from_decision(
            decision, logical_time="2026-01-01T12:00:00Z"
        )
        oid = created[0]["obligation_id"]
        lifecycle.advance_time("2026-01-01T13:00:01Z")
        failed = lifecycle.fail_compensation(
            oid,
            logical_time="2026-01-01T13:45:00Z",
            detail="rotation API denied",
        )
        assert failed["event_type"] == "compensation_failed"
        assert failed["status"] == "compensation_failed"
        assert failed["compensation"]["detail"] == "rotation API denied"

        chain = [e["event_type"] for e in lifecycle.events_for(oid)]
        assert chain == [
            "obligation_created",
            "obligation_violated",
            "compensation_required",
            "compensation_failed",
        ]
        for event in lifecycle.events_for(oid):
            assert_valid_event(event)

    def test_violation_without_compensation_does_not_require_compensation(
        self, lifecycle: ObligationLifecycle
    ):
        lifecycle.create(
            obligation_id="obl:no-comp",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            compensation=None,
        )
        events = lifecycle.advance_time("2026-01-01T14:00:00Z")
        assert [e["event_type"] for e in events] == ["obligation_violated"]
        assert lifecycle.events_of_type("compensation_required") == []

    def test_cannot_complete_compensation_before_required(
        self, lifecycle: ObligationLifecycle
    ):
        lifecycle.create(
            obligation_id="obl:premature",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            compensation={"action": "secrets/rotate"},
        )
        with pytest.raises(ValueError, match="compensating"):
            lifecycle.complete_compensation(
                "obl:premature", logical_time="2026-01-01T12:30:00Z"
            )

    def test_cannot_satisfy_after_violation(self, lifecycle: ObligationLifecycle):
        lifecycle.create(
            obligation_id="obl:post-viol",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
        )
        lifecycle.advance_time("2026-01-01T13:00:01Z")
        with pytest.raises(ValueError, match="pending"):
            lifecycle.satisfy("obl:post-viol", logical_time="2026-01-01T13:05:00Z")


# ---------------------------------------------------------------------------
# Content addressing
# ---------------------------------------------------------------------------


class TestContentAddressing:
    def test_events_are_content_addressed_deterministically(
        self, lifecycle: ObligationLifecycle
    ):
        a = lifecycle.create(
            obligation_id="obl:cid-a",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            action="audit/log",
            clause_id="cid-clause",
            deadline="2026-01-01T13:00:00Z",
        )
        # Independent lifecycle with identical inputs yields identical event_cid.
        other = ObligationLifecycle()
        b = other.create(
            obligation_id="obl:cid-a",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            action="audit/log",
            clause_id="cid-clause",
            deadline="2026-01-01T13:00:00Z",
        )
        assert a["event_cid"] == b["event_cid"]
        assert a["event_cid"] == mint_event_cid(a)

    def test_event_cid_excludes_self_and_covers_body(self):
        body = {
            "schema": SCHEMA_MARKER,
            "interface": INTERFACE,
            "event_type": "obligation_created",
            "obligation_id": "obl:body",
            "decision_cid": CID_DECISION,
            "logical_time": "2026-01-01T12:00:00Z",
            "status": "pending",
            "parents": [],
            "canonicalization": CANONICAL_ALGORITHM,
            "sequence": 0,
            "action": "audit/log",
        }
        cid1 = mint_event_cid(body)
        with_cid = attach_event_cid(body)
        # Re-minting with event_cid present still hashes the body without it.
        cid2 = mint_event_cid(with_cid)
        assert cid1 == cid2 == with_cid["event_cid"]

        # Tampering any body field changes the CID.
        tampered = dict(with_cid)
        tampered["action"] = "audit/tampered"
        assert mint_event_cid(tampered) != with_cid["event_cid"]

    def test_parent_chain_links_events(self, lifecycle: ObligationLifecycle):
        created = lifecycle.create(
            obligation_id="obl:chain",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            compensation={"action": "notify"},
        )
        advanced = lifecycle.advance_time("2026-01-01T13:00:01Z")
        completed = lifecycle.complete_compensation(
            "obl:chain",
            logical_time="2026-01-01T13:10:00Z",
            evidence_cid=CID_COMP_EVIDENCE,
        )
        violated = advanced[0]
        required = advanced[1]
        assert violated["parents"] == [created["event_cid"]]
        assert required["parents"] == [violated["event_cid"]]
        assert completed["parents"] == [required["event_cid"]]


# ---------------------------------------------------------------------------
# Decision integration + negative schema cases
# ---------------------------------------------------------------------------


class TestDecisionIntegration:
    def test_create_from_policy_decision_obligations(
        self, lifecycle: ObligationLifecycle
    ):
        decision = sample_decision_with_obligation(with_compensation=False)
        events = lifecycle.create_from_decision(
            decision, logical_time="2026-01-01T12:00:00Z"
        )
        assert len(events) == 1
        event = events[0]
        assert event["decision_cid"] == CID_DECISION
        assert event["intent_cid"] == CID_INTENT
        assert event["policy_cid"] == CID_POLICY
        assert event["clause_id"] == "audit-1"
        assert event["action"] == "audit/log"
        assert event["deadline"] == "2026-01-01T13:00:00Z"
        assert_valid_event(event)

    def test_incomplete_until_satisfied_or_compensated(
        self, lifecycle: ObligationLifecycle
    ):
        """An allow decision with obligations is incomplete until terminal status."""
        decision = sample_decision_with_obligation(with_compensation=True)
        created = lifecycle.create_from_decision(
            decision, logical_time="2026-01-01T12:00:00Z"
        )
        oid = created[0]["obligation_id"]
        state = lifecycle.get_state(oid)
        assert state["status"] == "pending"
        assert state["status"] not in TERMINAL_STATUSES

        lifecycle.advance_time("2026-01-01T13:00:01Z")
        assert lifecycle.get_state(oid)["status"] == "compensating"
        assert lifecycle.get_state(oid)["status"] not in TERMINAL_STATUSES

        lifecycle.complete_compensation(
            oid, logical_time="2026-01-01T13:20:00Z", evidence_cid=CID_COMP_EVIDENCE
        )
        assert lifecycle.get_state(oid)["status"] in TERMINAL_STATUSES


class TestSchemaNegatives:
    def test_unknown_event_type_rejected(self):
        event = attach_event_cid(
            {
                "schema": SCHEMA_MARKER,
                "interface": INTERFACE,
                "event_type": "obligation_skipped",
                "obligation_id": "obl:bad",
                "decision_cid": CID_DECISION,
                "logical_time": "2026-01-01T12:00:00Z",
                "status": "pending",
                "parents": [],
                "canonicalization": CANONICAL_ALGORITHM,
            }
        )
        ok, errors = validate_event(event)
        assert not ok
        assert any("event_type" in e for e in errors)

    def test_status_mismatch_rejected(self):
        event = attach_event_cid(
            {
                "schema": SCHEMA_MARKER,
                "interface": INTERFACE,
                "event_type": "obligation_created",
                "obligation_id": "obl:bad-status",
                "decision_cid": CID_DECISION,
                "logical_time": "2026-01-01T12:00:00Z",
                "status": "satisfied",  # must be pending
                "parents": [],
                "canonicalization": CANONICAL_ALGORITHM,
            }
        )
        ok, errors = validate_event(event)
        assert not ok
        assert any("status" in e for e in errors)

    def test_compensation_required_without_compensation_block_rejected(self):
        event = attach_event_cid(
            {
                "schema": SCHEMA_MARKER,
                "interface": INTERFACE,
                "event_type": "compensation_required",
                "obligation_id": "obl:bad-comp",
                "decision_cid": CID_DECISION,
                "logical_time": "2026-01-01T13:00:01Z",
                "status": "compensating",
                "parents": [CID_RECEIPT],
                "canonicalization": CANONICAL_ALGORITHM,
            }
        )
        ok, errors = validate_event(event)
        assert not ok
        assert any("compensation" in e for e in errors)

    def test_tampered_event_cid_rejected(self):
        event = attach_event_cid(
            {
                "schema": SCHEMA_MARKER,
                "interface": INTERFACE,
                "event_type": "obligation_created",
                "obligation_id": "obl:tamper",
                "decision_cid": CID_DECISION,
                "logical_time": "2026-01-01T12:00:00Z",
                "status": "pending",
                "parents": [],
                "canonicalization": CANONICAL_ALGORITHM,
                "sequence": 0,
            }
        )
        event["event_cid"] = CID_RECEIPT  # wrong CID
        ok, errors = validate_event(event)
        assert not ok
        assert any("event_cid" in e for e in errors)


class TestAllEventTypesEmittedCoverage:
    """Meta-coverage: journal contains every normative event type once exercised."""

    def test_suite_emits_all_six_event_types(self):
        lc = ObligationLifecycle()
        # Path A: create → satisfy
        lc.create(
            obligation_id="obl:cov-sat",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
        )
        lc.satisfy(
            "obl:cov-sat",
            logical_time="2026-01-01T12:30:00Z",
            receipt_cid=CID_RECEIPT,
        )
        # Path B: create → violate → compensation_required → completed
        lc.create(
            obligation_id="obl:cov-comp-ok",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T13:00:00Z",
            compensation={"action": "secrets/rotate"},
        )
        lc.advance_time("2026-01-01T13:00:01Z")
        lc.complete_compensation(
            "obl:cov-comp-ok",
            logical_time="2026-01-01T13:10:00Z",
            evidence_cid=CID_COMP_EVIDENCE,
        )
        # Path C: create → violate → compensation_required → failed
        lc.create(
            obligation_id="obl:cov-comp-fail",
            decision_cid=CID_DECISION,
            logical_time="2026-01-01T12:00:00Z",
            deadline="2026-01-01T15:00:00Z",
            compensation={"action": "notify/security"},
        )
        lc.advance_time("2026-01-01T15:00:01Z")
        lc.fail_compensation(
            "obl:cov-comp-fail", logical_time="2026-01-01T15:10:00Z"
        )

        seen = {e["event_type"] for e in lc.events}
        assert seen == set(EVENT_TYPES)
        for etype in EVENT_TYPES:
            samples = lc.events_of_type(etype)
            assert samples, f"missing positive emission for {etype}"
            assert_valid_event(samples[0])
