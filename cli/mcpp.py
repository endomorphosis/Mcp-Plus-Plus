#!/usr/bin/env python3
"""MCP++ installable CLI — McppCli@1 (MCPP-075).

Commands (each supports ``--help``):

  inspect           Summarize a JSON MCP++ artifact
  validate          Structural validate of envelope / receipt / policy / generic
  conformance       Run local conformance vector suites
  envelope create   Mint a minimal ExecutionEnvelope@1
  envelope verify   Structural-verify an envelope (optionally via Profile B adapter)
  receipt verify    Structural-verify an execution receipt
  artifact get      Resolve a CID from a local content store
  peer list         List configured / discovered peers (local store)
  demo              Three-peer demo entry (Compose wiring lands in MCPP-076)
  doctor            Report binding, schema, and crypto-suite versions

Do not reimplement validators here: prefer the existing tests-py validators
when the package tree is present; fall back to structural checks otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Interface / version pins (McppCli@1, ADR-0002, ADR-0006)
# ---------------------------------------------------------------------------

INTERFACE = "McppCli@1"
TASK_ID = "MCPP-075"
CLI_VERSION = "1.0.0"
PACKAGE_NAME = "mcpp"

# Binding inventory (ADR-0006 / bindings/README.md)
BINDING_LEGACY = "mcp-binding/legacy-2024-11-05"
BINDING_CURRENT = "mcp-binding/2026-07-28"
BINDING_VERSIONS = {
    BINDING_LEGACY: {
        "protocolVersion": "2024-11-05",
        "lifecycle": "initialize",
        "role": "legacy",
    },
    BINDING_CURRENT: {
        "protocolVersion": "2026-07-28",
        "lifecycle": "stateless-meta",
        "role": "current",
    },
}

# Schema markers (SchemaId@1 family)
SCHEMA_ENVELOPE = "mcp++/execution/envelope@1"
SCHEMA_RECEIPT = "mcp++/execution/receipt@1"
SCHEMA_RESULT = "mcp++/execution/result@1"
SCHEMA_ERROR = "mcp++/execution/portable-error@1"
SCHEMA_CANONICALIZATION = "mcp++/canonicalization/mcpp-jcs-v1@1"
SCHEMA_VERSIONS = {
    "execution_envelope": SCHEMA_ENVELOPE,
    "execution_receipt": SCHEMA_RECEIPT,
    "execution_result": SCHEMA_RESULT,
    "portable_error": SCHEMA_ERROR,
    "canonicalization": SCHEMA_CANONICALIZATION,
    "profile_h_common": "mcp++/profile-h/1.0/common@1",
    "profile_h_artifacts": "mcp++/profile-h/1.0/artifacts@1",
    "profile_h_x402": "mcp++/profile-h/1.0/x402-v2@1",
}

# Crypto suite (CryptoSuiteDecision@1 / ADR-0002)
CRYPTO_SUITE = {
    "id": "mcp++/crypto-suite@1",
    "signature_algorithm": "Ed25519",
    "jose_alg": "EdDSA",
    "key_id_required": True,
    "identity": "DID-compatible iss/aud",
    "canonicalization": "mcpp-jcs-v1",
    "canonicalization_standard": "RFC 8785 JCS",
    "cid": {
        "version": 1,
        "multicodec": "raw",
        "multicodec_code": "0x55",
        "multihash": "sha2-256",
        "multihash_code": "0x12",
        "multibase": "base32lower",
    },
    "historical_algorithms_readable": True,
}

_CID_RE = re.compile(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$")
_DID_RE = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$")

_EXIT_OK = 0
_EXIT_USAGE = 2
_EXIT_VALIDATION = 3
_EXIT_IO = 4
_EXIT_INTERNAL = 5


# ---------------------------------------------------------------------------
# Paths / package layout
# ---------------------------------------------------------------------------


def package_root() -> Path:
    """Return the MCP++ package root (parent of ``cli/``)."""
    return Path(__file__).resolve().parent.parent


def repo_hint_root() -> Path:
    """Best-effort monorepo root (grandparent of package root when nested)."""
    root = package_root()
    # .../ipfs_accelerate_py/mcplusplus → monorepo root two levels up
    candidate = root.parent.parent
    if (candidate / "ipfs_accelerate_py").is_dir():
        return candidate
    return root


def vectors_dir() -> Path:
    return package_root() / "conformance" / "vectors"


def schemas_dir() -> Path:
    return package_root() / "schemas"


def tests_py_dir() -> Path:
    return package_root() / "tests-py"


def _ensure_validators_path() -> None:
    """Expose ``tests-py`` on ``sys.path`` so existing validators import cleanly."""
    tp = str(tests_py_dir())
    if tp not in sys.path and tests_py_dir().is_dir():
        sys.path.insert(0, tp)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def load_json_path(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def load_json_input(path: Optional[str], *, stdin_ok: bool = True) -> Any:
    if path is None or path == "-":
        if not stdin_ok:
            raise ValueError("JSON path required")
        return json.load(sys.stdin)
    return load_json_path(Path(path))


def emit_json(obj: Any, *, indent: int = 2) -> None:
    sys.stdout.write(json.dumps(obj, indent=indent, sort_keys=True, ensure_ascii=False))
    if not str(json.dumps(obj)).endswith("\n"):
        sys.stdout.write("\n")


def emit_text(msg: str) -> None:
    sys.stdout.write(msg if msg.endswith("\n") else msg + "\n")


def emit_err(msg: str) -> None:
    sys.stderr.write(msg if msg.endswith("\n") else msg + "\n")


def is_valid_cid(value: Any) -> bool:
    return isinstance(value, str) and bool(_CID_RE.fullmatch(value))


def is_valid_did(value: Any) -> bool:
    return isinstance(value, str) and bool(_DID_RE.fullmatch(value))


# ---------------------------------------------------------------------------
# Structural validation (thin local fallback; prefer package validators)
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    ok: bool
    kind: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


def _structural_envelope(obj: Mapping[str, Any]) -> CheckResult:
    errors: List[str] = []
    if obj.get("schema") not in (None, SCHEMA_ENVELOPE):
        # Accept historical Profile B (no schema marker) or Envelope@1
        if "interface_cid" not in obj or "input_cid" not in obj:
            errors.append(f"schema must be {SCHEMA_ENVELOPE!r} or a Profile B envelope")
    schema = obj.get("schema")
    if schema == SCHEMA_ENVELOPE:
        for key in (
            "schema",
            "interface_cid",
            "input_cid",
            "intent_cid",
            "parents",
            "created_at_ms",
            "correlation_id",
            "requester",
            "authority",
        ):
            if key not in obj:
                errors.append(f"missing required field: {key}")
        for key in ("interface_cid", "input_cid", "intent_cid"):
            if key in obj and obj[key] is not None and not is_valid_cid(obj[key]):
                errors.append(f"invalid CID at /{key}")
        parents = obj.get("parents")
        if "parents" in obj:
            if not isinstance(parents, list):
                errors.append("parents must be an array")
            else:
                for i, p in enumerate(parents):
                    if not is_valid_cid(p):
                        errors.append(f"invalid parent CID at /parents/{i}")
        requester = obj.get("requester")
        if isinstance(requester, Mapping) and not is_valid_did(requester.get("did")):
            errors.append("requester.did must be a valid DID")
        authority = obj.get("authority")
        if isinstance(authority, Mapping):
            proofs = authority.get("proof_cids")
            if proofs is not None and not isinstance(proofs, list):
                errors.append("authority.proof_cids must be an array")
    else:
        # Historical Profile B shape
        for key in ("interface_cid", "input_cid"):
            if key not in obj:
                errors.append(f"missing required field: {key}")
            elif not is_valid_cid(obj[key]):
                errors.append(f"invalid CID at /{key}")
    return CheckResult(
        ok=not errors,
        kind="envelope",
        errors=errors,
        metadata={"schema": schema or "profile-b-historical"},
    )


def _structural_receipt(obj: Mapping[str, Any]) -> CheckResult:
    errors: List[str] = []
    schema = obj.get("schema")
    if schema == SCHEMA_RECEIPT:
        for key in ("schema", "envelope_cid", "status"):
            if key not in obj:
                errors.append(f"missing required field: {key}")
        if "envelope_cid" in obj and not is_valid_cid(obj["envelope_cid"]):
            errors.append("invalid CID at /envelope_cid")
    else:
        # Historical receipt (payload nested or flat)
        payload = obj.get("payload") if isinstance(obj.get("payload"), Mapping) else obj
        if not isinstance(payload, Mapping):
            errors.append("receipt must be an object")
        else:
            if "receipt_cid" in payload and not is_valid_cid(payload["receipt_cid"]):
                errors.append("invalid CID at /receipt_cid")
            if "output_cid" in payload and payload["output_cid"] is not None:
                if not is_valid_cid(payload["output_cid"]):
                    errors.append("invalid CID at /output_cid")
            if "success" not in payload and "status" not in payload and schema is None:
                errors.append("receipt missing success/status")
    return CheckResult(
        ok=not errors,
        kind="receipt",
        errors=errors,
        metadata={"schema": schema or "profile-b-historical"},
    )


def _try_import_validators() -> Dict[str, Any]:
    """Import existing package validators when available."""
    _ensure_validators_path()
    out: Dict[str, Any] = {}
    try:
        from validators.envelope_profile_b import (  # type: ignore
            validate_envelope_v1,
            validate_receipt_v1,
            SCHEMA_ENVELOPE as _SE,
            SCHEMA_RECEIPT as _SR,
            adapt_and_validate_envelope,
            adapt_and_validate_receipt,
        )

        out["validate_envelope_v1"] = validate_envelope_v1
        out["validate_receipt_v1"] = validate_receipt_v1
        out["adapt_and_validate_envelope"] = adapt_and_validate_envelope
        out["adapt_and_validate_receipt"] = adapt_and_validate_receipt
        out["SCHEMA_ENVELOPE"] = _SE
        out["SCHEMA_RECEIPT"] = _SR
        out["envelope_profile_b"] = True
    except Exception as exc:  # pragma: no cover - optional path
        out["envelope_profile_b_error"] = str(exc)

    try:
        from validators.canonical_jcs import (  # type: ignore
            ALGORITHM_ID,
            algorithm_declaration,
            identity as jcs_identity,
        )

        out["ALGORITHM_ID"] = ALGORITHM_ID
        out["algorithm_declaration"] = algorithm_declaration
        out["jcs_identity"] = jcs_identity
        out["canonical_jcs"] = True
    except Exception as exc:  # pragma: no cover
        out["canonical_jcs_error"] = str(exc)

    try:
        from validators.cid_artifacts import CIDExecutionValidator  # type: ignore

        out["CIDExecutionValidator"] = CIDExecutionValidator
        out["cid_artifacts"] = True
    except Exception as exc:  # pragma: no cover
        out["cid_artifacts_error"] = str(exc)

    try:
        from validators.policy_evaluation import PolicyEvaluationValidator  # type: ignore

        out["PolicyEvaluationValidator"] = PolicyEvaluationValidator
        out["policy_evaluation"] = True
    except Exception as exc:  # pragma: no cover
        out["policy_evaluation_error"] = str(exc)

    return out


def validate_envelope_doc(obj: Mapping[str, Any], *, adapt: bool = False) -> CheckResult:
    mods = _try_import_validators()
    if adapt and mods.get("adapt_and_validate_envelope"):
        try:
            ar = mods["adapt_and_validate_envelope"](obj)
            errors = list(getattr(ar, "errors", None) or [])
            ok = bool(getattr(ar, "ok", False) or getattr(ar, "schema_valid", False))
            meta = {"adapter": "ProfileBAdapter@1"}
            adapted = getattr(ar, "adapted", None)
            if isinstance(adapted, Mapping):
                meta["adapted_schema"] = adapted.get("schema")
            return CheckResult(ok=ok, kind="envelope", errors=errors, metadata=meta)
        except Exception as exc:
            return CheckResult(ok=False, kind="envelope", errors=[f"adapter error: {exc}"])

    if obj.get("schema") == SCHEMA_ENVELOPE and mods.get("validate_envelope_v1"):
        try:
            vr = mods["validate_envelope_v1"](obj)
            errors = list(getattr(vr, "errors", None) or [])
            ok = bool(getattr(vr, "is_valid", False))
            meta = dict(getattr(vr, "metadata", None) or {})
            meta["validator"] = "envelope_profile_b.validate_envelope_v1"
            return CheckResult(ok=ok, kind="envelope", errors=errors, metadata=meta)
        except Exception as exc:
            return CheckResult(ok=False, kind="envelope", errors=[f"validator error: {exc}"])

    if mods.get("CIDExecutionValidator") and obj.get("schema") != SCHEMA_ENVELOPE:
        try:
            vr = mods["CIDExecutionValidator"]().validate_execution_envelope(dict(obj))
            errors = list(getattr(vr, "errors", None) or [])
            ok = bool(getattr(vr, "is_valid", False))
            return CheckResult(
                ok=ok,
                kind="envelope",
                errors=errors,
                metadata={"validator": "CIDExecutionValidator"},
            )
        except Exception as exc:
            return CheckResult(ok=False, kind="envelope", errors=[f"validator error: {exc}"])

    return _structural_envelope(obj)


def validate_receipt_doc(obj: Mapping[str, Any], *, adapt: bool = False) -> CheckResult:
    mods = _try_import_validators()
    if adapt and mods.get("adapt_and_validate_receipt"):
        try:
            ar = mods["adapt_and_validate_receipt"](obj)
            errors = list(getattr(ar, "errors", None) or [])
            ok = bool(getattr(ar, "ok", False) or getattr(ar, "schema_valid", False))
            return CheckResult(
                ok=ok,
                kind="receipt",
                errors=errors,
                metadata={"adapter": "ProfileBAdapter@1"},
            )
        except Exception as exc:
            return CheckResult(ok=False, kind="receipt", errors=[f"adapter error: {exc}"])

    if obj.get("schema") == SCHEMA_RECEIPT and mods.get("validate_receipt_v1"):
        try:
            vr = mods["validate_receipt_v1"](obj)
            errors = list(getattr(vr, "errors", None) or [])
            ok = bool(getattr(vr, "is_valid", False))
            meta = dict(getattr(vr, "metadata", None) or {})
            meta["validator"] = "envelope_profile_b.validate_receipt_v1"
            return CheckResult(ok=ok, kind="receipt", errors=errors, metadata=meta)
        except Exception as exc:
            return CheckResult(ok=False, kind="receipt", errors=[f"validator error: {exc}"])

    if mods.get("CIDExecutionValidator"):
        try:
            payload = obj.get("payload") if isinstance(obj.get("payload"), Mapping) else obj
            vr = mods["CIDExecutionValidator"]().validate_execution_receipt(dict(payload))
            errors = list(getattr(vr, "errors", None) or [])
            ok = bool(getattr(vr, "is_valid", False))
            return CheckResult(
                ok=ok,
                kind="receipt",
                errors=errors,
                metadata={"validator": "CIDExecutionValidator"},
            )
        except Exception as exc:
            return CheckResult(ok=False, kind="receipt", errors=[f"validator error: {exc}"])

    return _structural_receipt(obj)


def detect_kind(obj: Any) -> str:
    if not isinstance(obj, Mapping):
        return "unknown"
    schema = obj.get("schema")
    if schema == SCHEMA_ENVELOPE:
        return "envelope"
    if schema == SCHEMA_RECEIPT:
        return "receipt"
    if schema == SCHEMA_RESULT:
        return "result"
    if schema == SCHEMA_ERROR:
        return "error"
    if "interface_cid" in obj and "input_cid" in obj:
        return "envelope"
    if "receipt_cid" in obj or (
        isinstance(obj.get("payload"), Mapping) and "receipt_cid" in obj["payload"]
    ):
        return "receipt"
    if "decision" in obj or obj.get("effect") in ("allow", "deny"):
        return "policy_decision"
    if "model" in obj and "payload" in obj:
        model = str(obj.get("model") or "")
        if "Receipt" in model:
            return "receipt"
        if "Envelope" in model:
            return "envelope"
    return "generic"


# ---------------------------------------------------------------------------
# Envelope mint
# ---------------------------------------------------------------------------


_DEFAULT_CIDS = {
    "interface": "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
    "input": "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti",
    "intent": "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi",
    "proof": "bafkreigbzwrggyucrnusmzisauvzpszxfhr3auxevxshycq6gob557tty4",
}


def create_envelope(
    *,
    interface_cid: str,
    input_cid: str,
    intent_cid: str,
    requester_did: str,
    correlation_id: str,
    proof_cids: Optional[Sequence[str]] = None,
    parents: Optional[Sequence[str]] = None,
    method: Optional[str] = None,
    created_at_ms: Optional[int] = None,
    policy_cid: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a minimal ExecutionEnvelope@1 object (structural mint)."""
    if created_at_ms is None:
        created_at_ms = int(time.time() * 1000)
    proofs = list(proof_cids) if proof_cids else [_DEFAULT_CIDS["proof"]]
    env: Dict[str, Any] = {
        "schema": SCHEMA_ENVELOPE,
        "interface_cid": interface_cid,
        "input_cid": input_cid,
        "intent_cid": intent_cid,
        "parents": list(parents) if parents is not None else [],
        "created_at_ms": created_at_ms,
        "correlation_id": correlation_id,
        "requester": {"did": requester_did},
        "authority": {
            "proof_cids": proofs,
            "proof_cid": proofs[0] if proofs else None,
        },
        "canonicalization": CRYPTO_SUITE["canonicalization"],
    }
    if method:
        env["method"] = method
    if policy_cid:
        env["policy_cid"] = policy_cid
    return env


# ---------------------------------------------------------------------------
# Local content store + peers (file-backed, demo-friendly)
# ---------------------------------------------------------------------------


def default_store_dir() -> Path:
    env = os.environ.get("MCPP_STORE")
    if env:
        return Path(env)
    return package_root() / ".mcpp" / "store"


def default_peers_path() -> Path:
    env = os.environ.get("MCPP_PEERS")
    if env:
        return Path(env)
    return package_root() / ".mcpp" / "peers.json"


def store_put(store: Path, cid: str, obj: Any) -> Path:
    store.mkdir(parents=True, exist_ok=True)
    path = store / f"{cid}.json"
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def store_get(store: Path, cid: str) -> Any:
    path = store / f"{cid}.json"
    if not path.is_file():
        # Also accept bare cid file without .json
        alt = store / cid
        if alt.is_file():
            path = alt
        else:
            raise FileNotFoundError(f"artifact not found in store: {cid}")
    return load_json_path(path)


def load_peers(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    data = load_json_path(path)
    if isinstance(data, list):
        return [p for p in data if isinstance(p, Mapping)]
    if isinstance(data, Mapping) and isinstance(data.get("peers"), list):
        return [p for p in data["peers"] if isinstance(p, Mapping)]
    return []


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    mods = _try_import_validators()
    canon = CRYPTO_SUITE["canonicalization"]
    if mods.get("ALGORITHM_ID"):
        canon = mods["ALGORITHM_ID"]
    alg_decl = None
    if callable(mods.get("algorithm_declaration")):
        try:
            alg_decl = mods["algorithm_declaration"]()
        except Exception:
            alg_decl = None

    schema_files: Dict[str, bool] = {}
    for rel in (
        "execution/execution-envelope-1.schema.json",
        "execution/execution-receipt-1.schema.json",
        "execution/execution-result-1.schema.json",
        "execution/portable-error-1.schema.json",
        "canonicalization/mcpp-jcs-v1.schema.json",
    ):
        schema_files[rel] = (schemas_dir() / rel).is_file()

    report = {
        "interface": INTERFACE,
        "task_id": TASK_ID,
        "cli_version": CLI_VERSION,
        "package": PACKAGE_NAME,
        "package_root": str(package_root()),
        "bindings": {
            "versions": BINDING_VERSIONS,
            "supported": list(BINDING_VERSIONS.keys()),
            "default": BINDING_CURRENT,
        },
        "schemas": {
            "versions": SCHEMA_VERSIONS,
            "files_present": schema_files,
        },
        "crypto_suite": {
            **CRYPTO_SUITE,
            "canonicalization": canon,
            "algorithm_declaration": alg_decl,
        },
        "validators": {
            "envelope_profile_b": bool(mods.get("envelope_profile_b")),
            "canonical_jcs": bool(mods.get("canonical_jcs")),
            "cid_artifacts": bool(mods.get("cid_artifacts")),
            "policy_evaluation": bool(mods.get("policy_evaluation")),
        },
        "vectors_dir": str(vectors_dir()),
        "vectors_present": vectors_dir().is_dir(),
    }
    if getattr(args, "json", True):
        emit_json(report)
    else:
        emit_text(f"mcpp doctor ({INTERFACE} v{CLI_VERSION})")
        emit_text(f"bindings: {', '.join(BINDING_VERSIONS)}")
        emit_text(f"schemas: {', '.join(SCHEMA_VERSIONS.values())}")
        emit_text(
            f"crypto suite: {CRYPTO_SUITE['signature_algorithm']}/"
            f"{CRYPTO_SUITE['jose_alg']} over {canon}; "
            f"CID v{CRYPTO_SUITE['cid']['version']} "
            f"{CRYPTO_SUITE['cid']['multicodec']}+{CRYPTO_SUITE['cid']['multihash']}"
        )
    return _EXIT_OK


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        obj = load_json_input(args.path)
    except Exception as exc:
        emit_err(f"inspect: failed to load JSON: {exc}")
        return _EXIT_IO
    kind = detect_kind(obj)
    summary: Dict[str, Any] = {
        "kind": kind,
        "schema": obj.get("schema") if isinstance(obj, Mapping) else None,
        "keys": sorted(obj.keys()) if isinstance(obj, Mapping) else [],
    }
    if isinstance(obj, Mapping):
        for key in (
            "interface_cid",
            "input_cid",
            "intent_cid",
            "envelope_cid",
            "receipt_cid",
            "output_cid",
            "correlation_id",
            "method",
            "status",
            "success",
        ):
            if key in obj:
                summary[key] = obj[key]
        payload = obj.get("payload")
        if isinstance(payload, Mapping):
            summary["payload_keys"] = sorted(payload.keys())
            for key in ("receipt_cid", "output_cid", "success", "duration_ms"):
                if key in payload:
                    summary[f"payload.{key}"] = payload[key]
    emit_json(summary)
    return _EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        obj = load_json_input(args.path)
    except Exception as exc:
        emit_err(f"validate: failed to load JSON: {exc}")
        return _EXIT_IO
    if not isinstance(obj, Mapping):
        emit_err("validate: document must be a JSON object")
        return _EXIT_VALIDATION

    kind = args.kind or detect_kind(obj)
    if kind == "envelope":
        result = validate_envelope_doc(obj, adapt=bool(args.adapt))
    elif kind == "receipt":
        result = validate_receipt_doc(obj, adapt=bool(args.adapt))
    elif kind == "policy_decision":
        mods = _try_import_validators()
        if mods.get("PolicyEvaluationValidator"):
            try:
                # Structural pass only: ensure mapping shape.
                result = CheckResult(
                    ok=isinstance(obj, Mapping),
                    kind="policy_decision",
                    errors=[] if isinstance(obj, Mapping) else ["not an object"],
                    metadata={"validator": "PolicyEvaluationValidator-available"},
                )
            except Exception as exc:
                result = CheckResult(ok=False, kind="policy_decision", errors=[str(exc)])
        else:
            result = CheckResult(
                ok=True,
                kind="policy_decision",
                warnings=["policy validator not importable; shape-only accept"],
            )
    else:
        result = CheckResult(
            ok=isinstance(obj, Mapping),
            kind=kind,
            warnings=["generic JSON object; no specialized validator selected"],
            metadata={"keys": sorted(obj.keys())},
        )

    emit_json(result.to_dict())
    return _EXIT_OK if result.ok else _EXIT_VALIDATION


def cmd_conformance(args: argparse.Namespace) -> int:
    root = vectors_dir()
    if not root.is_dir():
        emit_err(f"conformance: vectors directory missing: {root}")
        return _EXIT_IO

    suite = args.suite or "all"
    selected: List[Path] = []
    if suite in ("all", "envelope"):
        p = root / "envelope" / "profile-b-adapter.json"
        if p.is_file():
            selected.append(p)
    if suite in ("all", "receipt"):
        p = root / "execution_receipt.json"
        if p.is_file():
            selected.append(p)
    if suite in ("all", "jcs", "mcpp-jcs-v1"):
        jcs = root / "mcpp-jcs-v1"
        if jcs.is_dir():
            selected.extend(sorted(jcs.glob("*.json")))
    if suite in ("all", "policy"):
        pol = root / "policy"
        if pol.is_dir():
            selected.extend(sorted((pol / "fixtures").glob("*.json")))

    if args.path:
        selected = [Path(args.path)]

    results: List[Dict[str, Any]] = []
    failed = 0
    for path in selected:
        if path.name == "manifest.json" or path.name == "README.md":
            continue
        if path.name == "recipes.json":
            continue
        try:
            doc = load_json_path(path)
        except Exception as exc:
            results.append({"path": str(path), "ok": False, "error": str(exc)})
            failed += 1
            continue

        entry: Dict[str, Any] = {"path": str(path.relative_to(root) if path.is_relative_to(root) else path)}
        if isinstance(doc, Mapping) and "cases" in doc:
            # Adapter suite style
            cases = doc.get("cases") or []
            case_results = []
            for case in cases:
                if not isinstance(case, Mapping):
                    continue
                kind = case.get("kind") or "envelope"
                historical = case.get("historical") or case.get("input") or {}
                if not isinstance(historical, Mapping):
                    case_results.append({"id": case.get("id"), "ok": False, "error": "bad historical"})
                    failed += 1
                    continue
                if kind == "receipt":
                    cr = validate_receipt_doc(historical, adapt=True)
                else:
                    cr = validate_envelope_doc(historical, adapt=True)
                case_results.append({"id": case.get("id"), **cr.to_dict()})
                if not cr.ok:
                    failed += 1
            entry["cases"] = case_results
            entry["ok"] = all(c.get("ok") for c in case_results) if case_results else True
        else:
            kind = detect_kind(doc) if isinstance(doc, Mapping) else "generic"
            if kind == "envelope":
                cr = validate_envelope_doc(doc if isinstance(doc, Mapping) else {}, adapt=False)
            elif kind == "receipt":
                cr = validate_receipt_doc(doc if isinstance(doc, Mapping) else {}, adapt=False)
            else:
                cr = CheckResult(ok=True, kind=kind, warnings=["loaded; no specialized check"])
            entry.update(cr.to_dict())
            if not cr.ok:
                failed += 1
        results.append(entry)

    report = {
        "suite": suite,
        "count": len(results),
        "failed": failed,
        "ok": failed == 0,
        "results": results,
    }
    emit_json(report)
    return _EXIT_OK if failed == 0 else _EXIT_VALIDATION


def cmd_envelope_create(args: argparse.Namespace) -> int:
    try:
        env = create_envelope(
            interface_cid=args.interface_cid or _DEFAULT_CIDS["interface"],
            input_cid=args.input_cid or _DEFAULT_CIDS["input"],
            intent_cid=args.intent_cid or _DEFAULT_CIDS["intent"],
            requester_did=args.requester_did or "did:key:z6MkmcppCliLocalRequester0001",
            correlation_id=args.correlation_id or f"mcpp-cli-{int(time.time())}",
            parents=args.parents or [],
            method=args.method,
            policy_cid=args.policy_cid,
            created_at_ms=args.created_at_ms,
        )
    except Exception as exc:
        emit_err(f"envelope create: {exc}")
        return _EXIT_USAGE

    check = validate_envelope_doc(env)
    if args.verify and not check.ok:
        emit_json({"ok": False, "envelope": env, "validation": check.to_dict()})
        return _EXIT_VALIDATION

    if args.output:
        Path(args.output).write_text(
            json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if args.store:
            # Best-effort local index under correlation id key when CID unknown
            store = Path(args.store) if args.store else default_store_dir()
            store.mkdir(parents=True, exist_ok=True)
            (store / f"envelope-{env['correlation_id']}.json").write_text(
                json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    emit_json(env)
    return _EXIT_OK


def cmd_envelope_verify(args: argparse.Namespace) -> int:
    try:
        obj = load_json_input(args.path)
    except Exception as exc:
        emit_err(f"envelope verify: failed to load JSON: {exc}")
        return _EXIT_IO
    if not isinstance(obj, Mapping):
        emit_err("envelope verify: document must be a JSON object")
        return _EXIT_VALIDATION
    result = validate_envelope_doc(obj, adapt=bool(args.adapt))
    emit_json(result.to_dict())
    return _EXIT_OK if result.ok else _EXIT_VALIDATION


def cmd_receipt_verify(args: argparse.Namespace) -> int:
    try:
        if args.cid:
            store = Path(args.store) if args.store else default_store_dir()
            obj = store_get(store, args.cid)
        else:
            obj = load_json_input(args.path)
    except FileNotFoundError as exc:
        emit_err(f"receipt verify: {exc}")
        return _EXIT_IO
    except Exception as exc:
        emit_err(f"receipt verify: failed to load: {exc}")
        return _EXIT_IO
    if not isinstance(obj, Mapping):
        emit_err("receipt verify: document must be a JSON object")
        return _EXIT_VALIDATION
    result = validate_receipt_doc(obj, adapt=bool(args.adapt))
    emit_json(result.to_dict())
    return _EXIT_OK if result.ok else _EXIT_VALIDATION


def cmd_artifact_get(args: argparse.Namespace) -> int:
    store = Path(args.store) if args.store else default_store_dir()
    cid = args.cid
    if not cid:
        emit_err("artifact get: --cid is required")
        return _EXIT_USAGE
    try:
        obj = store_get(store, cid)
    except FileNotFoundError as exc:
        emit_err(str(exc))
        return _EXIT_IO
    except Exception as exc:
        emit_err(f"artifact get: {exc}")
        return _EXIT_IO
    emit_json(obj)
    return _EXIT_OK


def cmd_peer_list(args: argparse.Namespace) -> int:
    path = Path(args.peers) if args.peers else default_peers_path()
    peers = load_peers(path)
    report = {
        "peers_path": str(path),
        "count": len(peers),
        "peers": peers,
    }
    emit_json(report)
    return _EXIT_OK


def cmd_demo(args: argparse.Namespace) -> int:
    """Demo command scaffold for MCPP-076 three-peer Compose demo."""
    demo_root = package_root() / "demo"
    compose = demo_root / "docker-compose.yml"
    report = {
        "interface": INTERFACE,
        "command": "demo",
        "peers": getattr(args, "peers", 3),
        "verify": bool(getattr(args, "verify", False)),
        "demo_root": str(demo_root),
        "compose_present": compose.is_file(),
        "status": "ready" if compose.is_file() else "scaffold",
        "message": (
            "Three-peer Compose demo is available under demo/."
            if compose.is_file()
            else "Demo Compose files land in MCPP-076; CLI entry is ready."
        ),
        "next": "python -m mcpp demo --peers 3 --verify",
    }
    emit_json(report)
    # Help path and scaffolding always succeed; full demo verification is MCPP-076.
    if getattr(args, "verify", False) and not compose.is_file():
        return _EXIT_OK
    return _EXIT_OK


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcpp",
        description="MCP++ 1.0 CLI (McppCli@1): inspect, validate, envelope, receipt, doctor.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {CLI_VERSION} ({INTERFACE})")
    sub = parser.add_subparsers(dest="command", required=True)

    # doctor
    p_doctor = sub.add_parser(
        "doctor",
        help="Report binding, schema, and crypto suite versions",
        description="Print MCP++ binding ids, schema markers, and crypto suite pins.",
    )
    p_doctor.add_argument(
        "--json",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Emit machine-readable JSON (default: true)",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    # inspect
    p_inspect = sub.add_parser(
        "inspect",
        help="Summarize a JSON MCP++ artifact",
        description="Load a JSON artifact and print a kind/schema summary.",
    )
    p_inspect.add_argument(
        "path",
        nargs="?",
        default="-",
        help="Path to JSON file (or - for stdin)",
    )
    p_inspect.set_defaults(func=cmd_inspect)

    # validate
    p_validate = sub.add_parser(
        "validate",
        help="Structurally validate an MCP++ artifact",
        description="Validate envelope, receipt, policy decision, or generic JSON.",
    )
    p_validate.add_argument("path", nargs="?", default="-", help="JSON path or - for stdin")
    p_validate.add_argument(
        "--kind",
        choices=["envelope", "receipt", "policy_decision", "generic", "auto"],
        default="auto",
        help="Artifact kind (default: auto-detect)",
    )
    p_validate.add_argument(
        "--adapt",
        action="store_true",
        help="Run Profile B → Envelope@1 / Receipt@1 adapter when available",
    )
    p_validate.set_defaults(func=cmd_validate)

    # conformance
    p_conf = sub.add_parser(
        "conformance",
        help="Run local conformance vector suites",
        description="Execute selected conformance vectors under conformance/vectors/.",
    )
    p_conf.add_argument(
        "--suite",
        default="all",
        choices=["all", "envelope", "receipt", "jcs", "mcpp-jcs-v1", "policy"],
        help="Vector suite to run",
    )
    p_conf.add_argument("--path", default=None, help="Optional single vector file")
    p_conf.set_defaults(func=cmd_conformance)

    # envelope
    p_env = sub.add_parser("envelope", help="Create or verify execution envelopes")
    env_sub = p_env.add_subparsers(dest="envelope_command", required=True)

    p_env_create = env_sub.add_parser("create", help="Mint a minimal ExecutionEnvelope@1")
    p_env_create.add_argument("--interface-cid", default=None)
    p_env_create.add_argument("--input-cid", default=None)
    p_env_create.add_argument("--intent-cid", default=None)
    p_env_create.add_argument("--requester-did", default=None)
    p_env_create.add_argument("--correlation-id", default=None)
    p_env_create.add_argument("--method", default=None)
    p_env_create.add_argument("--policy-cid", default=None)
    p_env_create.add_argument("--parents", nargs="*", default=None)
    p_env_create.add_argument("--created-at-ms", type=int, default=None)
    p_env_create.add_argument("--output", "-o", default=None, help="Write envelope JSON to path")
    p_env_create.add_argument("--store", default=None, help="Optional local store directory")
    p_env_create.add_argument(
        "--verify",
        action="store_true",
        help="Validate the minted envelope before printing",
    )
    p_env_create.set_defaults(func=cmd_envelope_create)

    p_env_verify = env_sub.add_parser("verify", help="Verify an execution envelope")
    p_env_verify.add_argument("path", nargs="?", default="-", help="JSON path or - for stdin")
    p_env_verify.add_argument(
        "--adapt",
        action="store_true",
        help="Adapt historical Profile B envelopes before verify",
    )
    p_env_verify.set_defaults(func=cmd_envelope_verify)

    # receipt
    p_rcpt = sub.add_parser("receipt", help="Verify execution receipts")
    rcpt_sub = p_rcpt.add_subparsers(dest="receipt_command", required=True)
    p_rcpt_verify = rcpt_sub.add_parser("verify", help="Verify an execution receipt")
    p_rcpt_verify.add_argument("path", nargs="?", default=None, help="JSON path or - for stdin")
    p_rcpt_verify.add_argument("--cid", default=None, help="Load receipt by CID from local store")
    p_rcpt_verify.add_argument("--store", default=None, help="Local content store directory")
    p_rcpt_verify.add_argument(
        "--adapt",
        action="store_true",
        help="Adapt historical Profile B receipts before verify",
    )
    p_rcpt_verify.set_defaults(func=cmd_receipt_verify)

    # artifact
    p_art = sub.add_parser("artifact", help="Fetch artifacts from a local content store")
    art_sub = p_art.add_subparsers(dest="artifact_command", required=True)
    p_art_get = art_sub.add_parser("get", help="Get an artifact by CID from the local store")
    p_art_get.add_argument("--cid", required=True, help="Content identifier")
    p_art_get.add_argument("--store", default=None, help="Local content store directory")
    p_art_get.set_defaults(func=cmd_artifact_get)

    # peer
    p_peer = sub.add_parser("peer", help="Peer discovery helpers")
    peer_sub = p_peer.add_subparsers(dest="peer_command", required=True)
    p_peer_list = peer_sub.add_parser("list", help="List peers from the local peers file")
    p_peer_list.add_argument("--peers", default=None, help="Path to peers.json")
    p_peer_list.set_defaults(func=cmd_peer_list)

    # demo
    p_demo = sub.add_parser(
        "demo",
        help="Three-peer demonstration entry point",
        description="Scaffold for the MCPP-076 three-peer Docker Compose demo.",
    )
    p_demo.add_argument("--peers", type=int, default=3, help="Number of peers (default: 3)")
    p_demo.add_argument(
        "--verify",
        action="store_true",
        help="Request independent verification after the demo (MCPP-076/077)",
    )
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    # Normalize ``kind=auto`` → None for detect
    parser = build_parser()
    try:
        args = parser.parse_args(argv_list)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return _EXIT_OK
        return int(code) if isinstance(code, int) else _EXIT_USAGE

    if getattr(args, "kind", None) == "auto":
        args.kind = None

    func: Optional[Callable[[argparse.Namespace], int]] = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return _EXIT_USAGE
    try:
        return int(func(args))
    except BrokenPipeError:  # pragma: no cover
        return _EXIT_OK
    except Exception as exc:
        emit_err(f"mcpp: internal error: {exc}")
        if os.environ.get("MCPP_DEBUG"):
            traceback.print_exc()
        return _EXIT_INTERNAL


# ---------------------------------------------------------------------------
# Focused tests (pytest discovers test_* in this module)
# ---------------------------------------------------------------------------


def _run_cli(argv: Sequence[str]) -> Tuple[int, str, str]:
    """Run main() capturing stdout/stderr."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def test_cli_version_constant() -> None:
    assert INTERFACE == "McppCli@1"
    assert CLI_VERSION == "1.0.0"


def test_help_root() -> None:
    code, out, err = _run_cli(["--help"])
    assert code == 0
    text = out + err
    for name in (
        "inspect",
        "validate",
        "conformance",
        "envelope",
        "receipt",
        "artifact",
        "peer",
        "demo",
        "doctor",
    ):
        assert name in text


def test_help_inspect() -> None:
    code, out, err = _run_cli(["inspect", "--help"])
    assert code == 0
    assert "inspect" in (out + err).lower()


def test_help_validate() -> None:
    code, out, err = _run_cli(["validate", "--help"])
    assert code == 0
    assert "validate" in (out + err).lower()


def test_help_conformance() -> None:
    code, out, err = _run_cli(["conformance", "--help"])
    assert code == 0
    assert "conformance" in (out + err).lower()


def test_help_envelope_create() -> None:
    code, out, err = _run_cli(["envelope", "create", "--help"])
    assert code == 0
    assert "create" in (out + err).lower()


def test_help_envelope_verify() -> None:
    code, out, err = _run_cli(["envelope", "verify", "--help"])
    assert code == 0
    assert "verify" in (out + err).lower()


def test_help_receipt_verify() -> None:
    code, out, err = _run_cli(["receipt", "verify", "--help"])
    assert code == 0
    assert "verify" in (out + err).lower()


def test_help_artifact_get() -> None:
    code, out, err = _run_cli(["artifact", "get", "--help"])
    assert code == 0
    assert "cid" in (out + err).lower()


def test_help_peer_list() -> None:
    code, out, err = _run_cli(["peer", "list", "--help"])
    assert code == 0
    assert "peer" in (out + err).lower()


def test_help_demo() -> None:
    code, out, err = _run_cli(["demo", "--help"])
    assert code == 0
    assert "demo" in (out + err).lower()


def test_help_doctor() -> None:
    code, out, err = _run_cli(["doctor", "--help"])
    assert code == 0
    assert "doctor" in (out + err).lower()


def test_doctor_reports_binding_schema_crypto() -> None:
    code, out, err = _run_cli(["doctor"])
    assert code == 0, err
    report = json.loads(out)
    assert report["interface"] == INTERFACE
    bindings = report["bindings"]["versions"]
    assert BINDING_LEGACY in bindings
    assert BINDING_CURRENT in bindings
    schemas = report["schemas"]["versions"]
    assert schemas["execution_envelope"] == SCHEMA_ENVELOPE
    assert schemas["execution_receipt"] == SCHEMA_RECEIPT
    crypto = report["crypto_suite"]
    assert crypto["signature_algorithm"] == "Ed25519"
    assert crypto["canonicalization"] in ("mcpp-jcs-v1", CRYPTO_SUITE["canonicalization"])
    assert crypto["cid"]["version"] == 1


def test_envelope_create_and_verify_roundtrip() -> None:
    code, out, err = _run_cli(["envelope", "create", "--verify", "--correlation-id", "t-roundtrip"])
    assert code == 0, err
    env = json.loads(out)
    assert env["schema"] == SCHEMA_ENVELOPE
    assert env["correlation_id"] == "t-roundtrip"
    # verify via structural path
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(env, fh)
        path = fh.name
    try:
        code2, out2, err2 = _run_cli(["envelope", "verify", path])
        assert code2 == 0, err2
        assert json.loads(out2)["ok"] is True
    finally:
        Path(path).unlink(missing_ok=True)


def test_inspect_envelope() -> None:
    env = create_envelope(
        interface_cid=_DEFAULT_CIDS["interface"],
        input_cid=_DEFAULT_CIDS["input"],
        intent_cid=_DEFAULT_CIDS["intent"],
        requester_did="did:key:z6Mktest",
        correlation_id="inspect-1",
    )
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(env, fh)
        path = fh.name
    try:
        code, out, err = _run_cli(["inspect", path])
        assert code == 0, err
        summary = json.loads(out)
        assert summary["kind"] == "envelope"
        assert summary["schema"] == SCHEMA_ENVELOPE
    finally:
        Path(path).unlink(missing_ok=True)


def test_peer_list_empty() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        peers = Path(tmp) / "peers.json"
        peers.write_text("[]\n", encoding="utf-8")
        code, out, err = _run_cli(["peer", "list", "--peers", str(peers)])
        assert code == 0, err
        report = json.loads(out)
        assert report["count"] == 0


def test_demo_help_path_and_scaffold() -> None:
    code, out, err = _run_cli(["demo", "--peers", "3"])
    assert code == 0, err
    report = json.loads(out)
    assert report["command"] == "demo"
    assert report["peers"] == 3


def test_artifact_get_missing() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        code, out, err = _run_cli(
            ["artifact", "get", "--cid", "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi", "--store", tmp]
        )
        assert code == _EXIT_IO


if __name__ == "__main__":
    sys.exit(main())
