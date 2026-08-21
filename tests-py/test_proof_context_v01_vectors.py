"""PCCE-007: canonical proof-context v0.1 vectors and CID identity."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests-py"))

from validators.canonical_jcs import McppJcsError, artifact_cid, canonicalize_bytes  # noqa: E402

VECTORS = json.loads((ROOT / "conformance/vectors/proof-context-v0.1.json").read_text(encoding="utf-8"))
SCHEMA_DIR = ROOT / "schemas" / "proof-context" / "v0.1"

SCHEMA_FOR = {
    "repository-state": "repository-state.schema.json",
    "task-specification": "task-specification.schema.json",
    "coding-agent-invocation": "coding-agent-invocation.schema.json",
    "patch-proposal": "patch-proposal.schema.json",
    "execution-receipt-live-succeeded": "execution-receipt.schema.json",
    "execution-receipt-simulated-labeled": "execution-receipt.schema.json",
    "unknown-field": "task-specification.schema.json",
    "unknown-status": "execution-receipt.schema.json",
    "pseudo-cid": "task-specification.schema.json",
    "malformed-cid": "task-specification.schema.json",
    "qm-new-mint": "task-specification.schema.json",
    "wrong-parent-schema": "task-specification.schema.json",
    "stale-status-unlabeled-live": "execution-receipt.schema.json",
    "simulated-as-live": "execution-receipt.schema.json",
    "missing-required": "task-specification.schema.json",
}


def _schema_validator(name: str) -> Draft202012Validator:
    schema_file = SCHEMA_FOR[name]
    schema = json.loads((SCHEMA_DIR / schema_file).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _schema_ok(name: str, instance: dict) -> bool:
    try:
        _schema_validator(name).validate(instance)
        return True
    except ValidationError:
        return False


def _policy_ok(name: str, instance: dict) -> bool:
    if instance.get("provenance") == "simulated" and instance.get("status") == "succeeded":
        return False
    if instance.get("status") == "stale" and instance.get("provenance") == "live":
        # stale root is not a live success identity
        return False
    return True


@pytest.mark.parametrize("case", VECTORS["positives"], ids=lambda c: c["name"])
def test_positive_vector_matches_canonical_cid(case: dict) -> None:
    inst = case["instance"]
    assert _schema_ok(case["name"], inst)
    canonical = canonicalize_bytes(inst)
    assert canonical.decode("utf-8") == case["canonical_utf8"]
    assert artifact_cid(inst) == case["cid"]
    assert case["cid"].startswith("b")
    assert not case["cid"].startswith("Qm")
    assert not case["cid"].startswith("sha256:")


def test_equivalent_task_specification_has_identical_cid() -> None:
    task = next(c for c in VECTORS["positives"] if c["name"] == "task-specification")
    inst = task["instance"]
    reordered = {
        "provenance": inst["provenance"],
        "declared_files": list(inst["declared_files"]),
        "owned_paths": list(inst["owned_paths"]),
        "objective_id": inst["objective_id"],
        "task_id": inst["task_id"],
        "repository_state_cid": inst["repository_state_cid"],
        "schema": inst["schema"],
    }
    assert canonicalize_bytes(reordered) == canonicalize_bytes(inst)
    assert artifact_cid(reordered) == artifact_cid(inst) == task["cid"]


SCHEMA_REJECT = {
    "unknown-field",
    "unknown-status",
    "pseudo-cid",
    "malformed-cid",
    "qm-new-mint",
    "wrong-parent-schema",
    "missing-required",
}
POLICY_REJECT = {
    "simulated-as-live",
    "stale-status-unlabeled-live",
}


@pytest.mark.parametrize("case", VECTORS["negatives"], ids=lambda c: c["name"])
def test_negative_vector_fails_closed(case: dict) -> None:
    inst = case["instance"]
    schema_accept = _schema_ok(case["name"], inst)
    policy_accept = _policy_ok(case["name"], inst)
    if case["name"] in SCHEMA_REJECT:
        assert schema_accept is False
    elif case["name"] in POLICY_REJECT:
        assert policy_accept is False
    else:
        raise AssertionError(f"unclassified negative {case['name']}")
    cid_ok = True
    try:
        artifact_cid(inst)
    except (McppJcsError, ValueError, TypeError):
        cid_ok = False
    # Rejected identities must not be treated as admitted live CIDs.
    if case["name"] in SCHEMA_REJECT:
        assert schema_accept is False or cid_ok is False


def test_nan_infinity_cannot_be_canonicalized() -> None:
    with pytest.raises(McppJcsError):
        canonicalize_bytes({"x": float("nan")})
    with pytest.raises(McppJcsError):
        canonicalize_bytes({"x": float("inf")})
