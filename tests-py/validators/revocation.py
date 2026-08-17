"""
RevocationRecord@1 validator and fail-closed ledger (Profile C).

Schema: schemas/delegation/revocation-record-1.schema.json
Interface: RevocationRecord@1
Spec: docs/spec/ucan-delegation.md (§6 caveat checks / revocations)
Crypto: ADR-0002 Ed25519 over mcpp-jcs-v1 canonical bytes

Acceptance (MCPP-043):
  Revoked delegations fail closed even if the signature on the original token
  is valid.

A signed, discoverable RevocationRecord binds:
  - issuer
  - revoked_delegation_cid
  - effective_at
  - optional reason / replacement_cid
  - signature
  - discovery semantics

Verification order for execution-time checks is intentionally fail-closed:
  1. Ledger / registry availability (when required)
  2. Revocation membership for any token/proof CID or nonce
  3. Only then structural / cryptographic validation of the live token

SwissKnife ``UCANRevocationRegistry`` is an observation source for field
naming (tokenCid, revokedAt, revokedBy, reason) and fail-closed ordering.
"""

from __future__ import annotations

import base64
import copy
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

from .base_mcp import ValidationResult

try:
    from .canonical_jcs import ALGORITHM_ID, canonicalize_bytes
except Exception:  # pragma: no cover - package layout fallback
    ALGORITHM_ID = "mcpp-jcs-v1"

    def canonicalize_bytes(value: Any) -> bytes:  # type: ignore[misc]
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")


try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    HAVE_CRYPTO_ED25519 = True
except Exception:  # pragma: no cover
    InvalidSignature = Exception  # type: ignore[assignment,misc]
    Ed25519PublicKey = None  # type: ignore[assignment,misc]
    HAVE_CRYPTO_ED25519 = False


INTERFACE = "RevocationRecord@1"
SCHEMA_MARKER = "mcp++/delegation/revocation-record@1"
SCHEMA_RELATIVE_PATH = (
    "ipfs_accelerate_py/mcplusplus/schemas/delegation/revocation-record-1.schema.json"
)
CANONICAL_ALGORITHM = ALGORITHM_ID
SIGNATURE_ALG_EDDSA = "EdDSA"
SIGNATURE_ALG_ED25519 = "Ed25519"
REASON_REVOKED = "revoked"
REASON_LEDGER_UNAVAILABLE = "ledger_unavailable"
REASON_INVALID_RECORD = "invalid_revocation_record"
REASON_INVALID_SIGNATURE = "invalid_signature"
REASON_NOT_YET_EFFECTIVE = "revocation_not_yet_effective"
REASON_STRUCTURAL = "structural_invalid"

_SIG_META_KEYS = frozenset(
    {
        "signature",
        "sig",
        "signatures",
        "public_key",
        "publicKey",
        "public_key_b64",
        "issuer_public_key",
        "header",
        "protected",
        "alg",
        "kid",
        "signature_alg",
        "signatureAlg",
    }
)

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_CID_RE = re.compile(
    r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{50,}|sha256:[0-9a-fA-F]{64}|[A-Za-z0-9._:/-]{8,256})$"
)
_DID_RE = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$")
_ISO_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$"
)

DiscoveryMethod = str  # ledger | cid | registry | gossip | bundle | inline


# ---------------------------------------------------------------------------
# Encoding helpers (aligned with DelegationProof@1)
# ---------------------------------------------------------------------------


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty_base64url")
    for ch in text:
        if ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_":
            raise ValueError("invalid_base64url")
    pad = "=" * ((4 - (len(text) % 4)) % 4)
    decoded = base64.urlsafe_b64decode(text + pad)
    if _b64url_encode(decoded) != text:
        raise ValueError("noncanonical_base64url")
    return decoded


def _base58btc_decode(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        return b""
    acc = 0
    for ch in text:
        idx = _B58_ALPHABET.find(ch)
        if idx < 0:
            raise ValueError("invalid_base58btc")
        acc = acc * 58 + idx
    raw = acc.to_bytes((acc.bit_length() + 7) // 8, "big") if acc else b""
    zeros = 0
    for ch in text:
        if ch != "1":
            break
        zeros += 1
    return (b"\x00" * zeros) + raw


def ed25519_public_key_from_did_key(did: str) -> Optional[bytes]:
    """Extract 32-byte Ed25519 public key from ``did:key:z…`` (multicodec 0xed01)."""
    text = str(did or "").strip()
    if not text.startswith("did:key:"):
        return None
    mb = text[len("did:key:") :]
    if not mb.startswith("z"):
        return None
    try:
        decoded = _base58btc_decode(mb[1:])
    except ValueError:
        return None
    if len(decoded) >= 34 and decoded[0] == 0xED and decoded[1] == 0x01:
        return decoded[2:34]
    return None


def _decode_public_key(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return raw if len(raw) == 32 else None
    if isinstance(value, Mapping):
        alg = str(value.get("alg") or value.get("algorithm") or "").strip().lower()
        if alg and alg not in {"ed25519", "eddsa"}:
            return None
        for key in (
            "public_key",
            "public_key_b64",
            "public_key_base64",
            "publicKey",
            "key",
            "did_key",
            "did",
        ):
            if key in value:
                return _decode_public_key(value.get(key))
        return None

    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("did:key:"):
        return ed25519_public_key_from_did_key(text)
    if text.startswith("ed25519-pub:"):
        text = text.split(":", 1)[1].strip()
    if len(text) == 64:
        try:
            raw = bytes.fromhex(text)
            return raw if len(raw) == 32 else None
        except ValueError:
            pass
    try:
        raw = _b64url_decode(text)
        if len(raw) == 32:
            return raw
    except ValueError:
        pass
    try:
        pad = "=" * ((4 - (len(text) % 4)) % 4)
        raw = base64.b64decode(text + pad)
        if len(raw) == 32:
            return raw
    except Exception:
        return None
    return None


def _decode_signature(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return raw if len(raw) == 64 else None
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("ed25519:"):
        text = text.split(":", 1)[1].strip()
    elif text.startswith("ed25519-hex:") or text.startswith("hex:"):
        try:
            raw = bytes.fromhex(text.split(":", 1)[1].strip())
            return raw if len(raw) == 64 else None
        except ValueError:
            return None
    if len(text) == 128:
        try:
            raw = bytes.fromhex(text)
            return raw if len(raw) == 64 else None
        except ValueError:
            return None
    try:
        raw = _b64url_decode(text)
        return raw if len(raw) == 64 else None
    except ValueError:
        return None


def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify a pure Ed25519 signature; fail closed on any error."""
    if not HAVE_CRYPTO_ED25519:
        return False
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _level(
    *,
    valid: bool,
    errors: Optional[List[str]] = None,
    reason_code: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "valid": bool(valid),
        "errors": list(errors or []),
        "reason_code": reason_code,
    }


def _attach_levels(
    result: ValidationResult,
    structural: Dict[str, Any],
    cryptographic: Dict[str, Any],
) -> None:
    result.metadata["interface"] = INTERFACE
    result.metadata["canonical_algorithm"] = CANONICAL_ALGORITHM
    result.metadata["schema"] = SCHEMA_MARKER
    result.metadata["levels"] = {
        "structural": structural,
        "cryptographic": cryptographic,
    }
    if structural["valid"] and cryptographic["valid"]:
        result.metadata["conformance_level"] = "cryptographic"
    elif structural["valid"]:
        result.metadata["conformance_level"] = "structural"
    else:
        result.metadata["conformance_level"] = None


# ---------------------------------------------------------------------------
# Field normalization
# ---------------------------------------------------------------------------


def _parse_timestamp(value: Any, field_name: str) -> Tuple[Optional[float], Optional[str]]:
    if value is None:
        return None, f"missing_{field_name}"
    if isinstance(value, bool):
        return None, f"invalid_{field_name}"
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts != ts or ts in (float("inf"), float("-inf")) or ts < 0:
            return None, f"invalid_{field_name}"
        return ts, None
    text = str(value).strip()
    if not text:
        return None, f"missing_{field_name}"
    try:
        ts = float(text)
        if ts != ts or ts < 0:
            return None, f"invalid_{field_name}"
        return ts, None
    except ValueError:
        pass
    match = _ISO_RE.match(text)
    if not match:
        return None, f"invalid_{field_name}"
    try:
        # Prefer stdlib when available; keep fail-closed without zoneinfo edge cases.
        from datetime import datetime, timezone

        if text.endswith("Z"):
            text_norm = text[:-1] + "+00:00"
        else:
            text_norm = text
        dt = datetime.fromisoformat(text_norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp(), None
    except Exception:
        return None, f"invalid_{field_name}"


def normalize_revocation_record(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize SwissKnife / kit / full-name aliases into RevocationRecord@1 shape."""
    if not isinstance(raw, Mapping):
        raise TypeError("revocation_record_must_be_object")

    issuer = (
        raw.get("issuer")
        or raw.get("iss")
        or raw.get("revoked_by")
        or raw.get("revokedBy")
    )
    revoked_cid = (
        raw.get("revoked_delegation_cid")
        or raw.get("token_cid")
        or raw.get("tokenCid")
        or raw.get("delegation_cid")
        or raw.get("delegationCid")
    )
    # Bare SwissKnife entry may use cid for the token being revoked.
    if revoked_cid is None and raw.get("schema") is None and raw.get("cid") is not None:
        revoked_cid = raw.get("cid")

    effective_raw = (
        raw.get("effective_at")
        if "effective_at" in raw
        else raw.get("effective_time")
        if "effective_time" in raw
        else raw.get("revoked_at")
        if "revoked_at" in raw
        else raw.get("revokedAt")
    )
    replacement = raw.get("replacement_cid", raw.get("replacement"))
    signature = raw.get("signature", raw.get("sig"))
    discovery = raw.get("discovery")
    if discovery is None and any(
        k in raw for k in ("ledger_cid", "registry_id", "topic", "discovery_method")
    ):
        discovery = {
            "method": raw.get("discovery_method") or "registry",
            "ledger_cid": raw.get("ledger_cid"),
            "registry_id": raw.get("registry_id"),
            "topic": raw.get("topic"),
        }
        discovery = {k: v for k, v in discovery.items() if v is not None}

    out: Dict[str, Any] = {
        "schema": raw.get("schema") or SCHEMA_MARKER,
        "issuer": str(issuer).strip() if issuer is not None else None,
        "revoked_delegation_cid": str(revoked_cid).strip() if revoked_cid is not None else None,
        "effective_at": effective_raw,
        "reason": raw.get("reason"),
        "replacement_cid": str(replacement).strip() if replacement not in (None, "") else None,
        "signature": signature,
        "alg": raw.get("alg") or raw.get("signature_alg") or raw.get("signatureAlg"),
        "kid": raw.get("kid"),
        "public_key": raw.get("public_key") or raw.get("publicKey") or raw.get("issuer_public_key"),
        "nonce": raw.get("nonce"),
        "cid": raw.get("cid") if raw.get("schema") is not None else raw.get("record_cid"),
        "discovery": discovery,
        "not_before": raw.get("not_before", raw.get("nbf")),
        "expires_at": raw.get("expires_at", raw.get("exp")),
    }
    return out


def signing_object_from_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Logical object whose mcpp-jcs-v1 bytes are signed (detached form)."""
    normalized = normalize_revocation_record(record)
    body = {k: v for k, v in normalized.items() if k not in _SIG_META_KEYS and v is not None}
    # Drop nested signature aliases.
    for k in list(body.keys()):
        if k in _SIG_META_KEYS:
            del body[k]
    return body


def canonical_signing_bytes(record: Mapping[str, Any]) -> bytes:
    return canonicalize_bytes(signing_object_from_record(record))


# ---------------------------------------------------------------------------
# Durable / in-memory ledger
# ---------------------------------------------------------------------------


class LedgerUnavailableError(RuntimeError):
    """Raised when durable revocation state cannot be safely consulted."""


class LedgerFormatError(LedgerUnavailableError):
    """Raised for corrupt or unrecognised on-disk ledger state."""


_LEDGER_SCHEMA = "mcp++/delegation/revocation-ledger@1"
_LEDGER_LOCK = threading.RLock()


@dataclass
class StoredRevocation:
    """Normalized ledger entry for one revoked delegation identifier."""

    identifier: str
    issuer: str
    effective_at: float
    reason: str = ""
    replacement_cid: Optional[str] = None
    record_cid: Optional[str] = None
    discovery: Optional[Dict[str, Any]] = None
    signature_present: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "identifier": self.identifier,
            "issuer": self.issuer,
            "effective_at": self.effective_at,
            "reason": self.reason,
            "signature_present": self.signature_present,
        }
        if self.replacement_cid:
            payload["replacement_cid"] = self.replacement_cid
        if self.record_cid:
            payload["record_cid"] = self.record_cid
        if self.discovery:
            payload["discovery"] = self.discovery
        return payload


class RevocationLedger:
    """Fail-closed revocation membership store (in-memory or durable JSON).

    When constructed with a path, missing/unreadable/malformed state is
    unavailable rather than treated as empty (kit RevocationLedger pattern).
    In-memory mode is available for unit/conformance tests; production
    verifiers SHOULD require a durable path via ``require_ledger=True``.
    """

    def __init__(self, path: Optional[Union[str, os.PathLike[str]]] = None) -> None:
        self.path = Path(path) if path is not None else None
        self._failure: Optional[str] = None
        self._memory: Dict[str, StoredRevocation] = {}
        if self.path is not None:
            try:
                self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if self.path.exists():
                    self._read_state()
                else:
                    self._write_state(self._empty_state())
            except Exception as exc:  # retain reason; never silently recover
                self._failure = type(exc).__name__

    @staticmethod
    def _empty_state() -> Dict[str, Any]:
        return {"schema": _LEDGER_SCHEMA, "version": 1, "revoked": {}}

    @property
    def available(self) -> bool:
        if self._failure is not None:
            return False
        if self.path is None:
            return True
        try:
            self._read_state()
            return True
        except Exception:
            return False

    @property
    def failure_reason(self) -> Optional[str]:
        return self._failure

    def _require_available(self) -> Optional[Path]:
        if self._failure is not None:
            raise LedgerUnavailableError(self._failure)
        return self.path

    def _validate_state(self, state: Any) -> Dict[str, Any]:
        if not isinstance(state, dict) or state.get("schema") != _LEDGER_SCHEMA or state.get("version") != 1:
            raise LedgerFormatError("invalid_ledger_schema")
        revoked = state.get("revoked")
        if not isinstance(revoked, dict):
            raise LedgerFormatError("invalid_ledger_revoked")
        for identifier, record in revoked.items():
            if not isinstance(identifier, str) or not identifier or not isinstance(record, dict):
                raise LedgerFormatError("invalid_revocation")
            if record.get("effective_at") is None:
                raise LedgerFormatError("invalid_effective_at")
            try:
                float(record["effective_at"])
            except (TypeError, ValueError) as exc:
                raise LedgerFormatError("invalid_effective_at") from exc
        return state

    def _read_state(self) -> Dict[str, Any]:
        path = self._require_available()
        if path is None:
            return {
                "schema": _LEDGER_SCHEMA,
                "version": 1,
                "revoked": {k: v.to_dict() for k, v in self._memory.items()},
            }
        try:
            raw = path.read_bytes()
            state = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LedgerFormatError("ledger_read_failed") from exc
        return self._validate_state(state)

    def _write_state(self, state: Mapping[str, Any]) -> None:
        path = self._require_available()
        if path is None:
            checked = self._validate_state(copy.deepcopy(dict(state)))
            self._memory = {}
            for identifier, record in checked["revoked"].items():
                self._memory[identifier] = StoredRevocation(
                    identifier=identifier,
                    issuer=str(record.get("issuer") or ""),
                    effective_at=float(record["effective_at"]),
                    reason=str(record.get("reason") or ""),
                    replacement_cid=record.get("replacement_cid"),
                    record_cid=record.get("record_cid"),
                    discovery=record.get("discovery"),
                    signature_present=bool(record.get("signature_present")),
                )
            return
        checked = self._validate_state(copy.deepcopy(dict(state)))
        encoded = json.dumps(checked, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
        descriptor, temporary_name = tempfile.mkstemp(prefix=".mcpp-revocation-", dir=str(path.parent))
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
            directory_descriptor = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise

    def _mutate(self, operation: Any) -> Any:
        with _LEDGER_LOCK:
            state = self._read_state()
            result = operation(state)
            self._write_state(state)
            return result

    def _inspect(self, operation: Any) -> Any:
        with _LEDGER_LOCK:
            return operation(self._read_state())

    @staticmethod
    def _identifier(identifier: str) -> str:
        value = str(identifier or "").strip()
        if not value or len(value) > 512:
            raise ValueError("invalid_identifier")
        return value

    def revoke(
        self,
        identifier: str,
        *,
        issuer: str = "",
        effective_at: Optional[float] = None,
        reason: str = "",
        replacement_cid: Optional[str] = None,
        record_cid: Optional[str] = None,
        discovery: Optional[Mapping[str, Any]] = None,
        signature_present: bool = False,
    ) -> StoredRevocation:
        identifier = self._identifier(identifier)
        entry = StoredRevocation(
            identifier=identifier,
            issuer=str(issuer or "").strip(),
            effective_at=float(time.time() if effective_at is None else effective_at),
            reason=str(reason or "")[:512],
            replacement_cid=str(replacement_cid).strip() if replacement_cid else None,
            record_cid=str(record_cid).strip() if record_cid else None,
            discovery=dict(discovery) if discovery else None,
            signature_present=bool(signature_present),
        )

        def apply(state: Dict[str, Any]) -> StoredRevocation:
            # First-write wins; subsequent revoke calls leave the original effective_at.
            existing = state["revoked"].get(identifier)
            if existing is None:
                state["revoked"][identifier] = entry.to_dict()
                return entry
            return StoredRevocation(
                identifier=identifier,
                issuer=str(existing.get("issuer") or ""),
                effective_at=float(existing["effective_at"]),
                reason=str(existing.get("reason") or ""),
                replacement_cid=existing.get("replacement_cid"),
                record_cid=existing.get("record_cid"),
                discovery=existing.get("discovery"),
                signature_present=bool(existing.get("signature_present")),
            )

        return self._mutate(apply)

    def is_revoked(self, identifier: str, *, now: Optional[float] = None) -> bool:
        identifier = self._identifier(identifier)
        current = time.time() if now is None else float(now)

        def check(state: Dict[str, Any]) -> bool:
            record = state["revoked"].get(identifier)
            if record is None:
                return False
            return float(record["effective_at"]) <= current

        return bool(self._inspect(check))

    def get(self, identifier: str) -> Optional[Dict[str, Any]]:
        identifier = self._identifier(identifier)
        return self._inspect(lambda state: copy.deepcopy(state["revoked"].get(identifier)))

    def list_revoked(self) -> List[Dict[str, Any]]:
        return self._inspect(
            lambda state: [copy.deepcopy(v) for v in state["revoked"].values()]
        )

    def discover(
        self,
        *,
        issuer: Optional[str] = None,
        method: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Discovery semantics: filter ledger entries by issuer and/or method."""

        def filter_entries(state: Dict[str, Any]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for record in state["revoked"].values():
                if issuer is not None and str(record.get("issuer") or "") != issuer:
                    continue
                discovery = record.get("discovery") or {}
                if method is not None and str(discovery.get("method") or "") != method:
                    continue
                out.append(copy.deepcopy(record))
            return out

        return self._inspect(filter_entries)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


@dataclass
class RevocationDecision:
    """Fail-closed execution-time decision for a delegation under revocation."""

    allowed: bool
    reason: str
    revoked_identifiers: Tuple[str, ...] = ()
    record: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def denied(self) -> bool:
        return not self.allowed


class RevocationRecordValidator:
    """
    Validates RevocationRecord@1 artifacts and enforces fail-closed revocation.

    Interface: RevocationRecord@1
    """

    def __init__(
        self,
        *,
        ledger: Optional[RevocationLedger] = None,
        issuer_public_keys: Optional[Mapping[str, Any]] = None,
        require_signatures: bool = True,
        require_ledger: bool = False,
        require_discovery: bool = False,
    ) -> None:
        self.ledger = ledger if ledger is not None else RevocationLedger()
        self.issuer_public_keys: Dict[str, Any] = dict(issuer_public_keys or {})
        self.require_signatures = bool(require_signatures)
        self.require_ledger = bool(require_ledger)
        self.require_discovery = bool(require_discovery)

    # -- schema / structural / crypto -------------------------------------

    def validate_record(
        self,
        record: Mapping[str, Any],
        *,
        issuer_public_keys: Optional[Mapping[str, Any]] = None,
        now: Optional[float] = None,
        commit_to_ledger: bool = False,
    ) -> ValidationResult:
        """Validate a single RevocationRecord@1 (structural + cryptographic)."""
        result = ValidationResult(is_valid=True, message_type="revocation_record")
        structural_errors: List[str] = []
        crypto_errors: List[str] = []
        crypto_reason: Optional[str] = None
        keys = dict(self.issuer_public_keys)
        if issuer_public_keys:
            keys.update(dict(issuer_public_keys))
        current = time.time() if now is None else float(now)

        if not isinstance(record, Mapping):
            structural_errors.append("Revocation record must be an object")
            result.add_error(structural_errors[0])
            _attach_levels(
                result,
                _level(valid=False, errors=structural_errors, reason_code=REASON_STRUCTURAL),
                _level(valid=False, errors=["structural_failed"], reason_code="structural_failed"),
            )
            return result

        normalized = normalize_revocation_record(record)
        result.metadata["normalized"] = {
            k: v
            for k, v in normalized.items()
            if k not in {"signature", "public_key"} and v is not None
        }

        schema = normalized.get("schema")
        if schema != SCHEMA_MARKER:
            structural_errors.append(f"invalid_schema:{schema}")

        issuer = normalized.get("issuer")
        if not issuer or not isinstance(issuer, str) or not _DID_RE.match(issuer):
            structural_errors.append("missing_or_invalid_issuer")

        revoked_cid = normalized.get("revoked_delegation_cid")
        if (
            not revoked_cid
            or not isinstance(revoked_cid, str)
            or not _CID_RE.match(revoked_cid)
        ):
            structural_errors.append("missing_or_invalid_revoked_delegation_cid")

        effective_at, eff_err = _parse_timestamp(normalized.get("effective_at"), "effective_at")
        if eff_err:
            structural_errors.append(eff_err)
        else:
            normalized["effective_at"] = effective_at

        if normalized.get("reason") is not None and not isinstance(normalized.get("reason"), str):
            structural_errors.append("invalid_reason")
        elif isinstance(normalized.get("reason"), str) and len(normalized["reason"]) > 512:
            structural_errors.append("reason_too_long")

        replacement = normalized.get("replacement_cid")
        if replacement is not None and not _CID_RE.match(str(replacement)):
            structural_errors.append("invalid_replacement_cid")

        discovery = normalized.get("discovery")
        if discovery is not None:
            if not isinstance(discovery, Mapping):
                structural_errors.append("invalid_discovery")
            else:
                method = str(discovery.get("method") or "").strip()
                if method not in {"ledger", "cid", "registry", "gossip", "bundle", "inline"}:
                    structural_errors.append("invalid_discovery_method")
        elif self.require_discovery:
            structural_errors.append("discovery_required")

        nbf_raw = normalized.get("not_before")
        if nbf_raw is not None:
            nbf, nbf_err = _parse_timestamp(nbf_raw, "not_before")
            if nbf_err:
                structural_errors.append(nbf_err)
            elif nbf is not None and nbf > current:
                structural_errors.append(REASON_NOT_YET_EFFECTIVE)

        for err in structural_errors:
            result.add_error(err)

        structural_ok = len(structural_errors) == 0
        sig_raw = normalized.get("signature")
        has_sig = sig_raw is not None and str(sig_raw).strip() != ""

        if not has_sig:
            crypto_errors.append("missing_signature")
            crypto_reason = "missing_signature"
            crypto_ok = False
        elif not HAVE_CRYPTO_ED25519:
            crypto_errors.append("cryptography_ed25519_unavailable")
            crypto_reason = "crypto_unavailable"
            crypto_ok = False
        else:
            alg = normalized.get("alg")
            if alg is not None:
                alg_text = str(alg).strip()
                if alg_text in {"none", "None", "NONE", ""}:
                    crypto_errors.append("algorithm_or_version_downgrade")
                    crypto_reason = "algorithm_or_version_downgrade"
                    crypto_ok = False
                elif alg_text not in {
                    SIGNATURE_ALG_EDDSA,
                    SIGNATURE_ALG_ED25519,
                    "ed25519",
                    "Ed25519",
                }:
                    crypto_errors.append(f"unsupported_signature_alg:{alg_text}")
                    crypto_reason = "unsupported_signature_alg"
                    crypto_ok = False
                else:
                    crypto_ok = True
            else:
                crypto_ok = True

            if crypto_ok:
                kid = normalized.get("kid")
                if (kid is None or str(kid).strip() == "") and not str(issuer or "").startswith(
                    "did:key:"
                ):
                    crypto_errors.append("missing_kid")
                    crypto_reason = "missing_kid"
                    crypto_ok = False

            if crypto_ok:
                signature = _decode_signature(sig_raw)
                if signature is None:
                    crypto_errors.append("invalid_signature_encoding")
                    crypto_reason = "invalid_signature_encoding"
                    crypto_ok = False
                else:
                    public_key = self._resolve_public_key(normalized, keys)
                    if public_key is None:
                        crypto_errors.append("verification_key_unavailable")
                        crypto_reason = "verification_key_unavailable"
                        crypto_ok = False
                    else:
                        message = canonical_signing_bytes(normalized)
                        if not verify_ed25519(public_key, message, signature):
                            crypto_errors.append("invalid_signature")
                            crypto_reason = REASON_INVALID_SIGNATURE
                            crypto_ok = False
                        else:
                            crypto_ok = True

        if self.require_signatures and not crypto_ok:
            for err in crypto_errors:
                if err not in result.errors:
                    result.add_error(err)
            result.is_valid = False
        if has_sig and not crypto_ok:
            # Present-but-invalid signatures always fail closed.
            for err in crypto_errors:
                if err not in result.errors:
                    result.add_error(err)
            result.is_valid = False
        if not structural_ok:
            result.is_valid = False

        cryptographic_ok = structural_ok and crypto_ok
        _attach_levels(
            result,
            _level(
                valid=structural_ok,
                errors=structural_errors,
                reason_code=None if structural_ok else REASON_STRUCTURAL,
            ),
            _level(
                valid=cryptographic_ok,
                errors=crypto_errors
                if crypto_errors
                else ([] if cryptographic_ok else ["missing_signature"]),
                reason_code=None if cryptographic_ok else (crypto_reason or "missing_signature"),
            ),
        )

        if cryptographic_ok and commit_to_ledger:
            if not self.ledger.available:
                result.add_error(REASON_LEDGER_UNAVAILABLE)
                result.is_valid = False
                result.metadata["levels"]["cryptographic"]["valid"] = False
            else:
                try:
                    stored = self.ledger.revoke(
                        str(revoked_cid),
                        issuer=str(issuer or ""),
                        effective_at=float(effective_at or current),
                        reason=str(normalized.get("reason") or ""),
                        replacement_cid=normalized.get("replacement_cid"),
                        record_cid=str(normalized.get("cid") or "") or None,
                        discovery=normalized.get("discovery")
                        if isinstance(normalized.get("discovery"), Mapping)
                        else None,
                        signature_present=True,
                    )
                    result.metadata["ledger_entry"] = stored.to_dict()
                except (LedgerUnavailableError, ValueError) as exc:
                    result.add_error(str(exc) or REASON_LEDGER_UNAVAILABLE)
                    result.is_valid = False

        return result

    def _resolve_public_key(
        self,
        record: Mapping[str, Any],
        issuer_public_keys: Mapping[str, Any],
    ) -> Optional[bytes]:
        for key_name in ("public_key", "publicKey", "issuer_public_key", "public_key_b64"):
            if key_name in record and record.get(key_name) is not None:
                raw = _decode_public_key(record.get(key_name))
                if raw is not None:
                    return raw
        issuer = str(record.get("issuer") or "").strip()
        kid = str(record.get("kid") or "").strip()
        if issuer and issuer in issuer_public_keys:
            entry = issuer_public_keys[issuer]
            if isinstance(entry, Mapping) and kid and kid in entry and not any(
                k in entry for k in ("public_key", "public_key_b64", "alg", "algorithm", "key")
            ):
                raw = _decode_public_key(entry.get(kid))
                if raw is not None:
                    return raw
            raw = _decode_public_key(entry)
            if raw is not None:
                return raw
        if issuer:
            raw = ed25519_public_key_from_did_key(issuer)
            if raw is not None:
                return raw
        if kid:
            raw = ed25519_public_key_from_did_key(kid)
            if raw is not None:
                return raw
        return None

    # -- fail-closed execution gate ---------------------------------------

    def check_identifiers(
        self,
        identifiers: Sequence[str],
        *,
        now: Optional[float] = None,
    ) -> RevocationDecision:
        """Return deny if any identifier is revoked and effective."""
        if self.require_ledger and (self.ledger is None or not self.ledger.available):
            return RevocationDecision(allowed=False, reason=REASON_LEDGER_UNAVAILABLE)
        if self.ledger is None or not self.ledger.available:
            if self.require_ledger:
                return RevocationDecision(allowed=False, reason=REASON_LEDGER_UNAVAILABLE)
            # Soft mode without ledger: cannot prove revocation; do not allow
            # bypass of require_ledger. When ledger is optional and missing,
            # treat as no known revocations only if explicitly not required.
            return RevocationDecision(allowed=True, reason="ok")

        revoked: List[str] = []
        matched: Optional[Dict[str, Any]] = None
        current = time.time() if now is None else float(now)
        for identifier in identifiers:
            text = str(identifier or "").strip()
            if not text:
                continue
            try:
                if self.ledger.is_revoked(text, now=current):
                    revoked.append(text)
                    if matched is None:
                        matched = self.ledger.get(text)
            except (LedgerUnavailableError, ValueError):
                return RevocationDecision(allowed=False, reason=REASON_LEDGER_UNAVAILABLE)
        if revoked:
            return RevocationDecision(
                allowed=False,
                reason=REASON_REVOKED,
                revoked_identifiers=tuple(revoked),
                record=matched,
            )
        return RevocationDecision(allowed=True, reason="ok")

    def evaluate_delegation(
        self,
        token_or_chain: Union[Mapping[str, Any], Sequence[Any], str],
        *,
        token_signature_valid: bool = True,
        now: Optional[float] = None,
    ) -> RevocationDecision:
        """
        Fail-closed revocation gate for a delegation token or chain.

        ``token_signature_valid`` documents that the original UCAN signature
        may already have verified; a matching revocation still denies.
        """
        identifiers = extract_delegation_identifiers(token_or_chain)
        decision = self.check_identifiers(identifiers, now=now)
        decision.metadata = {
            "token_signature_valid": bool(token_signature_valid),
            "identifiers": list(identifiers),
            "interface": INTERFACE,
        }
        if decision.denied and token_signature_valid and decision.reason == REASON_REVOKED:
            # Acceptance: valid original signature does not override revocation.
            decision.metadata["fail_closed_despite_valid_signature"] = True
        return decision

    def admit_record(
        self,
        record: Mapping[str, Any],
        *,
        issuer_public_keys: Optional[Mapping[str, Any]] = None,
        now: Optional[float] = None,
    ) -> ValidationResult:
        """Validate a record and commit it to the ledger on success."""
        return self.validate_record(
            record,
            issuer_public_keys=issuer_public_keys,
            now=now,
            commit_to_ledger=True,
        )

    def discover_records(
        self,
        *,
        issuer: Optional[str] = None,
        method: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Discovery semantics over the configured ledger."""
        if not self.ledger.available:
            if self.require_ledger:
                raise LedgerUnavailableError(self.ledger.failure_reason or REASON_LEDGER_UNAVAILABLE)
            return []
        return self.ledger.discover(issuer=issuer, method=method)


def extract_delegation_identifiers(
    token_or_chain: Union[Mapping[str, Any], Sequence[Any], str],
) -> List[str]:
    """Collect candidate revocation identifiers from a token or chain."""
    found: List[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in found:
            found.append(text)

    def from_token(token: Any) -> None:
        if isinstance(token, str):
            add(token)
            return
        if not isinstance(token, Mapping):
            return
        for key in (
            "cid",
            "token_id",
            "token_cid",
            "tokenCid",
            "delegation_cid",
            "proof_cid",
            "nonce",
            "jti",
        ):
            if key in token:
                add(token.get(key))
        # Nested payload form
        payload = token.get("payload")
        if isinstance(payload, Mapping):
            for key in ("cid", "nonce", "jti", "prf"):
                if key in payload:
                    val = payload.get(key)
                    if isinstance(val, list):
                        for item in val:
                            add(item)
                    else:
                        add(val)
        prf = token.get("prf") or token.get("proof_cids") or token.get("proofs")
        if isinstance(prf, list):
            for item in prf:
                add(item)
        elif isinstance(prf, str):
            add(prf)

    if isinstance(token_or_chain, Mapping):
        from_token(token_or_chain)
    elif isinstance(token_or_chain, str):
        add(token_or_chain)
    else:
        try:
            for item in token_or_chain:
                from_token(item)
        except TypeError:
            pass
    return found


def load_schema() -> Dict[str, Any]:
    """Load the RevocationRecord@1 JSON Schema from the schemas tree."""
    here = Path(__file__).resolve()
    # tests-py/validators -> mcplusplus
    root = here.parents[2]
    schema_path = root / "schemas" / "delegation" / "revocation-record-1.schema.json"
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


__all__ = [
    "INTERFACE",
    "SCHEMA_MARKER",
    "SCHEMA_RELATIVE_PATH",
    "CANONICAL_ALGORITHM",
    "REASON_REVOKED",
    "REASON_LEDGER_UNAVAILABLE",
    "HAVE_CRYPTO_ED25519",
    "RevocationRecordValidator",
    "RevocationLedger",
    "RevocationDecision",
    "StoredRevocation",
    "LedgerUnavailableError",
    "LedgerFormatError",
    "normalize_revocation_record",
    "signing_object_from_record",
    "canonical_signing_bytes",
    "extract_delegation_identifiers",
    "make_signed_revocation_record",
    "verify_ed25519",
    "ed25519_public_key_from_did_key",
    "load_schema",
]


# ---------------------------------------------------------------------------
# Built-in regression coverage (pytest collects when this module is targeted).
# Integration suite: tests-py/integration -k revocation (imported below when
# present; otherwise these tests document the acceptance contract).
# ---------------------------------------------------------------------------


def _did_key_from_public(public_key: bytes) -> str:
    """Build a did:key:z… for a raw Ed25519 public key."""
    payload = bytes([0xED, 0x01]) + public_key
    # base58btc
    alphabet = _B58_ALPHABET
    n = int.from_bytes(payload, "big")
    chars = []
    while n > 0:
        n, rem = divmod(n, 58)
        chars.append(alphabet[rem])
    for byte in payload:
        if byte == 0:
            chars.append(alphabet[0])
        else:
            break
    return "did:key:z" + "".join(reversed(chars or [alphabet[0]]))


def make_signed_revocation_record(
    *,
    revoked_cid: str,
    reason: str = "test_revocation",
    replacement_cid: Optional[str] = None,
    discovery: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], bytes, str]:
    """Build a cryptographically valid RevocationRecord@1 for tests and fixtures."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    issuer = _did_key_from_public(public)
    body: Dict[str, Any] = {
        "schema": SCHEMA_MARKER,
        "issuer": issuer,
        "revoked_delegation_cid": revoked_cid,
        "effective_at": int(time.time()) - 1,
        "reason": reason,
        "alg": SIGNATURE_ALG_EDDSA,
        "kid": issuer,
        "discovery": discovery
        or {
            "method": "ledger",
            "registry_id": "mcp++/revocation-ledger@1",
            "published_at": int(time.time()),
        },
    }
    if replacement_cid:
        body["replacement_cid"] = replacement_cid
    message = canonical_signing_bytes(body)
    signature = private.sign(message)
    body["signature"] = _b64url_encode(signature)
    return body, public, issuer


# Back-compat alias used by embedded tests.
_make_signed_record = make_signed_revocation_record


def test_revocation_schema_marker_and_load():
    schema = load_schema()
    assert schema["$id"].endswith("revocation-record-1.schema.json")
    assert schema["properties"]["schema"]["const"] == SCHEMA_MARKER
    for required in (
        "schema",
        "issuer",
        "revoked_delegation_cid",
        "effective_at",
        "signature",
    ):
        assert required in schema["required"]
    assert "discovery" in schema["properties"]
    assert "replacement_cid" in schema["properties"]


def test_revocation_record_signed_and_discoverable():
    if not HAVE_CRYPTO_ED25519:
        return
    revoked = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    record, _pub, issuer = _make_signed_record(revoked_cid=revoked)
    ledger = RevocationLedger()
    validator = RevocationRecordValidator(ledger=ledger, require_signatures=True)
    result = validator.admit_record(record)
    assert result.is_valid, result.errors
    assert result.metadata["conformance_level"] == "cryptographic"
    assert result.metadata["levels"]["cryptographic"]["valid"] is True
    discovered = validator.discover_records(issuer=issuer, method="ledger")
    assert any(entry["identifier"] == revoked for entry in discovered)


def test_revocation_fail_closed_despite_valid_token_signature():
    """Acceptance: revoked delegations fail closed even if original token sig is valid."""
    if not HAVE_CRYPTO_ED25519:
        return
    revoked = "bafybeihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
    record, _pub, _issuer = _make_signed_record(revoked_cid=revoked)
    ledger = RevocationLedger()
    validator = RevocationRecordValidator(ledger=ledger, require_signatures=True)
    assert validator.admit_record(record).is_valid

    # Delegation token is assumed cryptographically valid.
    token = {
        "iss": "did:key:root",
        "aud": "did:key:agent",
        "att": [{"can": "tool/execute", "with": "weather-api"}],
        "exp": int(time.time()) + 3600,
        "cid": revoked,
        "signature": "valid-looking-but-irrelevant",
    }
    decision = validator.evaluate_delegation(token, token_signature_valid=True)
    assert decision.denied
    assert decision.reason == REASON_REVOKED
    assert revoked in decision.revoked_identifiers
    meta = getattr(decision, "metadata", {}) or {}
    assert meta.get("fail_closed_despite_valid_signature") is True
    assert meta.get("token_signature_valid") is True


def test_revocation_unsigned_record_fails_cryptographic_level():
    record = {
        "schema": SCHEMA_MARKER,
        "issuer": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
        "revoked_delegation_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        "effective_at": 1700000000,
        "discovery": {"method": "inline"},
    }
    validator = RevocationRecordValidator(require_signatures=True)
    result = validator.validate_record(record)
    assert not result.is_valid
    assert result.metadata["levels"]["structural"]["valid"] is True
    assert result.metadata["levels"]["cryptographic"]["valid"] is False


def test_revocation_tampered_record_signature_fails():
    if not HAVE_CRYPTO_ED25519:
        return
    record, _pub, _issuer = _make_signed_record(
        revoked_cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    )
    record["reason"] = "tampered-after-sign"
    validator = RevocationRecordValidator(require_signatures=True)
    result = validator.validate_record(record)
    assert not result.is_valid
    assert result.metadata["levels"]["cryptographic"]["reason_code"] == REASON_INVALID_SIGNATURE


def test_revocation_swissknife_alias_normalization():
    raw = {
        "tokenCid": "sha256:" + ("ab" * 32),
        "revokedAt": "2024-01-01T00:00:00Z",
        "revokedBy": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
        "reason": "observed_from_swissknife",
    }
    normalized = normalize_revocation_record(raw)
    assert normalized["revoked_delegation_cid"].startswith("sha256:")
    assert normalized["issuer"].startswith("did:key:")
    ts, err = _parse_timestamp(normalized["effective_at"], "effective_at")
    assert err is None and ts is not None


def test_revocation_durable_ledger_roundtrip(tmp_path=None):
    if tmp_path is None:
        import pathlib
        import tempfile as _tf

        base = pathlib.Path(_tf.mkdtemp())
    else:
        base = Path(tmp_path)
    path = base / "revocation-ledger.json"
    ledger = RevocationLedger(path)
    ledger.revoke("cid-1", issuer="did:key:a", reason="r1")
    assert ledger.is_revoked("cid-1")
    ledger2 = RevocationLedger(path)
    assert ledger2.is_revoked("cid-1")
    assert ledger2.get("cid-1")["reason"] == "r1"


def test_revocation_require_ledger_unavailable_fails_closed(tmp_path=None):
    if tmp_path is None:
        import pathlib
        import tempfile as _tf

        base = pathlib.Path(_tf.mkdtemp())
    else:
        base = Path(tmp_path)
    path = base / "missing-dir-never" / "nope.json"
    # Force unavailable by pointing at a path we poison after construct.
    ledger = RevocationLedger(None)
    validator = RevocationRecordValidator(ledger=ledger, require_ledger=True)
    # Simulate unavailable durable ledger.
    ledger._failure = "forced_unavailable"
    decision = validator.check_identifiers(["any-cid"])
    assert decision.denied
    assert decision.reason == REASON_LEDGER_UNAVAILABLE


def test_revocation_chain_proof_cid_membership():
    if not HAVE_CRYPTO_ED25519:
        return
    proof_cid = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    record, _pub, _issuer = _make_signed_record(revoked_cid=proof_cid)
    ledger = RevocationLedger()
    validator = RevocationRecordValidator(ledger=ledger)
    assert validator.admit_record(record).is_valid
    chain = [
        {
            "iss": "did:key:root",
            "aud": "did:key:mid",
            "att": [{"can": "*"}],
            "exp": 9999999999,
            "cid": "bafybeihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku",
        },
        {
            "iss": "did:key:mid",
            "aud": "did:key:leaf",
            "att": [{"can": "tool/x"}],
            "exp": 9999999999,
            "prf": [proof_cid],
            "cid": "leaf-token",
        },
    ]
    decision = validator.evaluate_delegation(chain, token_signature_valid=True)
    assert decision.denied and decision.reason == REASON_REVOKED
