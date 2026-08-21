"""PCCE-006: closed proof-context v0.1 schema tests.

MCP++ owns wire contracts only. These tests do not execute production runtime.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "proof-context" / "v0.1"

REQUIRED_FILES = (
    "repository-state.schema.json",
    "semantic-capsule.schema.json",
    "context-pack.schema.json",
    "task-specification.schema.json",
    "coding-agent-invocation.schema.json",
    "patch-proposal.schema.json",
    "invalidation-plan.schema.json",
    "verification-plan.schema.json",
    "model-route-decision.schema.json",
    "execution-receipt.schema.json",
    "proof-unit.schema.json",
    "incremental-seal.schema.json",
    "qualification-result.schema.json",
    "error-taxonomy.schema.json",
    "status-taxonomy.schema.json",
    "canonicalization.schema.json",
    "cid-behavior.schema.json",
)

STATUSES = {
    "succeeded",
    "rejected",
    "verification_failed",
    "proof_failed",
    "assurance_failed",
    "context_insufficient",
    "model_escalation_required",
    "human_review_required",
    "unavailable",
    "timeout",
    "cancelled",
    "invalid",
    "stale",
    "simulated",
    "infrastructure_failure",
    "partial_effect",
    "repair_required",
}

CID = "bafkreiapj52u5hi7pco5ebplvecv72olbnqglg2e7emwnmme4gguzsnpu4"
COMMIT = "b3669171b9bf34dac7e8f178bd0c2cc5936e57ae"
MARKER = "pcce/proof-context/v0.1"


def load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validator(name: str) -> Draft202012Validator:
    schema = load(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize("name", REQUIRED_FILES)
def test_schema_file_exists_and_is_draft_2020_12(name: str) -> None:
    schema = load(name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False


def test_status_taxonomy_is_closed() -> None:
    schema = load("status-taxonomy.schema.json")
    assert set(schema["enum"]) == STATUSES
    v = validator("status-taxonomy.schema.json")
    v.validate("succeeded")
    with pytest.raises(ValidationError):
        v.validate("failed")
    with pytest.raises(ValidationError):
        v.validate("ok")


def test_error_taxonomy_rejects_unknown() -> None:
    v = validator("error-taxonomy.schema.json")
    v.validate("pseudo_cid")
    with pytest.raises(ValidationError):
        v.validate("mystery")


def test_cid_behavior_forbids_pseudo_and_qm_new_mints() -> None:
    v = validator("cid-behavior.schema.json")
    inst = {
        "schema": f"{MARKER}/cid-behavior",
        "algorithm": "mcpp-jcs-v1",
        "codec": "raw",
        "multihash": "sha2-256",
        "cid_version": 1,
        "allow_pseudo_cid": False,
        "allow_qm_new_mints": False,
        "pattern": "^b[a-z2-7]{58,}$",
    }
    v.validate(inst)
    bad = dict(inst)
    bad["allow_pseudo_cid"] = True
    with pytest.raises(ValidationError):
        v.validate(bad)


def test_canonicalization_is_rfc8785() -> None:
    v = validator("canonicalization.schema.json")
    inst = {
        "schema": f"{MARKER}/canonicalization",
        "algorithm": "mcpp-jcs-v1",
        "standard": "RFC 8785",
        "unicode": "NFC",
        "reject_nan_infinity": True,
    }
    v.validate(inst)
    with pytest.raises(ValidationError):
        v.validate({**inst, "algorithm": "other-jcs"})


def _object_instance(name: str) -> dict:
    schema = f"{MARKER}/{name.removesuffix('.schema.json')}"
    base = {
        "repository-state.schema.json": {
            "schema": schema,
            "repository": "endomorphosis/ipfs_datasets_py",
            "remote": "https://github.com/endomorphosis/ipfs_datasets_py.git",
            "commit": COMMIT,
            "tree": "16ef68abe8a35a3033dfaf1ed4e8d6132600df8f",
        },
        "semantic-capsule.schema.json": {
            "schema": schema,
            "capsule_cid": CID,
            "repository_state_cid": CID,
            "symbol": "IncrementalSemanticIndex",
            "freshness": "fresh",
        },
        "context-pack.schema.json": {
            "schema": schema,
            "pack_cid": CID,
            "repository_state_cid": CID,
            "sufficiency": "sufficient",
            "provenance": "live",
        },
        "task-specification.schema.json": {
            "schema": schema,
            "task_id": "PCCE-006",
            "objective_id": "PCCE-G100",
            "repository_state_cid": CID,
            "owned_paths": ["schemas/proof-context/v0.1/repository-state.schema.json"],
            "provenance": "live",
        },
        "coding-agent-invocation.schema.json": {
            "schema": schema,
            "invocation_cid": CID,
            "task_id": "PCCE-006",
            "repository_state_cid": CID,
            "provider": "grok",
            "model": "grok-4.6",
            "revision": COMMIT,
            "tier": "implementation",
            "token_count": 1,
            "cached_token_count": 0,
            "latency_ms": 10,
            "cost_micros": 0,
            "response_artifact_cid": CID,
            "provenance": "live",
        },
        "patch-proposal.schema.json": {
            "schema": schema,
            "proposal_cid": CID,
            "task_id": "PCCE-006",
            "repository_state_cid": CID,
            "declared_files": ["schemas/proof-context/v0.1/patch-proposal.schema.json"],
            "patch_cid": CID,
            "provenance": "live",
        },
        "invalidation-plan.schema.json": {
            "schema": schema,
            "plan_cid": CID,
            "repository_state_cid": CID,
            "reason": "owned-path-changed",
            "affected_paths": ["ipfs_datasets_py/proof_context/context_pack.py"],
        },
        "verification-plan.schema.json": {
            "schema": schema,
            "plan_cid": CID,
            "repository_state_cid": CID,
            "task_id": "PCCE-006",
            "selected_tests": ["tests-py/test_proof_context_v01_schemas.py"],
        },
        "model-route-decision.schema.json": {
            "schema": schema,
            "decision_cid": CID,
            "task_id": "PCCE-006",
            "tier": "implementation",
            "provider": "grok",
            "model": "grok-4.6",
            "provenance": "live",
        },
        "execution-receipt.schema.json": {
            "schema": schema,
            "receipt_cid": CID,
            "task_id": "PCCE-006",
            "repository_state_cid": CID,
            "status": "succeeded",
            "provenance": "live",
            "started_at": "2026-08-21T15:00:00Z",
            "finished_at": "2026-08-21T15:00:01Z",
        },
        "proof-unit.schema.json": {
            "schema": schema,
            "unit_cid": CID,
            "repository_state_cid": CID,
            "obligation": "schema-closed",
            "status": "succeeded",
        },
        "incremental-seal.schema.json": {
            "schema": schema,
            "seal_cid": CID,
            "repository_state_cid": CID,
            "unit_cids": [CID],
            "status": "succeeded",
        },
        "qualification-result.schema.json": {
            "schema": schema,
            "result_cid": CID,
            "subject": "proof-context-v0.1",
            "status": "succeeded",
            "provenance": "live",
        },
        "canonicalization.schema.json": {
            "schema": schema,
            "algorithm": "mcpp-jcs-v1",
            "standard": "RFC 8785",
            "unicode": "NFC",
            "reject_nan_infinity": True,
        },
        "cid-behavior.schema.json": {
            "schema": schema,
            "algorithm": "mcpp-jcs-v1",
            "codec": "raw",
            "multihash": "sha2-256",
            "cid_version": 1,
            "allow_pseudo_cid": False,
            "allow_qm_new_mints": False,
        },
    }
    return base[name]


OBJECT_SCHEMAS = [
    name
    for name in REQUIRED_FILES
    if name
    not in (
        "status-taxonomy.schema.json",
        "error-taxonomy.schema.json",
    )
]


@pytest.mark.parametrize("name", OBJECT_SCHEMAS)
def test_valid_instance_passes(name: str) -> None:
    validator(name).validate(_object_instance(name))


@pytest.mark.parametrize("name", OBJECT_SCHEMAS)
def test_unknown_field_is_rejected(name: str) -> None:
    inst = _object_instance(name)
    inst["unexpected_field"] = "nope"
    with pytest.raises(ValidationError):
        validator(name).validate(inst)


def test_unknown_status_on_receipt_is_rejected() -> None:
    inst = _object_instance("execution-receipt.schema.json")
    inst["status"] = "failed"
    with pytest.raises(ValidationError):
        validator("execution-receipt.schema.json").validate(inst)


def test_pseudo_cid_is_rejected() -> None:
    inst = _object_instance("execution-receipt.schema.json")
    inst["receipt_cid"] = "sha256:deadbeef"
    with pytest.raises(ValidationError):
        validator("execution-receipt.schema.json").validate(inst)
    inst["receipt_cid"] = "not-a-cid"
    with pytest.raises(ValidationError):
        validator("execution-receipt.schema.json").validate(inst)
    inst["receipt_cid"] = "Qm" + ("a" * 44)
    with pytest.raises(ValidationError):
        validator("execution-receipt.schema.json").validate(inst)


def test_wrong_schema_marker_is_rejected() -> None:
    inst = _object_instance("task-specification.schema.json")
    inst["schema"] = "pcce/proof-context/v0.2/task-specification"
    with pytest.raises(ValidationError):
        validator("task-specification.schema.json").validate(inst)


def test_invocation_and_proposal_bind_identities() -> None:
    inv = _object_instance("coding-agent-invocation.schema.json")
    prop = _object_instance("patch-proposal.schema.json")
    for key in (
        "task_id",
        "repository_state_cid",
        "provider",
        "model",
        "revision",
        "tier",
        "provenance",
        "token_count",
        "cached_token_count",
        "latency_ms",
        "cost_micros",
        "response_artifact_cid",
    ):
        assert key in load("coding-agent-invocation.schema.json")["properties"]
    for key in ("declared_files", "patch_cid", "task_id", "repository_state_cid", "provenance"):
        assert key in load("patch-proposal.schema.json")["properties"]
    validator("coding-agent-invocation.schema.json").validate(inv)
    validator("patch-proposal.schema.json").validate(prop)


def test_simulated_provenance_is_distinct_from_live() -> None:
    inst = _object_instance("execution-receipt.schema.json")
    inst["provenance"] = "simulated"
    inst["status"] = "simulated"
    validator("execution-receipt.schema.json").validate(inst)
    inst["provenance"] = "live-replay"
    with pytest.raises(ValidationError):
        validator("execution-receipt.schema.json").validate(inst)
