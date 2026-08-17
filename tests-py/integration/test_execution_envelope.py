"""MCPP-033: four-language ExecutionEnvelope@1 family validators and vectors.

Interface: ExecutionEnvelopeValidator@1
Track: envelope-validators

Four languages (py/ts/go/rs) accept the same positive fixtures and reject the
same negatives for:

  - ExecutionEnvelope@1
  - ExecutionResult@1
  - ExecutionReceipt@1
  - PortableError@1

Python side uses the shared structural validators from envelope_profile_b
(also used by Profile B/G adapters). Case ids and accept/reject expectations
are mirrored in:

  - tests-ts/src/__tests__/execution-envelope.test.ts
  - tests-go/execution_envelope_test.go
  - tests-rs/tests/execution_envelope_test.rs
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validators.envelope_profile_b import (  # noqa: E402
    SCHEMA_ENVELOPE,
    SCHEMA_ERROR,
    SCHEMA_RECEIPT,
    SCHEMA_RESULT,
    validate_envelope_v1,
    validate_portable_error_v1,
    validate_receipt_v1,
    validate_result_v1,
)

# ---------------------------------------------------------------------------
# Interface / markers (ExecutionEnvelopeValidator@1)
# ---------------------------------------------------------------------------

INTERFACE = "ExecutionEnvelopeValidator@1"
TASK_ID = "MCPP-033"

SCHEMA_MARKERS = {
    "envelope": SCHEMA_ENVELOPE,
    "result": SCHEMA_RESULT,
    "receipt": SCHEMA_RECEIPT,
    "error": SCHEMA_ERROR,
}

# Stable CIDs used across all four language suites (must match CID pattern).
CID_A = "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
CID_B = "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti"
CID_C = "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi"
CID_D = "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"

DID_REQUESTER = "did:key:z6MkrequesterExample0001"
DID_EXECUTOR = "did:key:z6MkexecutorExample00001"


# ---------------------------------------------------------------------------
# Shared base fixtures (recipe bases; negatives are mutations)
# ---------------------------------------------------------------------------


def base_envelope() -> Dict[str, Any]:
    return {
        "schema": SCHEMA_ENVELOPE,
        "interface_cid": CID_A,
        "method": "repo.status",
        "input_cid": CID_B,
        "intent_cid": CID_C,
        "policy_cid": CID_D,
        "parents": [],
        "created_at_ms": 1783872000000,
        "correlation_id": "task-001",
        "requester": {"did": DID_REQUESTER},
        "authority": {
            "proof_cids": [CID_D],
            "proof_cid": CID_D,
        },
        "constraints": {"timeout_ms": 30000, "max_retries": 3},
        "state_refs": [],
        "canonicalization": "mcpp-jcs-v1",
    }


def base_portable_error() -> Dict[str, Any]:
    return {
        "schema": SCHEMA_ERROR,
        "code": "E_POLICY_DENIED",
        "message": "policy denied execution",
        "retryable": False,
        "failure_class": "policy",
    }


def base_result_succeeded() -> Dict[str, Any]:
    return {
        "schema": SCHEMA_RESULT,
        "envelope_cid": CID_A,
        "status": "succeeded",
        "output_cids": [CID_B],
        "state_transitions": [],
        "side_effects": [],
        "decision_cid": CID_D,
        "delegation_cid": CID_C,
        "executor": {"did": DID_EXECUTOR},
        "retry": {"attempt": 1},
        "duration_ms": 12.5,
        "error": None,
        "proofs": [CID_D],
        "started_at_ms": 1783872001100,
        "finished_at_ms": 1783872001113,
        "canonicalization": "mcpp-jcs-v1",
    }


def base_result_failed() -> Dict[str, Any]:
    obj = base_result_succeeded()
    obj["status"] = "failed"
    obj["output_cids"] = []
    obj["error"] = base_portable_error()
    return obj


def base_receipt_succeeded() -> Dict[str, Any]:
    return {
        "schema": SCHEMA_RECEIPT,
        "envelope_cid": CID_A,
        "result_cid": CID_B,
        "status": "succeeded",
        "output_cids": [CID_C],
        "state_transitions": [],
        "side_effects": [],
        "decision_cid": CID_D,
        "delegation_cid": CID_C,
        "executor": {
            "did": DID_EXECUTOR,
            "runtime": "ipfs_accelerate_py",
            "runtime_version": "3.2.0",
        },
        "retry": {"attempt": 1},
        "duration_ms": 12.5,
        "error": None,
        "proofs": [CID_D],
        "signature": None,
        "signature_alg": None,
        "event_cid": CID_A,
        "started_at_ms": 1783872001100,
        "finished_at_ms": 1783872001113,
        "canonicalization": "mcpp-jcs-v1",
    }


def base_receipt_failed() -> Dict[str, Any]:
    obj = base_receipt_succeeded()
    obj["status"] = "failed"
    obj["output_cids"] = []
    obj["error"] = base_portable_error()
    return obj


# ---------------------------------------------------------------------------
# Shared vector catalog (ids MUST match ts/go/rs suites)
# ---------------------------------------------------------------------------

# (case_id, kind, builder, expect_valid)
VectorCase = Tuple[str, str, Callable[[], Dict[str, Any]], bool]


def _mutate(base: Callable[[], Dict[str, Any]], **patches: Any) -> Callable[[], Dict[str, Any]]:
    def build() -> Dict[str, Any]:
        obj = base()
        for key, value in patches.items():
            if value is _DELETE:
                obj.pop(key, None)
            else:
                obj[key] = value
        return obj

    return build


class _Delete:
    pass


_DELETE = _Delete()


def _deep_set(base: Callable[[], Dict[str, Any]], path: str, value: Any) -> Callable[[], Dict[str, Any]]:
    def build() -> Dict[str, Any]:
        obj = base()
        cur: Any = obj
        parts = path.split(".")
        for p in parts[:-1]:
            cur = cur[p]
        if value is _DELETE:
            if isinstance(cur, dict):
                cur.pop(parts[-1], None)
        else:
            cur[parts[-1]] = value
        return obj

    return build


def vector_catalog() -> List[VectorCase]:
    """Canonical positive + negative cases shared across languages."""
    return [
        # ---- positives ----
        ("pos-envelope-minimal", "envelope", base_envelope, True),
        (
            "pos-envelope-with-parents",
            "envelope",
            _mutate(base_envelope, parents=[CID_A, CID_B]),
            True,
        ),
        ("pos-result-succeeded", "result", base_result_succeeded, True),
        ("pos-result-failed-with-error", "result", base_result_failed, True),
        ("pos-receipt-succeeded", "receipt", base_receipt_succeeded, True),
        ("pos-receipt-failed", "receipt", base_receipt_failed, True),
        ("pos-portable-error", "error", base_portable_error, True),
        # ---- envelope negatives ----
        (
            "neg-envelope-wrong-schema",
            "envelope",
            _mutate(base_envelope, schema="mcp++/execution/envelope@0"),
            False,
        ),
        (
            "neg-envelope-missing-interface-cid",
            "envelope",
            _mutate(base_envelope, interface_cid=_DELETE),
            False,
        ),
        (
            "neg-envelope-invalid-cid",
            "envelope",
            _mutate(base_envelope, interface_cid="not-a-cid"),
            False,
        ),
        (
            "neg-envelope-invalid-did",
            "envelope",
            _mutate(base_envelope, requester={"did": "not-a-did"}),
            False,
        ),
        (
            "neg-envelope-invalid-proof-cid",
            "envelope",
            _mutate(base_envelope, authority={"proof_cids": ["bad-cid"]}),
            False,
        ),
        (
            "neg-envelope-bad-canonicalization",
            "envelope",
            _mutate(base_envelope, canonicalization="jcs-v0"),
            False,
        ),
        (
            "neg-envelope-negative-timestamp",
            "envelope",
            _mutate(base_envelope, created_at_ms=-1),
            False,
        ),
        (
            "neg-envelope-empty-correlation",
            "envelope",
            _mutate(base_envelope, correlation_id=""),
            False,
        ),
        (
            "neg-envelope-bad-parent",
            "envelope",
            _mutate(base_envelope, parents=["not-a-cid"]),
            False,
        ),
        (
            "neg-envelope-missing-proof-cids",
            "envelope",
            _deep_set(base_envelope, "authority.proof_cids", _DELETE),
            False,
        ),
        # ---- portable-error negatives ----
        (
            "neg-error-wrong-schema",
            "error",
            _mutate(base_portable_error, schema="mcp++/execution/portable-error@0"),
            False,
        ),
        (
            "neg-error-missing-code",
            "error",
            _mutate(base_portable_error, code=_DELETE),
            False,
        ),
        (
            "neg-error-bad-failure-class",
            "error",
            _mutate(base_portable_error, failure_class="bogus"),
            False,
        ),
        (
            "neg-error-nonbool-retryable",
            "error",
            _mutate(base_portable_error, retryable="yes"),
            False,
        ),
        # ---- result negatives ----
        (
            "neg-result-wrong-schema",
            "result",
            _mutate(base_result_succeeded, schema="mcp++/execution/result@0"),
            False,
        ),
        (
            "neg-result-missing-status",
            "result",
            _mutate(base_result_succeeded, status=_DELETE),
            False,
        ),
        (
            "neg-result-bad-status",
            "result",
            _mutate(base_result_succeeded, status="running"),
            False,
        ),
        (
            "neg-result-succeeded-with-error",
            "result",
            _mutate(base_result_succeeded, error=base_portable_error()),
            False,
        ),
        (
            "neg-result-invalid-envelope-cid",
            "result",
            _mutate(base_result_succeeded, envelope_cid="not-a-cid"),
            False,
        ),
        # ---- receipt negatives ----
        (
            "neg-receipt-wrong-schema",
            "receipt",
            _mutate(base_receipt_succeeded, schema="mcp++/execution/receipt@0"),
            False,
        ),
        (
            "neg-receipt-missing-result-cid",
            "receipt",
            _mutate(base_receipt_succeeded, result_cid=_DELETE),
            False,
        ),
        (
            "neg-receipt-invalid-cid",
            "receipt",
            _mutate(base_receipt_succeeded, envelope_cid="not-a-cid"),
            False,
        ),
        (
            "neg-receipt-bad-status",
            "receipt",
            _mutate(base_receipt_succeeded, status="running"),
            False,
        ),
        (
            "neg-receipt-succeeded-with-error",
            "receipt",
            _mutate(base_receipt_succeeded, error=base_portable_error()),
            False,
        ),
        (
            "neg-receipt-time-order",
            "receipt",
            _mutate(
                base_receipt_succeeded,
                started_at_ms=100,
                finished_at_ms=1,
            ),
            False,
        ),
        (
            "neg-receipt-bad-executor-did",
            "receipt",
            _mutate(base_receipt_succeeded, executor={"did": "not-a-did"}),
            False,
        ),
        (
            "neg-receipt-retry-attempt-zero",
            "receipt",
            _mutate(base_receipt_succeeded, retry={"attempt": 0}),
            False,
        ),
    ]


# Expected case id sets — kept explicit so language drift fails loudly.
EXPECTED_POSITIVE_IDS = frozenset(
    {
        "pos-envelope-minimal",
        "pos-envelope-with-parents",
        "pos-result-succeeded",
        "pos-result-failed-with-error",
        "pos-receipt-succeeded",
        "pos-receipt-failed",
        "pos-portable-error",
    }
)
EXPECTED_NEGATIVE_IDS = frozenset(
    {
        "neg-envelope-wrong-schema",
        "neg-envelope-missing-interface-cid",
        "neg-envelope-invalid-cid",
        "neg-envelope-invalid-did",
        "neg-envelope-invalid-proof-cid",
        "neg-envelope-bad-canonicalization",
        "neg-envelope-negative-timestamp",
        "neg-envelope-empty-correlation",
        "neg-envelope-bad-parent",
        "neg-envelope-missing-proof-cids",
        "neg-error-wrong-schema",
        "neg-error-missing-code",
        "neg-error-bad-failure-class",
        "neg-error-nonbool-retryable",
        "neg-result-wrong-schema",
        "neg-result-missing-status",
        "neg-result-bad-status",
        "neg-result-succeeded-with-error",
        "neg-result-invalid-envelope-cid",
        "neg-receipt-wrong-schema",
        "neg-receipt-missing-result-cid",
        "neg-receipt-invalid-cid",
        "neg-receipt-bad-status",
        "neg-receipt-succeeded-with-error",
        "neg-receipt-time-order",
        "neg-receipt-bad-executor-did",
        "neg-receipt-retry-attempt-zero",
    }
)

_VALIDATORS: Mapping[str, Callable[[Mapping[str, Any]], Any]] = {
    "envelope": validate_envelope_v1,
    "result": validate_result_v1,
    "receipt": validate_receipt_v1,
    "error": validate_portable_error_v1,
}


def validate_kind(kind: str, payload: Mapping[str, Any]) -> bool:
    """ExecutionEnvelopeValidator@1 dispatch for one family member."""
    if kind not in _VALIDATORS:
        raise KeyError(f"unknown kind: {kind}")
    return bool(_VALIDATORS[kind](payload).is_valid)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExecutionEnvelopeValidatorInterface:
    def test_interface_constant(self):
        assert INTERFACE == "ExecutionEnvelopeValidator@1"
        assert TASK_ID == "MCPP-033"

    def test_schema_markers(self):
        assert SCHEMA_MARKERS["envelope"] == "mcp++/execution/envelope@1"
        assert SCHEMA_MARKERS["result"] == "mcp++/execution/result@1"
        assert SCHEMA_MARKERS["receipt"] == "mcp++/execution/receipt@1"
        assert SCHEMA_MARKERS["error"] == "mcp++/execution/portable-error@1"

    def test_catalog_ids_match_expected_sets(self):
        cases = vector_catalog()
        pos = {c[0] for c in cases if c[3]}
        neg = {c[0] for c in cases if not c[3]}
        assert pos == EXPECTED_POSITIVE_IDS
        assert neg == EXPECTED_NEGATIVE_IDS
        # No duplicate ids
        ids = [c[0] for c in cases]
        assert len(ids) == len(set(ids))


_CATALOG = vector_catalog()


@pytest.mark.parametrize(
    "case_id,kind,builder,expect_valid",
    _CATALOG,
    ids=[c[0] for c in _CATALOG],
)
def test_execution_envelope_vector(case_id, kind, builder, expect_valid):
    payload = builder()
    assert isinstance(payload, dict)
    ok = validate_kind(kind, payload)
    assert ok is expect_valid, (
        f"{case_id} ({kind}): expected valid={expect_valid}, got {ok}; "
        f"errors={_VALIDATORS[kind](payload).errors}"
    )


class TestExecutionEnvelopePositives:
    def test_all_positives_accept(self):
        for case_id, kind, builder, expect in vector_catalog():
            if not expect:
                continue
            assert validate_kind(kind, builder()), case_id

    def test_base_fixtures_are_deep_copy_safe(self):
        a = base_envelope()
        b = base_envelope()
        a["correlation_id"] = "mutated"
        assert b["correlation_id"] == "task-001"


class TestExecutionEnvelopeNegatives:
    def test_all_negatives_reject(self):
        for case_id, kind, builder, expect in vector_catalog():
            if expect:
                continue
            assert not validate_kind(kind, builder()), case_id


class TestExecutionEnvelopeCrossKindInvariants:
    def test_succeeded_result_error_must_be_null(self):
        payload = base_result_succeeded()
        assert payload["error"] is None
        assert validate_kind("result", payload)
        payload["error"] = base_portable_error()
        assert not validate_kind("result", payload)

    def test_failed_result_carries_portable_error(self):
        payload = base_result_failed()
        assert payload["error"]["schema"] == SCHEMA_ERROR
        assert validate_kind("result", payload)
        assert validate_kind("error", payload["error"])

    def test_receipt_requires_result_cid(self):
        payload = base_receipt_succeeded()
        del payload["result_cid"]
        assert not validate_kind("receipt", payload)
