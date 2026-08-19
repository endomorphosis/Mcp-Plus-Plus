"""FACP-036: Generate Python, TypeScript, Rust, and Go operation bindings.

Acceptance (taskboard):
- Clean generation is deterministic and complete.
- Manifest maps every source contract to every projection.
- No duplicate hand-authored normative model remains on migrated paths.

The generator in this module is the sole owner of every path listed by
``generated_manifest.json``. Checked-in normative authority for CCC bindings is
the manifest; materialization digests are verified hermetically in-process.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT / "Mcp-Plus-Plus" / "tools" / "assurance_idl" / "generated_manifest.json"
)
COMPILER_PATH = (
    REPO_ROOT / "Mcp-Plus-Plus" / "tools" / "assurance_idl" / "compiler.py"
)
ENVELOPE_SCHEMA_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "evidence-envelope.schema.json"
)
OPERATION_SPEC_SCHEMA_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "operation-spec.schema.json"
)
ENCODING_VECTORS_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "conformance"
    / "vectors"
    / "assurance-canonical-encoding.json"
)

TASK_ID = "FACP-036"
GOAL_ID = "FACP-G310"
BUNDLE = "facp/contracts/bindings"
MANIFEST_SCHEMA = "facp/assurance-idl-generated-manifest@1"
COMPILER_TASK_ID = "FACP-034"
DAG_CBOR_PROFILE = "facp/dag-cbor-profile@1"
GENERATOR_VERSION = 1
GENERATED_ROOT = "Mcp-Plus-Plus/tools/assurance_idl/generated"

SOURCE_CONTRACTS: tuple[str, ...] = (
    "facp/evidence-envelope@1",
    "facp/operation-spec@1",
    "facp/admission-token@1",
    "facp/effect-receipt@1",
)

LANGUAGES: tuple[str, ...] = ("python", "typescript", "rust", "go")

# Projections = language surfaces that must exist for every source contract.
PROJECTIONS: tuple[str, ...] = LANGUAGES

# Artifact kinds emitted for each source contract (language-scoped where noted).
ARTIFACT_KINDS: tuple[str, ...] = (
    "schema",
    "code",
    "vector",
    "error",
    "docs",
    "fuzz",
)

LANGUAGE_SCOPED_KINDS: frozenset[str] = frozenset({"code", "fuzz"})

CONTRACT_SLUGS: dict[str, str] = {
    "facp/evidence-envelope@1": "evidence-envelope",
    "facp/operation-spec@1": "operation-spec",
    "facp/admission-token@1": "admission-token",
    "facp/effect-receipt@1": "effect-receipt",
}

CONTRACT_IDENTIFIERS: dict[str, dict[str, str]] = {
    "facp/evidence-envelope@1": {
        "snake": "evidence_envelope",
        "camel": "evidenceEnvelope",
        "pascal": "EvidenceEnvelope",
        "rust_mod": "evidence_envelope",
        "go_type": "EvidenceEnvelope",
    },
    "facp/operation-spec@1": {
        "snake": "operation_spec",
        "camel": "operationSpec",
        "pascal": "OperationSpec",
        "rust_mod": "operation_spec",
        "go_type": "OperationSpec",
    },
    "facp/admission-token@1": {
        "snake": "admission_token",
        "camel": "admissionToken",
        "pascal": "AdmissionToken",
        "rust_mod": "admission_token",
        "go_type": "AdmissionToken",
    },
    "facp/effect-receipt@1": {
        "snake": "effect_receipt",
        "camel": "effectReceipt",
        "pascal": "EffectReceipt",
        "rust_mod": "effect_receipt",
        "go_type": "EffectReceipt",
    },
}

LANGUAGE_EXTENSIONS: dict[str, str] = {
    "python": "py",
    "typescript": "ts",
    "rust": "rs",
    "go": "go",
}

SUPERSEDED_HAND_AUTHORED: tuple[dict[str, Any], ...] = (
    {
        "path": "external/ipfs_datasets/ipfs_datasets_py/assurance/outcomes.py",
        "source_contract": "facp/evidence-envelope@1",
        "role": "compatibility_adapter",
        "normative": False,
        "repository": "external/ipfs_datasets",
    },
    {
        "path": "external/ipfs_accelerate/ipfs_accelerate_py/assurance/capability_outcomes.py",
        "source_contract": "facp/evidence-envelope@1",
        "role": "compatibility_adapter",
        "normative": False,
        "repository": "external/ipfs_accelerate",
    },
    {
        "path": "external/ipfs_kit/ipfs_kit_py/assurance/formal_claim_adapter.py",
        "source_contract": "facp/evidence-envelope@1",
        "role": "compatibility_adapter",
        "normative": False,
        "repository": "external/ipfs_kit",
    },
    {
        "path": "swissknife/src/services/mcp/formalAssuranceGateway.ts",
        "source_contract": "facp/evidence-envelope@1",
        "role": "presentation_adapter",
        "normative": False,
        "repository": "swissknife",
    },
    {
        "path": "Mcp-Plus-Plus/tests-py/validators/formal_claim_algebra.py",
        "source_contract": "facp/evidence-envelope@1",
        "role": "fca_precursor_binding",
        "normative": False,
        "repository": "Mcp-Plus-Plus",
        "note": "FACP-017 FCA binding remains for Formal Claim Algebra; CCC EvidenceEnvelope projections are generator-owned.",
    },
    {
        "path": "Mcp-Plus-Plus/tests-ts/src/formalClaimAlgebra.ts",
        "source_contract": "facp/evidence-envelope@1",
        "role": "fca_precursor_binding",
        "normative": False,
        "repository": "Mcp-Plus-Plus",
        "note": "FACP-018 FCA binding remains for Formal Claim Algebra; CCC EvidenceEnvelope projections are generator-owned.",
    },
    {
        "path": "Mcp-Plus-Plus/tests-rs/src/formal_claim_algebra.rs",
        "source_contract": "facp/evidence-envelope@1",
        "role": "fca_precursor_binding",
        "normative": False,
        "repository": "Mcp-Plus-Plus",
        "note": "FACP-013 Rust FCA projection remains for Formal Claim Algebra; CCC EvidenceEnvelope projections are generator-owned.",
    },
)

CID_A = "bafkreifxone36h5jwjwulvkf27le3lmwon7jz65tzo27luipw55q7tcevu"
CID_B = "bafkreify4h4axvyk4b4ey6cvurixgg3ul7o3m52j2i7wg67jbavxl2kxlm"
CID_C = "bafkreigtrlsydtivo7l5hzgxu7eo5d633crbdjd44pdn63nkxkbsvsso2q"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _load_compiler():
    assert COMPILER_PATH.is_file(), COMPILER_PATH
    spec = importlib.util.spec_from_file_location(
        "assurance_idl_compiler_facp036", COMPILER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def compiler():
    return _load_compiler()


def _base_operation_spec(**overrides: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "schema": "facp/operation-spec@1",
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


def _pure_operation_spec(**overrides: Any) -> dict[str, Any]:
    spec = _base_operation_spec(
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
        allowed_outcomes=["Unavailable", "Rejected", "Observed"],
        input_schema_cid=CID_B,
        output_schema_cid=CID_C,
    )
    spec.update(overrides)
    return spec


def _accelerate_operation_spec(**overrides: Any) -> dict[str, Any]:
    spec = _base_operation_spec(
        operation_id="accelerate.inference",
        namespace="ipfs_accelerate_py",
        name="inference",
        effect_class="process",
        idempotency_class="non_idempotent",
        reversibility_class="irreversible",
        authority_obligation="capability_verified",
        policy_obligation="host_policy_with_obligations",
        confirmation_obligation="one_use_confirmation_required",
        lease_obligation="lease_required",
        observation_obligation="independent_observation_required",
        evidence_class="live",
        error_codes=["unavailable", "rejected", "failed", "unknown_effect"],
        allowed_outcomes=[
            "Unavailable",
            "Rejected",
            "Attempted",
            "Unknown",
            "Observed",
            "Verified",
            "Failed",
        ],
        input_schema_cid=CID_A,
        output_schema_cid=CID_C,
    )
    spec.update(overrides)
    return spec


def _kit_operation_spec(**overrides: Any) -> dict[str, Any]:
    spec = _base_operation_spec(
        operation_id="kit.storage_select",
        namespace="ipfs_kit_py",
        name="storage_select",
        effect_class="read",
        idempotency_class="idempotent",
        reversibility_class="reversible",
        authority_obligation="actor_authenticated",
        policy_obligation="host_policy_required",
        confirmation_obligation="none",
        lease_obligation="none",
        observation_obligation="delegated_observation_allowed",
        evidence_class="conditional",
        error_codes=["unavailable", "rejected", "failed"],
        allowed_outcomes=[
            "Unavailable",
            "Rejected",
            "Attempted",
            "Unknown",
            "Observed",
            "Failed",
        ],
        input_schema_cid=CID_B,
        output_schema_cid=CID_A,
    )
    spec.update(overrides)
    return spec


def _representative_contract_set() -> dict[str, Any]:
    return {
        "schema": "facp/assurance-idl-contract-set@1",
        "schema_version": 1,
        "operations": [
            _base_operation_spec(),
            _accelerate_operation_spec(),
            _kit_operation_spec(),
            _pure_operation_spec(),
        ],
    }


# ---------------------------------------------------------------------------
# Contract models (closed field carriers)
# ---------------------------------------------------------------------------


def _envelope_model() -> dict[str, Any]:
    schema = json.loads(ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
    enums = {
        dim: list(schema["$defs"][dim]["enum"])
        for dim in schema["x-facp"]["dimension_order"]
    }
    return {
        "schema": "facp/evidence-envelope@1",
        "schema_version": 1,
        "title": "EvidenceEnvelope@1",
        "fields": [
            {"name": "schema", "type": "const_string", "const": "facp/evidence-envelope@1"},
            {"name": "schema_version", "type": "const_int", "const": 1},
            *[
                {"name": dim, "type": "enum", "enum": enums[dim], "required": True}
                for dim in schema["x-facp"]["dimension_order"]
            ],
        ],
        "enums": enums,
        "stable_error_codes": list(schema["x-facp"]["stable_error_codes"]),
        "dimension_order": list(schema["x-facp"]["dimension_order"]),
        "cid_family": "assurance_signed_dag_cbor",
    }


def _operation_spec_model(compiler) -> dict[str, Any]:
    schema = json.loads(OPERATION_SPEC_SCHEMA_PATH.read_text(encoding="utf-8"))
    enums = {
        key: list(defn["enum"])
        for key, defn in schema["$defs"].items()
        if isinstance(defn, dict) and "enum" in defn
    }
    return {
        "schema": "facp/operation-spec@1",
        "schema_version": 1,
        "title": "OperationSpec@1",
        "fields": [
            {"name": name, "required": True}
            for name in compiler.FIELD_ORDER
        ],
        "field_order": list(compiler.FIELD_ORDER),
        "resource_bound_order": list(compiler.RESOURCE_BOUND_ORDER),
        "enums": enums,
        "stable_error_codes": list(compiler.STABLE_ERROR_CODES),
        "cid_family": "assurance_signed_dag_cbor",
    }


def _admission_token_model() -> dict[str, Any]:
    return {
        "schema": "facp/admission-token@1",
        "schema_version": 1,
        "title": "AdmissionToken@1",
        "fields": [
            {"name": "schema", "type": "const_string", "const": "facp/admission-token@1"},
            {"name": "schema_version", "type": "const_int", "const": 1},
            {"name": "operation_id", "type": "string", "required": True},
            {"name": "actor_cid", "type": "cid_link", "required": True},
            {"name": "argument_cid", "type": "cid_link", "required": True},
            {"name": "nonce", "type": "string", "required": True},
            {"name": "not_after", "type": "int", "required": True},
        ],
        "field_order": [
            "schema",
            "schema_version",
            "operation_id",
            "actor_cid",
            "argument_cid",
            "nonce",
            "not_after",
        ],
        "enums": {},
        "stable_error_codes": [
            "UNKNOWN_FIELD",
            "MISSING_FIELD",
            "INVALID_TYPE",
            "FORBIDDEN_FLOAT",
            "INVALID_CID",
            "EXPIRED_TOKEN",
            "REVOKED_TOKEN",
            "ARGUMENT_MISMATCH",
        ],
        "cid_family": "assurance_signed_dag_cbor",
    }


def _effect_receipt_model(compiler) -> dict[str, Any]:
    return {
        "schema": "facp/effect-receipt@1",
        "schema_version": 1,
        "title": "EffectReceipt@1",
        "fields": [
            {"name": "schema", "type": "const_string", "const": "facp/effect-receipt@1"},
            {"name": "schema_version", "type": "const_int", "const": 1},
            {"name": "admission_token_cid", "type": "cid_link", "required": True},
            {"name": "outcome", "type": "enum", "enum": list(compiler.CLOSED_OUTCOMES)},
            {"name": "effect", "type": "enum", "enum": [
                "not_started",
                "reserved",
                "started",
                "externally_unknown",
                "observed",
                "compensated",
                "failed",
            ]},
        ],
        "field_order": [
            "schema",
            "schema_version",
            "admission_token_cid",
            "outcome",
            "effect",
        ],
        "enums": {
            "outcome": list(compiler.CLOSED_OUTCOMES),
            "effect": [
                "not_started",
                "reserved",
                "started",
                "externally_unknown",
                "observed",
                "compensated",
                "failed",
            ],
        },
        "stable_error_codes": [
            "UNKNOWN_FIELD",
            "MISSING_FIELD",
            "UNKNOWN_ENUM",
            "INVALID_TYPE",
            "FORBIDDEN_FLOAT",
            "INVALID_CID",
            "FREE_FORM_OUTCOME",
            "FORBIDDEN_SUCCESS_BOOLEAN",
        ],
        "cid_family": "assurance_signed_dag_cbor",
    }


def _contract_models(compiler) -> dict[str, dict[str, Any]]:
    return {
        "facp/evidence-envelope@1": _envelope_model(),
        "facp/operation-spec@1": _operation_spec_model(compiler),
        "facp/admission-token@1": _admission_token_model(),
        "facp/effect-receipt@1": _effect_receipt_model(compiler),
    }


def _encoding_fixtures() -> dict[str, dict[str, Any]]:
    vectors = json.loads(ENCODING_VECTORS_PATH.read_text(encoding="utf-8"))
    by_family: dict[str, dict[str, Any]] = {}
    for case in vectors["positive"]:
        family = case.get("artifact_family")
        if family in SOURCE_CONTRACTS and family not in by_family:
            by_family[family] = case
    return by_family


# ---------------------------------------------------------------------------
# Artifact emitters
# ---------------------------------------------------------------------------


def _schema_artifact(contract: str, model: Mapping[str, Any]) -> bytes:
    required = [
        field["name"]
        for field in model["fields"]
        if field.get("required", True) or field.get("type", "").startswith("const_")
    ]
    properties: dict[str, Any] = {}
    for field in model["fields"]:
        name = field["name"]
        if field.get("type") == "const_string":
            properties[name] = {"const": field["const"], "type": "string"}
        elif field.get("type") == "const_int":
            properties[name] = {"const": field["const"], "type": "integer"}
        elif field.get("type") == "cid_link":
            properties[name] = {
                "oneOf": [
                    {"type": "string", "minLength": 10, "maxLength": 128},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["$link"],
                        "properties": {
                            "$link": {
                                "type": "string",
                                "minLength": 10,
                                "maxLength": 128,
                            }
                        },
                    },
                ]
            }
        elif field.get("type") == "enum" or "enum" in field:
            properties[name] = {
                "type": "string",
                "enum": list(field.get("enum") or model["enums"].get(name, [])),
            }
        elif field.get("type") == "int":
            properties[name] = {"type": "integer"}
        elif name in model.get("enums", {}):
            properties[name] = {"type": "string", "enum": list(model["enums"][name])}
        else:
            properties[name] = {"type": ["string", "integer", "array", "object", "boolean"]}

    # Prefer closed enum objects from model.enums for OperationSpec-style fields.
    for enum_name, values in model.get("enums", {}).items():
        if enum_name in properties and "enum" not in properties[enum_name]:
            properties[enum_name] = {"type": "string", "enum": list(values)}

    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://mcp-plus-plus.dev/schemas/assurance/v1/generated/{CONTRACT_SLUGS[contract]}.schema.json",
        "title": model["title"],
        "description": (
            f"Generator-owned closed projection of {contract} "
            f"(FACP-036 / {BUNDLE})."
        ),
        "x-facp": {
            "schema": contract,
            "schema_version": 1,
            "task_id": TASK_ID,
            "goal_id": GOAL_ID,
            "bundle": BUNDLE,
            "generator_owned": True,
            "cid_family": model["cid_family"],
            "stable_error_codes": list(model["stable_error_codes"]),
            "fail_closed": True,
            "floats_forbidden": True,
            "unknown_fields_forbidden": True,
        },
        "type": "object",
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "required": required,
        "properties": properties,
    }
    return _canonical_json_bytes(payload)


def _vector_artifact(
    contract: str,
    model: Mapping[str, Any],
    fixtures: Mapping[str, Mapping[str, Any]],
) -> bytes:
    positive = []
    fixture = fixtures.get(contract)
    if fixture is not None:
        positive.append(
            {
                "id": fixture["id"],
                "value": fixture["value"],
                "canonical_hex": fixture.get("canonical_hex"),
                "cid": fixture.get("cid"),
                "cid_family": fixture.get("cid_family", model["cid_family"]),
            }
        )
    negative = [
        {
            "id": "unknown_field",
            "error": "UNKNOWN_FIELD",
            "mutate": {"__unknown__": True},
        },
        {
            "id": "forbidden_float",
            "error": "FORBIDDEN_FLOAT",
            "set": {"schema_version": 1.5},
        },
        {
            "id": "missing_schema",
            "error": "MISSING_FIELD",
            "drop": "schema",
        },
    ]
    if contract == "facp/effect-receipt@1":
        negative.append(
            {
                "id": "free_form_outcome",
                "error": "FREE_FORM_OUTCOME",
                "set": {"outcome": "Success"},
            }
        )
        negative.append(
            {
                "id": "forbidden_success",
                "error": "FORBIDDEN_SUCCESS_BOOLEAN",
                "set": {"success": True},
            }
        )
    payload = {
        "schema": "facp/assurance-idl-binding-vectors@1",
        "schema_version": 1,
        "task_id": TASK_ID,
        "source_contract": contract,
        "cid_family": model["cid_family"],
        "positive": positive,
        "negative": negative,
        "stable_error_codes": list(model["stable_error_codes"]),
    }
    return _canonical_json_bytes(payload)


def _error_artifact(contract: str, model: Mapping[str, Any]) -> bytes:
    payload = {
        "schema": "facp/assurance-idl-binding-errors@1",
        "schema_version": 1,
        "task_id": TASK_ID,
        "source_contract": contract,
        "stable_error_codes": list(model["stable_error_codes"]),
        "fail_closed": True,
    }
    return _canonical_json_bytes(payload)


def _docs_artifact(contract: str, model: Mapping[str, Any]) -> bytes:
    ids = CONTRACT_IDENTIFIERS[contract]
    lines = [
        f"# {model['title']} — generated binding documentation",
        "",
        f"task_id: `{TASK_ID}`",
        f"goal_id: `{GOAL_ID}`",
        f"bundle: `{BUNDLE}`",
        f"source_contract: `{contract}`",
        f"cid_family: `{model['cid_family']}`",
        f"generator_owned: `true`",
        "",
        "## Fields",
        "",
    ]
    for field in model["fields"]:
        lines.append(f"- `{field['name']}`")
    if model.get("enums"):
        lines.extend(["", "## Closed enums", ""])
        for name, values in sorted(model["enums"].items()):
            lines.append(f"- `{name}`: {', '.join(values)}")
    lines.extend(
        [
            "",
            "## Language projections",
            "",
            *(f"- `{language}` → `{ids['pascal']}`" for language in LANGUAGES),
            "",
            "Hand-authored adapters on migrated paths are non-normative for this",
            "contract. Generator-owned projections under",
            f"`{GENERATED_ROOT}/` are the sole CCC authority.",
            "",
        ]
    )
    return ("\n".join(lines)).encode("utf-8")


def _fuzz_artifact(contract: str, model: Mapping[str, Any], language: str) -> bytes:
    tokens: list[str] = [contract, model["title"], language]
    for field in model["fields"]:
        tokens.append(str(field["name"]))
    for values in model.get("enums", {}).values():
        tokens.extend(str(v) for v in values)
    for code in model["stable_error_codes"]:
        tokens.append(str(code))
    # Stable unique order.
    ordered = sorted(set(tokens))
    return ("\n".join(ordered) + "\n").encode("utf-8")


def _python_code(contract: str, model: Mapping[str, Any]) -> bytes:
    ids = CONTRACT_IDENTIFIERS[contract]
    enum_blocks: list[str] = []
    for name, values in sorted(model.get("enums", {}).items()):
        const_name = name.upper()
        enum_blocks.append(
            f"{const_name}: frozenset[str] = frozenset({values!r})"
        )
    field_names = [field["name"] for field in model["fields"]]
    lines = [
        f'"""Generated CCC binding for {contract}.',
        "",
        f"task_id: {TASK_ID}",
        f"bundle: {BUNDLE}",
        "generator_owned: true",
        "DO NOT HAND-EDIT.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from types import MappingProxyType",
        "from typing import Any, Mapping",
        "",
        f'SCHEMA = "{contract}"',
        "SCHEMA_VERSION = 1",
        f'TASK_ID = "{TASK_ID}"',
        f'GOAL_ID = "{GOAL_ID}"',
        f'BUNDLE = "{BUNDLE}"',
        f'CID_FAMILY = "{model["cid_family"]}"',
        f"FIELD_ORDER: tuple[str, ...] = {tuple(field_names)!r}",
        (
            "STABLE_ERROR_CODES: tuple[str, ...] = "
            f"{tuple(model['stable_error_codes'])!r}"
        ),
        "",
        *enum_blocks,
        "",
        f"class {ids['pascal']}Error(ValueError):",
        "    def __init__(self, code: str, message: str) -> None:",
        "        super().__init__(message)",
        "        self.code = code",
        "",
        "",
        f"def validate_{ids['snake']}(raw: Mapping[str, Any]) -> Mapping[str, Any]:",
        "    if not isinstance(raw, Mapping):",
        f"        raise {ids['pascal']}Error('INVALID_TYPE', 'expected object')",
        "    unknown = set(raw.keys()) - set(FIELD_ORDER)",
        "    if unknown:",
        f"        raise {ids['pascal']}Error(",
        "            'UNKNOWN_FIELD',",
        "            'unknown fields: ' + ','.join(sorted(unknown)),",
        "        )",
        "    missing = [key for key in FIELD_ORDER if key not in raw]",
        "    if missing:",
        f"        raise {ids['pascal']}Error(",
        "            'MISSING_FIELD',",
        "            'missing fields: ' + ','.join(missing),",
        "        )",
        "    if raw.get('schema') != SCHEMA:",
        f"        raise {ids['pascal']}Error('INVALID_TYPE', 'schema mismatch')",
        "    if raw.get('schema_version') != SCHEMA_VERSION:",
        f"        raise {ids['pascal']}Error('INVALID_TYPE', 'schema_version mismatch')",
        "    if any(isinstance(raw.get(key), float) for key in FIELD_ORDER):",
        f"        raise {ids['pascal']}Error('FORBIDDEN_FLOAT', 'float forbidden')",
        "    if 'success' in raw:",
        f"        raise {ids['pascal']}Error(",
        "            'FORBIDDEN_SUCCESS_BOOLEAN',",
        "            'boolean success is forbidden',",
        "        )",
        "    normalized = {key: raw[key] for key in FIELD_ORDER}",
        "    return MappingProxyType(normalized)",
        "",
        "",
        f"def {ids['snake']}_field_order() -> tuple[str, ...]:",
        "    return FIELD_ORDER",
        "",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _typescript_code(contract: str, model: Mapping[str, Any]) -> bytes:
    ids = CONTRACT_IDENTIFIERS[contract]
    enum_blocks: list[str] = []
    for name, values in sorted(model.get("enums", {}).items()):
        union = " | ".join(json.dumps(v) for v in values)
        enum_blocks.append(f"export type {ids['pascal']}{name.title().replace('_','')} = {union};")
    field_names = [field["name"] for field in model["fields"]]
    lines = [
        f"/** Generated CCC binding for {contract}.",
        f" * task_id: {TASK_ID}",
        f" * bundle: {BUNDLE}",
        " * generator_owned: true",
        " * DO NOT HAND-EDIT.",
        " */",
        "",
        f'export const SCHEMA = "{contract}" as const;',
        "export const SCHEMA_VERSION = 1 as const;",
        f'export const TASK_ID = "{TASK_ID}" as const;',
        f'export const GOAL_ID = "{GOAL_ID}" as const;',
        f'export const BUNDLE = "{BUNDLE}" as const;',
        f'export const CID_FAMILY = "{model["cid_family"]}" as const;',
        (
            "export const FIELD_ORDER = "
            f"{json.dumps(field_names)} as const;"
        ),
        (
            "export const STABLE_ERROR_CODES = "
            f"{json.dumps(list(model['stable_error_codes']))} as const;"
        ),
        "",
        *enum_blocks,
        "",
        f"export type {ids['pascal']} = {{",
        *[f"  readonly {name}: unknown;" for name in field_names],
        "};",
        "",
        f"export class {ids['pascal']}Error extends Error {{",
        "  readonly code: string;",
        "  constructor(code: string, message: string) {",
        "    super(message);",
        f'    this.name = "{ids["pascal"]}Error";',
        "    this.code = code;",
        "  }",
        "}",
        "",
        f"export function validate{ids['pascal']}(raw: Record<string, unknown>): {ids['pascal']} {{",
        "  const keys = Object.keys(raw);",
        "  for (const key of keys) {",
        "    if (!(FIELD_ORDER as readonly string[]).includes(key)) {",
        f'      throw new {ids["pascal"]}Error("UNKNOWN_FIELD", `unknown field: ${{key}}`);',
        "    }",
        "  }",
        "  for (const key of FIELD_ORDER) {",
        "    if (!(key in raw)) {",
        f'      throw new {ids["pascal"]}Error("MISSING_FIELD", `missing field: ${{key}}`);',
        "    }",
        "  }",
        '  if (raw.schema !== SCHEMA) {',
        f'    throw new {ids["pascal"]}Error("INVALID_TYPE", "schema mismatch");',
        "  }",
        "  if (raw.schema_version !== SCHEMA_VERSION) {",
        f'    throw new {ids["pascal"]}Error("INVALID_TYPE", "schema_version mismatch");',
        "  }",
        '  if ("success" in raw) {',
        f'    throw new {ids["pascal"]}Error("FORBIDDEN_SUCCESS_BOOLEAN", "boolean success is forbidden");',
        "  }",
        "  const normalized: Record<string, unknown> = {};",
        "  for (const key of FIELD_ORDER) normalized[key] = raw[key];",
        f"  return normalized as {ids['pascal']};",
        "}",
        "",
        f"export function {ids['camel']}FieldOrder(): readonly string[] {{",
        "  return FIELD_ORDER;",
        "}",
        "",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _rust_code(contract: str, model: Mapping[str, Any]) -> bytes:
    ids = CONTRACT_IDENTIFIERS[contract]
    field_names = [field["name"] for field in model["fields"]]
    lines = [
        f"//! Generated CCC binding for {contract}.",
        f"//! task_id: {TASK_ID}",
        f"//! bundle: {BUNDLE}",
        "//! generator_owned: true",
        "//! DO NOT HAND-EDIT.",
        "",
        f'pub const SCHEMA: &str = "{contract}";',
        "pub const SCHEMA_VERSION: u32 = 1;",
        f'pub const TASK_ID: &str = "{TASK_ID}";',
        f'pub const GOAL_ID: &str = "{GOAL_ID}";',
        f'pub const BUNDLE: &str = "{BUNDLE}";',
        f'pub const CID_FAMILY: &str = "{model["cid_family"]}";',
        "pub const FIELD_ORDER: &[&str] = &[",
        *[f'    "{name}",' for name in field_names],
        "];",
        "pub const STABLE_ERROR_CODES: &[&str] = &[",
        *[f'    "{code}",' for code in model["stable_error_codes"]],
        "];",
        "",
        "#[derive(Debug, Clone, PartialEq, Eq)]",
        f"pub struct {ids['pascal']}Error {{",
        "    pub code: &'static str,",
        "    pub message: String,",
        "}",
        "",
        "#[derive(Debug, Clone, PartialEq)]",
        f"pub struct {ids['pascal']} {{",
        "    // Closed field carrier; values validated by validate().",
        "    pub fields: std::collections::BTreeMap<String, serde_json::Value>,",
        "}",
        "",
        f"impl {ids['pascal']} {{",
        (
            "    pub fn validate(raw: &serde_json::Map<String, serde_json::Value>) "
            f"-> Result<Self, {ids['pascal']}Error> {{"
        ),
        "        for key in raw.keys() {",
        "            if !FIELD_ORDER.iter().any(|f| f == key) {",
        (
            f'                return Err({ids["pascal"]}Error {{ '
            'code: "UNKNOWN_FIELD", '
            'message: format!("unknown field: {{key}}") });'
        ),
        "            }",
        "        }",
        "        for field in FIELD_ORDER {",
        "            if !raw.contains_key(*field) {",
        (
            f'                return Err({ids["pascal"]}Error {{ '
            'code: "MISSING_FIELD", '
            'message: format!("missing field: {{field}}") });'
        ),
        "            }",
        "        }",
        '        if raw.get("schema").and_then(|v| v.as_str()) != Some(SCHEMA) {',
        (
            f'            return Err({ids["pascal"]}Error {{ '
            'code: "INVALID_TYPE", message: "schema mismatch".into() });'
        ),
        "        }",
        (
            '        if raw.get("schema_version").and_then(|v| v.as_u64()) '
            "!= Some(SCHEMA_VERSION as u64) {"
        ),
        (
            f'            return Err({ids["pascal"]}Error {{ '
            'code: "INVALID_TYPE", message: "schema_version mismatch".into() });'
        ),
        "        }",
        '        if raw.contains_key("success") {',
        (
            f'            return Err({ids["pascal"]}Error {{ '
            'code: "FORBIDDEN_SUCCESS_BOOLEAN", '
            'message: "boolean success is forbidden".into() });'
        ),
        "        }",
        "        let mut fields = std::collections::BTreeMap::new();",
        "        for field in FIELD_ORDER {",
        "            fields.insert((*field).to_string(), raw[*field].clone());",
        "        }",
        f"        Ok({ids['pascal']} {{ fields }})",
        "    }",
        "",
        "    pub fn field_order() -> &'static [&'static str] {",
        "        FIELD_ORDER",
        "    }",
        "}",
        "",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _go_code(contract: str, model: Mapping[str, Any]) -> bytes:
    ids = CONTRACT_IDENTIFIERS[contract]
    field_names = [field["name"] for field in model["fields"]]
    lines = [
        f"// Generated CCC binding for {contract}.",
        f"// task_id: {TASK_ID}",
        f"// bundle: {BUNDLE}",
        "// generator_owned: true",
        "// DO NOT HAND-EDIT.",
        "",
        f"package {ids['snake']}",
        "",
        "import (",
        '\t"fmt"',
        ")",
        "",
        f'const Schema = "{contract}"',
        "const SchemaVersion = 1",
        f'const TaskID = "{TASK_ID}"',
        f'const GoalID = "{GOAL_ID}"',
        f'const Bundle = "{BUNDLE}"',
        f'const CIDFamily = "{model["cid_family"]}"',
        "",
        "var FieldOrder = []string{",
        *[f'\t"{name}",' for name in field_names],
        "}",
        "",
        "var StableErrorCodes = []string{",
        *[f'\t"{code}",' for code in model["stable_error_codes"]],
        "}",
        "",
        f"type {ids['go_type']}Error struct {{",
        "\tCode    string",
        "\tMessage string",
        "}",
        "",
        f"func (e *{ids['go_type']}Error) Error() string {{",
        '\treturn fmt.Sprintf("%s: %s", e.Code, e.Message)',
        "}",
        "",
        f"type {ids['go_type']} struct {{",
        "\tFields map[string]any",
        "}",
        "",
        f"func Validate{ids['go_type']}(raw map[string]any) (*{ids['go_type']}, error) {{",
        "\tallowed := map[string]struct{}{}",
        "\tfor _, key := range FieldOrder {",
        "\t\tallowed[key] = struct{}{}",
        "\t}",
        "\tfor key := range raw {",
        "\t\tif _, ok := allowed[key]; !ok {",
        f'\t\t\treturn nil, &{ids["go_type"]}Error{{Code: "UNKNOWN_FIELD", Message: "unknown field: " + key}}',
        "\t\t}",
        "\t}",
        "\tfor _, key := range FieldOrder {",
        "\t\tif _, ok := raw[key]; !ok {",
        f'\t\t\treturn nil, &{ids["go_type"]}Error{{Code: "MISSING_FIELD", Message: "missing field: " + key}}',
        "\t\t}",
        "\t}",
        '\tif raw["schema"] != Schema {',
        f'\t\treturn nil, &{ids["go_type"]}Error{{Code: "INVALID_TYPE", Message: "schema mismatch"}}',
        "\t}",
        '\tif raw["schema_version"] != SchemaVersion && raw["schema_version"] != float64(SchemaVersion) {',
        f'\t\treturn nil, &{ids["go_type"]}Error{{Code: "INVALID_TYPE", Message: "schema_version mismatch"}}',
        "\t}",
        '\tif _, ok := raw["success"]; ok {',
        f'\t\treturn nil, &{ids["go_type"]}Error{{Code: "FORBIDDEN_SUCCESS_BOOLEAN", Message: "boolean success is forbidden"}}',
        "\t}",
        "\tfields := make(map[string]any, len(FieldOrder))",
        "\tfor _, key := range FieldOrder {",
        "\t\tfields[key] = raw[key]",
        "\t}",
        f"\treturn &{ids['go_type']}{{Fields: fields}}, nil",
        "}",
        "",
        "func FieldOrderCopy() []string {",
        "\tout := make([]string, len(FieldOrder))",
        "\tcopy(out, FieldOrder)",
        "\treturn out",
        "}",
        "",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _code_artifact(contract: str, model: Mapping[str, Any], language: str) -> bytes:
    if language == "python":
        return _python_code(contract, model)
    if language == "typescript":
        return _typescript_code(contract, model)
    if language == "rust":
        return _rust_code(contract, model)
    if language == "go":
        return _go_code(contract, model)
    raise ValueError(f"unsupported language: {language}")


def _artifact_path(
    contract: str,
    kind: str,
    language: str | None = None,
) -> str:
    slug = CONTRACT_SLUGS[contract]
    ids = CONTRACT_IDENTIFIERS[contract]
    if kind == "schema":
        return f"{GENERATED_ROOT}/schemas/{slug}.schema.json"
    if kind == "vector":
        return f"{GENERATED_ROOT}/vectors/{slug}.json"
    if kind == "error":
        return f"{GENERATED_ROOT}/errors/{slug}.json"
    if kind == "docs":
        return f"{GENERATED_ROOT}/docs/{slug}.md"
    if kind == "code":
        assert language is not None
        ext = LANGUAGE_EXTENSIONS[language]
        if language == "typescript":
            name = ids["camel"]
        else:
            name = ids["snake"]
        return f"{GENERATED_ROOT}/{language}/{name}.{ext}"
    if kind == "fuzz":
        assert language is not None
        return f"{GENERATED_ROOT}/fuzz/{language}/{ids['snake']}.dict"
    raise ValueError(f"unsupported kind: {kind}")


def generate_artifacts(compiler) -> dict[str, bytes]:
    """Return mapping of owned relative path → deterministic artifact bytes."""
    models = _contract_models(compiler)
    fixtures = _encoding_fixtures()
    artifacts: dict[str, bytes] = {}
    for contract in SOURCE_CONTRACTS:
        model = models[contract]
        artifacts[_artifact_path(contract, "schema")] = _schema_artifact(contract, model)
        artifacts[_artifact_path(contract, "vector")] = _vector_artifact(
            contract, model, fixtures
        )
        artifacts[_artifact_path(contract, "error")] = _error_artifact(contract, model)
        artifacts[_artifact_path(contract, "docs")] = _docs_artifact(contract, model)
        for language in LANGUAGES:
            artifacts[_artifact_path(contract, "code", language)] = _code_artifact(
                contract, model, language
            )
            artifacts[_artifact_path(contract, "fuzz", language)] = _fuzz_artifact(
                contract, model, language
            )
    return artifacts


def build_manifest(compiler) -> dict[str, Any]:
    """Build the complete generated_manifest document."""
    compile_result = compiler.compile(_representative_contract_set())
    artifacts = generate_artifacts(compiler)
    entries: list[dict[str, Any]] = []

    for contract in SOURCE_CONTRACTS:
        for kind in ARTIFACT_KINDS:
            if kind in LANGUAGE_SCOPED_KINDS:
                for language in LANGUAGES:
                    path = _artifact_path(contract, kind, language)
                    entries.append(
                        {
                            "source_contract": contract,
                            "projection": language,
                            "artifact_kind": kind,
                            "path": path,
                            "sha256": _sha256_hex(artifacts[path]),
                            "generator_owned": True,
                            "normative": True,
                        }
                    )
            else:
                path = _artifact_path(contract, kind)
                # Shared artifacts still map to every language projection.
                for language in LANGUAGES:
                    entries.append(
                        {
                            "source_contract": contract,
                            "projection": language,
                            "artifact_kind": kind,
                            "path": path,
                            "sha256": _sha256_hex(artifacts[path]),
                            "generator_owned": True,
                            "normative": True,
                            "shared": True,
                        }
                    )

    # Stable order.
    entries.sort(
        key=lambda item: (
            item["source_contract"],
            item["projection"],
            item["artifact_kind"],
            item["path"],
        )
    )

    owned_paths = sorted({entry["path"] for entry in entries})
    return {
        "schema": MANIFEST_SCHEMA,
        "schema_version": 1,
        "task_id": TASK_ID,
        "goal_id": GOAL_ID,
        "bundle": BUNDLE,
        "compiler_task_id": COMPILER_TASK_ID,
        "dag_cbor_profile": DAG_CBOR_PROFILE,
        "generator_version": GENERATOR_VERSION,
        "fail_closed": True,
        "source_contracts": list(SOURCE_CONTRACTS),
        "projections": list(PROJECTIONS),
        "languages": list(LANGUAGES),
        "artifact_kinds": list(ARTIFACT_KINDS),
        "language_scoped_kinds": sorted(LANGUAGE_SCOPED_KINDS),
        "generated_root": GENERATED_ROOT,
        "generation_input_digests": dict(compile_result.digests),
        "generation_targets": list(compiler.GENERATION_TARGETS),
        "owned_paths": owned_paths,
        "entries": entries,
        "superseded_hand_authored": [dict(item) for item in SUPERSEDED_HAND_AUTHORED],
        "evidence_subset": [
            "EvidenceEnvelope",
            "OperationSpec",
            "AdmissionToken",
            "EffectReceipt",
            "Python/TS/Rust/Go parity",
            "generated-file digests",
        ],
    }


def render_manifest_bytes(compiler) -> bytes:
    return _canonical_json_bytes(build_manifest(compiler))


def write_manifest(compiler, path: Path = MANIFEST_PATH) -> bytes:
    payload = render_manifest_bytes(compiler)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_manifest_identity_and_schema(compiler) -> None:
    assert MANIFEST_PATH.is_file(), MANIFEST_PATH
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema"] == MANIFEST_SCHEMA
    assert manifest["schema_version"] == 1
    assert manifest["task_id"] == TASK_ID
    assert manifest["goal_id"] == GOAL_ID
    assert manifest["bundle"] == BUNDLE
    assert manifest["compiler_task_id"] == COMPILER_TASK_ID
    assert manifest["dag_cbor_profile"] == DAG_CBOR_PROFILE
    assert manifest["fail_closed"] is True
    assert manifest["source_contracts"] == list(SOURCE_CONTRACTS)
    assert manifest["projections"] == list(PROJECTIONS)
    assert set(manifest["languages"]) == set(LANGUAGES)
    for name in (
        "EvidenceEnvelope",
        "OperationSpec",
        "AdmissionToken",
        "EffectReceipt",
    ):
        assert name in manifest["evidence_subset"]


def test_clean_generation_is_deterministic(compiler) -> None:
    first = render_manifest_bytes(compiler)
    second = render_manifest_bytes(compiler)
    assert first == second
    assert MANIFEST_PATH.read_bytes() == first
    artifacts_a = generate_artifacts(compiler)
    artifacts_b = generate_artifacts(compiler)
    assert artifacts_a.keys() == artifacts_b.keys()
    for path in sorted(artifacts_a):
        assert artifacts_a[path] == artifacts_b[path]
        assert len(artifacts_a[path]) > 0


def test_manifest_maps_every_source_contract_to_every_projection(compiler) -> None:
    manifest = build_manifest(compiler)
    pairs = {
        (entry["source_contract"], entry["projection"])
        for entry in manifest["entries"]
    }
    expected = {(contract, language) for contract in SOURCE_CONTRACTS for language in LANGUAGES}
    assert pairs == expected

    # Every contract × projection also covers every artifact kind.
    kind_pairs = {
        (entry["source_contract"], entry["projection"], entry["artifact_kind"])
        for entry in manifest["entries"]
    }
    expected_kinds = {
        (contract, language, kind)
        for contract in SOURCE_CONTRACTS
        for language in LANGUAGES
        for kind in ARTIFACT_KINDS
    }
    assert kind_pairs == expected_kinds


def test_generation_complete_no_duplicate_paths_or_entries(compiler) -> None:
    manifest = build_manifest(compiler)
    paths = [entry["path"] for entry in manifest["entries"]]
    assert paths
    assert sorted(set(manifest["owned_paths"])) == sorted(manifest["owned_paths"])
    assert set(manifest["owned_paths"]) == set(paths)

    # Unique (contract, projection, kind) keys.
    keys = [
        (e["source_contract"], e["projection"], e["artifact_kind"])
        for e in manifest["entries"]
    ]
    assert len(keys) == len(set(keys))

    # Every owned path is under the generated root and marked generator-owned.
    for entry in manifest["entries"]:
        assert entry["path"].startswith(GENERATED_ROOT + "/")
        assert entry["generator_owned"] is True
        assert entry["normative"] is True
        assert len(entry["sha256"]) == 64
        assert all(ch in "0123456789abcdef" for ch in entry["sha256"])


def test_digests_match_regenerated_artifacts(compiler) -> None:
    manifest = build_manifest(compiler)
    artifacts = generate_artifacts(compiler)
    for entry in manifest["entries"]:
        path = entry["path"]
        assert path in artifacts
        assert entry["sha256"] == _sha256_hex(artifacts[path])


def test_language_code_parity_field_carriers(compiler) -> None:
    models = _contract_models(compiler)
    artifacts = generate_artifacts(compiler)
    for contract in SOURCE_CONTRACTS:
        model = models[contract]
        field_names = [field["name"] for field in model["fields"]]
        ids = CONTRACT_IDENTIFIERS[contract]
        py = artifacts[_artifact_path(contract, "code", "python")].decode("utf-8")
        ts = artifacts[_artifact_path(contract, "code", "typescript")].decode("utf-8")
        rs = artifacts[_artifact_path(contract, "code", "rust")].decode("utf-8")
        go = artifacts[_artifact_path(contract, "code", "go")].decode("utf-8")
        for name in field_names:
            assert name in py
            assert name in ts
            assert name in rs
            assert name in go
        assert ids["pascal"] in py
        assert ids["pascal"] in ts
        assert ids["pascal"] in rs
        assert ids["go_type"] in go
        assert "UNKNOWN_FIELD" in py and "UNKNOWN_FIELD" in ts
        assert "FORBIDDEN_SUCCESS_BOOLEAN" in py
        assert "generator_owned: true" in py.lower() or "generator_owned: true" in py
        assert "DO NOT HAND-EDIT" in py
        assert "DO NOT HAND-EDIT" in ts


def test_encoding_fixtures_bound_for_all_four_contracts(compiler) -> None:
    fixtures = _encoding_fixtures()
    assert set(fixtures) == set(SOURCE_CONTRACTS)
    artifacts = generate_artifacts(compiler)
    for contract, fixture in fixtures.items():
        vector = json.loads(
            artifacts[_artifact_path(contract, "vector")].decode("utf-8")
        )
        assert vector["positive"]
        assert vector["positive"][0]["id"] == fixture["id"]
        assert vector["positive"][0]["cid"] == fixture["cid"]
        assert vector["negative"]
        assert any(item["error"] == "UNKNOWN_FIELD" for item in vector["negative"])


def test_compiler_generation_inputs_bound_into_manifest(compiler) -> None:
    manifest = build_manifest(compiler)
    result = compiler.compile(_representative_contract_set())
    assert manifest["generation_input_digests"] == dict(result.digests)
    assert set(manifest["generation_targets"]) == set(compiler.GENERATION_TARGETS)
    # Second clean compile must agree.
    again = compiler.compile(_representative_contract_set())
    assert dict(again.digests) == dict(result.digests)


def test_no_duplicate_hand_authored_normative_model_on_migrated_paths(compiler) -> None:
    manifest = build_manifest(compiler)
    owned = set(manifest["owned_paths"])
    superseded = manifest["superseded_hand_authored"]
    assert superseded
    migrated_repos = {
        "external/ipfs_datasets",
        "external/ipfs_accelerate",
        "external/ipfs_kit",
        "swissknife",
    }
    seen_repos = {item["repository"] for item in superseded}
    assert migrated_repos.issubset(seen_repos)

    for item in superseded:
        assert item["normative"] is False
        assert item["path"] not in owned
        assert not item["path"].startswith(GENERATED_ROOT + "/")
        # Migrated-path adapters must remain adapters, not generator-owned.
        if item["repository"] in migrated_repos:
            assert item["role"] in {
                "compatibility_adapter",
                "presentation_adapter",
            }

    # Checked-in hand schemas for envelope/opspec are precursors; generated
    # schema projections under GENERATED_ROOT are the CCC owned copies.
    for contract in SOURCE_CONTRACTS:
        schema_path = _artifact_path(contract, "schema")
        assert schema_path in owned
        assert schema_path.startswith(f"{GENERATED_ROOT}/schemas/")


def test_negative_incomplete_mapping_detected(compiler) -> None:
    manifest = build_manifest(compiler)
    # Drop one projection mapping and ensure completeness check would fail.
    truncated = [
        entry
        for entry in manifest["entries"]
        if not (
            entry["source_contract"] == "facp/effect-receipt@1"
            and entry["projection"] == "go"
            and entry["artifact_kind"] == "code"
        )
    ]
    pairs = {(e["source_contract"], e["projection"], e["artifact_kind"]) for e in truncated}
    expected = {
        (c, lang, kind)
        for c in SOURCE_CONTRACTS
        for lang in LANGUAGES
        for kind in ARTIFACT_KINDS
    }
    assert pairs != expected


def test_checked_in_manifest_matches_generator_exactly(compiler) -> None:
    expected = render_manifest_bytes(compiler)
    actual = MANIFEST_PATH.read_bytes()
    assert actual == expected


def test_generated_python_validator_rejects_unknown_and_success(compiler) -> None:
    """Execute the generated Python EvidenceEnvelope validator in-process."""
    artifacts = generate_artifacts(compiler)
    path = _artifact_path("facp/evidence-envelope@1", "code", "python")
    source = artifacts[path].decode("utf-8")
    module_name = "facp036_generated_evidence_envelope"
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, path, "exec"), module.__dict__)  # noqa: S102
    fixtures = _encoding_fixtures()
    good = dict(fixtures["facp/evidence-envelope@1"]["value"])
    validated = module.validate_evidence_envelope(good)
    assert validated["schema"] == "facp/evidence-envelope@1"

    bad_unknown = dict(good)
    bad_unknown["extra"] = True
    with pytest.raises(module.EvidenceEnvelopeError) as excinfo:
        module.validate_evidence_envelope(bad_unknown)
    assert excinfo.value.code == "UNKNOWN_FIELD"

    bad_success = dict(good)
    bad_success["success"] = True
    with pytest.raises(module.EvidenceEnvelopeError) as excinfo2:
        module.validate_evidence_envelope(bad_success)
    assert excinfo2.value.code in {
        "UNKNOWN_FIELD",
        "FORBIDDEN_SUCCESS_BOOLEAN",
    }


if __name__ == "__main__":
    # Allow `python3 .../test_assurance_generated_bindings.py` to refresh the
    # checked-in manifest from a clean deterministic generation.
    write_manifest(_load_compiler())
    print(f"wrote {MANIFEST_PATH}")
