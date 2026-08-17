#!/usr/bin/env python3
"""Independent MCP++ evidence-bundle verifier — IndependentVerifier@1 (MCPP-077).

Validates a machine-readable ``DemoEvidenceBundle@1`` produced by the three-peer
demonstration. This process is **not** a demo peer: it only reads a bundle
(and optional embedded artifact payloads) and exits:

  * ``0`` — structural shape, declared CIDs, and signatures all verify
  * nonzero — any structural failure, CID mismatch (tamper), or signature failure

Schema:
  ``docs/reports/mcplusplus-1.0-gap-closure/demo/evidence-bundle.schema.json``

Crypto suite (ADR-0002 / KD-4 / KD-5):
  * Ed25519 over mcpp-jcs-v1 (RFC 8785 JCS) canonical UTF-8 bytes
  * CIDv1 + multicodec raw (0x55) + multihash sha2-256 (0x12)

Usage:
  python -m ipfs_accelerate_py.mcplusplus.cli.verify_bundle path/to/bundle.json
  python ipfs_accelerate_py/mcplusplus/cli/verify_bundle.py path/to/bundle.json
  python ipfs_accelerate_py/mcplusplus/cli/verify_bundle.py --self-test
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Interface pins
# ---------------------------------------------------------------------------

INTERFACE = "IndependentVerifier@1"
BUNDLE_INTERFACE = "DemoEvidenceBundle@1"
BUNDLE_SCHEMA = "mcp++/demo/evidence-bundle@1"
BUNDLE_ID = "mcplusplus/1.0/demo-verifier"
TASK_ID = "MCPP-077"
GOAL_ID = "MCPP-G160"
CANONICALIZATION = "mcpp-jcs-v1"
SIGNATURE_ALG = "Ed25519"
VERIFIER_VERSION = "1.0.0"

SCHEMA_MARKER_ENVELOPE = "mcp++/execution/envelope@1"
SCHEMA_MARKER_RECEIPT = "mcp++/execution/receipt@1"
SCHEMA_MARKER_RESULT = "mcp++/execution/result@1"
SCHEMA_MARKER_ERROR = "mcp++/execution/portable-error@1"
SCHEMA_MARKER_CANON = "mcp++/canonicalization/mcpp-jcs-v1@1"

CID_VERSION = 1
MULTICODEC_RAW = 0x55
MULTIHASH_SHA2_256 = 0x12
MULTIHASH_LEN = 32

CID_RE = re.compile(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$")
DID_RE = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$")
HEX_SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")
HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

_EXIT_OK = 0
_EXIT_USAGE = 2
_EXIT_VALIDATION = 3
_EXIT_TAMPER = 4
_EXIT_IO = 5
_EXIT_INTERNAL = 6

# Fields excluded from detached signing payloads (ADR-0002 / receipt style).
_SIG_META_KEYS = frozenset(
    {
        "signature",
        "sig",
        "signatures",
        "signature_alg",
        "signatureAlg",
        "public_key",
        "publicKey",
        "public_key_b64",
        "public_key_b64url",
        "issuer_public_key",
        "bundle_cid",
        "receipt_cid",
    }
)

# Map artifact role → cids map key.
_ROLE_TO_CID_KEY = {
    "interface": "interface_cid",
    "envelope": "envelope_cid",
    "policy": "policy_cid",
    "proof": "proof_cid",
    "decision": "decision_cid",
    "state": "state_cid",
    "output": "output_cid",
    "receipt": "receipt_cid",
    "event": "event_cid",
    "delegation": "delegation_cid",
    "result": "result_cid",
}

_REQUIRED_CID_KEYS = (
    "interface_cid",
    "envelope_cid",
    "output_cid",
    "receipt_cid",
    "event_cid",
)

# ---------------------------------------------------------------------------
# Optional cryptography
# ---------------------------------------------------------------------------

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    HAVE_CRYPTO = True
except Exception:  # pragma: no cover
    InvalidSignature = Exception  # type: ignore[misc, assignment]
    Ed25519PrivateKey = None  # type: ignore[misc, assignment]
    Ed25519PublicKey = None  # type: ignore[misc, assignment]
    HAVE_CRYPTO = False


# ---------------------------------------------------------------------------
# mcpp-jcs-v1 (self-contained; prefer package validator when importable)
# ---------------------------------------------------------------------------

_ESCAPE = re.compile(r'[\x00-\x1f\\"\b\f\n\r\t]')
_ESCAPE_DCT = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}
for _i in range(0x20):
    _ESCAPE_DCT.setdefault(chr(_i), f"\\u{_i:04x}")

SAFE_INTEGER_MIN = -9007199254740991
SAFE_INTEGER_MAX = 9007199254740991


class McppJcsError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        super().__init__(message)


def _utf16_code_units(text: str) -> List[int]:
    units: List[int] = []
    for ch in text:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            raise McppJcsError(
                "reject_lone_surrogate",
                f"lone UTF-16 surrogate U+{cp:04X}",
            )
        if cp >= 0x10000:
            cp -= 0x10000
            units.append(0xD800 | ((cp >> 10) & 0x3FF))
            units.append(0xDC00 | (cp & 0x3FF))
        else:
            units.append(cp)
    return units


def _es6_number_to_string(value: float | int) -> str:
    if isinstance(value, bool):
        raise McppJcsError("reject_unsupported_type", "boolean is not a JSON number")
    if isinstance(value, int) and not isinstance(value, bool):
        if value < SAFE_INTEGER_MIN or value > SAFE_INTEGER_MAX:
            raise McppJcsError("reject_unsafe_integer", f"integer {value} out of range")
        return str(value)
    fvalue = float(value)
    if math.isnan(fvalue) or math.isinf(fvalue):
        raise McppJcsError("reject_nan_infinity", "NaN and ±Infinity are not JSON numbers")
    if fvalue == 0.0:
        return "0"
    # Good-enough ES6-compatible path for conformance fixtures and evidence bodies.
    text = json.dumps(fvalue, allow_nan=False)
    if text.startswith("+"):
        text = text[1:]
    return text


def _escape_string(s: str) -> str:
    def repl(match: re.Match[str]) -> str:
        ch = match.group(0)
        return _ESCAPE_DCT.get(ch, f"\\u{ord(ch):04x}")

    return '"' + _ESCAPE.sub(repl, s) + '"'


def _canonicalize_value(value: Any, seen: set[int]) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return _es6_number_to_string(value)
    if isinstance(value, float):
        return _es6_number_to_string(value)
    if isinstance(value, list):
        obj_id = id(value)
        if obj_id in seen:
            raise McppJcsError("reject_cycles", "cycle in array")
        seen.add(obj_id)
        try:
            return "[" + ",".join(_canonicalize_value(v, seen) for v in value) + "]"
        finally:
            seen.discard(obj_id)
    if isinstance(value, Mapping):
        obj_id = id(value)
        if obj_id in seen:
            raise McppJcsError("reject_cycles", "cycle in object")
        seen.add(obj_id)
        try:
            keys = sorted((str(k) for k in value.keys()), key=_utf16_code_units)
            parts = [
                _escape_string(k) + ":" + _canonicalize_value(value[k], seen)  # type: ignore[index]
                for k in keys
            ]
            return "{" + ",".join(parts) + "}"
        finally:
            seen.discard(obj_id)
    raise McppJcsError("reject_unsupported_type", f"unsupported type {type(value)!r}")


def canonicalize_bytes_local(value: Any) -> bytes:
    text = _canonicalize_value(value, set())
    if text.endswith("\n") or text.endswith("\r"):
        raise McppJcsError("reject_non_canonical_bytes", "trailing newline forbidden")
    data = text.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        raise McppJcsError("reject_non_canonical_bytes", "BOM forbidden")
    return data


def _base32_lower_nopad(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").lower().rstrip("=")


def cid_v1_raw_sha256(digest32: bytes) -> str:
    if len(digest32) != MULTIHASH_LEN:
        raise McppJcsError("reject_digest_len", "sha2-256 digest must be 32 bytes")
    raw = bytes([CID_VERSION, MULTICODEC_RAW, MULTIHASH_SHA2_256, MULTIHASH_LEN]) + digest32
    return "b" + _base32_lower_nopad(raw)


def artifact_cid_local(value: Any) -> str:
    digest = hashlib.sha256(canonicalize_bytes_local(value)).digest()
    return cid_v1_raw_sha256(digest)


def _try_import_package_jcs() -> Tuple[Any, Any]:
    """Prefer the four-language validator implementation when available."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "tests-py",
        here.parent.parent.parent.parent / "ipfs_accelerate_py" / "mcplusplus" / "tests-py",
    ]
    for root in candidates:
        if not root.is_dir():
            continue
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from validators.canonical_jcs import (  # type: ignore
                artifact_cid as pkg_cid,
                canonicalize_bytes as pkg_canon,
            )

            return pkg_canon, pkg_cid
        except Exception:
            continue
    return canonicalize_bytes_local, artifact_cid_local


canonicalize_bytes, artifact_cid = _try_import_package_jcs()


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty_base64url")
    pad = "=" * ((4 - (len(text) % 4)) % 4)
    return base64.urlsafe_b64decode(text + pad)


def decode_public_key(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return raw if len(raw) == 32 else None
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 64:
        try:
            raw = bytes.fromhex(text)
            return raw if len(raw) == 32 else None
        except ValueError:
            pass
    try:
        raw = b64url_decode(text)
        return raw if len(raw) == 32 else None
    except Exception:
        return None


def decode_signature(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return raw if len(raw) == 64 else None
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 128:
        try:
            raw = bytes.fromhex(text)
            return raw if len(raw) == 64 else None
        except ValueError:
            return None
    try:
        raw = b64url_decode(text)
        return raw if len(raw) == 64 else None
    except Exception:
        return None


def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if not HAVE_CRYPTO:
        return False
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def signing_object(doc: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k not in _SIG_META_KEYS}


def bundle_body_for_cid(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    """Document body used for ``bundle_cid`` (excludes self-address only)."""
    return {k: v for k, v in bundle.items() if k != "bundle_cid"}


def bundle_body_for_signature(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    """Detached body for top-level / role=bundle signatures."""
    return {
        k: v
        for k, v in bundle.items()
        if k not in {"signature", "signatures", "bundle_cid"}
    }


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    ok: bool
    reason_code: Optional[str] = None
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"name": self.name, "ok": self.ok}
        if self.reason_code:
            out["reason_code"] = self.reason_code
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass
class VerifyVerdict:
    accepted: bool
    exit_code: int
    reason_codes: List[str] = field(default_factory=list)
    checks: List[CheckResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add(
        self,
        name: str,
        ok: bool,
        *,
        reason_code: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        self.checks.append(
            CheckResult(name=name, ok=ok, reason_code=reason_code, detail=detail)
        )
        if not ok:
            self.accepted = False
            if reason_code and reason_code not in self.reason_codes:
                self.reason_codes.append(reason_code)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "exit_code": self.exit_code if not self.accepted else _EXIT_OK,
            "reason_codes": list(self.reason_codes),
            "checks": [c.to_dict() for c in self.checks],
            "metadata": self.metadata,
            "interface": INTERFACE,
            "bundle_interface": BUNDLE_INTERFACE,
            "verifier_version": VERIFIER_VERSION,
            "task_id": TASK_ID,
        }


# ---------------------------------------------------------------------------
# Structural validation (fail-closed; does not require jsonschema package)
# ---------------------------------------------------------------------------


def _is_cid(value: Any) -> bool:
    return isinstance(value, str) and bool(CID_RE.match(value))


def _is_optional_cid(value: Any) -> bool:
    return value is None or _is_cid(value)


def structural_validate(bundle: Mapping[str, Any], verdict: VerifyVerdict) -> None:
    if not isinstance(bundle, Mapping):
        verdict.add(
            "type",
            False,
            reason_code="not_an_object",
            detail="bundle root must be a JSON object",
        )
        return

    if bundle.get("schema") != BUNDLE_SCHEMA:
        verdict.add(
            "schema",
            False,
            reason_code="schema_mismatch",
            detail=f"expected {BUNDLE_SCHEMA!r}, got {bundle.get('schema')!r}",
        )
    else:
        verdict.add("schema", True)

    if bundle.get("interface") != BUNDLE_INTERFACE:
        verdict.add(
            "interface",
            False,
            reason_code="interface_mismatch",
            detail=f"expected {BUNDLE_INTERFACE!r}",
        )
    else:
        verdict.add("interface", True)

    if bundle.get("canonicalization") != CANONICALIZATION:
        verdict.add(
            "canonicalization",
            False,
            reason_code="canonicalization_mismatch",
            detail=f"expected {CANONICALIZATION!r}",
        )
    else:
        verdict.add("canonicalization", True)

    for key in (
        "schema_version",
        "task_id",
        "goal_id",
        "generated_at",
        "commits",
        "schema_versions",
        "cids",
        "signatures",
        "test_results",
        "external_dependencies",
    ):
        if key not in bundle:
            verdict.add(
                f"required.{key}",
                False,
                reason_code="missing_field",
                detail=f"missing required field {key}",
            )

    commits = bundle.get("commits")
    if isinstance(commits, Mapping):
        head = commits.get("head")
        if not isinstance(head, str) or not HEX_SHA_RE.match(head):
            verdict.add(
                "commits.head",
                False,
                reason_code="invalid_commit_sha",
                detail="commits.head must be lowercase hex git SHA",
            )
        else:
            verdict.add("commits.head", True)
    elif "commits" in bundle:
        verdict.add(
            "commits",
            False,
            reason_code="invalid_commits",
            detail="commits must be an object",
        )

    schema_versions = bundle.get("schema_versions")
    if isinstance(schema_versions, Mapping) and schema_versions:
        verdict.add("schema_versions", True)
    elif "schema_versions" in bundle:
        verdict.add(
            "schema_versions",
            False,
            reason_code="invalid_schema_versions",
            detail="schema_versions must be a non-empty object",
        )

    cids = bundle.get("cids")
    if isinstance(cids, Mapping):
        for key in _REQUIRED_CID_KEYS:
            if key not in cids:
                verdict.add(
                    f"cids.{key}",
                    False,
                    reason_code="missing_cid",
                    detail=f"cids.{key} is required",
                )
            elif not _is_cid(cids.get(key)):
                verdict.add(
                    f"cids.{key}",
                    False,
                    reason_code="invalid_cid_format",
                    detail=f"cids.{key} is not a valid CID",
                )
            else:
                verdict.add(f"cids.{key}", True)
        for key in (
            "policy_cid",
            "proof_cid",
            "decision_cid",
            "state_cid",
            "delegation_cid",
            "result_cid",
        ):
            if key in cids and not _is_optional_cid(cids.get(key)):
                verdict.add(
                    f"cids.{key}",
                    False,
                    reason_code="invalid_cid_format",
                    detail=f"cids.{key} is not a valid CID or null",
                )
    elif "cids" in bundle:
        verdict.add(
            "cids",
            False,
            reason_code="invalid_cids",
            detail="cids must be an object",
        )

    signatures = bundle.get("signatures")
    if isinstance(signatures, list) and len(signatures) >= 1:
        for i, sig in enumerate(signatures):
            if not isinstance(sig, Mapping):
                verdict.add(
                    f"signatures[{i}]",
                    False,
                    reason_code="invalid_signature_entry",
                    detail="signature entry must be an object",
                )
                continue
            for field_name in (
                "role",
                "algorithm",
                "kid",
                "public_key_b64url",
                "signature_b64url",
            ):
                if field_name not in sig:
                    verdict.add(
                        f"signatures[{i}].{field_name}",
                        False,
                        reason_code="missing_signature_field",
                        detail=f"missing {field_name}",
                    )
            if sig.get("algorithm") not in (None, SIGNATURE_ALG):
                verdict.add(
                    f"signatures[{i}].algorithm",
                    False,
                    reason_code="unsupported_signature_alg",
                    detail=f"only {SIGNATURE_ALG} is accepted",
                )
        if all(c.ok for c in verdict.checks if c.name.startswith("signatures[")):
            verdict.add("signatures", True)
    elif "signatures" in bundle:
        verdict.add(
            "signatures",
            False,
            reason_code="invalid_signatures",
            detail="signatures must be a non-empty array",
        )

    tests = bundle.get("test_results")
    if isinstance(tests, list) and len(tests) >= 1:
        for i, t in enumerate(tests):
            if not isinstance(t, Mapping) or "name" not in t or "status" not in t:
                verdict.add(
                    f"test_results[{i}]",
                    False,
                    reason_code="invalid_test_result",
                    detail="each test result needs name and status",
                )
        if all(c.ok for c in verdict.checks if c.name.startswith("test_results[")):
            verdict.add("test_results", True)
    elif "test_results" in bundle:
        verdict.add(
            "test_results",
            False,
            reason_code="invalid_test_results",
            detail="test_results must be a non-empty array",
        )

    deps = bundle.get("external_dependencies")
    if isinstance(deps, list):
        for i, d in enumerate(deps):
            if not isinstance(d, Mapping) or not all(
                k in d for k in ("name", "required", "status")
            ):
                verdict.add(
                    f"external_dependencies[{i}]",
                    False,
                    reason_code="invalid_external_dependency",
                    detail="dependency needs name, required, status",
                )
        if all(
            c.ok for c in verdict.checks if c.name.startswith("external_dependencies[")
        ):
            verdict.add("external_dependencies", True)
    elif "external_dependencies" in bundle:
        verdict.add(
            "external_dependencies",
            False,
            reason_code="invalid_external_dependencies",
            detail="external_dependencies must be an array",
        )

    if "bundle_cid" in bundle and bundle["bundle_cid"] is not None:
        if not _is_cid(bundle["bundle_cid"]):
            verdict.add(
                "bundle_cid",
                False,
                reason_code="invalid_cid_format",
                detail="bundle_cid is not a valid CID",
            )


# ---------------------------------------------------------------------------
# CID verification
# ---------------------------------------------------------------------------


def verify_cids(bundle: Mapping[str, Any], verdict: VerifyVerdict) -> None:
    cids = bundle.get("cids")
    if not isinstance(cids, Mapping):
        return

    artifacts = bundle.get("artifacts")
    if artifacts is None:
        # Without payloads we can only format-check (already done structurally).
        verdict.add(
            "cid_recompute",
            True,
            detail="no embedded artifacts; format-only CID checks",
        )
    elif not isinstance(artifacts, list):
        verdict.add(
            "artifacts",
            False,
            reason_code="invalid_artifacts",
            detail="artifacts must be an array when present",
        )
        return
    else:
        for i, entry in enumerate(artifacts):
            if not isinstance(entry, Mapping):
                verdict.add(
                    f"artifacts[{i}]",
                    False,
                    reason_code="invalid_artifact_entry",
                    detail="artifact entry must be an object",
                )
                continue
            role = entry.get("role")
            declared = entry.get("cid")
            payload = entry.get("payload")
            if not isinstance(role, str) or not _is_cid(declared):
                verdict.add(
                    f"artifacts[{i}]",
                    False,
                    reason_code="invalid_artifact_entry",
                    detail="role and cid required",
                )
                continue
            try:
                recomputed = artifact_cid(payload)
            except Exception as exc:
                verdict.add(
                    f"artifacts[{i}].cid",
                    False,
                    reason_code="cid_compute_error",
                    detail=str(exc),
                )
                continue
            if recomputed != declared:
                verdict.add(
                    f"artifacts[{i}].cid",
                    False,
                    reason_code="cid_mismatch",
                    detail=(
                        f"role={role}: declared {declared} != recomputed {recomputed}"
                    ),
                )
            else:
                verdict.add(f"artifacts[{i}].cid", True)

            cid_key = _ROLE_TO_CID_KEY.get(role)
            if cid_key and cid_key in cids and cids[cid_key] is not None:
                if cids[cid_key] != declared:
                    verdict.add(
                        f"artifacts[{i}].cids_map",
                        False,
                        reason_code="cid_map_mismatch",
                        detail=(
                            f"cids.{cid_key}={cids[cid_key]!r} != artifact cid {declared!r}"
                        ),
                    )
                else:
                    verdict.add(f"artifacts[{i}].cids_map", True)

    # Self-address of the bundle when declared.
    declared_bundle_cid = bundle.get("bundle_cid")
    if declared_bundle_cid:
        try:
            body = bundle_body_for_cid(bundle)
            recomputed = artifact_cid(body)
        except Exception as exc:
            verdict.add(
                "bundle_cid",
                False,
                reason_code="cid_compute_error",
                detail=str(exc),
            )
            return
        if recomputed != declared_bundle_cid:
            verdict.add(
                "bundle_cid",
                False,
                reason_code="cid_mismatch",
                detail=(
                    f"bundle_cid declared {declared_bundle_cid} != recomputed {recomputed}"
                ),
            )
        else:
            verdict.add("bundle_cid", True)
            verdict.metadata["recomputed_bundle_cid"] = recomputed


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def _signed_message_for_entry(
    bundle: Mapping[str, Any], entry: Mapping[str, Any]
) -> Tuple[Optional[bytes], Optional[str]]:
    """Return (message_bytes, error_reason)."""
    signed_over = entry.get("signed_over")
    role = str(entry.get("role") or "")

    if signed_over is None:
        if role == "bundle":
            signed_over = "bundle_body"
        elif entry.get("artifact_role"):
            signed_over = "artifact_payload"
        elif "payload" in entry:
            signed_over = "embedded_payload"
        else:
            signed_over = "bundle_body"

    try:
        if signed_over == "bundle_body":
            return canonicalize_bytes(bundle_body_for_signature(bundle)), None
        if signed_over == "embedded_payload":
            if "payload" not in entry:
                return None, "missing_embedded_payload"
            payload = entry["payload"]
            if isinstance(payload, Mapping):
                payload = signing_object(payload)
            return canonicalize_bytes(payload), None
        if signed_over == "artifact_payload":
            art_role = entry.get("artifact_role") or role
            if art_role == "bundle":
                return None, "artifact_role_required"
            artifacts = bundle.get("artifacts") or []
            if not isinstance(artifacts, list):
                return None, "missing_artifacts"
            match = None
            for a in artifacts:
                if isinstance(a, Mapping) and a.get("role") == art_role:
                    match = a
                    break
            if match is None:
                return None, f"artifact_not_found:{art_role}"
            payload = match.get("payload")
            if isinstance(payload, Mapping):
                payload = signing_object(payload)
            return canonicalize_bytes(payload), None
        if signed_over == "raw_bytes_sha256":
            digest_hex = entry.get("message_sha256")
            if not isinstance(digest_hex, str) or not HEX_DIGEST_RE.match(digest_hex):
                return None, "missing_message_sha256"
            # For this mode the signature covers the raw 32-byte digest.
            return bytes.fromhex(digest_hex), None
        return None, f"unsupported_signed_over:{signed_over}"
    except Exception as exc:
        return None, f"canonicalize_error:{exc}"


def verify_signatures(bundle: Mapping[str, Any], verdict: VerifyVerdict) -> None:
    if not HAVE_CRYPTO:
        verdict.add(
            "crypto_available",
            False,
            reason_code="crypto_unavailable",
            detail="cryptography package with Ed25519 is required",
        )
        return
    verdict.add("crypto_available", True)

    signatures = bundle.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return

    for i, entry in enumerate(signatures):
        if not isinstance(entry, Mapping):
            continue
        pub = decode_public_key(entry.get("public_key_b64url"))
        sig = decode_signature(entry.get("signature_b64url"))
        if pub is None:
            verdict.add(
                f"signatures[{i}].public_key",
                False,
                reason_code="invalid_public_key",
                detail="public_key_b64url must decode to 32 bytes",
            )
            continue
        if sig is None:
            verdict.add(
                f"signatures[{i}].signature",
                False,
                reason_code="invalid_signature_encoding",
                detail="signature_b64url must decode to 64 bytes",
            )
            continue
        message, err = _signed_message_for_entry(bundle, entry)
        if message is None:
            verdict.add(
                f"signatures[{i}].message",
                False,
                reason_code="signed_message_error",
                detail=err or "unknown",
            )
            continue

        digest_hex = hashlib.sha256(message).hexdigest()
        expected_digest = entry.get("message_sha256")
        if isinstance(expected_digest, str) and expected_digest:
            if expected_digest != digest_hex and entry.get("signed_over") != "raw_bytes_sha256":
                verdict.add(
                    f"signatures[{i}].message_sha256",
                    False,
                    reason_code="message_digest_mismatch",
                    detail=f"declared {expected_digest} != recomputed {digest_hex}",
                )
                # Still attempt signature verify for additional diagnostics.

        if not verify_ed25519(pub, message, sig):
            verdict.add(
                f"signatures[{i}].verify",
                False,
                reason_code="signature_invalid",
                detail=f"Ed25519 verification failed for role={entry.get('role')!r}",
            )
        else:
            verdict.add(f"signatures[{i}].verify", True)

    # Optional top-level signature convenience field.
    top = bundle.get("signature")
    if isinstance(top, Mapping):
        pub = decode_public_key(top.get("public_key_b64url"))
        sig = decode_signature(top.get("signature_b64url"))
        if pub is None or sig is None:
            verdict.add(
                "signature",
                False,
                reason_code="invalid_top_level_signature",
                detail="top-level signature encoding invalid",
            )
        else:
            try:
                message = canonicalize_bytes(bundle_body_for_signature(bundle))
            except Exception as exc:
                verdict.add(
                    "signature",
                    False,
                    reason_code="signed_message_error",
                    detail=str(exc),
                )
                return
            if not verify_ed25519(pub, message, sig):
                verdict.add(
                    "signature",
                    False,
                    reason_code="signature_invalid",
                    detail="top-level Ed25519 verification failed",
                )
            else:
                verdict.add("signature", True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_bundle(bundle: Mapping[str, Any]) -> VerifyVerdict:
    """Verify a DemoEvidenceBundle@1 document. Fail closed on tamper."""
    verdict = VerifyVerdict(accepted=True, exit_code=_EXIT_OK)
    verdict.metadata["process"] = "independent"
    verdict.metadata["not_a_demo_peer"] = True
    verdict.metadata["canonicalization"] = CANONICALIZATION
    verdict.metadata["signature_algorithm"] = SIGNATURE_ALG

    structural_validate(bundle, verdict)
    if not verdict.accepted and any(
        c.reason_code
        in {
            "not_an_object",
            "schema_mismatch",
            "interface_mismatch",
            "missing_field",
        }
        for c in verdict.checks
        if not c.ok
    ):
        # Still run crypto/CID checks when possible for fuller reports, but
        # structural failure already fails closed.
        pass

    verify_cids(bundle, verdict)
    verify_signatures(bundle, verdict)

    if not verdict.accepted:
        # Prefer tamper exit code when CID or signature failed.
        tamper_codes = {
            "cid_mismatch",
            "cid_map_mismatch",
            "signature_invalid",
            "message_digest_mismatch",
        }
        if any(code in tamper_codes for code in verdict.reason_codes):
            verdict.exit_code = _EXIT_TAMPER
        else:
            verdict.exit_code = _EXIT_VALIDATION
    else:
        verdict.exit_code = _EXIT_OK
    return verdict


def load_bundle(path: Path) -> Mapping[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("bundle root must be a JSON object")
    return data


def schema_path_candidates() -> List[Path]:
    here = Path(__file__).resolve()
    monorepo = here.parents[3]  # .../ipfs_accelerate_py/mcplusplus/cli → monorepo?
    # cli -> mcplusplus -> ipfs_accelerate_py -> repo root
    roots = [
        here.parents[3],
        here.parents[2],
        Path.cwd(),
    ]
    rel = Path("docs/reports/mcplusplus-1.0-gap-closure/demo/evidence-bundle.schema.json")
    out: List[Path] = []
    for root in roots:
        candidate = root / rel
        if candidate not in out:
            out.append(candidate)
    # Also try relative walk from package root
    pkg = here.parent.parent
    out.append(pkg.parents[1] / rel)
    return out


def locate_schema() -> Optional[Path]:
    for p in schema_path_candidates():
        if p.is_file():
            return p
    return None


# ---------------------------------------------------------------------------
# Fixture minting (for --self-test / operator demos)
# ---------------------------------------------------------------------------


def mint_valid_bundle(
    *,
    private_key: Optional[Any] = None,
    head_sha: str = "0123456789abcdef0123456789abcdef01234567",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Mint a cryptographically valid DemoEvidenceBundle@1 for tests.

    Returns ``(bundle, meta)`` where meta includes public_key_b64url.
    """
    if not HAVE_CRYPTO:
        raise RuntimeError("cryptography Ed25519 required to mint fixtures")

    priv = private_key or Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes_raw()
    pub_b64 = b64url_encode(pub)

    # Content-addressed demo artifacts (small deterministic payloads).
    interface_payload = {
        "schema": "mcp++/demo/interface-pin@1",
        "name": "demo.echo",
        "version": "1",
    }
    envelope_payload = {
        "schema": SCHEMA_MARKER_ENVELOPE,
        "requester_did": "did:web:demo-runner.example",
        "input_cid_hint": "demo-input",
    }
    policy_payload = {"schema": "mcp++/policy/pin@1", "effect": "permit"}
    proof_payload = {"schema": "mcp++/proof/pin@1", "kind": "ucan-ref"}
    decision_payload = {"schema": "mcp++/policy/decision@1", "decision": "allow"}
    state_payload = {"schema": "mcp++/state/root@1", "mode": "single_authority"}
    output_payload = {"schema": "mcp++/demo/output@1", "ok": True}
    receipt_payload = {
        "schema": SCHEMA_MARKER_RECEIPT,
        "status": "succeeded",
        "executor": {"did": "did:key:zDemoVerifierFixture"},
    }
    event_payload = {
        "schema": "mcp++/event-dag/node@1",
        "type": "task_completed",
    }

    roles_payloads = {
        "interface": interface_payload,
        "envelope": envelope_payload,
        "policy": policy_payload,
        "proof": proof_payload,
        "decision": decision_payload,
        "state": state_payload,
        "output": output_payload,
        "receipt": receipt_payload,
        "event": event_payload,
    }
    artifacts = []
    cids: Dict[str, Any] = {}
    for role, payload in roles_payloads.items():
        cid = artifact_cid(payload)
        artifacts.append({"role": role, "cid": cid, "payload": payload})
        cids[_ROLE_TO_CID_KEY[role]] = cid

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle: Dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "interface": BUNDLE_INTERFACE,
        "schema_version": "1.0.0",
        "task_id": TASK_ID,
        "goal_id": GOAL_ID,
        "bundle": BUNDLE_ID,
        "generated_at": now,
        "canonicalization": CANONICALIZATION,
        "commits": {
            "head": head_sha,
            "branch": "main",
            "dirty": False,
            "repositories": [
                {"id": "ipfs-accelerate", "sha": head_sha, "ref": "main"}
            ],
        },
        "schema_versions": {
            "execution_envelope": SCHEMA_MARKER_ENVELOPE,
            "execution_receipt": SCHEMA_MARKER_RECEIPT,
            "execution_result": SCHEMA_MARKER_RESULT,
            "portable_error": SCHEMA_MARKER_ERROR,
            "canonicalization": SCHEMA_MARKER_CANON,
            "evidence_bundle": BUNDLE_SCHEMA,
            "three_peer_demo": "ThreePeerDemo@1",
            "crypto_suite": "mcp++/crypto-suite@1",
        },
        "cids": cids,
        "artifacts": artifacts,
        "signatures": [],  # filled below
        "test_results": [
            {
                "name": "three-peer-demo-steps",
                "status": "pass",
                "command": "docker compose up --abort-on-container-exit --exit-code-from demo-runner",
                "exit_code": 0,
                "suite": "ThreePeerDemo@1",
            },
            {
                "name": "profile-g-exclusive-safety",
                "status": "pass",
                "suite": "ThreePeerHarness@1",
                "exit_code": 0,
            },
        ],
        "external_dependencies": [
            {
                "name": "docker-compose",
                "version": "v2",
                "required": True,
                "status": "present",
            },
            {
                "name": "circuit-relay-v2",
                "required": False,
                "status": "documented-not-required",
                "notes": (
                    "Optional relays are not part of the happy path; missing relays "
                    "are documented blockers for WAN/NAT assertions only."
                ),
            },
        ],
        "demo": {
            "interface": "ThreePeerDemo@1",
            "peers": 3,
            "steps_total": 16,
            "steps_passed": 16,
            "status": "pass",
            "optional_relays": {
                "required_for_happy_path": False,
                "status": "documented-not-required",
            },
        },
        "producer": {
            "name": "verify_bundle.py",
            "version": VERIFIER_VERSION,
            "did": "did:web:independent-verifier.example",
            "peer_id": None,
        },
        "notes": [
            "Minted by IndependentVerifier@1 for fixture / self-test use.",
            "This process is not a demo peer.",
        ],
    }

    # Bundle signature over detached body (no signatures / signature / bundle_cid).
    body = bundle_body_for_signature(bundle)
    message = canonicalize_bytes(body)
    sig = priv.sign(message)
    sig_entry = {
        "role": "bundle",
        "algorithm": SIGNATURE_ALG,
        "kid": "demo-verifier-v1",
        "signer_did": "did:web:independent-verifier.example",
        "public_key_b64url": pub_b64,
        "signature_b64url": b64url_encode(sig),
        "signed_over": "bundle_body",
        "message_sha256": hashlib.sha256(message).hexdigest(),
    }
    bundle["signatures"] = [sig_entry]

    # Also sign the receipt artifact for multi-signature coverage.
    receipt_message = canonicalize_bytes(signing_object(receipt_payload))
    receipt_sig = priv.sign(receipt_message)
    bundle["signatures"].append(
        {
            "role": "receipt",
            "algorithm": SIGNATURE_ALG,
            "kid": "demo-verifier-v1",
            "signer_did": "did:web:independent-verifier.example",
            "public_key_b64url": pub_b64,
            "signature_b64url": b64url_encode(receipt_sig),
            "signed_over": "artifact_payload",
            "artifact_role": "receipt",
            "message_sha256": hashlib.sha256(receipt_message).hexdigest(),
        }
    )

    # Self-address after signatures are attached.
    bundle["bundle_cid"] = artifact_cid(bundle_body_for_cid(bundle))

    meta = {
        "public_key_b64url": pub_b64,
        "private_key": priv,
        "message_sha256": sig_entry["message_sha256"],
    }
    return bundle, meta


def run_self_test() -> int:
    """Prove acceptance: valid → 0; CID tamper → nonzero; signature tamper → nonzero."""
    report: Dict[str, Any] = {
        "interface": INTERFACE,
        "task_id": TASK_ID,
        "self_test": True,
        "cases": [],
    }

    if not HAVE_CRYPTO:
        report["accepted"] = False
        report["error"] = "cryptography Ed25519 unavailable"
        print(json.dumps(report, indent=2, sort_keys=True))
        return _EXIT_INTERNAL

    bundle, _meta = mint_valid_bundle()

    # Case 1: valid
    v1 = verify_bundle(bundle)
    report["cases"].append(
        {
            "name": "valid_bundle",
            "accepted": v1.accepted,
            "exit_code": v1.exit_code,
            "reason_codes": v1.reason_codes,
        }
    )
    if not v1.accepted or v1.exit_code != _EXIT_OK:
        report["accepted"] = False
        report["error"] = "valid bundle failed verification"
        report["verdict"] = v1.to_dict()
        print(json.dumps(report, indent=2, sort_keys=True))
        return _EXIT_INTERNAL

    # Case 2: tamper a declared artifact CID
    tampered_cid = dict(bundle)
    tampered_cid = json.loads(json.dumps(bundle))  # deep copy
    arts = tampered_cid["artifacts"]
    arts[0]["cid"] = "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    # Keep cids map in sync so only the artifact self-check fires, or break map too.
    role0 = arts[0]["role"]
    key0 = _ROLE_TO_CID_KEY[role0]
    tampered_cid["cids"][key0] = arts[0]["cid"]
    # Recompute bundle_cid would still fail if we leave old self-cid; drop it so
    # the failure is clearly the artifact CID.
    tampered_cid.pop("bundle_cid", None)
    # Signatures still cover original body; pop signatures re-check or leave —
    # body change would also invalidate signature. For pure CID tamper of an
    # embedded artifact without changing the signed bundle_body fields that
    # include artifacts, signatures over bundle_body will also fail. That is
    # correct fail-closed behaviour; we still assert cid_mismatch is reported
    # when verifying a payload whose declared cid was swapped:
    v2 = verify_bundle(tampered_cid)
    report["cases"].append(
        {
            "name": "tampered_cid",
            "accepted": v2.accepted,
            "exit_code": v2.exit_code,
            "reason_codes": v2.reason_codes,
        }
    )
    if v2.accepted or v2.exit_code == _EXIT_OK:
        report["accepted"] = False
        report["error"] = "tampered CID was accepted"
        print(json.dumps(report, indent=2, sort_keys=True))
        return _EXIT_INTERNAL
    if "cid_mismatch" not in v2.reason_codes and "signature_invalid" not in v2.reason_codes:
        report["accepted"] = False
        report["error"] = "expected cid_mismatch or signature_invalid after CID tamper"
        print(json.dumps(report, indent=2, sort_keys=True))
        return _EXIT_INTERNAL

    # Case 3: pure signature tamper (flip one byte of signature, leave CIDs intact)
    tampered_sig = json.loads(json.dumps(bundle))
    raw_sig = bytearray(b64url_decode(tampered_sig["signatures"][0]["signature_b64url"]))
    raw_sig[0] ^= 0x01
    tampered_sig["signatures"][0]["signature_b64url"] = b64url_encode(bytes(raw_sig))
    # bundle_cid included the old signature bytes; drop self-cid to isolate sig check
    # (self-cid would also mismatch — both are tamper).
    tampered_sig.pop("bundle_cid", None)
    v3 = verify_bundle(tampered_sig)
    report["cases"].append(
        {
            "name": "tampered_signature",
            "accepted": v3.accepted,
            "exit_code": v3.exit_code,
            "reason_codes": v3.reason_codes,
        }
    )
    if v3.accepted or v3.exit_code == _EXIT_OK:
        report["accepted"] = False
        report["error"] = "tampered signature was accepted"
        print(json.dumps(report, indent=2, sort_keys=True))
        return _EXIT_INTERNAL
    if "signature_invalid" not in v3.reason_codes:
        report["accepted"] = False
        report["error"] = "expected signature_invalid after signature tamper"
        print(json.dumps(report, indent=2, sort_keys=True))
        return _EXIT_INTERNAL

    # Case 4: pure artifact payload rewrite with matching declared CID swapped out
    # (recompute detects mismatch even if signatures somehow omitted)
    unsigned = json.loads(json.dumps(bundle))
    unsigned["signatures"] = [
        {
            **unsigned["signatures"][0],
            # keep structure but we will only check CID path by also using a
            # second artifact-only path via verify_cids
        }
    ]
    unsigned["artifacts"][1]["payload"] = {"tampered": True}
    # Keep declared cid from original → mismatch on recompute
    unsigned.pop("bundle_cid", None)
    v4 = verify_bundle(unsigned)
    report["cases"].append(
        {
            "name": "tampered_payload_cid_recompute",
            "accepted": v4.accepted,
            "exit_code": v4.exit_code,
            "reason_codes": v4.reason_codes,
        }
    )
    if v4.accepted or "cid_mismatch" not in v4.reason_codes:
        report["accepted"] = False
        report["error"] = "expected cid_mismatch after payload rewrite"
        print(json.dumps(report, indent=2, sort_keys=True))
        return _EXIT_INTERNAL

    report["accepted"] = True
    report["exit_code"] = _EXIT_OK
    report["schema_path"] = str(locate_schema()) if locate_schema() else None
    print(json.dumps(report, indent=2, sort_keys=True))
    return _EXIT_OK


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verify_bundle",
        description=(
            "IndependentVerifier@1 — validate a DemoEvidenceBundle@1. "
            "Exits 0 on success; nonzero if any CID or signature is tampered. "
            "This process is separate from the three demo peers."
        ),
    )
    p.add_argument(
        "bundle",
        nargs="?",
        default=None,
        help="Path to evidence bundle JSON (or - for stdin)",
    )
    p.add_argument(
        "--schema",
        default=None,
        help="Optional path to evidence-bundle.schema.json (informational)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print full verdict JSON to stdout (default)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout; rely on exit code only",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Mint a valid fixture, verify it, then prove CID/signature tamper fails",
    )
    p.add_argument(
        "--mint",
        metavar="PATH",
        default=None,
        help="Mint a valid DemoEvidenceBundle@1 fixture to PATH and exit 0",
    )
    p.add_argument(
        "--version",
        action="store_true",
        help="Print verifier version JSON and exit",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.version:
        print(
            json.dumps(
                {
                    "interface": INTERFACE,
                    "bundle_interface": BUNDLE_INTERFACE,
                    "schema": BUNDLE_SCHEMA,
                    "task_id": TASK_ID,
                    "goal_id": GOAL_ID,
                    "version": VERIFIER_VERSION,
                    "canonicalization": CANONICALIZATION,
                    "signature_algorithm": SIGNATURE_ALG,
                    "crypto_available": HAVE_CRYPTO,
                    "separate_process_from_demo_peers": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return _EXIT_OK

    if args.self_test:
        return run_self_test()

    if args.mint:
        if not HAVE_CRYPTO:
            print(
                json.dumps({"error": "cryptography Ed25519 unavailable"}),
                file=sys.stderr,
            )
            return _EXIT_INTERNAL
        bundle, _meta = mint_valid_bundle()
        out = Path(args.mint)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not args.quiet:
            print(
                json.dumps(
                    {
                        "minted": str(out),
                        "bundle_cid": bundle.get("bundle_cid"),
                        "interface": BUNDLE_INTERFACE,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        return _EXIT_OK

    if not args.bundle:
        parser.error("bundle path is required (or use --self-test / --mint)")

    try:
        if args.bundle == "-":
            data = json.load(sys.stdin)
            if not isinstance(data, dict):
                raise ValueError("bundle root must be a JSON object")
            bundle = data
        else:
            path = Path(args.bundle)
            if not path.is_file():
                print(
                    json.dumps({"error": "bundle_not_found", "path": str(path)}),
                    file=sys.stderr,
                )
                return _EXIT_IO
            bundle = dict(load_bundle(path))
    except json.JSONDecodeError as exc:
        print(
            json.dumps({"error": "invalid_json", "detail": str(exc)}),
            file=sys.stderr,
        )
        return _EXIT_IO
    except Exception as exc:
        print(
            json.dumps({"error": "load_failed", "detail": str(exc)}),
            file=sys.stderr,
        )
        return _EXIT_IO

    schema = Path(args.schema) if args.schema else locate_schema()
    try:
        verdict = verify_bundle(bundle)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": "internal_error",
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ),
            file=sys.stderr,
        )
        return _EXIT_INTERNAL

    verdict.metadata["schema_path"] = str(schema) if schema else None
    payload = verdict.to_dict()
    if not args.quiet:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return _EXIT_OK if verdict.accepted else verdict.exit_code


if __name__ == "__main__":
    sys.exit(main())
