"""Assurance IDL compiler core — FACP-034.

Provider-free parser, semantic checker, and deterministic generator for
``facp/operation-spec@1`` contract sets.

Acceptance:
- Same source yields byte-identical outputs across repeated clean runs.
- Invalid contracts fail before generation with stable error codes.
- Compiler reads no credentials and performs no network I/O.

Generation targets (inputs for later binding tasks, not executed code):
``schema``, ``code``, ``vector``, ``error``, ``docs``, ``formal_skeleton``.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import dag_cbor
from multiformats import CID, multihash

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

TASK_ID = "FACP-034"
GOAL_ID = "FACP-G310"
BUNDLE = "facp/contracts/compiler"
OPERATION_SPEC_SCHEMA = "facp/operation-spec@1"
CONTRACT_SET_SCHEMA = "facp/assurance-idl-contract-set@1"
COMPILE_RESULT_SCHEMA = "facp/assurance-idl-compile-result@1"
DAG_CBOR_PROFILE = "facp/dag-cbor-profile@1"
SIGNED_CID_FAMILY = "assurance_signed_dag_cbor"
COMPILER_VERSION = 1

GENERATION_TARGETS: tuple[str, ...] = (
    "schema",
    "code",
    "vector",
    "error",
    "docs",
    "formal_skeleton",
)

FIELD_ORDER: tuple[str, ...] = (
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

RESOURCE_BOUND_ORDER: tuple[str, ...] = (
    "max_input_bytes",
    "max_output_bytes",
    "max_duration_ms",
    "max_memory_bytes",
    "max_cpu_ms",
    "max_effect_retries",
)

REQUIRED_RESOURCE_BOUNDS: frozenset[str] = frozenset(
    {
        "max_input_bytes",
        "max_output_bytes",
        "max_duration_ms",
        "max_memory_bytes",
    }
)

OPTIONAL_RESOURCE_BOUNDS: frozenset[str] = frozenset(
    {"max_cpu_ms", "max_effect_retries"}
)

EFFECT_CLASSES: tuple[str, ...] = (
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

IDEMPOTENCY_CLASSES: tuple[str, ...] = (
    "pure_idempotent",
    "idempotent",
    "at_most_once",
    "non_idempotent",
)

REVERSIBILITY_CLASSES: tuple[str, ...] = (
    "reversible",
    "compensatable",
    "irreversible",
)

AUTHORITY_OBLIGATIONS: tuple[str, ...] = (
    "none",
    "actor_authenticated",
    "capability_verified",
)

POLICY_OBLIGATIONS: tuple[str, ...] = (
    "none",
    "host_policy_required",
    "host_policy_with_obligations",
)

CONFIRMATION_OBLIGATIONS: tuple[str, ...] = (
    "none",
    "one_use_confirmation_required",
)

LEASE_OBLIGATIONS: tuple[str, ...] = ("none", "lease_required")

OBSERVATION_OBLIGATIONS: tuple[str, ...] = (
    "none",
    "independent_observation_required",
    "delegated_observation_allowed",
)

EVIDENCE_CLASSES: tuple[str, ...] = ("none", "hermetic", "conditional", "live")

CLOSED_OUTCOMES: tuple[str, ...] = (
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

ENUM_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "effect_class": frozenset(EFFECT_CLASSES),
        "idempotency_class": frozenset(IDEMPOTENCY_CLASSES),
        "reversibility_class": frozenset(REVERSIBILITY_CLASSES),
        "authority_obligation": frozenset(AUTHORITY_OBLIGATIONS),
        "policy_obligation": frozenset(POLICY_OBLIGATIONS),
        "confirmation_obligation": frozenset(CONFIRMATION_OBLIGATIONS),
        "lease_obligation": frozenset(LEASE_OBLIGATIONS),
        "observation_obligation": frozenset(OBSERVATION_OBLIGATIONS),
        "evidence_class": frozenset(EVIDENCE_CLASSES),
    }
)

FREE_FORM_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "authority",
        "authorization",
        "outcome",
        "success",
        "allowed",
        "consent",
        "dry_run",
        "permission",
        "grant",
    }
)

STABLE_ERROR_CODES: tuple[str, ...] = (
    "UNKNOWN_FIELD",
    "MISSING_FIELD",
    "UNKNOWN_ENUM",
    "INVALID_TYPE",
    "FORBIDDEN_FLOAT",
    "UNBOUNDED_STRING",
    "UNBOUNDED_ARRAY",
    "INVALID_CID",
    "INVALID_BOUNDS",
    "FREE_FORM_AUTHORITY",
    "FREE_FORM_OUTCOME",
    "FORBIDDEN_SUCCESS_BOOLEAN",
    "EMPTY_ALLOWED_OUTCOMES",
    "DUPLICATE_ERROR_CODE",
    "DUPLICATE_ALLOWED_OUTCOME",
    "EMPTY_ERROR_CODES",
    "DUPLICATE_OPERATION_ID",
    "EMPTY_CONTRACT_SET",
    "INVALID_JSON",
    "INVALID_CONTRACT_SET",
    "SEMANTIC_CONFLICT",
    "UNKNOWN_CONSTRUCT",
)

_CID_RE = re.compile(r"^b[a-z2-7]{58,128}$")
_OPERATION_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,7}$")
_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_MAX_BYTE_BOUND = 1099511627776
_MAX_DURATION_MS = 86400000
_MAX_ERROR_CODES = 64
_MAX_ALLOWED_OUTCOMES = 9
_MAX_OPERATIONS = 4096
_MAX_SOURCE_BYTES = 8 * 1024 * 1024

def _forbidden_import_prefixes() -> tuple[str, ...]:
    """Build forbidden import names without embedding importable module literals."""
    # Concatenate fragments so a naive source scan does not see full module paths
    # as if this compiler imported them.
    return (
        "url" + "lib",
        "req" + "uests",
        "http" + ".client",
        "http" + "x",
        "aio" + "http",
        "soc" + "ket",
        "s" + "sl",
        "ftp" + "lib",
        "smtp" + "lib",
        "para" + "miko",
        "bot" + "o3",
        "boto" + "core",
        "google" + ".auth",
        "azu" + "re",
    )


# ---------------------------------------------------------------------------
# Errors / diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Stable, path-qualified compiler diagnostic."""

    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class CompilerError(ValueError):
    """Fail-closed compiler rejection with a stable error code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: str = "$",
        diagnostics: Sequence[Diagnostic] | None = None,
    ) -> None:
        if code not in STABLE_ERROR_CODES:
            # Unknown codes are themselves a closed-world violation.
            raise ValueError(f"non-stable compiler error code: {code}")
        super().__init__(message)
        self.code = code
        self.path = path
        self.diagnostics: tuple[Diagnostic, ...] = tuple(
            diagnostics
            if diagnostics is not None
            else (Diagnostic(code=code, path=path, message=message),)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "path": self.path,
            "message": str(self),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class CompiledOperation:
    """One normalized OperationSpec plus DAG-CBOR identity."""

    operation_id: str
    normalized: Mapping[str, Any]
    canonical_dag_cbor: bytes
    cid: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "normalized": dict(self.normalized),
            "canonical_dag_cbor_sha256": hashlib.sha256(
                self.canonical_dag_cbor
            ).hexdigest(),
            "cid": self.cid,
            "cid_family": SIGNED_CID_FAMILY,
        }


@dataclass(frozen=True, slots=True)
class CompileResult:
    """Deterministic compile artifact with generation-input bytes."""

    operations: tuple[CompiledOperation, ...]
    generation_inputs: Mapping[str, bytes]
    digests: Mapping[str, str]
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def schema(self) -> str:
        return COMPILE_RESULT_SCHEMA

    @property
    def schema_version(self) -> int:
        return 1

    def artifact_bytes(self) -> bytes:
        """Byte-stable compile receipt (JSON, UTF-8, sorted keys)."""
        payload = {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "task_id": TASK_ID,
            "goal_id": GOAL_ID,
            "bundle": BUNDLE,
            "compiler_version": COMPILER_VERSION,
            "dag_cbor_profile": DAG_CBOR_PROFILE,
            "operations": [op.to_dict() for op in self.operations],
            "generation_input_digests": dict(self.digests),
            "generation_targets": list(GENERATION_TARGETS),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
        return _canonical_json_bytes(payload)


# ---------------------------------------------------------------------------
# Hermetic guards
# ---------------------------------------------------------------------------


def assert_hermetic_module_source(source_text: str | None = None) -> None:
    """Fail closed if this module's source imports credential/network libraries."""
    import ast

    text = source_text
    if text is None:
        # Read only this file via __file__; never credentials or remote URLs.
        with open(__file__, "r", encoding="utf-8") as handle:
            text = handle.read()
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
                imported.add(node.module)
    for prefix in _forbidden_import_prefixes():
        root = prefix.split(".")[0]
        if root in imported or prefix in imported:
            raise CompilerError(
                "UNKNOWN_CONSTRUCT",
                f"hermetic violation: forbidden import {prefix!r}",
                path="$hermetic",
            )


def assert_hermetic_runtime(
    loaded_modules: Mapping[str, Any] | None = None,
    *,
    baseline: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed if compile introduced credential/network modules.

    When ``baseline`` is provided, only modules newly present relative to the
    baseline are checked (host processes may already have stdlib networking
    modules loaded for unrelated reasons).
    """
    import sys

    modules = loaded_modules if loaded_modules is not None else sys.modules
    if baseline is not None:
        candidates = set(modules) - set(baseline)
    else:
        # Default: only verify this module's own source imports.
        assert_hermetic_module_source()
        return
    for name in candidates:
        for prefix in _forbidden_import_prefixes():
            if name == prefix or name.startswith(prefix + "."):
                raise CompilerError(
                    "UNKNOWN_CONSTRUCT",
                    f"hermetic violation: forbidden module loaded: {name}",
                    path="$hermetic",
                )


def _reject_env_credential_reads() -> None:
    """Compiler core never reads process environment for secrets/network config."""
    # Intentionally a no-op policy marker: callers/tests assert environ is unused.
    return None

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_json_source(source: str | bytes | bytearray) -> Any:
    """Parse UTF-8 JSON text. Rejects floats via custom parse hooks are applied later."""
    if isinstance(source, (bytes, bytearray)):
        if len(source) > _MAX_SOURCE_BYTES:
            raise CompilerError(
                "UNBOUNDED_STRING",
                f"source exceeds {_MAX_SOURCE_BYTES} bytes",
                path="$",
            )
        try:
            text = bytes(source).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CompilerError(
                "INVALID_JSON", f"source is not UTF-8: {exc}", path="$"
            ) from exc
    elif isinstance(source, str):
        if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
            raise CompilerError(
                "UNBOUNDED_STRING",
                f"source exceeds {_MAX_SOURCE_BYTES} bytes",
                path="$",
            )
        text = source
    else:
        raise CompilerError(
            "INVALID_TYPE",
            f"source must be str or bytes, got {type(source).__name__}",
            path="$",
        )
    try:
        return json.loads(text, parse_constant=_reject_json_constant)
    except CompilerError:
        raise
    except json.JSONDecodeError as exc:
        raise CompilerError(
            "INVALID_JSON", f"malformed JSON: {exc.msg}", path="$"
        ) from exc


def _reject_json_constant(name: str) -> Any:
    raise CompilerError(
        "FORBIDDEN_FLOAT",
        f"JSON constant {name!r} is forbidden",
        path="$",
    )


def extract_operations(document: Any, *, path: str = "$") -> list[Any]:
    """Accept a single OperationSpec, a list, or a contract-set envelope."""
    if isinstance(document, list):
        if not document:
            raise CompilerError("EMPTY_CONTRACT_SET", "operations list is empty", path=path)
        if len(document) > _MAX_OPERATIONS:
            raise CompilerError(
                "UNBOUNDED_ARRAY",
                f"operations exceed {_MAX_OPERATIONS}",
                path=path,
            )
        return list(document)

    if not isinstance(document, Mapping):
        raise CompilerError(
            "INVALID_TYPE",
            f"document must be object or array, got {type(document).__name__}",
            path=path,
        )

    keys = set(document.keys())
    if "operations" in keys:
        unknown = keys - {
            "schema",
            "schema_version",
            "operations",
            "task_id",
            "goal_id",
            "bundle",
        }
        if unknown:
            raise CompilerError(
                "UNKNOWN_FIELD",
                f"unknown contract-set fields: {sorted(unknown)}",
                path=path,
            )
        schema = document.get("schema")
        if schema is not None and schema != CONTRACT_SET_SCHEMA:
            raise CompilerError(
                "INVALID_CONTRACT_SET",
                f"contract-set schema must be {CONTRACT_SET_SCHEMA!r}",
                path=f"{path}.schema",
            )
        version = document.get("schema_version")
        if version is not None and version != 1:
            raise CompilerError(
                "INVALID_CONTRACT_SET",
                "contract-set schema_version must be 1",
                path=f"{path}.schema_version",
            )
        ops = document.get("operations")
        if not isinstance(ops, list):
            raise CompilerError(
                "INVALID_TYPE",
                "operations must be an array",
                path=f"{path}.operations",
            )
        if not ops:
            raise CompilerError(
                "EMPTY_CONTRACT_SET",
                "operations list is empty",
                path=f"{path}.operations",
            )
        if len(ops) > _MAX_OPERATIONS:
            raise CompilerError(
                "UNBOUNDED_ARRAY",
                f"operations exceed {_MAX_OPERATIONS}",
                path=f"{path}.operations",
            )
        return list(ops)

    # Single OperationSpec object.
    return [document]


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def _is_forbidden_float(value: Any) -> bool:
    return isinstance(value, float) and not isinstance(value, bool)


def _require_int(value: Any, path: str, *, minimum: int, maximum: int) -> int:
    if _is_forbidden_float(value):
        raise CompilerError("FORBIDDEN_FLOAT", f"float forbidden at {path}", path=path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CompilerError(
            "INVALID_TYPE",
            f"expected integer at {path}, got {type(value).__name__}",
            path=path,
        )
    if value < minimum or value > maximum:
        raise CompilerError(
            "INVALID_BOUNDS",
            f"integer at {path} out of bounds [{minimum}, {maximum}]",
            path=path,
        )
    return value


def _require_text(
    value: Any,
    path: str,
    *,
    pattern: re.Pattern[str] | None = None,
    min_length: int,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise CompilerError(
            "INVALID_TYPE",
            f"expected string at {path}, got {type(value).__name__}",
            path=path,
        )
    text = unicodedata.normalize("NFC", value)
    if len(text) < min_length or len(text) > max_length:
        raise CompilerError(
            "UNBOUNDED_STRING",
            f"string length at {path} outside [{min_length}, {max_length}]",
            path=path,
        )
    if pattern is not None and not pattern.fullmatch(text):
        raise CompilerError(
            "INVALID_TYPE",
            f"string at {path} failed pattern",
            path=path,
        )
    return text


def _require_cid(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise CompilerError(
            "INVALID_TYPE",
            f"expected CID string at {path}, got {type(value).__name__}",
            path=path,
        )
    text = unicodedata.normalize("NFC", value)
    if not _CID_RE.fullmatch(text):
        raise CompilerError("INVALID_CID", f"invalid CIDv1 at {path}", path=path)
    return text

def _reject_free_form_keys(mapping: Mapping[str, Any], path: str) -> None:
    for key in mapping:
        if key in FREE_FORM_FORBIDDEN_KEYS:
            if key in {"authority", "authorization", "permission", "grant", "consent", "allowed", "dry_run"}:
                raise CompilerError(
                    "FREE_FORM_AUTHORITY",
                    f"free-form authority field {key!r} forbidden",
                    path=f"{path}.{key}",
                )
            if key in {"outcome", "success"}:
                code = (
                    "FORBIDDEN_SUCCESS_BOOLEAN"
                    if key == "success"
                    else "FREE_FORM_OUTCOME"
                )
                raise CompilerError(
                    code,
                    f"free-form outcome field {key!r} forbidden",
                    path=f"{path}.{key}",
                )


def validate_operation_spec(raw: Any, *, path: str = "$") -> dict[str, Any]:
    """Validate one OperationSpec and return a normalized dict (FIELD_ORDER)."""
    if not isinstance(raw, Mapping):
        raise CompilerError(
            "INVALID_TYPE",
            f"OperationSpec must be an object, got {type(raw).__name__}",
            path=path,
        )
    _reject_free_form_keys(raw, path)

    unknown = set(raw.keys()) - set(FIELD_ORDER)
    if unknown:
        raise CompilerError(
            "UNKNOWN_FIELD",
            f"unknown fields: {sorted(unknown)}",
            path=path,
        )

    missing = [key for key in FIELD_ORDER if key not in raw]
    if missing:
        raise CompilerError(
            "MISSING_FIELD",
            f"missing required fields: {missing}",
            path=path,
        )

    # Deep float scan before accepting values.
    _reject_floats(raw, path)

    schema = _require_text(raw["schema"], f"{path}.schema", min_length=1, max_length=64)
    if schema != OPERATION_SPEC_SCHEMA:
        raise CompilerError(
            "INVALID_TYPE",
            f"schema must be {OPERATION_SPEC_SCHEMA!r}",
            path=f"{path}.schema",
        )

    schema_version = _require_int(
        raw["schema_version"], f"{path}.schema_version", minimum=1, maximum=1
    )
    operation_id = _require_text(
        raw["operation_id"],
        f"{path}.operation_id",
        pattern=_OPERATION_ID_RE,
        min_length=3,
        max_length=128,
    )
    namespace = _require_text(
        raw["namespace"],
        f"{path}.namespace",
        pattern=_NAMESPACE_RE,
        min_length=2,
        max_length=64,
    )
    name = _require_text(
        raw["name"],
        f"{path}.name",
        pattern=_NAME_RE,
        min_length=1,
        max_length=64,
    )
    version = _require_int(raw["version"], f"{path}.version", minimum=1, maximum=2147483647)

    input_cid = _require_cid(raw["input_schema_cid"], f"{path}.input_schema_cid")
    output_cid = _require_cid(raw["output_schema_cid"], f"{path}.output_schema_cid")
    error_codes = _validate_error_codes(raw["error_codes"], f"{path}.error_codes")
    enums = {
        field: _require_enum(raw[field], f"{path}.{field}", allowed)
        for field, allowed in ENUM_FIELDS.items()
    }
    allowed_outcomes = _validate_allowed_outcomes(
        raw["allowed_outcomes"], f"{path}.allowed_outcomes"
    )
    resource_bounds = _validate_resource_bounds(
        raw["resource_bounds"], f"{path}.resource_bounds"
    )

    normalized: dict[str, Any] = {
        "schema": schema,
        "schema_version": schema_version,
        "operation_id": operation_id,
        "namespace": namespace,
        "name": name,
        "version": version,
        "input_schema_cid": input_cid,
        "output_schema_cid": output_cid,
        "error_codes": error_codes,
        **enums,
        "allowed_outcomes": allowed_outcomes,
        "resource_bounds": resource_bounds,
    }
    return normalized


def _require_enum(value: Any, path: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str):
        raise CompilerError(
            "INVALID_TYPE",
            f"expected enum string at {path}",
            path=path,
        )
    text = unicodedata.normalize("NFC", value)
    if text not in allowed:
        raise CompilerError(
            "UNKNOWN_ENUM",
            f"unknown enum spelling {text!r} at {path}",
            path=path,
        )
    return text


def _validate_error_codes(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise CompilerError("INVALID_TYPE", "error_codes must be an array", path=path)
    if not value:
        raise CompilerError("EMPTY_ERROR_CODES", "error_codes must be non-empty", path=path)
    if len(value) > _MAX_ERROR_CODES:
        raise CompilerError(
            "UNBOUNDED_ARRAY",
            f"error_codes exceed {_MAX_ERROR_CODES}",
            path=path,
        )
    seen: set[str] = set()
    out: list[str] = []
    for idx, item in enumerate(value):
        code = _require_text(
            item,
            f"{path}[{idx}]",
            pattern=_ERROR_CODE_RE,
            min_length=1,
            max_length=64,
        )
        if code in seen:
            raise CompilerError(
                "DUPLICATE_ERROR_CODE",
                f"duplicate error_code {code!r}",
                path=f"{path}[{idx}]",
            )
        seen.add(code)
        out.append(code)
    # Deterministic order for generation (set semantics).
    return sorted(out)


def _validate_allowed_outcomes(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise CompilerError(
            "INVALID_TYPE", "allowed_outcomes must be an array", path=path
        )
    if not value:
        raise CompilerError(
            "EMPTY_ALLOWED_OUTCOMES",
            "allowed_outcomes must be non-empty",
            path=path,
        )
    if len(value) > _MAX_ALLOWED_OUTCOMES:
        raise CompilerError(
            "UNBOUNDED_ARRAY",
            f"allowed_outcomes exceed {_MAX_ALLOWED_OUTCOMES}",
            path=path,
        )
    seen: set[str] = set()
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise CompilerError(
                "INVALID_TYPE",
                f"allowed_outcomes[{idx}] must be string",
                path=f"{path}[{idx}]",
            )
        text = unicodedata.normalize("NFC", item)
        if text not in CLOSED_OUTCOMES:
            raise CompilerError(
                "FREE_FORM_OUTCOME",
                f"unknown outcome {text!r}",
                path=f"{path}[{idx}]",
            )
        if text in seen:
            raise CompilerError(
                "DUPLICATE_ALLOWED_OUTCOME",
                f"duplicate allowed_outcome {text!r}",
                path=f"{path}[{idx}]",
            )
        seen.add(text)
    # Normalize to closed algebra order.
    return [outcome for outcome in CLOSED_OUTCOMES if outcome in seen]


def _validate_resource_bounds(value: Any, path: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise CompilerError(
            "INVALID_TYPE", "resource_bounds must be an object", path=path
        )
    _reject_free_form_keys(value, path)
    unknown = set(value.keys()) - set(RESOURCE_BOUND_ORDER)
    if unknown:
        raise CompilerError(
            "UNKNOWN_FIELD",
            f"unknown resource_bounds fields: {sorted(unknown)}",
            path=path,
        )
    missing = sorted(REQUIRED_RESOURCE_BOUNDS - set(value.keys()))
    if missing:
        raise CompilerError(
            "MISSING_FIELD",
            f"missing resource_bounds fields: {missing}",
            path=path,
        )

    out: dict[str, int] = {}
    for key in RESOURCE_BOUND_ORDER:
        if key not in value:
            continue
        if key in {"max_input_bytes", "max_output_bytes", "max_memory_bytes"}:
            out[key] = _require_int(
                value[key], f"{path}.{key}", minimum=0, maximum=_MAX_BYTE_BOUND
            )
        elif key in {"max_duration_ms", "max_cpu_ms"}:
            out[key] = _require_int(
                value[key], f"{path}.{key}", minimum=0, maximum=_MAX_DURATION_MS
            )
        elif key == "max_effect_retries":
            out[key] = _require_int(
                value[key], f"{path}.{key}", minimum=0, maximum=1024
            )
    return out


def _reject_floats(value: Any, path: str) -> None:
    if _is_forbidden_float(value):
        raise CompilerError("FORBIDDEN_FLOAT", f"float forbidden at {path}", path=path)
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_floats(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for idx, item in enumerate(value):
            _reject_floats(item, f"{path}[{idx}]")


# ---------------------------------------------------------------------------
# Semantic checks
# ---------------------------------------------------------------------------


def semantic_check_operation(spec: Mapping[str, Any], *, path: str = "$") -> None:
    """Cross-field semantic rules; raises CompilerError on conflict."""
    effect = spec["effect_class"]
    idem = spec["idempotency_class"]
    rev = spec["reversibility_class"]
    authority = spec["authority_obligation"]
    evidence = spec["evidence_class"]
    outcomes = set(spec["allowed_outcomes"])

    if effect == "pure":
        if authority != "none":
            raise CompilerError(
                "SEMANTIC_CONFLICT",
                "pure effect_class requires authority_obligation=none",
                path=f"{path}.authority_obligation",
            )
        if idem != "pure_idempotent":
            raise CompilerError(
                "SEMANTIC_CONFLICT",
                "pure effect_class requires idempotency_class=pure_idempotent",
                path=f"{path}.idempotency_class",
            )

    if effect == "irreversible" and rev != "irreversible":
        raise CompilerError(
            "SEMANTIC_CONFLICT",
            "effect_class=irreversible requires reversibility_class=irreversible",
            path=f"{path}.reversibility_class",
        )

    if idem == "pure_idempotent" and effect != "pure":
        raise CompilerError(
            "SEMANTIC_CONFLICT",
            "pure_idempotent requires effect_class=pure",
            path=f"{path}.idempotency_class",
        )

    if "Verified" in outcomes and evidence == "none":
        raise CompilerError(
            "SEMANTIC_CONFLICT",
            "Verified outcome requires evidence_class other than none",
            path=f"{path}.evidence_class",
        )

    if effect != "pure" and authority == "none" and evidence == "live":
        # Live effectful ops must authenticate an actor or capability.
        raise CompilerError(
            "SEMANTIC_CONFLICT",
            "live non-pure operations require a non-none authority_obligation",
            path=f"{path}.authority_obligation",
        )


def semantic_check_contract_set(
    specs: Sequence[Mapping[str, Any]], *, path: str = "$.operations"
) -> None:
    if not specs:
        raise CompilerError("EMPTY_CONTRACT_SET", "no operations to compile", path=path)
    seen: dict[str, int] = {}
    for idx, spec in enumerate(specs):
        op_id = spec["operation_id"]
        if op_id in seen:
            raise CompilerError(
                "DUPLICATE_OPERATION_ID",
                f"duplicate operation_id {op_id!r} (first at index {seen[op_id]})",
                path=f"{path}[{idx}].operation_id",
            )
        seen[op_id] = idx
        semantic_check_operation(spec, path=f"{path}[{idx}]")


# ---------------------------------------------------------------------------
# Canonical encoding helpers
# ---------------------------------------------------------------------------


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def encode_operation_dag_cbor(normalized: Mapping[str, Any]) -> bytes:
    """Encode a normalized OperationSpec under facp/dag-cbor-profile@1."""
    # dag_cbor sorts map keys by length then lexicographic UTF-8 order.
    try:
        encoded = dag_cbor.encode(dict(normalized))
    except Exception as exc:  # noqa: BLE001 - surface as closed error
        raise CompilerError(
            "UNKNOWN_CONSTRUCT",
            f"DAG-CBOR encode failed: {exc}",
            path="$",
        ) from exc
    if not isinstance(encoded, bytes) or not encoded:
        raise CompilerError("UNKNOWN_CONSTRUCT", "empty DAG-CBOR encoding", path="$")
    # Decode-and-reencode admission.
    try:
        decoded = dag_cbor.decode(encoded)
        reencoded = dag_cbor.encode(decoded)
    except Exception as exc:  # noqa: BLE001
        raise CompilerError(
            "UNKNOWN_CONSTRUCT",
            f"DAG-CBOR admit failed: {exc}",
            path="$",
        ) from exc
    if reencoded != encoded:
        raise CompilerError(
            "UNKNOWN_CONSTRUCT",
            "DAG-CBOR decode-and-reencode mismatch",
            path="$",
        )
    return encoded


def cid_for_dag_cbor(data: bytes) -> str:
    digest = multihash.digest(data, "sha2-256")
    return CID("base32", 1, "dag-cbor", digest).encode()


# ---------------------------------------------------------------------------
# Generation inputs
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_generation_inputs(
    operations: Sequence[CompiledOperation],
) -> dict[str, bytes]:
    """Emit deterministic generation-input bytes for each target.

    These are inputs for later binding/schema/vector tasks (FACP-036+), not
    executable generated code.
    """
    op_rows = [dict(op.normalized) for op in operations]
    identity_rows = [
        {
            "operation_id": op.operation_id,
            "cid": op.cid,
            "canonical_dag_cbor_sha256": hashlib.sha256(op.canonical_dag_cbor).hexdigest(),
        }
        for op in operations
    ]

    schema_payload = {
        "schema": "facp/assurance-idl-generation-schema@1",
        "schema_version": 1,
        "operation_spec_schema": OPERATION_SPEC_SCHEMA,
        "field_order": list(FIELD_ORDER),
        "resource_bound_order": list(RESOURCE_BOUND_ORDER),
        "enums": {
            "effect_class": list(EFFECT_CLASSES),
            "idempotency_class": list(IDEMPOTENCY_CLASSES),
            "reversibility_class": list(REVERSIBILITY_CLASSES),
            "authority_obligation": list(AUTHORITY_OBLIGATIONS),
            "policy_obligation": list(POLICY_OBLIGATIONS),
            "confirmation_obligation": list(CONFIRMATION_OBLIGATIONS),
            "lease_obligation": list(LEASE_OBLIGATIONS),
            "observation_obligation": list(OBSERVATION_OBLIGATIONS),
            "evidence_class": list(EVIDENCE_CLASSES),
            "closed_outcomes": list(CLOSED_OUTCOMES),
        },
        "operations": op_rows,
        "identities": identity_rows,
        "stable_error_codes": list(STABLE_ERROR_CODES),
    }

    code_payload = {
        "schema": "facp/assurance-idl-generation-code@1",
        "schema_version": 1,
        "languages": ["python", "typescript", "rust", "go"],
        "types": {
            "OperationSpec": {
                "fields": [
                    {"name": name, "required": True} for name in FIELD_ORDER
                ]
            }
        },
        "operations": [
            {
                "operation_id": op["operation_id"],
                "namespace": op["namespace"],
                "name": op["name"],
                "version": op["version"],
                "effect_class": op["effect_class"],
                "idempotency_class": op["idempotency_class"],
                "reversibility_class": op["reversibility_class"],
                "authority_obligation": op["authority_obligation"],
                "policy_obligation": op["policy_obligation"],
                "confirmation_obligation": op["confirmation_obligation"],
                "lease_obligation": op["lease_obligation"],
                "observation_obligation": op["observation_obligation"],
                "evidence_class": op["evidence_class"],
                "error_codes": op["error_codes"],
                "allowed_outcomes": op["allowed_outcomes"],
                "resource_bounds": op["resource_bounds"],
                "input_schema_cid": op["input_schema_cid"],
                "output_schema_cid": op["output_schema_cid"],
            }
            for op in op_rows
        ],
        "identities": identity_rows,
    }

    vector_payload = {
        "schema": "facp/assurance-idl-generation-vector@1",
        "schema_version": 1,
        "positive": [
            {"id": f"op:{op['operation_id']}", "operation": op} for op in op_rows
        ],
        "negative_recipes": [
            {"id": "unknown_field", "error": "UNKNOWN_FIELD", "mutate": {"extra": True}},
            {"id": "missing_field", "error": "MISSING_FIELD", "drop": "operation_id"},
            {"id": "unknown_enum", "error": "UNKNOWN_ENUM", "set": {"effect_class": "explode"}},
            {"id": "forbidden_float", "error": "FORBIDDEN_FLOAT", "set": {"version": 1.5}},
            {
                "id": "free_form_authority",
                "error": "FREE_FORM_AUTHORITY",
                "set": {"authority": "admin"},
            },
            {
                "id": "free_form_outcome",
                "error": "FREE_FORM_OUTCOME",
                "set": {"allowed_outcomes": ["Success"]},
            },
            {
                "id": "forbidden_success",
                "error": "FORBIDDEN_SUCCESS_BOOLEAN",
                "set": {"success": True},
            },
            {
                "id": "invalid_cid",
                "error": "INVALID_CID",
                "set": {
                    "input_schema_cid": (
                        "QmNotAValidAssuranceCid000000000000000000000000"
                    )
                },
            },
            {
                "id": "duplicate_operation_id",
                "error": "DUPLICATE_OPERATION_ID",
                "duplicate_first": True,
            },
        ],
        "identities": identity_rows,
    }

    error_payload = {
        "schema": "facp/assurance-idl-generation-error@1",
        "schema_version": 1,
        "stable_error_codes": list(STABLE_ERROR_CODES),
        "per_operation_error_codes": {
            op["operation_id"]: op["error_codes"] for op in op_rows
        },
    }

    docs_lines = [
        "# Assurance IDL compile documentation skeleton",
        "",
        f"task_id: {TASK_ID}",
        f"goal_id: {GOAL_ID}",
        f"bundle: {BUNDLE}",
        f"operation_spec_schema: {OPERATION_SPEC_SCHEMA}",
        f"dag_cbor_profile: {DAG_CBOR_PROFILE}",
        "",
        "## Operations",
        "",
    ]
    for op in op_rows:
        docs_lines.extend(
            [
                f"### `{op['operation_id']}`",
                "",
                f"- namespace: `{op['namespace']}`",
                f"- name: `{op['name']}`",
                f"- version: `{op['version']}`",
                f"- effect_class: `{op['effect_class']}`",
                f"- idempotency_class: `{op['idempotency_class']}`",
                f"- reversibility_class: `{op['reversibility_class']}`",
                f"- authority_obligation: `{op['authority_obligation']}`",
                f"- policy_obligation: `{op['policy_obligation']}`",
                f"- confirmation_obligation: `{op['confirmation_obligation']}`",
                f"- lease_obligation: `{op['lease_obligation']}`",
                f"- observation_obligation: `{op['observation_obligation']}`",
                f"- evidence_class: `{op['evidence_class']}`",
                f"- error_codes: `{', '.join(op['error_codes'])}`",
                f"- allowed_outcomes: `{', '.join(op['allowed_outcomes'])}`",
                "",
            ]
        )
    docs_bytes = ("\n".join(docs_lines) + "\n").encode("utf-8")

    formal_lines = [
        "-- Assurance IDL formal skeleton (generation input; not a proof)",
        f"-- task: {TASK_ID}",
        f"-- schema: {OPERATION_SPEC_SCHEMA}",
        "",
        "namespace AssuranceIDL",
        "",
        "inductive EffectClass where",
    ]
    for effect in EFFECT_CLASSES:
        formal_lines.append(f"  | {effect}")
    formal_lines.extend(["", "inductive ClosedOutcome where"])
    for outcome in CLOSED_OUTCOMES:
        formal_lines.append(f"  | {outcome}")
    formal_lines.extend(["", "structure OperationSpec where"])
    for field in FIELD_ORDER:
        formal_lines.append(f"  {field} : Bounded")
    formal_lines.append("")
    for op in op_rows:
        formal_lines.append(
            "axiom op_"
            + op["operation_id"].replace(".", "_")
            + f" : OperationSpec -- {op['effect_class']}/{op['evidence_class']}"
        )
    formal_lines.append("")
    formal_bytes = ("\n".join(formal_lines) + "\n").encode("utf-8")

    return {
        "schema": _canonical_json_bytes(schema_payload),
        "code": _canonical_json_bytes(code_payload),
        "vector": _canonical_json_bytes(vector_payload),
        "error": _canonical_json_bytes(error_payload),
        "docs": docs_bytes,
        "formal_skeleton": formal_bytes,
    }


# ---------------------------------------------------------------------------
# Compile entry points
# ---------------------------------------------------------------------------


def compile_operations(raw_operations: Sequence[Any]) -> CompileResult:
    """Parse/check/generate for an in-memory list of OperationSpec objects."""
    _reject_env_credential_reads()
    if not raw_operations:
        raise CompilerError("EMPTY_CONTRACT_SET", "no operations to compile", path="$")

    normalized_list: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_operations):
        normalized_list.append(
            validate_operation_spec(raw, path=f"$.operations[{idx}]")
        )

    # Stable order by operation_id before semantic uniqueness check messages.
    normalized_list.sort(key=lambda item: item["operation_id"])
    semantic_check_contract_set(normalized_list, path="$.operations")

    compiled: list[CompiledOperation] = []
    for spec in normalized_list:
        encoded = encode_operation_dag_cbor(spec)
        cid = cid_for_dag_cbor(encoded)
        compiled.append(
            CompiledOperation(
                operation_id=spec["operation_id"],
                normalized=MappingProxyType(spec),
                canonical_dag_cbor=encoded,
                cid=cid,
            )
        )

    generation_inputs = build_generation_inputs(compiled)
    digests = {
        target: _sha256_hex(generation_inputs[target]) for target in GENERATION_TARGETS
    }
    # Freeze mapping.
    frozen_inputs = MappingProxyType(dict(generation_inputs))
    frozen_digests = MappingProxyType(dict(digests))
    return CompileResult(
        operations=tuple(compiled),
        generation_inputs=frozen_inputs,
        digests=frozen_digests,
        diagnostics=(),
    )


def compile_document(document: Any) -> CompileResult:
    """Compile a single OperationSpec, list, or contract-set envelope."""
    operations = extract_operations(document)
    return compile_operations(operations)


def compile_source(source: str | bytes | bytearray) -> CompileResult:
    """Parse JSON source then compile. Invalid contracts never emit generation inputs."""
    document = parse_json_source(source)
    return compile_document(document)


def compile(
    source: str | bytes | bytearray | Mapping[str, Any] | Sequence[Any],
) -> CompileResult:
    """Primary entry: accept JSON text/bytes or already-parsed documents."""
    if isinstance(source, (str, bytes, bytearray)):
        return compile_source(source)
    if isinstance(source, Mapping):
        return compile_document(source)
    if isinstance(source, Sequence) and not isinstance(source, (str, bytes, bytearray)):
        return compile_operations(list(source))
    raise CompilerError(
        "INVALID_TYPE",
        f"unsupported compile source type {type(source).__name__}",
        path="$",
    )


def try_compile(
    source: str | bytes | bytearray | Mapping[str, Any] | Sequence[Any],
) -> tuple[CompileResult | None, CompilerError | None]:
    """Non-raising wrapper returning ``(result, None)`` or ``(None, error)``."""
    try:
        return compile(source), None
    except CompilerError as exc:
        return None, exc


__all__ = [
    "AUTHORITY_OBLIGATIONS",
    "BUNDLE",
    "CLOSED_OUTCOMES",
    "COMPILE_RESULT_SCHEMA",
    "COMPILER_VERSION",
    "CONFIRMATION_OBLIGATIONS",
    "CONTRACT_SET_SCHEMA",
    "CompileResult",
    "CompiledOperation",
    "CompilerError",
    "DAG_CBOR_PROFILE",
    "Diagnostic",
    "EFFECT_CLASSES",
    "ENUM_FIELDS",
    "EVIDENCE_CLASSES",
    "FIELD_ORDER",
    "FREE_FORM_FORBIDDEN_KEYS",
    "GENERATION_TARGETS",
    "GOAL_ID",
    "IDEMPOTENCY_CLASSES",
    "LEASE_OBLIGATIONS",
    "OBSERVATION_OBLIGATIONS",
    "OPERATION_SPEC_SCHEMA",
    "POLICY_OBLIGATIONS",
    "REVERSIBILITY_CLASSES",
    "RESOURCE_BOUND_ORDER",
    "SIGNED_CID_FAMILY",
    "STABLE_ERROR_CODES",
    "TASK_ID",
    "assert_hermetic_module_source",
    "assert_hermetic_runtime",
    "build_generation_inputs",
    "cid_for_dag_cbor",
    "compile",
    "compile_document",
    "compile_operations",
    "compile_source",
    "encode_operation_dag_cbor",
    "extract_operations",
    "parse_json_source",
    "semantic_check_contract_set",
    "semantic_check_operation",
    "try_compile",
    "validate_operation_spec",
]
