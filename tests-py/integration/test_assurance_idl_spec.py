"""FACP-032: Assurance IDL OperationSpec@1 schema and specification.

Acceptance (taskboard):
- OperationSpec is versioned, closed, bounded, no critical floats.
- Can describe all migrated operations without free-form authority or
  outcome fields.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "operation-spec.schema.json"
)
SPEC_PATH = REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "assurance-idl.md"
EVIDENCE_ENVELOPE_SCHEMA_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "evidence-envelope.schema.json"
)

SCHEMA_ID = "facp/operation-spec@1"
TASK_ID = "FACP-032"
GOAL_ID = "FACP-G310"
BUNDLE = "facp/contracts/idl"

EFFECT_CLASSES = (
    "pure",
    "read",
    "write",
    "process",
    "credential",
    "install",
    "repository",
    "publish",
    "payment",
    "private",
    "legal",
    "irreversible",
)

IDEMPOTENCY_CLASSES = (
    "pure_idempotent",
    "idempotent",
    "at_most_once",
    "non_idempotent",
)

REVERSIBILITY_CLASSES = (
    "reversible",
    "compensatable",
    "irreversible",
)

AUTHORITY_OBLIGATIONS = (
    "none",
    "actor_authenticated",
    "capability_verified",
)

POLICY_OBLIGATIONS = (
    "none",
    "host_policy_required",
    "host_policy_with_obligations",
)

CONFIRMATION_OBLIGATIONS = (
    "none",
    "one_use_confirmation_required",
)

LEASE_OBLIGATIONS = (
    "none",
    "lease_required",
)

OBSERVATION_OBLIGATIONS = (
    "none",
    "independent_observation_required",
    "delegated_observation_allowed",
)

EVIDENCE_CLASSES = (
    "none",
    "hermetic",
    "conditional",
    "live",
)

CLOSED_OUTCOMES = (
    "Unavailable",
    "Rejected",
    "Simulated",
    "Attempted",
    "Unknown",
    "Observed",
    "Verified",
    "Failed",
    "Compensated",
)

REQUIRED_FIELDS = (
    "schema",
    "schema_version",
    "operation_id",
    "namespace",
    "name",
    "version",
    "input_schema_cid",
    "output_schema_cid",
    "error_codes",
    "effect_class",
    "idempotency_class",
    "reversibility_class",
    "authority_obligation",
    "policy_obligation",
    "confirmation_obligation",
    "lease_obligation",
    "observation_obligation",
    "evidence_class",
    "allowed_outcomes",
    "resource_bounds",
)

# Deterministic CIDv1 fixtures (Profile B bafkrei… length/alphabet).
CID_A = "bafkreifxone36h5jwjwulvkf27le3lmwon7jz65tzo27luipw55q7tcevu"
CID_B = "bafkreify4h4axvyk4b4ey6cvurixgg3ul7o3m52j2i7wg67jbavxl2kxlm"
CID_C = "bafkreigtrlsydtivo7l5hzgxu7eo5d633crbdjd44pdn63nkxkbsvsso2q"
CID_D = "bafkreiea6ifqo536vjhu5iab3gccs3e6mp2hsabokmm7juyh64wz6a2mpi"
CID_E = "bafkreieforcfnzh4w7vxu34d3ihmor2tacjuwptd6slvtb7nk5tttcq2km"

FREE_FORM_FORBIDDEN_KEYS = (
    "authority",
    "authorization",
    "outcome",
    "success",
    "allowed",
    "consent",
    "dry_run",
    "permission",
    "grant",
)


def _base_spec(**overrides: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "schema_version": 1,
        "operation_id": "datasets.download",
        "namespace": "ipfs_datasets_py",
        "name": "download",
        "version": 1,
        "input_schema_cid": CID_A,
        "output_schema_cid": CID_B,
        "error_codes": ["unavailable", "rejected", "failed", "unknown_effect"],
        "effect_class": "write",
        "idempotency_class": "at_most_once",
        "reversibility_class": "compensatable",
        "authority_obligation": "capability_verified",
        "policy_obligation": "host_policy_required",
        "confirmation_obligation": "none",
        "lease_obligation": "lease_required",
        "observation_obligation": "independent_observation_required",
        "evidence_class": "live",
        "allowed_outcomes": [
            "Unavailable",
            "Rejected",
            "Attempted",
            "Unknown",
            "Observed",
            "Verified",
            "Failed",
            "Compensated",
        ],
        "resource_bounds": {
            "max_input_bytes": 1048576,
            "max_output_bytes": 67108864,
            "max_duration_ms": 60000,
            "max_memory_bytes": 268435456,
            "max_cpu_ms": 30000,
            "max_effect_retries": 1,
        },
    }
    spec.update(overrides)
    return spec


def _migrated_operation_fixtures() -> dict[str, dict[str, Any]]:
    """Representative OperationSpec instances for all four migrated paths."""
    effectful_outcomes = [
        "Unavailable",
        "Rejected",
        "Attempted",
        "Unknown",
        "Observed",
        "Verified",
        "Failed",
        "Compensated",
    ]
    return {
        "datasets.download": _base_spec(
            operation_id="datasets.download",
            namespace="ipfs_datasets_py",
            name="download",
            effect_class="write",
            input_schema_cid=CID_A,
            output_schema_cid=CID_B,
        ),
        "datasets.upload": _base_spec(
            operation_id="datasets.upload",
            namespace="ipfs_datasets_py",
            name="upload",
            effect_class="write",
            reversibility_class="compensatable",
            input_schema_cid=CID_B,
            output_schema_cid=CID_C,
        ),
        "datasets.get": _base_spec(
            operation_id="datasets.get",
            namespace="ipfs_datasets_py",
            name="get",
            effect_class="read",
            idempotency_class="idempotent",
            reversibility_class="reversible",
            lease_obligation="none",
            observation_obligation="independent_observation_required",
            evidence_class="conditional",
            input_schema_cid=CID_C,
            output_schema_cid=CID_D,
            allowed_outcomes=[
                "Unavailable",
                "Rejected",
                "Observed",
                "Verified",
                "Failed",
            ],
        ),
        "datasets.save": _base_spec(
            operation_id="datasets.save",
            namespace="ipfs_datasets_py",
            name="save",
            effect_class="write",
            input_schema_cid=CID_D,
            output_schema_cid=CID_E,
        ),
        "datasets.pin": _base_spec(
            operation_id="datasets.pin",
            namespace="ipfs_datasets_py",
            name="pin",
            effect_class="write",
            input_schema_cid=CID_E,
            output_schema_cid=CID_A,
        ),
        "datasets.semantic": _base_spec(
            operation_id="datasets.semantic",
            namespace="ipfs_datasets_py",
            name="semantic",
            effect_class="process",
            evidence_class="hermetic",
            input_schema_cid=CID_A,
            output_schema_cid=CID_C,
            allowed_outcomes=[
                "Unavailable",
                "Rejected",
                "Simulated",
                "Attempted",
                "Unknown",
                "Observed",
                "Verified",
                "Failed",
            ],
        ),
        "accelerate.capability_probe": _base_spec(
            operation_id="accelerate.capability_probe",
            namespace="ipfs_accelerate_py",
            name="capability_probe",
            effect_class="read",
            idempotency_class="idempotent",
            reversibility_class="reversible",
            authority_obligation="actor_authenticated",
            confirmation_obligation="none",
            lease_obligation="none",
            observation_obligation="independent_observation_required",
            evidence_class="live",
            error_codes=["unavailable", "rejected", "stale_probe", "failed"],
            input_schema_cid=CID_B,
            output_schema_cid=CID_D,
            allowed_outcomes=[
                "Unavailable",
                "Rejected",
                "Observed",
                "Verified",
                "Failed",
            ],
        ),
        "accelerate.inference": _base_spec(
            operation_id="accelerate.inference",
            namespace="ipfs_accelerate_py",
            name="inference",
            effect_class="process",
            idempotency_class="at_most_once",
            reversibility_class="compensatable",
            authority_obligation="capability_verified",
            policy_obligation="host_policy_with_obligations",
            observation_obligation="delegated_observation_allowed",
            evidence_class="live",
            error_codes=[
                "unavailable",
                "rejected",
                "inference_unobserved",
                "failed",
            ],
            input_schema_cid=CID_C,
            output_schema_cid=CID_E,
            # Simulated remains an allowed closed outcome for explicit test mode.
            allowed_outcomes=[
                "Unavailable",
                "Rejected",
                "Simulated",
                "Attempted",
                "Unknown",
                "Observed",
                "Verified",
                "Failed",
                "Compensated",
            ],
        ),
        "kit.storage_select": _base_spec(
            operation_id="kit.storage_select",
            namespace="ipfs_kit_py",
            name="storage_select",
            effect_class="read",
            idempotency_class="idempotent",
            reversibility_class="reversible",
            authority_obligation="capability_verified",
            policy_obligation="host_policy_required",
            lease_obligation="none",
            observation_obligation="independent_observation_required",
            evidence_class="live",
            error_codes=["unavailable", "rejected", "stale", "failed"],
            input_schema_cid=CID_D,
            output_schema_cid=CID_A,
            allowed_outcomes=[
                "Unavailable",
                "Rejected",
                "Observed",
                "Verified",
                "Failed",
            ],
        ),
        "kit.proof_role_transition": _base_spec(
            operation_id="kit.proof_role_transition",
            namespace="ipfs_kit_py",
            name="proof_role_transition",
            effect_class="write",
            idempotency_class="at_most_once",
            reversibility_class="irreversible",
            authority_obligation="capability_verified",
            confirmation_obligation="one_use_confirmation_required",
            lease_obligation="lease_required",
            observation_obligation="independent_observation_required",
            evidence_class="live",
            error_codes=[
                "unavailable",
                "rejected",
                "operation_id_reuse_conflict",
                "failed",
            ],
            input_schema_cid=CID_E,
            output_schema_cid=CID_B,
            allowed_outcomes=effectful_outcomes,
        ),
        "swissknife.present_evidence": _base_spec(
            operation_id="swissknife.present_evidence",
            namespace="swissknife",
            name="present_evidence",
            effect_class="pure",
            idempotency_class="pure_idempotent",
            reversibility_class="reversible",
            authority_obligation="none",
            policy_obligation="none",
            confirmation_obligation="none",
            lease_obligation="none",
            observation_obligation="none",
            evidence_class="none",
            error_codes=["unavailable", "rejected"],
            input_schema_cid=CID_A,
            output_schema_cid=CID_D,
            allowed_outcomes=["Unavailable", "Rejected", "Observed"],
            resource_bounds={
                "max_input_bytes": 65536,
                "max_output_bytes": 65536,
                "max_duration_ms": 5000,
                "max_memory_bytes": 16777216,
            },
        ),
        "swissknife.project_confirmation_intent": _base_spec(
            operation_id="swissknife.project_confirmation_intent",
            namespace="swissknife",
            name="project_confirmation_intent",
            effect_class="pure",
            idempotency_class="pure_idempotent",
            reversibility_class="reversible",
            authority_obligation="none",
            policy_obligation="none",
            confirmation_obligation="none",
            lease_obligation="none",
            observation_obligation="none",
            evidence_class="none",
            error_codes=["unavailable", "rejected"],
            input_schema_cid=CID_B,
            output_schema_cid=CID_C,
            allowed_outcomes=["Unavailable", "Rejected", "Observed"],
            resource_bounds={
                "max_input_bytes": 32768,
                "max_output_bytes": 32768,
                "max_duration_ms": 5000,
                "max_memory_bytes": 8388608,
            },
        ),
    }


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    assert SCHEMA_PATH.is_file(), SCHEMA_PATH
    data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def spec_text() -> str:
    assert SPEC_PATH.is_file(), SPEC_PATH
    return SPEC_PATH.read_text(encoding="utf-8")


def _contains_float(value: Any) -> bool:
    if isinstance(value, float) and not isinstance(value, bool):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float(v) for v in value)
    return False


def _classify_schema_error(
    instance: Any,
    error: jsonschema.ValidationError,
) -> str:
    """Map Draft 2020-12 failures onto stable FACP OperationSpec error codes."""
    if _contains_float(instance):
        return "FORBIDDEN_FLOAT"

    validator_name = error.validator
    path = list(error.absolute_path)

    if isinstance(instance, dict):
        for key in FREE_FORM_FORBIDDEN_KEYS:
            if key in instance:
                if key in {"authority", "authorization", "permission", "grant"}:
                    return "FREE_FORM_AUTHORITY"
                if key in {"outcome", "success"}:
                    return "FREE_FORM_OUTCOME" if key == "outcome" else "FORBIDDEN_SUCCESS_BOOLEAN"
                return "UNKNOWN_FIELD"

    if validator_name == "additionalProperties":
        bad = error.message.split(" ")[0].strip("'\"")
        if bad in {"authority", "authorization", "permission", "grant"}:
            return "FREE_FORM_AUTHORITY"
        if bad == "outcome":
            return "FREE_FORM_OUTCOME"
        if bad == "success":
            return "FORBIDDEN_SUCCESS_BOOLEAN"
        return "UNKNOWN_FIELD"
    if validator_name == "required":
        return "MISSING_FIELD"
    if validator_name == "enum":
        return "UNKNOWN_ENUM"
    if validator_name == "const":
        return "UNKNOWN_ENUM"
    if validator_name == "type":
        if path:
            cursor: Any = instance
            for part in path:
                if isinstance(cursor, dict) and part in cursor:
                    cursor = cursor[part]
                elif isinstance(cursor, list) and isinstance(part, int) and part < len(cursor):
                    cursor = cursor[part]
                else:
                    cursor = None
                    break
            if isinstance(cursor, float) and not isinstance(cursor, bool):
                return "FORBIDDEN_FLOAT"
        return "INVALID_TYPE"
    if validator_name in {"maxLength", "minLength", "pattern"}:
        if path and path[-1] in {"input_schema_cid", "output_schema_cid"}:
            return "INVALID_CID"
        if validator_name == "maxLength":
            return "UNBOUNDED_STRING"
        return "INVALID_TYPE"
    if validator_name in {"maxItems", "minItems"}:
        return "UNBOUNDED_ARRAY"
    if validator_name in {"maximum", "minimum"}:
        return "INVALID_BOUNDS"
    if validator_name == "uniqueItems":
        if path and path[-1] == "allowed_outcomes":
            return "DUPLICATE_ALLOWED_OUTCOME"
        if path and path[-1] == "error_codes":
            return "DUPLICATE_ERROR_CODE"
        return "INVALID_TYPE"

    message = error.message.lower()
    if "additional" in message or "unevaluated" in message:
        return "UNKNOWN_FIELD"
    if "is a required property" in message:
        return "MISSING_FIELD"
    if "is not one of" in message or "is not one of the given" in message:
        return "UNKNOWN_ENUM"
    return f"SCHEMA_REJECT:{validator_name}"


def _validate(
    validator: Draft202012Validator,
    instance: Any,
) -> tuple[bool, str]:
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if not errors:
        if _contains_float(instance):
            return False, "FORBIDDEN_FLOAT"
        return True, ""
    return False, _classify_schema_error(instance, errors[0])


# ---------------------------------------------------------------------------
# Artifacts exist and are versioned
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert SCHEMA_PATH.is_file()
    assert SPEC_PATH.is_file()
    assert EVIDENCE_ENVELOPE_SCHEMA_PATH.is_file()


def test_schema_metadata_versioned(schema: Mapping[str, Any]) -> None:
    x_facp = schema["x-facp"]
    assert x_facp["schema"] == SCHEMA_ID
    assert x_facp["schema_version"] == 1
    assert x_facp["task_id"] == TASK_ID
    assert x_facp["goal_id"] == GOAL_ID
    assert x_facp["bundle"] == BUNDLE
    assert x_facp["floats_forbidden"] is True
    assert x_facp["unknown_fields_forbidden"] is True
    assert x_facp["free_form_authority_forbidden"] is True
    assert x_facp["free_form_outcome_forbidden"] is True
    assert x_facp["boolean_success_forbidden"] is True
    assert schema["properties"]["schema"]["const"] == SCHEMA_ID
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["properties"]["schema_version"]["type"] == "integer"


def test_spec_documents_operation_spec(spec_text: str) -> None:
    assert "OperationSpec@1" in spec_text
    assert SCHEMA_ID in spec_text
    assert "FACP-032" in spec_text
    assert "no critical floats" in spec_text.lower() or "Floats are forbidden" in spec_text
    assert "free-form" in spec_text.lower()
    for field in (
        "effect_class",
        "idempotency_class",
        "reversibility_class",
        "authority_obligation",
        "policy_obligation",
        "confirmation_obligation",
        "lease_obligation",
        "observation_obligation",
        "evidence_class",
        "allowed_outcomes",
        "resource_bounds",
    ):
        assert field in spec_text


# ---------------------------------------------------------------------------
# Closed / bounded / no floats
# ---------------------------------------------------------------------------


def test_schema_is_closed(schema: Mapping[str, Any]) -> None:
    assert schema.get("additionalProperties") is False
    assert schema.get("unevaluatedProperties") is False
    bounds = schema["$defs"]["resource_bounds"]
    assert bounds.get("additionalProperties") is False
    assert bounds.get("unevaluatedProperties") is False
    assert set(schema["required"]) == set(REQUIRED_FIELDS)
    assert set(schema["properties"]) == set(REQUIRED_FIELDS)


def test_schema_enums_match_closed_vocabularies(schema: Mapping[str, Any]) -> None:
    defs = schema["$defs"]
    assert tuple(defs["effect_class"]["enum"]) == EFFECT_CLASSES
    assert tuple(defs["idempotency_class"]["enum"]) == IDEMPOTENCY_CLASSES
    assert tuple(defs["reversibility_class"]["enum"]) == REVERSIBILITY_CLASSES
    assert tuple(defs["authority_obligation"]["enum"]) == AUTHORITY_OBLIGATIONS
    assert tuple(defs["policy_obligation"]["enum"]) == POLICY_OBLIGATIONS
    assert tuple(defs["confirmation_obligation"]["enum"]) == CONFIRMATION_OBLIGATIONS
    assert tuple(defs["lease_obligation"]["enum"]) == LEASE_OBLIGATIONS
    assert tuple(defs["observation_obligation"]["enum"]) == OBSERVATION_OBLIGATIONS
    assert tuple(defs["evidence_class"]["enum"]) == EVIDENCE_CLASSES
    assert tuple(defs["closed_outcome"]["enum"]) == CLOSED_OUTCOMES


def test_schema_bounds_are_finite(schema: Mapping[str, Any]) -> None:
    defs = schema["$defs"]
    for key in (
        "operation_id",
        "namespace",
        "operation_name",
        "error_code",
        "cid_v1",
        "effect_class",
        "closed_outcome",
    ):
        assert "maxLength" in defs[key]
    assert defs["cid_v1"]["maxLength"] <= 129
    assert schema["properties"]["error_codes"]["maxItems"] == 64
    assert schema["properties"]["allowed_outcomes"]["maxItems"] == 9
    assert defs["byte_bound"]["type"] == "integer"
    assert defs["duration_bound_ms"]["type"] == "integer"
    assert schema["properties"]["version"]["type"] == "integer"
    assert schema["properties"]["schema_version"]["type"] == "integer"
    # No JSON Schema "number" types anywhere (floats would be admissible).
    blob = json.dumps(schema)
    assert '"type": "number"' not in blob
    assert '"type":"number"' not in blob


def test_valid_base_spec(validator: Draft202012Validator) -> None:
    ok, code = _validate(validator, _base_spec())
    assert ok, code


def test_unknown_field_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec()
    spec["extra_authority_blob"] = "grant-everything"
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "UNKNOWN_FIELD"


def test_missing_required_field_rejected(validator: Draft202012Validator) -> None:
    for field in REQUIRED_FIELDS:
        spec = _base_spec()
        del spec[field]
        ok, code = _validate(validator, spec)
        assert not ok, field
        assert code == "MISSING_FIELD", field


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("effect_class", "mutate"),
        ("idempotency_class", "maybe"),
        ("reversibility_class", "undoable"),
        ("authority_obligation", "browser_granted"),
        ("policy_obligation", "ui_allow"),
        ("confirmation_obligation", "cookie_consent"),
        ("lease_obligation", "soft_lease"),
        ("observation_obligation", "self_reported"),
        ("evidence_class", "production"),
    ],
)
def test_unknown_enums_rejected(
    validator: Draft202012Validator, field: str, bad_value: str
) -> None:
    spec = _base_spec(**{field: bad_value})
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "UNKNOWN_ENUM"


def test_free_form_authority_field_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec()
    spec["authority"] = "did:key:zActor#cap"
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "FREE_FORM_AUTHORITY"


def test_free_form_outcome_field_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec()
    spec["outcome"] = "looks_good"
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "FREE_FORM_OUTCOME"


def test_boolean_success_field_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec()
    spec["success"] = True
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "FORBIDDEN_SUCCESS_BOOLEAN"


def test_free_form_outcome_string_in_allowed_outcomes_rejected(
    validator: Draft202012Validator,
) -> None:
    spec = _base_spec(allowed_outcomes=["Unavailable", "totally_fine"])
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "UNKNOWN_ENUM"


def test_float_resource_bound_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec()
    spec["resource_bounds"] = {
        "max_input_bytes": 1024.5,
        "max_output_bytes": 2048,
        "max_duration_ms": 1000,
        "max_memory_bytes": 4096,
    }
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "FORBIDDEN_FLOAT"


def test_float_version_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec(version=1.5)
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "FORBIDDEN_FLOAT"


def test_float_schema_version_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec(schema_version=1.0)
    # 1.0 is a float in Python even when equal to 1
    assert isinstance(spec["schema_version"], float)
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "FORBIDDEN_FLOAT"


def test_invalid_cid_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec(input_schema_cid="QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG")
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "INVALID_CID"


def test_empty_allowed_outcomes_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec(allowed_outcomes=[])
    ok, code = _validate(validator, spec)
    assert not ok
    assert code in {"UNBOUNDED_ARRAY", "MISSING_FIELD", "INVALID_TYPE"}


def test_duplicate_allowed_outcomes_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec(allowed_outcomes=["Unavailable", "Unavailable", "Observed"])
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "DUPLICATE_ALLOWED_OUTCOME"


def test_unknown_resource_bound_field_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec()
    bounds = copy.deepcopy(spec["resource_bounds"])
    bounds["max_latency_seconds"] = 1.25
    spec["resource_bounds"] = bounds
    ok, code = _validate(validator, spec)
    assert not ok
    assert code in {"UNKNOWN_FIELD", "FORBIDDEN_FLOAT"}


def test_wrong_schema_const_rejected(validator: Draft202012Validator) -> None:
    spec = _base_spec(schema="facp/operation-spec@2")
    ok, code = _validate(validator, spec)
    assert not ok
    assert code == "UNKNOWN_ENUM"


# ---------------------------------------------------------------------------
# Migrated operations coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("operation_id", sorted(_migrated_operation_fixtures()))
def test_migrated_operation_fixture_valid(
    validator: Draft202012Validator, operation_id: str
) -> None:
    fixtures = _migrated_operation_fixtures()
    ok, code = _validate(validator, fixtures[operation_id])
    assert ok, f"{operation_id}: {code}"


def test_all_four_migration_paths_covered(validator: Draft202012Validator) -> None:
    fixtures = _migrated_operation_fixtures()
    namespaces = {spec["namespace"] for spec in fixtures.values()}
    assert namespaces >= {
        "ipfs_datasets_py",
        "ipfs_accelerate_py",
        "ipfs_kit_py",
        "swissknife",
    }
    # SwissKnife presentation never carries authority obligations.
    for op_id, spec in fixtures.items():
        if spec["namespace"] == "swissknife":
            assert spec["authority_obligation"] == "none", op_id
            assert spec["effect_class"] == "pure", op_id
            assert "success" not in spec
            assert "authority" not in spec
            assert "outcome" not in spec
    # Every fixture uses only closed outcomes.
    for op_id, spec in fixtures.items():
        assert set(spec["allowed_outcomes"]) <= set(CLOSED_OUTCOMES), op_id
        ok, code = _validate(validator, spec)
        assert ok, f"{op_id}: {code}"


def test_effectful_migrated_ops_require_observation_when_not_pure(
    validator: Draft202012Validator,
) -> None:
    fixtures = _migrated_operation_fixtures()
    for op_id, spec in fixtures.items():
        if spec["effect_class"] == "pure":
            continue
        assert spec["observation_obligation"] in {
            "independent_observation_required",
            "delegated_observation_allowed",
        }, op_id
        assert "Observed" in spec["allowed_outcomes"] or "Verified" in spec["allowed_outcomes"], op_id
        ok, code = _validate(validator, spec)
        assert ok, f"{op_id}: {code}"


def test_spec_lists_migrated_path_coverage(spec_text: str) -> None:
    for token in (
        "datasets.download",
        "accelerate.inference",
        "kit.storage_select",
        "swissknife.present_evidence",
    ):
        assert token in spec_text


def test_stable_error_codes_documented(schema: Mapping[str, Any]) -> None:
    codes = set(schema["x-facp"]["stable_error_codes"])
    for required in (
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "UNKNOWN_ENUM",
        "FORBIDDEN_FLOAT",
        "FREE_FORM_AUTHORITY",
        "FREE_FORM_OUTCOME",
        "FORBIDDEN_SUCCESS_BOOLEAN",
        "INVALID_CID",
    ):
        assert required in codes


def test_schema_id_matches_file_id(schema: Mapping[str, Any]) -> None:
    assert schema["$id"].endswith("operation-spec.schema.json")
    assert schema["title"] == "OperationSpec@1"
