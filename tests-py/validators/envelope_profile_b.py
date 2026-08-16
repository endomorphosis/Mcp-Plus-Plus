"""Profile B → ExecutionEnvelope@1 adapter (ProfileBAdapter@1).

Maps historical Profile B CID-native artifacts onto the shared execution
envelope family without rewriting historical CIDs (MCPP-031 / plan KD-7).

Normative:
  - docs/spec/execution-envelope.md
  - docs/spec/cid-native-artifacts.md
  - schemas/execution/execution-envelope-1.schema.json
  - schemas/execution/execution-receipt-1.schema.json
  - schemas/execution/execution-result-1.schema.json
  - schemas/execution/portable-error-1.schema.json

Acceptance:
  - Historical Profile B CIDs remain readable under their recorded algorithms
    and are referenced unchanged via profile_b_*_cid adapter fields.
  - Adapter output validates structurally as Envelope@1 / Receipt@1 / Result@1.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

from .base_mcp import ValidationResult
from .cid_artifacts import CIDExecutionValidator

try:
    from .canonical_jcs import ALGORITHM_ID as CANONICAL_ALGORITHM
    from .canonical_jcs import artifact_cid as jcs_artifact_cid
except Exception:  # pragma: no cover - package layout fallback
    CANONICAL_ALGORITHM = "mcpp-jcs-v1"

    def jcs_artifact_cid(value: Any) -> str:  # type: ignore[misc]
        import hashlib
        import base64

        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
        digest = hashlib.sha256(raw).digest()
        cid_bytes = bytes([0x01, 0x55, 0x12, 0x20]) + digest
        return "b" + base64.b32encode(cid_bytes).decode("ascii").rstrip("=").lower()


INTERFACE = "ProfileBAdapter@1"
SCHEMA_ENVELOPE = "mcp++/execution/envelope@1"
SCHEMA_RECEIPT = "mcp++/execution/receipt@1"
SCHEMA_RESULT = "mcp++/execution/result@1"
SCHEMA_ERROR = "mcp++/execution/portable-error@1"
CANONICALIZATION = CANONICAL_ALGORITHM

ENVELOPE_SCHEMA_REL = (
    "ipfs_accelerate_py/mcplusplus/schemas/execution/execution-envelope-1.schema.json"
)
RECEIPT_SCHEMA_REL = (
    "ipfs_accelerate_py/mcplusplus/schemas/execution/execution-receipt-1.schema.json"
)
RESULT_SCHEMA_REL = (
    "ipfs_accelerate_py/mcplusplus/schemas/execution/execution-result-1.schema.json"
)
ERROR_SCHEMA_REL = (
    "ipfs_accelerate_py/mcplusplus/schemas/execution/portable-error-1.schema.json"
)
VECTORS_REL = (
    "ipfs_accelerate_py/mcplusplus/conformance/vectors/envelope/profile-b-adapter.json"
)

# Envelope@1 CID pattern (historical CIDv0 + CIDv1; longer CIDv1 forms allowed).
_CID_RE = re.compile(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$")
# Profile B structural validators historically accepted exact 59-char bafkrei forms.
_CID_B_STRICT_RE = re.compile(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")
_DID_RE = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$")

_DEFAULT_REQUESTER_DID = "did:key:z6MkprofileBAdapterLocalTrust1"
_DEFAULT_EXECUTOR_DID = "did:key:z6MkprofileBAdapterExecutor01"
_DEFAULT_CORRELATION = "profile-b-adapted"

_ENVELOPE_REQUIRED = (
    "schema",
    "interface_cid",
    "input_cid",
    "intent_cid",
    "parents",
    "created_at_ms",
    "correlation_id",
    "requester",
    "authority",
)
_RECEIPT_REQUIRED = (
    "schema",
    "envelope_cid",
    "result_cid",
    "status",
    "output_cids",
    "state_transitions",
    "side_effects",
    "decision_cid",
    "delegation_cid",
    "executor",
    "retry",
    "duration_ms",
    "error",
    "proofs",
    "signature",
    "event_cid",
    "started_at_ms",
    "finished_at_ms",
)
_RESULT_REQUIRED = (
    "schema",
    "envelope_cid",
    "status",
    "output_cids",
    "state_transitions",
    "side_effects",
    "decision_cid",
    "delegation_cid",
    "executor",
    "retry",
    "duration_ms",
    "error",
    "proofs",
    "started_at_ms",
    "finished_at_ms",
)
_STATUS_VALUES = frozenset(
    {"succeeded", "failed", "cancelled", "rejected", "timed_out", "compensated"}
)
_FAILURE_CLASSES = frozenset(
    {
        "none",
        "retryable",
        "permanent",
        "policy",
        "authority",
        "fenced",
        "resource",
        "cancelled",
        "timeout",
        "internal",
    }
)


class ProfileBAdapterError(ValueError):
    """Fail-closed adapter rejection."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        self.code = code
        self.path = path
        super().__init__(message if not path else f"{path}: {message}")


@dataclass
class AdapterResult:
    """Outcome of adapting one historical Profile B artifact."""

    adapted: Dict[str, Any]
    historical_cid: Optional[str] = None
    historical_kind: str = "envelope"
    historical_valid: bool = True
    schema_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.historical_valid and self.schema_valid and not self.errors


# ---------------------------------------------------------------------------
# Path / schema loading
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    # .../ipfs_accelerate_py/mcplusplus/tests-py/validators/this.py
    # parents: 0=validators 1=tests-py 2=mcplusplus 3=ipfs_accelerate_py 4=repo
    for parent in here.parents:
        if (parent / "ipfs_accelerate_py" / "mcplusplus").is_dir():
            return parent
        if (parent / "schemas" / "execution").is_dir() and (parent / "tests-py").is_dir():
            # Running with mcplusplus as cwd / submodule root.
            return parent.parent.parent if parent.name == "mcplusplus" else parent
    return here.parents[4]


def _resolve_path(relative: str) -> Path:
    root = _repo_root()
    candidate = root / relative
    if candidate.is_file():
        return candidate
    # Submodule-local layout: schemas/ next to tests-py/
    alt = Path(__file__).resolve().parents[2] / relative.split("mcplusplus/", 1)[-1]
    if alt.is_file():
        return alt
    # Relative to mcplusplus package root
    mcp = Path(__file__).resolve().parents[2]
    name = Path(relative).name
    for sub in (
        mcp / "schemas" / "execution" / name,
        mcp / "conformance" / "vectors" / "envelope" / name,
    ):
        if sub.is_file():
            return sub
    return candidate


def load_json_schema(relative: str) -> Dict[str, Any]:
    path = _resolve_path(relative)
    if not path.is_file():
        raise ProfileBAdapterError("schema_missing", f"schema not found: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_adapter_vectors(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load profile-b-adapter.json conformance vectors."""
    if path is None:
        resolved = _resolve_path(VECTORS_REL)
    else:
        resolved = Path(path)
    if not resolved.is_file():
        raise ProfileBAdapterError("vectors_missing", f"vectors not found: {resolved}")
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProfileBAdapterError("vectors_invalid", "vectors root must be an object")
    return data


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------


def is_valid_cid(value: Any, *, strict_profile_b: bool = False) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if strict_profile_b:
        return bool(_CID_B_STRICT_RE.match(value))
    return bool(_CID_RE.match(value))


def is_valid_did(value: Any) -> bool:
    return isinstance(value, str) and bool(_DID_RE.match(value))


def _require_mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProfileBAdapterError("type_error", "expected object", path=path)
    return value


def _optional_cid(value: Any, *, path: str) -> Optional[str]:
    if value is None or value == "":
        return None
    if not is_valid_cid(value):
        raise ProfileBAdapterError("invalid_cid", f"invalid CID: {value!r}", path=path)
    return str(value)


def _require_cid(value: Any, *, path: str) -> str:
    cid = _optional_cid(value, path=path)
    if cid is None:
        raise ProfileBAdapterError("missing_cid", "required CID missing", path=path)
    return cid


def _as_cid_list(value: Any, *, path: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_require_cid(value, path=path)]
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        raise ProfileBAdapterError("type_error", "expected CID array", path=path)
    out: List[str] = []
    seen = set()
    for i, item in enumerate(value):
        cid = _require_cid(item, path=f"{path}/{i}")
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def _parse_timestamp_ms(value: Any, *, path: str = "/created_at_ms") -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ProfileBAdapterError("type_error", "timestamp must be numeric or ISO", path=path)
    if isinstance(value, int):
        # Heuristic: seconds vs milliseconds
        if value < 10_000_000_000:
            return value * 1000
        return value
    if isinstance(value, float):
        if value < 10_000_000_000:
            return int(value * 1000)
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return _parse_timestamp_ms(int(text), path=path)
        try:
            # Support trailing Z
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError as exc:
            raise ProfileBAdapterError(
                "invalid_timestamp", f"unparseable timestamp: {value!r}", path=path
            ) from exc
    raise ProfileBAdapterError("type_error", f"unsupported timestamp type: {type(value).__name__}", path=path)


def _party(did: Any, *, path: str, key_id: Any = None, peer_id: Any = None) -> Dict[str, Any]:
    if not is_valid_did(did):
        raise ProfileBAdapterError("invalid_did", f"invalid DID: {did!r}", path=path)
    out: Dict[str, Any] = {"did": str(did)}
    if key_id is not None:
        out["key_id"] = key_id
    if peer_id is not None:
        out["peer_id"] = peer_id
    return out


def _authority_from_historical(
    hist: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any],
) -> Dict[str, Any]:
    proof_cids: List[str] = []
    primary: Optional[str] = None

    if "proof_cid" in hist and hist["proof_cid"] not in (None, ""):
        primary = _require_cid(hist["proof_cid"], path="/proof_cid")
        proof_cids.append(primary)
    if "proof_cids" in hist:
        for cid in _as_cid_list(hist.get("proof_cids"), path="/proof_cids"):
            if cid not in proof_cids:
                proof_cids.append(cid)
    # Nested proof bundle on composite envelopes
    if isinstance(hist.get("proof"), Mapping) and hist["proof"].get("cid"):
        cid = _require_cid(hist["proof"]["cid"], path="/proof/cid")
        if cid not in proof_cids:
            proof_cids.append(cid)
        primary = primary or cid

    # Intent proofs_checked / decision proofs
    for key in ("proofs_checked", "proofs"):
        if key in hist:
            for cid in _as_cid_list(hist.get(key), path=f"/{key}"):
                if cid not in proof_cids:
                    proof_cids.append(cid)

    if not proof_cids and defaults.get("proof_cid"):
        primary = _require_cid(defaults["proof_cid"], path="/defaults/proof_cid")
        proof_cids = [primary]
    if not proof_cids and defaults.get("proof_cids"):
        proof_cids = _as_cid_list(defaults["proof_cids"], path="/defaults/proof_cids")
        primary = proof_cids[0] if proof_cids else None

    authority: Dict[str, Any] = {"proof_cids": proof_cids}
    if primary is not None:
        authority["proof_cid"] = primary
    elif proof_cids:
        authority["proof_cid"] = proof_cids[0]
    else:
        # Empty proofs only for same-trust local adaptation (structural).
        authority["proof_cid"] = None

    for optional in ("resource", "ability", "delegation_cids"):
        if optional in defaults:
            authority[optional] = copy.deepcopy(defaults[optional])
        elif optional in hist:
            authority[optional] = copy.deepcopy(hist[optional])
    return authority


def _requester_from_historical(
    hist: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any],
) -> Dict[str, Any]:
    if isinstance(defaults.get("requester"), Mapping):
        req = defaults["requester"]
        return _party(
            req.get("did"),
            path="/defaults/requester/did",
            key_id=req.get("key_id"),
            peer_id=req.get("peer_id"),
        )
    if isinstance(hist.get("requester"), Mapping):
        req = hist["requester"]
        return _party(
            req.get("did"),
            path="/requester/did",
            key_id=req.get("key_id"),
            peer_id=req.get("peer_id"),
        )
    if isinstance(hist.get("requester"), str) and hist["requester"].startswith("did:"):
        return _party(hist["requester"], path="/requester")
    if isinstance(hist.get("peer_did"), str) and hist["peer_did"].startswith("did:"):
        return _party(hist["peer_did"], path="/peer_did")
    meta = hist.get("metadata") if isinstance(hist.get("metadata"), Mapping) else {}
    if isinstance(meta.get("requester_did"), str):
        return _party(meta["requester_did"], path="/metadata/requester_did")
    if isinstance(defaults.get("requester_did"), str):
        return _party(defaults["requester_did"], path="/defaults/requester_did")
    return _party(_DEFAULT_REQUESTER_DID, path="/requester")


def _normalize_historical_envelope(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten common Profile B envelope wire shapes into a field dict."""
    hist = dict(raw)

    # Composite runtime shape: {cid, intent:{...}, decision:{...}, receipt:{...}}
    if "intent" in hist and isinstance(hist["intent"], Mapping):
        intent = hist["intent"]
        if "interface_cid" not in hist and intent.get("interface_cid"):
            hist["interface_cid"] = intent["interface_cid"]
        if "input_cid" not in hist and intent.get("input_cid"):
            hist["input_cid"] = intent["input_cid"]
        if "intent_cid" not in hist:
            if intent.get("cid"):
                hist["intent_cid"] = intent["cid"]
            elif hist.get("intent") and isinstance(hist.get("intent_cid"), str):
                pass
        if "correlation_id" not in hist and intent.get("correlation_id"):
            hist["correlation_id"] = intent["correlation_id"]
        if "method" not in hist and intent.get("tool"):
            hist["method"] = intent["tool"]
        if "method" not in hist and intent.get("method"):
            hist["method"] = intent["method"]
        if "declared_side_effects" not in hist and intent.get("declared_side_effects"):
            hist["declared_side_effects"] = intent["declared_side_effects"]
        if "expected_output_schema_cid" not in hist and intent.get("expected_output_schema_cid"):
            hist["expected_output_schema_cid"] = intent["expected_output_schema_cid"]
        if "policy_cid" not in hist and intent.get("constraints_policy_cid"):
            hist["policy_cid"] = intent["constraints_policy_cid"]

    if "decision" in hist and isinstance(hist["decision"], Mapping):
        decision = hist["decision"]
        if "decision_cid" not in hist and decision.get("cid"):
            hist["decision_cid"] = decision["cid"]
        if "policy_cid" not in hist and decision.get("policy_cid"):
            hist["policy_cid"] = decision["policy_cid"]
        if "proofs_checked" in decision and "proofs_checked" not in hist:
            hist["proofs_checked"] = decision["proofs_checked"]

    # Nested envelope wrapper
    if "envelope" in hist and isinstance(hist["envelope"], Mapping):
        nested = dict(hist["envelope"])
        nested.update({k: v for k, v in hist.items() if k != "envelope"})
        hist = nested

    return hist


# ---------------------------------------------------------------------------
# Structural validators (Envelope@1 family)
# ---------------------------------------------------------------------------


def _validate_cid_field(obj: Mapping[str, Any], key: str, errors: List[str], *, required: bool = False) -> None:
    if key not in obj or obj[key] is None:
        if required:
            errors.append(f"missing required field: {key}")
        return
    if not is_valid_cid(obj[key]):
        errors.append(f"invalid CID at /{key}: {obj[key]!r}")


def validate_envelope_v1(envelope: Mapping[str, Any]) -> ValidationResult:
    """Structural validation of ExecutionEnvelope@1 (ADR-0003 structural level)."""
    result = ValidationResult(is_valid=True, message_type="execution_envelope_v1")
    if not isinstance(envelope, Mapping):
        result.add_error("envelope must be an object")
        return result

    if envelope.get("schema") != SCHEMA_ENVELOPE:
        result.add_error(f"schema must be {SCHEMA_ENVELOPE!r}")

    for key in _ENVELOPE_REQUIRED:
        if key not in envelope:
            result.add_error(f"missing required field: {key}")

    for key in (
        "interface_cid",
        "input_cid",
        "intent_cid",
        "policy_cid",
        "decision_cid",
        "constraints_cid",
        "expected_output_schema_cid",
        "metadata_cid",
        "profile_b_envelope_cid",
    ):
        if key in envelope and envelope[key] is not None:
            if not is_valid_cid(envelope[key]):
                result.add_error(f"invalid CID at /{key}")

    parents = envelope.get("parents")
    if "parents" in envelope:
        if not isinstance(parents, list):
            result.add_error("parents must be an array")
        else:
            for i, p in enumerate(parents):
                if not is_valid_cid(p):
                    result.add_error(f"invalid parent CID at /parents/{i}")

    created = envelope.get("created_at_ms")
    if "created_at_ms" in envelope and (
        not isinstance(created, int) or isinstance(created, bool) or created < 0
    ):
        result.add_error("created_at_ms must be a non-negative integer")

    corr = envelope.get("correlation_id")
    if "correlation_id" in envelope and (
        not isinstance(corr, str) or not (1 <= len(corr) <= 128)
    ):
        result.add_error("correlation_id must be a string of length 1..128")

    requester = envelope.get("requester")
    if "requester" in envelope:
        if not isinstance(requester, Mapping) or not is_valid_did(requester.get("did")):
            result.add_error("requester.did must be a valid DID")

    authority = envelope.get("authority")
    if "authority" in envelope:
        if not isinstance(authority, Mapping):
            result.add_error("authority must be an object")
        elif "proof_cids" not in authority:
            result.add_error("authority.proof_cids is required")
        elif not isinstance(authority.get("proof_cids"), list):
            result.add_error("authority.proof_cids must be an array")
        else:
            for i, cid in enumerate(authority["proof_cids"]):
                if not is_valid_cid(cid):
                    result.add_error(f"invalid CID at /authority/proof_cids/{i}")
            if authority.get("proof_cid") is not None and not is_valid_cid(authority["proof_cid"]):
                result.add_error("invalid CID at /authority/proof_cid")

    if "canonicalization" in envelope and envelope["canonicalization"] not in (
        None,
        CANONICALIZATION,
    ):
        result.add_error(f"canonicalization must be {CANONICALIZATION!r} when present")

    # Optional jsonschema when available (stricter additionalProperties etc.)
    schema_errors = _jsonschema_errors(envelope, ENVELOPE_SCHEMA_REL)
    for err in schema_errors:
        result.add_error(err)

    result.metadata["interface"] = INTERFACE
    result.metadata["schema"] = SCHEMA_ENVELOPE
    return result


def validate_receipt_v1(receipt: Mapping[str, Any]) -> ValidationResult:
    """Structural validation of ExecutionReceipt@1."""
    result = ValidationResult(is_valid=True, message_type="execution_receipt_v1")
    if not isinstance(receipt, Mapping):
        result.add_error("receipt must be an object")
        return result

    if receipt.get("schema") != SCHEMA_RECEIPT:
        result.add_error(f"schema must be {SCHEMA_RECEIPT!r}")

    for key in _RECEIPT_REQUIRED:
        if key not in receipt:
            result.add_error(f"missing required field: {key}")

    for key in (
        "envelope_cid",
        "result_cid",
        "intent_cid",
        "receipt_cid",
        "decision_cid",
        "delegation_cid",
        "proof_cid",
        "event_cid",
        "primary_output_cid",
        "resource_use_cid",
        "policy_cid",
        "profile_b_receipt_cid",
        "profile_g_task_receipt_cid",
    ):
        if key in receipt and receipt[key] is not None and not is_valid_cid(receipt[key]):
            result.add_error(f"invalid CID at /{key}")

    if "output_cids" in receipt:
        if not isinstance(receipt["output_cids"], list):
            result.add_error("output_cids must be an array")
        else:
            for i, cid in enumerate(receipt["output_cids"]):
                if not is_valid_cid(cid):
                    result.add_error(f"invalid CID at /output_cids/{i}")

    status = receipt.get("status")
    if "status" in receipt and status not in _STATUS_VALUES:
        result.add_error(f"invalid status: {status!r}")

    if "executor" in receipt:
        ex = receipt["executor"]
        if not isinstance(ex, Mapping) or not is_valid_did(ex.get("did")):
            result.add_error("executor.did must be a valid DID")

    if "retry" in receipt:
        retry = receipt["retry"]
        if not isinstance(retry, Mapping) or not isinstance(retry.get("attempt"), int) or isinstance(retry.get("attempt"), bool):
            result.add_error("retry.attempt must be an integer >= 1")
        elif retry["attempt"] < 1:
            result.add_error("retry.attempt must be >= 1")

    if "error" in receipt and receipt["error"] is not None:
        err = receipt["error"]
        if not isinstance(err, Mapping):
            result.add_error("error must be PortableError@1 object or null")
        else:
            pe = validate_portable_error_v1(err)
            if not pe.is_valid:
                result.errors.extend(pe.errors)
                result.is_valid = False

    if status == "succeeded" and receipt.get("error") is not None:
        result.add_error("error must be null when status is succeeded")

    for ts in ("started_at_ms", "finished_at_ms"):
        if ts in receipt and (
            not isinstance(receipt[ts], int)
            or isinstance(receipt[ts], bool)
            or receipt[ts] < 0
        ):
            result.add_error(f"{ts} must be a non-negative integer")

    if (
        isinstance(receipt.get("started_at_ms"), int)
        and isinstance(receipt.get("finished_at_ms"), int)
        and receipt["finished_at_ms"] < receipt["started_at_ms"]
    ):
        result.add_error("finished_at_ms must be >= started_at_ms")

    schema_errors = _jsonschema_errors(receipt, RECEIPT_SCHEMA_REL)
    for err in schema_errors:
        result.add_error(err)

    result.metadata["interface"] = INTERFACE
    result.metadata["schema"] = SCHEMA_RECEIPT
    return result


def validate_result_v1(result_obj: Mapping[str, Any]) -> ValidationResult:
    """Structural validation of ExecutionResult@1."""
    result = ValidationResult(is_valid=True, message_type="execution_result_v1")
    if not isinstance(result_obj, Mapping):
        result.add_error("result must be an object")
        return result

    if result_obj.get("schema") != SCHEMA_RESULT:
        result.add_error(f"schema must be {SCHEMA_RESULT!r}")

    for key in _RESULT_REQUIRED:
        if key not in result_obj:
            result.add_error(f"missing required field: {key}")

    if "status" in result_obj and result_obj["status"] not in _STATUS_VALUES:
        result.add_error(f"invalid status: {result_obj.get('status')!r}")

    if result_obj.get("status") == "succeeded" and result_obj.get("error") is not None:
        result.add_error("error must be null when status is succeeded")

    schema_errors = _jsonschema_errors(result_obj, RESULT_SCHEMA_REL)
    for err in schema_errors:
        result.add_error(err)

    result.metadata["interface"] = INTERFACE
    result.metadata["schema"] = SCHEMA_RESULT
    return result


def validate_portable_error_v1(error: Mapping[str, Any]) -> ValidationResult:
    result = ValidationResult(is_valid=True, message_type="portable_error_v1")
    if not isinstance(error, Mapping):
        result.add_error("error must be an object")
        return result
    if error.get("schema") != SCHEMA_ERROR:
        result.add_error(f"schema must be {SCHEMA_ERROR!r}")
    for key in ("code", "message", "retryable", "failure_class"):
        if key not in error:
            result.add_error(f"missing required field: {key}")
    if "failure_class" in error and error["failure_class"] not in _FAILURE_CLASSES:
        result.add_error(f"invalid failure_class: {error.get('failure_class')!r}")
    if "retryable" in error and not isinstance(error["retryable"], bool):
        result.add_error("retryable must be a boolean")
    schema_errors = _jsonschema_errors(error, ERROR_SCHEMA_REL)
    for err in schema_errors:
        result.add_error(err)
    return result


_SCHEMA_CACHE: Dict[str, Any] = {}
_VALIDATOR_CACHE: Dict[str, Any] = {}


def _jsonschema_errors(instance: Mapping[str, Any], schema_rel: str) -> List[str]:
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012
    except Exception:
        return []

    try:
        if schema_rel not in _VALIDATOR_CACHE:
            schema_dir = _resolve_path(schema_rel).parent
            resources = []
            for path in schema_dir.glob("*.json"):
                doc = json.loads(path.read_text(encoding="utf-8"))
                resources.append(
                    (doc.get("$id", path.name), Resource.from_contents(doc, default_specification=DRAFT202012))
                )
                resources.append(
                    (path.name, Resource.from_contents(doc, default_specification=DRAFT202012))
                )
            registry = Registry().with_resources(resources)
            schema = json.loads(_resolve_path(schema_rel).read_text(encoding="utf-8"))
            _VALIDATOR_CACHE[schema_rel] = Draft202012Validator(schema, registry=registry)
        validator = _VALIDATOR_CACHE[schema_rel]
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
        out = []
        for err in errors:
            path = "/" + "/".join(str(p) for p in err.absolute_path) if err.absolute_path else "/"
            out.append(f"jsonschema{path}: {err.message}")
        return out
    except Exception as exc:  # pragma: no cover - defensive
        return [f"jsonschema_unavailable: {exc}"]


# ---------------------------------------------------------------------------
# Historical Profile B verification (no mutation)
# ---------------------------------------------------------------------------


def verify_historical_envelope(historical: Mapping[str, Any]) -> ValidationResult:
    """Validate a historical Profile B envelope with the existing B validator."""
    hist = _normalize_historical_envelope(historical)
    # CIDExecutionValidator requires interface_cid + input_cid.
    return CIDExecutionValidator().validate_execution_envelope(dict(hist))


def verify_historical_receipt(historical: Mapping[str, Any]) -> ValidationResult:
    """Validate a historical Profile B receipt (tolerant of wire variants)."""
    result = ValidationResult(is_valid=True, message_type="profile_b_receipt")
    if not isinstance(historical, Mapping):
        result.add_error("receipt must be an object")
        return result

    # Classic validator path when both CID fields present
    if "output_cid" in historical and "receipt_cid" in historical:
        return CIDExecutionValidator().validate_execution_receipt(dict(historical))

    # Wire shape from execution_receipt.json / models.ExecutionReceipt
    if "success" in historical:
        if not isinstance(historical["success"], bool):
            result.add_error("success must be boolean")
        for key in ("output_cid", "receipt_cid", "envelope_cid", "decision_cid"):
            if key in historical and historical[key] is not None:
                if not is_valid_cid(historical[key], strict_profile_b=True) and not is_valid_cid(
                    historical[key]
                ):
                    result.add_error(f"invalid CID at /{key}")
        return result

    # Spec §6 receipt shape
    if "intent_cid" in historical or "output_cid" in historical:
        for key in ("intent_cid", "output_cid", "decision_cid"):
            if key in historical and historical[key] is not None and not is_valid_cid(historical[key]):
                result.add_error(f"invalid CID at /{key}")
        return result

    result.add_error("unrecognized Profile B receipt shape")
    return result


def historical_cid_unchanged(historical_cid: str, adapted: Mapping[str, Any], *, kind: str) -> bool:
    """Return True when the adapter preserved the historical CID reference."""
    if not is_valid_cid(historical_cid):
        return False
    if kind == "envelope":
        return adapted.get("profile_b_envelope_cid") == historical_cid
    if kind == "receipt":
        return adapted.get("profile_b_receipt_cid") == historical_cid
    return False


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


def adapt_profile_b_envelope(
    historical: Mapping[str, Any],
    *,
    historical_cid: Optional[str] = None,
    defaults: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Adapt a historical Profile B envelope to ExecutionEnvelope@1.

    Does not mutate *historical*. When *historical_cid* is provided it is
    copied into ``profile_b_envelope_cid`` unchanged.
    """
    defaults = dict(defaults or {})
    hist = _normalize_historical_envelope(_require_mapping(historical, path="/"))

    interface_cid = _require_cid(
        hist.get("interface_cid") or defaults.get("interface_cid"),
        path="/interface_cid",
    )
    input_cid = _require_cid(
        hist.get("input_cid") or defaults.get("input_cid"),
        path="/input_cid",
    )

    intent_cid = hist.get("intent_cid") or defaults.get("intent_cid")
    if not intent_cid and isinstance(hist.get("intent"), Mapping):
        intent_cid = hist["intent"].get("cid")
    if not intent_cid:
        # Deterministic synthetic intent binding for incomplete historical
        # envelopes — does not rewrite any historical artifact CID.
        intent_cid = jcs_artifact_cid(
            {
                "schema": "mcp++/profile-b/adapted-intent@1",
                "interface_cid": interface_cid,
                "input_cid": input_cid,
                "source": "profile-b-adapter",
            }
        )
    intent_cid = _require_cid(intent_cid, path="/intent_cid")

    parents = hist.get("parents", defaults.get("parents", []))
    if parents is None:
        parents = []
    parent_cids = _as_cid_list(parents, path="/parents")

    created_at_ms = None
    for key in ("created_at_ms", "timestamp", "time", "created"):
        if key in hist:
            created_at_ms = _parse_timestamp_ms(hist[key], path=f"/{key}")
            if created_at_ms is not None:
                break
    if created_at_ms is None and "created_at_ms" in defaults:
        created_at_ms = _parse_timestamp_ms(defaults["created_at_ms"], path="/defaults/created_at_ms")
    if created_at_ms is None:
        created_at_ms = 0

    correlation_id = hist.get("correlation_id") or defaults.get("correlation_id")
    if not correlation_id and isinstance(hist.get("metadata"), Mapping):
        correlation_id = hist["metadata"].get("correlation_id")
    if not correlation_id:
        correlation_id = _DEFAULT_CORRELATION
    if not isinstance(correlation_id, str) or not correlation_id:
        raise ProfileBAdapterError("invalid_correlation_id", "correlation_id must be non-empty string")

    requester = _requester_from_historical(hist, defaults=defaults)
    authority = _authority_from_historical(hist, defaults=defaults)

    adapted: Dict[str, Any] = {
        "schema": SCHEMA_ENVELOPE,
        "interface_cid": interface_cid,
        "input_cid": input_cid,
        "intent_cid": intent_cid,
        "parents": parent_cids,
        "created_at_ms": int(created_at_ms),
        "correlation_id": str(correlation_id)[:128],
        "requester": requester,
        "authority": authority,
        "canonicalization": CANONICALIZATION,
        "state_refs": list(defaults.get("state_refs") or hist.get("state_refs") or []),
    }

    method = hist.get("method") or hist.get("tool") or defaults.get("method")
    if method is not None:
        adapted["method"] = method

    for src_key, dst_key in (
        ("policy_cid", "policy_cid"),
        ("decision_cid", "decision_cid"),
        ("expected_output_schema_cid", "expected_output_schema_cid"),
        ("constraints_cid", "constraints_cid"),
        ("nonce", "nonce"),
        ("deadline_ms", "deadline_ms"),
        ("metadata_cid", "metadata_cid"),
    ):
        value = hist.get(src_key, defaults.get(src_key))
        if value is not None and value != "":
            if dst_key.endswith("_cid") or dst_key.endswith("_ms"):
                if dst_key.endswith("_cid"):
                    adapted[dst_key] = _require_cid(value, path=f"/{src_key}")
                else:
                    adapted[dst_key] = int(_parse_timestamp_ms(value, path=f"/{src_key}") or value)
            else:
                adapted[dst_key] = value

    if "constraints" in hist or "constraints" in defaults:
        adapted["constraints"] = copy.deepcopy(
            hist.get("constraints", defaults.get("constraints"))
        )
    if "declared_side_effects" in hist or "declared_side_effects" in defaults:
        adapted["declared_side_effects"] = list(
            hist.get("declared_side_effects") or defaults.get("declared_side_effects") or []
        )
    if "audience" in hist or "audience" in defaults:
        aud = hist.get("audience", defaults.get("audience"))
        if isinstance(aud, Mapping):
            adapted["audience"] = _party(
                aud.get("did"),
                path="/audience/did",
                key_id=aud.get("key_id"),
                peer_id=aud.get("peer_id"),
            )
        elif isinstance(aud, str) and aud.startswith("did:"):
            adapted["audience"] = _party(aud, path="/audience")

    # Historical CID reference — never rewritten.
    cid_ref = historical_cid or hist.get("cid") or hist.get("envelope_cid") or defaults.get(
        "profile_b_envelope_cid"
    )
    if cid_ref is not None:
        adapted["profile_b_envelope_cid"] = _require_cid(cid_ref, path="/historical_cid")

    return adapted


def _portable_error_from_historical(
    historical: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    if historical.get("error") in (None, "", False) and historical.get("success", True):
        return None
    raw = historical.get("error")
    if isinstance(raw, Mapping) and raw.get("schema") == SCHEMA_ERROR:
        return dict(raw)
    if isinstance(raw, Mapping) and {"code", "message"} <= set(raw.keys()):
        return {
            "schema": SCHEMA_ERROR,
            "code": str(raw.get("code") or "E_EXECUTION_FAILED"),
            "message": str(raw.get("message") or "execution failed"),
            "retryable": bool(raw.get("retryable", False)),
            "failure_class": str(raw.get("failure_class") or "permanent"),
        }
    message = str(raw) if raw not in (None, "") else str(
        defaults.get("error_message") or "execution failed"
    )
    return {
        "schema": SCHEMA_ERROR,
        "code": str(defaults.get("error_code") or "E_EXECUTION_FAILED"),
        "message": message[:4096],
        "retryable": bool(defaults.get("retryable", False)),
        "failure_class": str(defaults.get("failure_class") or "permanent"),
    }


def _status_from_historical(historical: Mapping[str, Any], *, defaults: Mapping[str, Any]) -> str:
    if "status" in historical and historical["status"] in _STATUS_VALUES:
        return str(historical["status"])
    if "status" in defaults and defaults["status"] in _STATUS_VALUES:
        return str(defaults["status"])
    if "success" in historical:
        return "succeeded" if historical["success"] else "failed"
    if historical.get("error") not in (None, "", False):
        return "failed"
    return "succeeded"


def _executor_from_historical(
    historical: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any],
) -> Dict[str, Any]:
    if isinstance(defaults.get("executor"), Mapping):
        ex = defaults["executor"]
        base = _party(
            ex.get("did") or _DEFAULT_EXECUTOR_DID,
            path="/defaults/executor/did",
            key_id=ex.get("key_id"),
            peer_id=ex.get("peer_id"),
        )
        for k in ("runtime", "runtime_version"):
            if k in ex:
                base[k] = ex[k]
        return base
    if isinstance(historical.get("executor"), Mapping):
        ex = historical["executor"]
        base = _party(
            ex.get("did") or _DEFAULT_EXECUTOR_DID,
            path="/executor/did",
            key_id=ex.get("key_id"),
            peer_id=ex.get("peer_id"),
        )
        for k in ("runtime", "runtime_version"):
            if k in ex:
                base[k] = ex[k]
        return base
    if isinstance(historical.get("executor"), str) and historical["executor"].startswith("did:"):
        return _party(historical["executor"], path="/executor")
    if isinstance(historical.get("executor"), str) and historical["executor"]:
        return {
            "did": _DEFAULT_EXECUTOR_DID,
            "runtime": str(historical["executor"])[:128],
        }
    return {"did": _DEFAULT_EXECUTOR_DID, "runtime": "profile-b-adapter"}


def _side_effects_from_historical(historical: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw = historical.get("observed_side_effects") or historical.get("side_effects") or []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping) and item.get("kind"):
            effect: Dict[str, Any] = {"kind": str(item["kind"])[:128]}
            if item.get("effect_cid"):
                effect["effect_cid"] = _require_cid(item["effect_cid"], path="/side_effects/effect_cid")
            if "description" in item:
                effect["description"] = item["description"]
            if "compensatable" in item:
                effect["compensatable"] = bool(item["compensatable"])
            out.append(effect)
        elif isinstance(item, str) and item:
            if is_valid_cid(item):
                out.append({"kind": "observed", "effect_cid": item})
            else:
                out.append({"kind": item[:128]})
    return out


def adapt_profile_b_result(
    historical: Mapping[str, Any],
    *,
    envelope_cid: str,
    historical_cid: Optional[str] = None,
    defaults: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Adapt a historical Profile B receipt-like object to ExecutionResult@1."""
    defaults = dict(defaults or {})
    hist = dict(_require_mapping(historical, path="/"))
    status = _status_from_historical(hist, defaults=defaults)

    output_cids: List[str] = []
    if hist.get("output_cid"):
        output_cids.append(_require_cid(hist["output_cid"], path="/output_cid"))
    if hist.get("output_cids"):
        for cid in _as_cid_list(hist["output_cids"], path="/output_cids"):
            if cid not in output_cids:
                output_cids.append(cid)
    if defaults.get("output_cids"):
        for cid in _as_cid_list(defaults["output_cids"], path="/defaults/output_cids"):
            if cid not in output_cids:
                output_cids.append(cid)

    duration_ms = hist.get("duration_ms", defaults.get("duration_ms", 0))
    if not isinstance(duration_ms, (int, float)) or isinstance(duration_ms, bool) or duration_ms < 0:
        raise ProfileBAdapterError("invalid_duration", f"invalid duration_ms: {duration_ms!r}")

    started = hist.get("started_at_ms", defaults.get("started_at_ms"))
    finished = hist.get("finished_at_ms", defaults.get("finished_at_ms"))
    if started is None and hist.get("time_observed"):
        finished = finished or _parse_timestamp_ms(hist["time_observed"], path="/time_observed")
        started = int(finished or 0) - int(duration_ms)
        if started < 0:
            started = 0
    if started is None:
        started = int(defaults.get("started_at_ms", 0))
    if finished is None:
        finished = int(started) + int(duration_ms)

    proofs: List[str] = []
    for key in ("proofs_checked", "proofs"):
        if key in hist:
            for cid in _as_cid_list(hist.get(key), path=f"/{key}"):
                if cid not in proofs:
                    proofs.append(cid)
    if hist.get("proof_cid"):
        cid = _require_cid(hist["proof_cid"], path="/proof_cid")
        if cid not in proofs:
            proofs.append(cid)

    decision_cid = hist.get("decision_cid", defaults.get("decision_cid"))
    if decision_cid in ("",):
        decision_cid = None
    if decision_cid is not None:
        decision_cid = _require_cid(decision_cid, path="/decision_cid")

    delegation_cid = hist.get("delegation_cid", defaults.get("delegation_cid"))
    if delegation_cid in ("",):
        delegation_cid = None
    if delegation_cid is not None:
        delegation_cid = _require_cid(delegation_cid, path="/delegation_cid")

    attempt = int(hist.get("attempt") or defaults.get("attempt") or 1)
    if attempt < 1:
        attempt = 1

    error = _portable_error_from_historical(hist, defaults=defaults) if status != "succeeded" else None

    result_obj: Dict[str, Any] = {
        "schema": SCHEMA_RESULT,
        "envelope_cid": _require_cid(envelope_cid, path="/envelope_cid"),
        "status": status,
        "output_cids": output_cids,
        "state_transitions": list(
            hist.get("state_transitions") or defaults.get("state_transitions") or []
        ),
        "side_effects": _side_effects_from_historical(hist),
        "decision_cid": decision_cid,
        "delegation_cid": delegation_cid,
        "executor": _executor_from_historical(hist, defaults=defaults),
        "retry": {"attempt": attempt},
        "duration_ms": float(duration_ms),
        "error": error,
        "proofs": proofs,
        "started_at_ms": int(started),
        "finished_at_ms": int(finished),
        "canonicalization": CANONICALIZATION,
    }

    if hist.get("intent_cid") or defaults.get("intent_cid"):
        result_obj["intent_cid"] = _require_cid(
            hist.get("intent_cid") or defaults.get("intent_cid"), path="/intent_cid"
        )
    if output_cids:
        result_obj["primary_output_cid"] = output_cids[0]
    if hist.get("correlation_id") or defaults.get("correlation_id"):
        result_obj["correlation_id"] = str(
            hist.get("correlation_id") or defaults.get("correlation_id")
        )[:128]
    if hist.get("event_cid") or defaults.get("event_cid"):
        result_obj["event_cid"] = _require_cid(
            hist.get("event_cid") or defaults.get("event_cid"), path="/event_cid"
        )
    if hist.get("resource_use_cid") or defaults.get("resource_use_cid"):
        result_obj["resource_use_cid"] = _require_cid(
            hist.get("resource_use_cid") or defaults.get("resource_use_cid"),
            path="/resource_use_cid",
        )

    # Signature on result is optional
    sig = hist.get("signature")
    if isinstance(hist.get("signatures"), list) and hist["signatures"]:
        sig = sig or hist["signatures"][0]
    if sig:
        result_obj["signature"] = str(sig)
        result_obj["signature_alg"] = defaults.get("signature_alg") or "Ed25519"
    else:
        result_obj["signature"] = None
        result_obj["signature_alg"] = None

    # historical_cid is for receipt adapter; result itself does not carry profile_b_* 
    _ = historical_cid
    return result_obj


def adapt_profile_b_receipt(
    historical: Mapping[str, Any],
    *,
    historical_cid: Optional[str] = None,
    envelope_cid: Optional[str] = None,
    result_cid: Optional[str] = None,
    defaults: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Adapt a historical Profile B receipt to ExecutionReceipt@1.

    Preserves the historical receipt CID in ``profile_b_receipt_cid``.
    """
    defaults = dict(defaults or {})
    hist = dict(_require_mapping(historical, path="/"))

    env_cid = (
        envelope_cid
        or hist.get("envelope_cid")
        or defaults.get("envelope_cid")
    )
    if not env_cid:
        # Deterministic placeholder envelope binding for receipt-only fixtures.
        env_cid = jcs_artifact_cid(
            {
                "schema": "mcp++/profile-b/adapted-envelope-ref@1",
                "receipt_hint": hist.get("receipt_cid") or historical_cid,
                "output_cid": hist.get("output_cid"),
            }
        )
    env_cid = _require_cid(env_cid, path="/envelope_cid")

    result_obj = adapt_profile_b_result(
        hist,
        envelope_cid=env_cid,
        historical_cid=historical_cid,
        defaults=defaults,
    )
    if result_cid is None:
        # Content-address the adapted result under mcpp-jcs-v1 (new view, not a rewrite).
        unsigned = {k: v for k, v in result_obj.items() if k != "signature"}
        result_cid = jcs_artifact_cid(unsigned)
    result_cid = _require_cid(result_cid, path="/result_cid")

    receipt: Dict[str, Any] = {
        "schema": SCHEMA_RECEIPT,
        "envelope_cid": env_cid,
        "result_cid": result_cid,
        "status": result_obj["status"],
        "output_cids": list(result_obj["output_cids"]),
        "state_transitions": list(result_obj["state_transitions"]),
        "side_effects": list(result_obj["side_effects"]),
        "decision_cid": result_obj.get("decision_cid"),
        "delegation_cid": result_obj.get("delegation_cid"),
        "executor": dict(result_obj["executor"]),
        "retry": dict(result_obj["retry"]),
        "duration_ms": result_obj["duration_ms"],
        "error": copy.deepcopy(result_obj.get("error")),
        "proofs": list(result_obj.get("proofs") or []),
        "signature": result_obj.get("signature"),
        "signature_alg": result_obj.get("signature_alg"),
        "event_cid": result_obj.get("event_cid"),
        "started_at_ms": result_obj["started_at_ms"],
        "finished_at_ms": result_obj["finished_at_ms"],
        "canonicalization": CANONICALIZATION,
    }

    if result_obj.get("intent_cid"):
        receipt["intent_cid"] = result_obj["intent_cid"]
    if result_obj.get("primary_output_cid"):
        receipt["primary_output_cid"] = result_obj["primary_output_cid"]
    if result_obj.get("correlation_id"):
        receipt["correlation_id"] = result_obj["correlation_id"]
    if result_obj.get("resource_use_cid"):
        receipt["resource_use_cid"] = result_obj["resource_use_cid"]
    if hist.get("policy_cid") or defaults.get("policy_cid"):
        receipt["policy_cid"] = _require_cid(
            hist.get("policy_cid") or defaults.get("policy_cid"), path="/policy_cid"
        )

    # Self-address of historical receipt (unchanged reference).
    hist_receipt_cid = (
        historical_cid
        or hist.get("receipt_cid")
        or hist.get("cid")
        or defaults.get("profile_b_receipt_cid")
    )
    if hist_receipt_cid is not None:
        receipt["profile_b_receipt_cid"] = _require_cid(
            hist_receipt_cid, path="/historical_cid"
        )
        # Also surface as receipt_cid when it was the historical self-address.
        if hist.get("receipt_cid"):
            receipt["receipt_cid"] = _require_cid(hist["receipt_cid"], path="/receipt_cid")

    if "event_cid" not in receipt:
        receipt["event_cid"] = None

    return receipt


def adapt_and_validate_envelope(
    historical: Mapping[str, Any],
    *,
    historical_cid: Optional[str] = None,
    defaults: Optional[Mapping[str, Any]] = None,
    require_historical_valid: bool = True,
) -> AdapterResult:
    """Adapt a Profile B envelope and validate both historical + Envelope@1 views."""
    hist_check = verify_historical_envelope(historical)
    if require_historical_valid and not hist_check.is_valid:
        return AdapterResult(
            adapted={},
            historical_cid=historical_cid,
            historical_kind="envelope",
            historical_valid=False,
            schema_valid=False,
            errors=list(hist_check.errors),
        )

    adapted = adapt_profile_b_envelope(
        historical, historical_cid=historical_cid, defaults=defaults
    )
    schema_check = validate_envelope_v1(adapted)
    errors: List[str] = []
    if not schema_check.is_valid:
        errors.extend(schema_check.errors)

    if historical_cid and not historical_cid_unchanged(historical_cid, adapted, kind="envelope"):
        errors.append("historical envelope CID was not preserved on profile_b_envelope_cid")

    return AdapterResult(
        adapted=adapted,
        historical_cid=historical_cid or adapted.get("profile_b_envelope_cid"),
        historical_kind="envelope",
        historical_valid=hist_check.is_valid,
        schema_valid=schema_check.is_valid and not errors,
        errors=errors,
        warnings=list(hist_check.warnings),
        metadata={"interface": INTERFACE},
    )


def adapt_and_validate_receipt(
    historical: Mapping[str, Any],
    *,
    historical_cid: Optional[str] = None,
    envelope_cid: Optional[str] = None,
    result_cid: Optional[str] = None,
    defaults: Optional[Mapping[str, Any]] = None,
    require_historical_valid: bool = True,
) -> AdapterResult:
    """Adapt a Profile B receipt and validate historical + Receipt@1 views."""
    hist_check = verify_historical_receipt(historical)
    if require_historical_valid and not hist_check.is_valid:
        return AdapterResult(
            adapted={},
            historical_cid=historical_cid,
            historical_kind="receipt",
            historical_valid=False,
            schema_valid=False,
            errors=list(hist_check.errors),
        )

    adapted = adapt_profile_b_receipt(
        historical,
        historical_cid=historical_cid,
        envelope_cid=envelope_cid,
        result_cid=result_cid,
        defaults=defaults,
    )
    schema_check = validate_receipt_v1(adapted)
    errors: List[str] = []
    if not schema_check.is_valid:
        errors.extend(schema_check.errors)

    if historical_cid and not historical_cid_unchanged(historical_cid, adapted, kind="receipt"):
        errors.append("historical receipt CID was not preserved on profile_b_receipt_cid")

    return AdapterResult(
        adapted=adapted,
        historical_cid=historical_cid or adapted.get("profile_b_receipt_cid"),
        historical_kind="receipt",
        historical_valid=hist_check.is_valid,
        schema_valid=schema_check.is_valid and not errors,
        errors=errors,
        warnings=list(hist_check.warnings),
        metadata={"interface": INTERFACE},
    )


class ProfileBAdapter:
    """Object-oriented facade for ProfileBAdapter@1."""

    interface = INTERFACE

    def adapt_envelope(self, historical: Mapping[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return adapt_profile_b_envelope(historical, **kwargs)

    def adapt_receipt(self, historical: Mapping[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return adapt_profile_b_receipt(historical, **kwargs)

    def adapt_result(self, historical: Mapping[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return adapt_profile_b_result(historical, **kwargs)

    def validate_envelope(self, envelope: Mapping[str, Any]) -> ValidationResult:
        return validate_envelope_v1(envelope)

    def validate_receipt(self, receipt: Mapping[str, Any]) -> ValidationResult:
        return validate_receipt_v1(receipt)

    def run_vector_case(self, case: Mapping[str, Any]) -> AdapterResult:
        return run_vector_case(case)


# ---------------------------------------------------------------------------
# Conformance vector runner
# ---------------------------------------------------------------------------


def run_vector_case(case: Mapping[str, Any]) -> AdapterResult:
    """Execute one profile-b-adapter vector case."""
    kind = str(case.get("kind") or "envelope")
    historical = case.get("historical") or case.get("payload") or {}
    historical_cid = case.get("historical_cid")
    defaults = case.get("defaults") or {}
    expect = case.get("expect") or case.get("expected") or {}

    if kind == "envelope":
        result = adapt_and_validate_envelope(
            historical,
            historical_cid=historical_cid,
            defaults=defaults,
            require_historical_valid=bool(case.get("require_historical_valid", True)),
        )
    elif kind == "receipt":
        result = adapt_and_validate_receipt(
            historical,
            historical_cid=historical_cid,
            envelope_cid=case.get("envelope_cid") or defaults.get("envelope_cid"),
            result_cid=case.get("result_cid") or defaults.get("result_cid"),
            defaults=defaults,
            require_historical_valid=bool(case.get("require_historical_valid", True)),
        )
    else:
        raise ProfileBAdapterError("unknown_kind", f"unsupported case kind: {kind}")

    # Expectation checks (compact field equality / presence).
    for key, expected in expect.items():
        if key == "schema_valid":
            if bool(result.schema_valid) != bool(expected):
                result.errors.append(f"expect.schema_valid={expected} got {result.schema_valid}")
                result.schema_valid = False
            continue
        if key == "historical_valid":
            if bool(result.historical_valid) != bool(expected):
                result.errors.append(
                    f"expect.historical_valid={expected} got {result.historical_valid}"
                )
                result.historical_valid = False
            continue
        if key.startswith("adapted."):
            path = key[len("adapted.") :]
            actual = result.adapted
            for part in path.split("."):
                if isinstance(actual, Mapping):
                    actual = actual.get(part)
                else:
                    actual = None
                    break
            if actual != expected:
                result.errors.append(f"expect {key}={expected!r} got {actual!r}")
                result.schema_valid = False
            continue
        # Top-level adapted field
        if result.adapted.get(key) != expected:
            result.errors.append(
                f"expect {key}={expected!r} got {result.adapted.get(key)!r}"
            )
            result.schema_valid = False

    if case.get("expect_ok", True) and not result.ok:
        # already recorded errors
        pass
    return result


def run_all_vector_cases(
    vectors: Optional[Mapping[str, Any]] = None,
) -> List[Tuple[str, AdapterResult]]:
    data = vectors if vectors is not None else load_adapter_vectors()
    cases = data.get("cases") or []
    out: List[Tuple[str, AdapterResult]] = []
    for case in cases:
        case_id = str(case.get("id") or case.get("case") or f"case-{len(out)}")
        out.append((case_id, run_vector_case(case)))
    return out


# ---------------------------------------------------------------------------
# Built-in regression tests (collected via tests-py/integration/test_profile_b_adapter.py)
# ---------------------------------------------------------------------------


def _fixture_cids() -> Dict[str, str]:
    # Well-formed 59-char CIDv1 placeholders used across MCP++ fixtures.
    return {
        "interface": "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        "input": "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti",
        "intent": "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi",
        "policy": "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku",
        "proof": "bafkreigbzwrggyucrnusmzisauvzpszxfhr3auxevxshycq6gob557tty4",
        "parent_a": "bafkreihojjgp4soxeawgk64e4vhafpz3kdtlastu5hfnbdv5upb6c2cd7e",
        "parent_b": "bafkreifyiloqasaswqrluaxwzlyyeftgi2vwfyfe3rahohy4vcpat3vxcq",
        "envelope": "bafkreidpgkdasegkb6zkedd73ikdmzvqtw7y3njdqgk4scsyn62uf7ymvu",
        "output": "bafkreiclrltegoplfz2o3djv7ydnyrozwrr5zkgw6lxmnzaxd7pnqdt62u",
        "receipt": "bafkreif5oexc3wdpabmikptk5lvk6ireyzfyhuuwa2znh7bxbxtvpytfpy",
        "decision": "bafkreiepz7gpm5nr6c75hholweybkbjp5av4khaahqlfuqijixerhw5sxy",
        "event": "bafkreify4h4axvyk4b4ey6cvurixgg3ul7o3m52j2i7wg67jbavxl2kxlm",
    }


def test_profile_b_adapter_interface_constant() -> None:
    assert INTERFACE == "ProfileBAdapter@1"
    assert SCHEMA_ENVELOPE == "mcp++/execution/envelope@1"
    assert ProfileBAdapter.interface == INTERFACE


def test_profile_b_adapter_envelope_validates_as_envelope_v1() -> None:
    c = _fixture_cids()
    historical = {
        "interface_cid": c["interface"],
        "input_cid": c["input"],
        "intent_cid": c["intent"],
        "policy_cid": c["policy"],
        "proof_cid": c["proof"],
        "parents": [c["parent_a"], c["parent_b"]],
        "timestamp": 1783872000,
    }
    historical_cid = c["envelope"]
    # Snapshot historical bytes for non-mutation check
    historical_snapshot = json.dumps(historical, sort_keys=True)

    result = adapt_and_validate_envelope(
        historical,
        historical_cid=historical_cid,
        defaults={
            "correlation_id": "task-b-001",
            "requester": {"did": "did:key:z6MkrequesterExample0001"},
            "created_at_ms": 1783872000000,
        },
    )
    assert result.historical_valid, result.errors
    assert result.schema_valid, result.errors
    assert result.ok, result.errors
    assert result.adapted["schema"] == SCHEMA_ENVELOPE
    assert result.adapted["profile_b_envelope_cid"] == historical_cid
    assert result.adapted["interface_cid"] == c["interface"]
    assert result.adapted["input_cid"] == c["input"]
    assert result.adapted["intent_cid"] == c["intent"]
    assert result.adapted["authority"]["proof_cid"] == c["proof"]
    assert c["proof"] in result.adapted["authority"]["proof_cids"]
    # Historical artifact not mutated
    assert json.dumps(historical, sort_keys=True) == historical_snapshot
    assert historical_cid_unchanged(historical_cid, result.adapted, kind="envelope")


def test_profile_b_adapter_receipt_validates_as_receipt_v1() -> None:
    c = _fixture_cids()
    historical = {
        "success": True,
        "receipt_cid": c["receipt"],
        "output_cid": c["output"],
        "error": None,
        "duration_ms": 0.08,
        "signature": "604b46e0",
        "decision_cid": c["decision"],
        "intent_cid": c["intent"],
    }
    snapshot = json.dumps(historical, sort_keys=True)
    result = adapt_and_validate_receipt(
        historical,
        historical_cid=c["receipt"],
        envelope_cid=c["envelope"],
        defaults={
            "started_at_ms": 1783872001100,
            "executor": {
                "did": "did:key:z6MkexecutorExample00001",
                "runtime": "ipfs_accelerate_py",
                "runtime_version": "3.2.0",
            },
        },
    )
    assert result.historical_valid, result.errors
    assert result.schema_valid, result.errors
    assert result.ok, result.errors
    assert result.adapted["schema"] == SCHEMA_RECEIPT
    assert result.adapted["profile_b_receipt_cid"] == c["receipt"]
    assert result.adapted["status"] == "succeeded"
    assert result.adapted["error"] is None
    assert c["output"] in result.adapted["output_cids"]
    assert json.dumps(historical, sort_keys=True) == snapshot
    assert historical_cid_unchanged(c["receipt"], result.adapted, kind="receipt")


def test_profile_b_adapter_historical_b_validator_still_accepts() -> None:
    c = _fixture_cids()
    envelope = {
        "interface_cid": c["interface"],
        "input_cid": c["input"],
        "intent_cid": c["intent"],
        "parents": [c["parent_a"]],
    }
    receipt = {
        "output_cid": c["output"],
        "receipt_cid": c["receipt"],
        "signature": "0xabc",
    }
    assert verify_historical_envelope(envelope).is_valid
    assert verify_historical_receipt(receipt).is_valid
    # After adaptation, historical still validates (unchanged)
    adapt_profile_b_envelope(envelope, historical_cid=c["envelope"])
    adapt_profile_b_receipt(receipt, historical_cid=c["receipt"], envelope_cid=c["envelope"])
    assert verify_historical_envelope(envelope).is_valid
    assert verify_historical_receipt(receipt).is_valid


def test_profile_b_adapter_execution_receipt_vector() -> None:
    """Historical conformance vector execution_receipt.json still verifies and adapts."""
    path = _resolve_path(
        "ipfs_accelerate_py/mcplusplus/conformance/vectors/execution_receipt.json"
    )
    if not path.is_file():
        # Submodule-local
        path = Path(__file__).resolve().parents[2] / "conformance" / "vectors" / "execution_receipt.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    payload = data["payload"] if isinstance(data, dict) and "payload" in data else data
    c = _fixture_cids()
    hist_cid = payload.get("receipt_cid")
    assert hist_cid and is_valid_cid(hist_cid)
    hist_check = verify_historical_receipt(payload)
    assert hist_check.is_valid, hist_check.errors
    result = adapt_and_validate_receipt(
        payload,
        historical_cid=hist_cid,
        envelope_cid=c["envelope"],
        defaults={
            "started_at_ms": 1783872000000,
            "intent_cid": c["intent"],
            "executor": {"did": "did:key:z6MkexecutorFromVector0001"},
        },
    )
    assert result.ok, result.errors
    assert result.adapted["profile_b_receipt_cid"] == hist_cid


def test_profile_b_adapter_vectors_file() -> None:
    data = load_adapter_vectors()
    assert data.get("interface") == INTERFACE
    cases = data.get("cases") or []
    assert len(cases) >= 1
    for case_id, result in run_all_vector_cases(data):
        assert result.ok, f"{case_id}: {result.errors}"


def test_profile_b_adapter_failed_receipt_maps_portable_error() -> None:
    c = _fixture_cids()
    historical = {
        "success": False,
        "receipt_cid": c["receipt"],
        "output_cid": None,
        "error": "policy denied",
        "duration_ms": 3.5,
    }
    # output_cid None is awkward for historical validator; use require_historical_valid=False
    # when only success/error wire shape is present without output_cid.
    historical_with_output = {
        "success": False,
        "receipt_cid": c["receipt"],
        "output_cid": c["output"],
        "error": "policy denied",
        "duration_ms": 3.5,
    }
    result = adapt_and_validate_receipt(
        historical_with_output,
        historical_cid=c["receipt"],
        envelope_cid=c["envelope"],
        defaults={
            "started_at_ms": 1783872000000,
            "failure_class": "policy",
            "error_code": "E_POLICY_DENIED",
            "executor": {"did": "did:key:z6MkexecutorExample00001"},
        },
    )
    assert result.ok, result.errors
    assert result.adapted["status"] == "failed"
    assert result.adapted["error"] is not None
    assert result.adapted["error"]["schema"] == SCHEMA_ERROR
    assert result.adapted["error"]["failure_class"] == "policy"
    assert result.adapted["profile_b_receipt_cid"] == c["receipt"]


def test_profile_b_adapter_composite_runtime_envelope() -> None:
    c = _fixture_cids()
    historical = {
        "cid": c["envelope"],
        "intent": {
            "cid": c["intent"],
            "interface_cid": c["interface"],
            "input_cid": c["input"],
            "method": "repo.status",
            "correlation_id": "corr-composite",
        },
        "decision": {
            "cid": c["decision"],
            "authorized": True,
            "policy_cid": c["policy"],
            "proofs_checked": [c["proof"]],
        },
        "parents": [],
        "timestamp": 1783872000.5,
    }
    result = adapt_and_validate_envelope(historical, historical_cid=c["envelope"])
    assert result.ok, result.errors
    assert result.adapted["method"] == "repo.status"
    assert result.adapted["intent_cid"] == c["intent"]
    assert result.adapted["decision_cid"] == c["decision"]
    assert result.adapted["policy_cid"] == c["policy"]
    assert result.adapted["correlation_id"] == "corr-composite"
    assert result.adapted["profile_b_envelope_cid"] == c["envelope"]
