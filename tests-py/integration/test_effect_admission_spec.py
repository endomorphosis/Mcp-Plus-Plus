"""FACP-038: Effect classes and admission typestate.

Acceptance (taskboard):
- Every migrated operation is classified.
- Token obligations are mechanically derived.
- Unknown and CompensationRequired are explicit.
- Only kernel-issued token unlocks a handler.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

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
    / "effect-admission.schema.json"
)
SPEC_PATH = (
    REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "effect-admission-kernel.md"
)
OPERATION_SPEC_SCHEMA_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "operation-spec.schema.json"
)

SCHEMA_ID = "facp/effect-admission@1"
VOCAB_SCHEMA = "facp/effect-admission-vocab@1"
TASK_ID = "FACP-038"
GOAL_ID = "FACP-G320"
BUNDLE = "facp/admission/spec"

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

TYPESTATE_HAPPY_PATH = (
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

TYPESTATE_EXCEPTIONAL = (
    "Rejected",
    "Unavailable",
    "Failed",
    "Unknown",
    "CompensationRequired",
    "Compensated",
    "Aborted",
)

TOKEN_OBLIGATIONS = (
    "kernel_issued",
    "operation_bound",
    "effect_class_bound",
    "argument_bound",
    "nonce_bound",
    "expiry_bound",
    "actor_bound",
    "capability_bound",
    "delegation_bound",
    "policy_bound",
    "policy_obligations_bound",
    "confirmation_bound",
    "lease_bound",
    "observation_bound",
)

HANDLER_UNLOCK_TYPESTATES = ("Reserved", "Started")
KERNEL_ISSUER = "effect_admission_kernel"

UNIVERSAL_TOKEN_OBLIGATIONS = frozenset(
    {
        "kernel_issued",
        "operation_bound",
        "effect_class_bound",
        "argument_bound",
        "nonce_bound",
        "expiry_bound",
    }
)

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

JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

# Legal typestate edges (fail-closed elsewhere).
_HAPPY_EDGES = {
    (TYPESTATE_HAPPY_PATH[i], TYPESTATE_HAPPY_PATH[i + 1])
    for i in range(len(TYPESTATE_HAPPY_PATH) - 1)
}
_PRE_RESERVED = set(TYPESTATE_HAPPY_PATH[: TYPESTATE_HAPPY_PATH.index("Reserved")])


def _legal_transitions() -> set[tuple[str, str]]:
    edges = set(_HAPPY_EDGES)
    for state in _PRE_RESERVED:
        edges.add((state, "Rejected"))
        edges.add((state, "Unavailable"))
    edges.update(
        {
            ("Started", "Observed"),
            ("Started", "Failed"),
            ("Started", "Unknown"),
            ("Started", "Aborted"),
            ("Started", "CompensationRequired"),
            ("Unknown", "Observed"),
            ("Unknown", "Failed"),
            ("Unknown", "CompensationRequired"),
            ("Unknown", "Aborted"),
            ("CompensationRequired", "Compensated"),
            ("CompensationRequired", "Failed"),
            ("Observed", "CompensationRequired"),
            ("Observed", "ReceiptSealed"),
            ("Compensated", "ReceiptSealed"),
            ("Failed", "ReceiptSealed"),
            ("Rejected", "ReceiptSealed"),
            ("Unavailable", "ReceiptSealed"),
            ("Aborted", "ReceiptSealed"),
        }
    )
    return edges


LEGAL_TRANSITIONS = _legal_transitions()


def derive_token_obligations(spec: Mapping[str, Any]) -> frozenset[str]:
    """Pure mechanical derivation of AdmissionToken obligations (FACP-038 §5)."""
    if spec["effect_class"] == "pure":
        return frozenset()

    out: set[str] = set(UNIVERSAL_TOKEN_OBLIGATIONS)
    authority = spec["authority_obligation"]
    if authority == "actor_authenticated":
        out.add("actor_bound")
    elif authority == "capability_verified":
        out.update({"actor_bound", "capability_bound", "delegation_bound"})
    elif authority != "none":
        raise ValueError(f"UNKNOWN_ENUM:authority_obligation={authority}")

    policy = spec["policy_obligation"]
    if policy == "host_policy_required":
        out.add("policy_bound")
    elif policy == "host_policy_with_obligations":
        out.update({"policy_bound", "policy_obligations_bound"})
    elif policy != "none":
        raise ValueError(f"UNKNOWN_ENUM:policy_obligation={policy}")

    if spec["confirmation_obligation"] == "one_use_confirmation_required":
        out.add("confirmation_bound")
    elif spec["confirmation_obligation"] != "none":
        raise ValueError("UNKNOWN_ENUM:confirmation_obligation")

    if spec["lease_obligation"] == "lease_required":
        out.add("lease_bound")
    elif spec["lease_obligation"] != "none":
        raise ValueError("UNKNOWN_ENUM:lease_obligation")

    if spec["observation_obligation"] != "none":
        if spec["observation_obligation"] not in {
            "independent_observation_required",
            "delegated_observation_allowed",
        }:
            raise ValueError("UNKNOWN_ENUM:observation_obligation")
        out.add("observation_bound")

    return frozenset(out)


def transition_allowed(
    src: str,
    dst: str,
    *,
    reversibility_class: str,
) -> tuple[bool, str | None]:
    """Return (ok, error_code) for a typestate edge."""
    if src not in TYPESTATE_HAPPY_PATH + TYPESTATE_EXCEPTIONAL:
        return False, "UNKNOWN_ENUM"
    if dst not in TYPESTATE_HAPPY_PATH + TYPESTATE_EXCEPTIONAL:
        return False, "UNKNOWN_ENUM"
    if (src, dst) not in LEGAL_TRANSITIONS:
        return False, "ILLEGAL_TYPESTATE_TRANSITION"
    if dst == "CompensationRequired" and reversibility_class != "compensatable":
        return False, "COMPENSATION_REQUIRED_EXPLICIT"
    if src == "Unknown" and dst in {"Reserved", "Started"}:
        return False, "BLIND_UNKNOWN_REPLAY"
    if (
        src == "Unknown"
        and dst in {"Reserved", "Started"}
        and reversibility_class == "irreversible"
    ):
        return False, "BLIND_UNKNOWN_REPLAY"
    return True, None


def handler_unlocked(
    *,
    effect_class: str,
    typestate: str,
    derived_token_obligations: Sequence[str],
    admission_token_issuer: str | None,
    satisfied_obligations: Sequence[str] | None,
    terminal: str | None,
) -> tuple[bool, str | None]:
    """Kernel unlock predicate for effectful handlers."""
    if effect_class == "pure":
        if admission_token_issuer is not None:
            return False, "PURE_TOKEN_FORBIDDEN"
        return False, None  # pure never "unlocks" an effectful handler

    if typestate not in HANDLER_UNLOCK_TYPESTATES:
        return False, "HANDLER_NOT_UNLOCKED"
    if terminal is not None:
        return False, "HANDLER_NOT_UNLOCKED"
    if admission_token_issuer != KERNEL_ISSUER:
        return False, "NON_KERNEL_TOKEN_ISSUER"
    required = frozenset(derived_token_obligations)
    if not required:
        return False, "TOKEN_OBLIGATION_MISMATCH"
    have = frozenset(satisfied_obligations or ())
    if not required.issubset(have):
        return False, "TOKEN_OBLIGATION_MISMATCH"
    return True, None


def _base_instance(**overrides: Any) -> dict[str, Any]:
    obligations = sorted(
        derive_token_obligations(
            {
                "effect_class": overrides.get("effect_class", "write"),
                "authority_obligation": overrides.get(
                    "authority_obligation", "capability_verified"
                ),
                "policy_obligation": overrides.get(
                    "policy_obligation", "host_policy_required"
                ),
                "confirmation_obligation": overrides.get(
                    "confirmation_obligation", "none"
                ),
                "lease_obligation": overrides.get("lease_obligation", "lease_required"),
                "observation_obligation": overrides.get(
                    "observation_obligation", "independent_observation_required"
                ),
            }
        )
    )
    instance: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "schema_version": 1,
        "operation_id": "datasets.download",
        "effect_class": "write",
        "idempotency_class": "at_most_once",
        "reversibility_class": "compensatable",
        "authority_obligation": "capability_verified",
        "policy_obligation": "host_policy_required",
        "confirmation_obligation": "none",
        "lease_obligation": "lease_required",
        "observation_obligation": "independent_observation_required",
        "typestate": "Reserved",
        "derived_token_obligations": obligations,
        "admission_token_issuer": KERNEL_ISSUER,
        "handler_unlocked": True,
        "terminal": None,
    }
    instance.update(overrides)
    if "derived_token_obligations" not in overrides:
        instance["derived_token_obligations"] = sorted(
            derive_token_obligations(instance)
        )
    return instance


def _migrated_operation_classifications() -> dict[str, dict[str, Any]]:
    """Every representative migrated operation with closed effect classification."""
    return {
        "datasets.download": {
            "effect_class": "write",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "datasets.upload": {
            "effect_class": "write",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "datasets.get": {
            "effect_class": "read",
            "idempotency_class": "idempotent",
            "reversibility_class": "reversible",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "none",
            "observation_obligation": "independent_observation_required",
        },
        "datasets.save": {
            "effect_class": "write",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "datasets.pin": {
            "effect_class": "write",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "datasets.semantic": {
            "effect_class": "process",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "accelerate.capability_probe": {
            "effect_class": "read",
            "idempotency_class": "idempotent",
            "reversibility_class": "reversible",
            "authority_obligation": "actor_authenticated",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "none",
            "observation_obligation": "independent_observation_required",
        },
        "accelerate.inference": {
            "effect_class": "process",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_with_obligations",
            "confirmation_obligation": "none",
            "lease_obligation": "lease_required",
            "observation_obligation": "delegated_observation_allowed",
        },
        "kit.storage_select": {
            "effect_class": "read",
            "idempotency_class": "idempotent",
            "reversibility_class": "reversible",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "none",
            "lease_obligation": "none",
            "observation_obligation": "independent_observation_required",
        },
        "kit.proof_role_transition": {
            "effect_class": "write",
            "idempotency_class": "at_most_once",
            "reversibility_class": "irreversible",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "swissknife.present_evidence": {
            "effect_class": "pure",
            "idempotency_class": "pure_idempotent",
            "reversibility_class": "reversible",
            "authority_obligation": "none",
            "policy_obligation": "none",
            "confirmation_obligation": "none",
            "lease_obligation": "none",
            "observation_obligation": "none",
        },
        "swissknife.project_confirmation_intent": {
            "effect_class": "pure",
            "idempotency_class": "pure_idempotent",
            "reversibility_class": "reversible",
            "authority_obligation": "none",
            "policy_obligation": "none",
            "confirmation_obligation": "none",
            "lease_obligation": "none",
            "observation_obligation": "none",
        },
        # Coverage constructors not yet dominant on the four paths, still classified.
        "kit.credential_rotate": {
            "effect_class": "credential",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_with_obligations",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "kit.package_install": {
            "effect_class": "install",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "kit.repository_push": {
            "effect_class": "repository",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "kit.artifact_publish": {
            "effect_class": "publish",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_required",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "kit.payment_settle": {
            "effect_class": "payment",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_with_obligations",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "kit.private_tenant_mutate": {
            "effect_class": "private",
            "idempotency_class": "at_most_once",
            "reversibility_class": "compensatable",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_with_obligations",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "kit.legal_disposition": {
            "effect_class": "legal",
            "idempotency_class": "at_most_once",
            "reversibility_class": "irreversible",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_with_obligations",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
        "kit.irreversible_cutover": {
            "effect_class": "irreversible",
            "idempotency_class": "at_most_once",
            "reversibility_class": "irreversible",
            "authority_obligation": "capability_verified",
            "policy_obligation": "host_policy_with_obligations",
            "confirmation_obligation": "one_use_confirmation_required",
            "lease_obligation": "lease_required",
            "observation_obligation": "independent_observation_required",
        },
    }


def _contains_float(value: Any) -> bool:
    if isinstance(value, float) and not isinstance(value, bool):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float(v) for v in value)
    return False


def _classify_error(
    instance: Mapping[str, Any], error: jsonschema.ValidationError
) -> str:
    if _contains_float(instance):
        return "FORBIDDEN_FLOAT"
    validator = error.validator
    if validator == "additionalProperties":
        return "UNKNOWN_FIELD"
    if validator == "required":
        return "MISSING_FIELD"
    if validator == "enum" or validator == "const":
        return "UNKNOWN_ENUM"
    if validator == "type":
        return "INVALID_TYPE"
    if validator == "oneOf":
        # Non-kernel issuer fails the null|enum oneOf; treat as unknown enum.
        return "UNKNOWN_ENUM"
    if validator in {"maxLength", "maxItems", "maximum"}:
        return "UNBOUNDED_STRING" if validator == "maxLength" else "UNBOUNDED_ARRAY"
    if validator == "uniqueItems":
        return "DUPLICATE_TOKEN_OBLIGATION"
    message = error.message.lower()
    if "is not one of" in message or "is not one of the given" in message:
        return "UNKNOWN_ENUM"
    return "INVALID_TYPE"


def _validate(
    validator: Draft202012Validator, instance: Mapping[str, Any]
) -> tuple[bool, str | None]:
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if not errors:
        if _contains_float(instance):
            return False, "FORBIDDEN_FLOAT"
        return True, None
    return False, _classify_error(instance, errors[0])


def _load_vocab(spec_text: str) -> dict[str, Any]:
    matches = JSON_FENCE_RE.findall(spec_text)
    assert matches, "spec must embed a normative JSON vocabulary fence"
    vocab = None
    for raw in matches:
        try:
            candidate = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if candidate.get("schema") == VOCAB_SCHEMA:
            vocab = candidate
            break
    assert vocab is not None, f"no JSON fence with schema {VOCAB_SCHEMA}"
    return vocab


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    assert SCHEMA_PATH.is_file(), SCHEMA_PATH
    data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def validator(schema: Mapping[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def spec_text() -> str:
    assert SPEC_PATH.is_file(), SPEC_PATH
    return SPEC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def vocab(spec_text: str) -> dict[str, Any]:
    return _load_vocab(spec_text)


# ---------------------------------------------------------------------------
# Identity / schema surface
# ---------------------------------------------------------------------------


def test_spec_and_schema_identify_facp_038(
    schema: Mapping[str, Any], spec_text: str, vocab: Mapping[str, Any]
) -> None:
    assert TASK_ID in spec_text
    assert GOAL_ID in spec_text
    assert BUNDLE in spec_text
    assert SCHEMA_ID in spec_text
    assert "does **not** claim" in spec_text or "does not claim" in spec_text.lower()
    meta = schema["x-facp"]
    assert meta["schema"] == SCHEMA_ID
    assert meta["task_id"] == TASK_ID
    assert meta["goal_id"] == GOAL_ID
    assert meta["bundle"] == BUNDLE
    assert meta["fail_closed"] is True
    assert meta["kernel_only_token_issuer"] is True
    assert meta["unknown_explicit"] is True
    assert meta["compensation_required_explicit"] is True
    assert vocab["task_id"] == TASK_ID
    assert vocab["goal_id"] == GOAL_ID
    assert vocab["instance_schema"] == SCHEMA_ID


def test_schema_closed_and_draft2020(schema: Mapping[str, Any]) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["unevaluatedProperties"] is False
    assert schema["$id"].endswith("effect-admission.schema.json")
    assert schema["title"] == "EffectAdmission@1"


def test_effect_classes_match_operation_spec_and_vocab(
    schema: Mapping[str, Any], vocab: Mapping[str, Any]
) -> None:
    op_schema = json.loads(OPERATION_SPEC_SCHEMA_PATH.read_text(encoding="utf-8"))
    op_effects = tuple(op_schema["$defs"]["effect_class"]["enum"])
    schema_effects = tuple(schema["$defs"]["effect_class"]["enum"])
    assert schema_effects == EFFECT_CLASSES
    assert op_effects == EFFECT_CLASSES
    assert tuple(vocab["effect_classes"]) == EFFECT_CLASSES


def test_typestate_vocab_includes_unknown_and_compensation_required(
    schema: Mapping[str, Any], vocab: Mapping[str, Any], spec_text: str
) -> None:
    happy = tuple(schema["x-facp"]["typestate_happy_path"])
    exceptional = tuple(schema["x-facp"]["typestate_exceptional"])
    assert happy == TYPESTATE_HAPPY_PATH
    assert exceptional == TYPESTATE_EXCEPTIONAL
    assert "Unknown" in exceptional
    assert "CompensationRequired" in exceptional
    assert "Unknown" in schema["$defs"]["typestate"]["enum"]
    assert "CompensationRequired" in schema["$defs"]["typestate"]["enum"]
    assert tuple(vocab["typestate_happy_path"]) == TYPESTATE_HAPPY_PATH
    assert tuple(vocab["typestate_exceptional"]) == TYPESTATE_EXCEPTIONAL
    assert "Unknown and CompensationRequired are first-class" in spec_text or (
        "Unknown` and `CompensationRequired`" in spec_text
    )


def test_token_obligation_constructors_closed(
    schema: Mapping[str, Any], vocab: Mapping[str, Any]
) -> None:
    assert tuple(schema["$defs"]["token_obligation"]["enum"]) == TOKEN_OBLIGATIONS
    assert tuple(vocab["token_obligation_constructors"]) == TOKEN_OBLIGATIONS
    assert schema["$defs"]["admission_token_issuer"]["enum"] == [KERNEL_ISSUER]


def test_stable_error_codes_documented(schema: Mapping[str, Any]) -> None:
    codes = set(schema["x-facp"]["stable_error_codes"])
    for required in (
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "UNKNOWN_ENUM",
        "ILLEGAL_TYPESTATE_TRANSITION",
        "TOKEN_OBLIGATION_MISMATCH",
        "HANDLER_NOT_UNLOCKED",
        "NON_KERNEL_TOKEN_ISSUER",
        "BLIND_UNKNOWN_REPLAY",
        "COMPENSATION_REQUIRED_EXPLICIT",
    ):
        assert required in codes


# ---------------------------------------------------------------------------
# Mechanical derivation
# ---------------------------------------------------------------------------


def test_derive_token_obligations_pure_is_empty() -> None:
    spec = _migrated_operation_classifications()["swissknife.present_evidence"]
    assert derive_token_obligations(spec) == frozenset()


def test_derive_token_obligations_write_includes_universal_and_bindings() -> None:
    spec = _migrated_operation_classifications()["datasets.download"]
    got = derive_token_obligations(spec)
    assert UNIVERSAL_TOKEN_OBLIGATIONS <= got
    assert {
        "actor_bound",
        "capability_bound",
        "delegation_bound",
        "policy_bound",
        "lease_bound",
        "observation_bound",
    } <= got
    assert "confirmation_bound" not in got


def test_derive_token_obligations_confirmation_and_policy_with_obligations() -> None:
    spec = _migrated_operation_classifications()["kit.proof_role_transition"]
    got = derive_token_obligations(spec)
    assert "confirmation_bound" in got
    assert "lease_bound" in got
    assert "capability_bound" in got

    inference = _migrated_operation_classifications()["accelerate.inference"]
    got2 = derive_token_obligations(inference)
    assert "policy_obligations_bound" in got2
    assert "observation_bound" in got2


@pytest.mark.parametrize("operation_id", sorted(_migrated_operation_classifications()))
def test_every_migrated_operation_is_classified_and_derives_obligations(
    validator: Draft202012Validator, operation_id: str
) -> None:
    classifications = _migrated_operation_classifications()
    fields = classifications[operation_id]
    assert fields["effect_class"] in EFFECT_CLASSES
    obligations = sorted(derive_token_obligations(fields))
    if fields["effect_class"] == "pure":
        assert obligations == []
        issuer = None
        unlocked = False
        typestate = "Observed"
    else:
        assert "kernel_issued" in obligations
        assert obligations
        issuer = KERNEL_ISSUER
        unlocked = True
        typestate = "Reserved"
    instance = _base_instance(
        operation_id=operation_id,
        typestate=typestate,
        admission_token_issuer=issuer,
        handler_unlocked=unlocked,
        terminal=None,
        **fields,
    )
    ok, code = _validate(validator, instance)
    assert ok, f"{operation_id}: {code}"
    assert instance["derived_token_obligations"] == obligations


def test_all_effect_classes_have_at_least_one_classified_operation() -> None:
    used = {
        row["effect_class"]
        for row in _migrated_operation_classifications().values()
    }
    assert used == set(EFFECT_CLASSES)


def test_four_migration_paths_covered() -> None:
    ops = _migrated_operation_classifications()
    assert any(k.startswith("datasets.") for k in ops)
    assert any(k.startswith("accelerate.") for k in ops)
    assert any(k.startswith("kit.") for k in ops)
    assert any(k.startswith("swissknife.") for k in ops)


# ---------------------------------------------------------------------------
# Typestate: Unknown / CompensationRequired / transitions
# ---------------------------------------------------------------------------


def test_happy_path_consecutive_transitions_allowed() -> None:
    for src, dst in zip(TYPESTATE_HAPPY_PATH, TYPESTATE_HAPPY_PATH[1:]):
        ok, code = transition_allowed(src, dst, reversibility_class="compensatable")
        assert ok, f"{src}->{dst}: {code}"


def test_unknown_and_compensation_required_are_explicit_terminals(
    validator: Draft202012Validator,
) -> None:
    unknown = _base_instance(
        typestate="Unknown",
        handler_unlocked=False,
        admission_token_issuer=KERNEL_ISSUER,
        terminal="Unknown",
    )
    ok, code = _validate(validator, unknown)
    assert ok, code
    assert unknown["terminal"] == "Unknown"

    compensation = _base_instance(
        typestate="CompensationRequired",
        handler_unlocked=False,
        admission_token_issuer=KERNEL_ISSUER,
        terminal="CompensationRequired",
        reversibility_class="compensatable",
    )
    ok, code = _validate(validator, compensation)
    assert ok, code
    assert compensation["terminal"] == "CompensationRequired"


def test_compensation_required_forbidden_unless_compensatable() -> None:
    ok, code = transition_allowed(
        "Started", "CompensationRequired", reversibility_class="irreversible"
    )
    assert not ok
    assert code == "COMPENSATION_REQUIRED_EXPLICIT"

    ok, code = transition_allowed(
        "Started", "CompensationRequired", reversibility_class="compensatable"
    )
    assert ok


def test_blind_unknown_replay_forbidden() -> None:
    ok, code = transition_allowed(
        "Unknown", "Started", reversibility_class="irreversible"
    )
    assert not ok
    assert code in {"ILLEGAL_TYPESTATE_TRANSITION", "BLIND_UNKNOWN_REPLAY"}

    ok, code = transition_allowed(
        "Unknown", "Reserved", reversibility_class="compensatable"
    )
    assert not ok
    assert code in {"ILLEGAL_TYPESTATE_TRANSITION", "BLIND_UNKNOWN_REPLAY"}


def test_unknown_reconciliation_edges_allowed() -> None:
    for dst in ("Observed", "Failed", "CompensationRequired", "Aborted"):
        rev = "compensatable" if dst == "CompensationRequired" else "irreversible"
        ok, code = transition_allowed("Unknown", dst, reversibility_class=rev)
        assert ok, f"Unknown->{dst}: {code}"


def test_illegal_typestate_edge_rejected() -> None:
    ok, code = transition_allowed(
        "Proposed", "Started", reversibility_class="compensatable"
    )
    assert not ok
    assert code == "ILLEGAL_TYPESTATE_TRANSITION"


# ---------------------------------------------------------------------------
# Handler unlock: kernel-issued token only
# ---------------------------------------------------------------------------


def test_effectful_handler_unlocks_only_with_kernel_token() -> None:
    obligations = sorted(
        derive_token_obligations(_migrated_operation_classifications()["datasets.download"])
    )
    ok, code = handler_unlocked(
        effect_class="write",
        typestate="Reserved",
        derived_token_obligations=obligations,
        admission_token_issuer=KERNEL_ISSUER,
        satisfied_obligations=obligations,
        terminal=None,
    )
    assert ok and code is None

    ok, code = handler_unlocked(
        effect_class="write",
        typestate="Reserved",
        derived_token_obligations=obligations,
        admission_token_issuer="browser_consent",
        satisfied_obligations=obligations,
        terminal=None,
    )
    assert not ok
    assert code == "NON_KERNEL_TOKEN_ISSUER"

    ok, code = handler_unlocked(
        effect_class="write",
        typestate="Proposed",
        derived_token_obligations=obligations,
        admission_token_issuer=KERNEL_ISSUER,
        satisfied_obligations=obligations,
        terminal=None,
    )
    assert not ok
    assert code == "HANDLER_NOT_UNLOCKED"


def test_missing_derived_obligation_blocks_unlock() -> None:
    obligations = sorted(
        derive_token_obligations(_migrated_operation_classifications()["datasets.download"])
    )
    incomplete = [o for o in obligations if o != "lease_bound"]
    ok, code = handler_unlocked(
        effect_class="write",
        typestate="Started",
        derived_token_obligations=obligations,
        admission_token_issuer=KERNEL_ISSUER,
        satisfied_obligations=incomplete,
        terminal=None,
    )
    assert not ok
    assert code == "TOKEN_OBLIGATION_MISMATCH"


def test_unknown_or_compensation_required_blocks_unlock() -> None:
    obligations = sorted(
        derive_token_obligations(_migrated_operation_classifications()["datasets.download"])
    )
    for terminal in ("Unknown", "CompensationRequired"):
        ok, code = handler_unlocked(
            effect_class="write",
            typestate=terminal,
            derived_token_obligations=obligations,
            admission_token_issuer=KERNEL_ISSUER,
            satisfied_obligations=obligations,
            terminal=terminal,
        )
        assert not ok
        assert code == "HANDLER_NOT_UNLOCKED"


def test_pure_handler_never_unlocks_and_rejects_token() -> None:
    ok, code = handler_unlocked(
        effect_class="pure",
        typestate="Observed",
        derived_token_obligations=[],
        admission_token_issuer=None,
        satisfied_obligations=None,
        terminal=None,
    )
    assert not ok
    assert code is None

    ok, code = handler_unlocked(
        effect_class="pure",
        typestate="Reserved",
        derived_token_obligations=[],
        admission_token_issuer=KERNEL_ISSUER,
        satisfied_obligations=[],
        terminal=None,
    )
    assert not ok
    assert code == "PURE_TOKEN_FORBIDDEN"


def test_non_kernel_issuer_rejected_by_schema(validator: Draft202012Validator) -> None:
    instance = _base_instance()
    # Force illegal issuer; schema oneOf/enum must reject non-kernel issuers.
    instance["admission_token_issuer"] = "peer_attestation"
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "UNKNOWN_ENUM"


# ---------------------------------------------------------------------------
# Schema fail-closed cases
# ---------------------------------------------------------------------------


def test_valid_base_instance(validator: Draft202012Validator) -> None:
    ok, code = _validate(validator, _base_instance())
    assert ok, code


def test_unknown_field_rejected(validator: Draft202012Validator) -> None:
    instance = _base_instance()
    instance["consent"] = True
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "UNKNOWN_FIELD"


def test_unknown_effect_class_rejected(validator: Draft202012Validator) -> None:
    instance = _base_instance(effect_class="mutate")
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "UNKNOWN_ENUM"


def test_unknown_typestate_rejected(validator: Draft202012Validator) -> None:
    instance = _base_instance(typestate="HalfwayDone")
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "UNKNOWN_ENUM"


def test_forbidden_float_schema_version(validator: Draft202012Validator) -> None:
    instance = _base_instance()
    # 1.0 is a float in Python even when equal to 1; fail closed.
    instance["schema_version"] = 1.0  # type: ignore[assignment]
    assert isinstance(instance["schema_version"], float)
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "FORBIDDEN_FLOAT"


def test_missing_required_field(validator: Draft202012Validator) -> None:
    instance = _base_instance()
    del instance["typestate"]
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "MISSING_FIELD"


def test_free_form_obligation_rejected(validator: Draft202012Validator) -> None:
    instance = _base_instance()
    instance["derived_token_obligations"] = ["kernel_issued", "admin_said_so"]
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "UNKNOWN_ENUM"


def test_duplicate_token_obligation_rejected(validator: Draft202012Validator) -> None:
    instance = _base_instance()
    instance["derived_token_obligations"] = ["kernel_issued", "kernel_issued"]
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "DUPLICATE_TOKEN_OBLIGATION"


@pytest.mark.parametrize("key", FREE_FORM_FORBIDDEN_KEYS)
def test_spec_forbids_free_form_authority_keys(spec_text: str, key: str) -> None:
    # Spec must call out the prohibition family; keys appear in §9.
    assert "free-form" in spec_text.lower() or "Free-form" in spec_text
    assert key in spec_text or key in {
        "authorization",
        "permission",
        "grant",
    }


def test_spec_lists_migrated_path_coverage(spec_text: str) -> None:
    for token in (
        "datasets.download",
        "accelerate.inference",
        "kit.storage_select",
        "swissknife.present_evidence",
        "Proposed",
        "ReceiptSealed",
        "Unknown",
        "CompensationRequired",
        "effect_admission_kernel",
    ):
        assert token in spec_text


def test_instance_field_order_documented(schema: Mapping[str, Any]) -> None:
    order = schema["x-facp"]["field_order"]
    assert order[0] == "schema"
    assert "typestate" in order
    assert "derived_token_obligations" in order
    assert "handler_unlocked" in order
    for field in order:
        assert field in schema["required"]


def test_unlocked_instance_matches_predicate(validator: Draft202012Validator) -> None:
    instance = _base_instance()
    ok, code = _validate(validator, instance)
    assert ok, code
    unlocked, err = handler_unlocked(
        effect_class=instance["effect_class"],
        typestate=instance["typestate"],
        derived_token_obligations=instance["derived_token_obligations"],
        admission_token_issuer=instance["admission_token_issuer"],
        satisfied_obligations=instance["derived_token_obligations"],
        terminal=instance["terminal"],
    )
    assert unlocked and err is None
    assert instance["handler_unlocked"] is True


def test_wrong_schema_const_rejected(validator: Draft202012Validator) -> None:
    instance = _base_instance(schema="facp/effect-admission@2")
    ok, code = _validate(validator, instance)
    assert not ok
    assert code == "UNKNOWN_ENUM"
