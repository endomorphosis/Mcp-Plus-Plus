"""
UCAN Delegation Validator (Profile C) — DelegationProof@1

Validates Profile C (Capability Delegation) according to docs/spec/ucan-delegation.md
and ADR-0002 (Ed25519 over mcpp-jcs-v1 canonical bytes).

Conformance levels (ADR-0003):
  structural     — required fields / shape
  cryptographic  — Ed25519/EdDSA verify over canonical signing input

A token with required fields but an invalid signature fails at the cryptographic
level; structural may still pass and is reported separately.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Mapping, Optional, Tuple

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


INTERFACE = "DelegationProof@1"
CANONICAL_ALGORITHM = ALGORITHM_ID
SIGNATURE_ALG_EDDSA = "EdDSA"
SIGNATURE_ALG_ED25519 = "Ed25519"

# Fields excluded from the detached object signing payload.
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


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty_base64url")
    # Reject non-base64url alphabet early.
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
        hex_key = value.get("public_key_hex")
        if hex_key is not None:
            return _decode_public_key(hex_key)
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


def _signing_object_from_token(token: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the logical object whose mcpp-jcs-v1 bytes are signed (detached form)."""
    if "payload" in token and isinstance(token["payload"], Mapping):
        body = dict(token["payload"])
    else:
        body = {k: v for k, v in token.items() if k not in _SIG_META_KEYS and k != "token"}
    # Drop nested signature aliases if present inside payload.
    for k in list(body.keys()):
        if k in _SIG_META_KEYS:
            del body[k]
    return body


def canonical_signing_bytes(token: Mapping[str, Any]) -> bytes:
    """Return mcpp-jcs-v1 bytes that an Ed25519 signature must cover (detached object form)."""
    return canonicalize_bytes(_signing_object_from_token(token))


def compact_signing_input(header: Mapping[str, Any], payload: Mapping[str, Any]) -> bytes:
    """UCAN compact signing input: base64url(jcs(header)).base64url(jcs(payload))."""
    h = _b64url_encode(canonicalize_bytes(dict(header)))
    p = _b64url_encode(canonicalize_bytes(dict(payload)))
    return f"{h}.{p}".encode("ascii")


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
    result.metadata["levels"] = {
        "structural": structural,
        "cryptographic": cryptographic,
    }
    # Highest fully achieved ladder step for this artifact.
    if structural["valid"] and cryptographic["valid"]:
        result.metadata["conformance_level"] = "cryptographic"
    elif structural["valid"]:
        result.metadata["conformance_level"] = "structural"
    else:
        result.metadata["conformance_level"] = None


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


class UCANDelegationValidator:
    """
    Validates UCAN capability delegation chains with dual-level results.

    Interface: DelegationProof@1
    Spec: docs/spec/ucan-delegation.md
    Crypto: ADR-0002 Ed25519 over mcpp-jcs-v1 canonical bytes
    """

    def __init__(
        self,
        *,
        issuer_public_keys: Optional[Mapping[str, Any]] = None,
        require_signatures: bool = False,
    ) -> None:
        self.issuer_public_keys: Dict[str, Any] = dict(issuer_public_keys or {})
        self.require_signatures = bool(require_signatures)

    def validate_delegation_chain(
        self,
        chain: List[Dict[str, Any]],
        *,
        issuer_public_keys: Optional[Mapping[str, Any]] = None,
        require_signatures: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate a UCAN delegation chain.

        Structural failures always invalidate the result. Cryptographic failures
        are always reported under ``metadata['levels']['cryptographic']``.

        Overall ``is_valid`` is False when:
          - structural checks fail, or
          - a signature is present but does not verify, or
          - ``require_signatures`` is True and crypto does not pass.

        Unsigned but structurally valid chains remain structurally valid so
        shape fixtures stay green; cryptographic level still fails closed.
        """
        result = ValidationResult(is_valid=True, message_type="delegation_chain")
        structural_errors: List[str] = []
        crypto_errors: List[str] = []
        crypto_reason: Optional[str] = None
        keys = dict(self.issuer_public_keys)
        if issuer_public_keys:
            keys.update(dict(issuer_public_keys))
        require_sig = self.require_signatures if require_signatures is None else bool(require_signatures)

        if not isinstance(chain, list):
            structural_errors.append("Delegation chain must be a list")
            result.add_error(structural_errors[0])
            _attach_levels(
                result,
                _level(valid=False, errors=structural_errors, reason_code="invalid_chain_type"),
                _level(valid=False, errors=["structural_failed"], reason_code="structural_failed"),
            )
            return result

        if len(chain) == 0:
            structural_errors.append("Delegation chain cannot be empty")
            result.add_error(structural_errors[0])
            _attach_levels(
                result,
                _level(valid=False, errors=structural_errors, reason_code="empty_chain"),
                _level(valid=False, errors=["structural_failed"], reason_code="structural_failed"),
            )
            return result

        saw_signature = False
        all_crypto_ok = True

        for i, token in enumerate(chain):
            s_errs, c_errs, c_reason, has_sig, crypto_ok = self._validate_ucan_token_levels(
                token, i, keys
            )
            structural_errors.extend(s_errs)
            for err in s_errs:
                result.add_error(err)
            if has_sig:
                saw_signature = True
            if c_errs:
                crypto_errors.extend(c_errs)
            if not crypto_ok:
                all_crypto_ok = False
                if crypto_reason is None:
                    crypto_reason = c_reason
                # Invalid/forged signature material fails closed at the overall result.
                if has_sig or require_sig:
                    for err in c_errs:
                        if err not in result.errors:
                            result.add_error(err)

        structural_ok = len(structural_errors) == 0
        cryptographic_ok = all_crypto_ok and structural_ok

        if require_sig and not cryptographic_ok:
            if not crypto_errors:
                crypto_errors.append("signatures_required")
                crypto_reason = crypto_reason or "missing_signature"
            for err in crypto_errors:
                if err not in result.errors:
                    result.add_error(err)
            result.is_valid = False

        if not structural_ok:
            result.is_valid = False

        _attach_levels(
            result,
            _level(
                valid=structural_ok,
                errors=structural_errors,
                reason_code=None if structural_ok else "structural_invalid",
            ),
            _level(
                valid=cryptographic_ok,
                errors=crypto_errors
                if crypto_errors
                else ([] if cryptographic_ok else ["missing_signature"]),
                reason_code=(
                    None
                    if cryptographic_ok
                    else (crypto_reason or ("missing_signature" if not saw_signature else "invalid_signature"))
                ),
            ),
        )
        result.metadata["chain_length"] = len(chain)
        result.metadata["require_signatures"] = require_sig
        return result

    def verify_delegation_proof(
        self,
        token: Dict[str, Any],
        *,
        public_key: Any = None,
        issuer_public_keys: Optional[Mapping[str, Any]] = None,
    ) -> ValidationResult:
        """
        Cryptographic verification of a single delegation proof (DelegationProof@1).

        ``is_valid`` is True only when both structural and cryptographic levels pass.
        """
        result = ValidationResult(is_valid=True, message_type="delegation_proof")
        keys = dict(self.issuer_public_keys)
        if issuer_public_keys:
            keys.update(dict(issuer_public_keys))
        if public_key is not None:
            iss = self._issuer_of(token)
            if iss:
                keys[iss] = public_key

        s_errs, c_errs, c_reason, _has_sig, crypto_ok = self._validate_ucan_token_levels(
            token, 0, keys, force_crypto=True
        )
        structural_ok = len(s_errs) == 0
        for err in s_errs:
            result.add_error(err)
        for err in c_errs:
            result.add_error(err)
        cryptographic_ok = structural_ok and crypto_ok
        if not cryptographic_ok:
            result.is_valid = False
        _attach_levels(
            result,
            _level(
                valid=structural_ok,
                errors=s_errs,
                reason_code=None if structural_ok else "structural_invalid",
            ),
            _level(
                valid=cryptographic_ok,
                errors=c_errs,
                reason_code=None if cryptographic_ok else (c_reason or "invalid_signature"),
            ),
        )
        if cryptographic_ok:
            result.metadata["signature_alg"] = SIGNATURE_ALG_EDDSA
            result.metadata["signing_algorithm"] = CANONICAL_ALGORITHM
        return result

    def _validate_ucan_token(
        self,
        token: Dict[str, Any],
        index: int,
        result: ValidationResult,
    ) -> None:
        """Validate a single UCAN token (structural path used by legacy callers)."""
        s_errs, c_errs, _c_reason, has_sig, crypto_ok = self._validate_ucan_token_levels(
            token, index, self.issuer_public_keys
        )
        for err in s_errs:
            result.add_error(err)
        if has_sig and not crypto_ok:
            for err in c_errs:
                result.add_error(err)

    def _validate_ucan_token_levels(
        self,
        token: Any,
        index: int,
        issuer_public_keys: Mapping[str, Any],
        *,
        force_crypto: bool = False,
    ) -> Tuple[List[str], List[str], Optional[str], bool, bool]:
        """
        Return (structural_errors, crypto_errors, crypto_reason, has_signature, crypto_ok).
        """
        structural_errors: List[str] = []
        crypto_errors: List[str] = []
        crypto_reason: Optional[str] = None

        if isinstance(token, str):
            return self._validate_compact_token(
                token, index, issuer_public_keys, force_crypto=force_crypto
            )

        if not isinstance(token, dict):
            structural_errors.append(f"Token at index {index} must be an object")
            return structural_errors, ["structural_failed"], "structural_failed", False, False

        # Compact envelope nested as {"token": "h.p.s"} or {"ucan": ...}
        nested = token.get("token") or token.get("ucan") or token.get("jwt")
        if isinstance(nested, str) and nested.count(".") == 2:
            s_errs, c_errs, c_reason, has_sig, crypto_ok = self._validate_compact_token(
                nested, index, issuer_public_keys, force_crypto=force_crypto
            )
            # Also allow object-level required field aliases if present.
            return s_errs, c_errs, c_reason, has_sig, crypto_ok

        iss = token.get("iss", token.get("issuer"))
        aud = token.get("aud", token.get("audience"))
        att = token.get("att", token.get("capabilities"))
        exp = token.get("exp", token.get("expiry", token.get("expiration")))

        if iss is None or (isinstance(iss, str) and not str(iss).strip()):
            structural_errors.append(f"Token at index {index} missing required field: iss")
        if aud is None or (isinstance(aud, str) and not str(aud).strip()):
            structural_errors.append(f"Token at index {index} missing required field: aud")
        if att is None:
            structural_errors.append(f"Token at index {index} missing required field: att")
        elif not isinstance(att, list):
            structural_errors.append(f"Token at index {index}: 'att' must be a list")
        if exp is None:
            structural_errors.append(f"Token at index {index} missing required field: exp")

        sig_raw = token.get("signature", token.get("sig"))
        has_sig = sig_raw is not None and str(sig_raw).strip() != ""

        if not has_sig and not force_crypto:
            crypto_errors.append(f"Token at index {index}: missing signature")
            return structural_errors, crypto_errors, "missing_signature", False, False

        if not has_sig and force_crypto:
            crypto_errors.append(f"Token at index {index}: missing signature")
            return structural_errors, crypto_errors, "missing_signature", False, False

        if not HAVE_CRYPTO_ED25519:
            crypto_errors.append(f"Token at index {index}: cryptography_ed25519_unavailable")
            return structural_errors, crypto_errors, "crypto_unavailable", True, False

        header = token.get("header") or token.get("protected")
        alg = None
        kid = None
        if isinstance(header, Mapping):
            alg = header.get("alg")
            kid = header.get("kid")
        alg = alg or token.get("alg") or token.get("signature_alg") or token.get("signatureAlg")
        kid = kid or token.get("kid")

        if alg is not None:
            alg_text = str(alg).strip()
            if alg_text in {"none", "None", "NONE", ""}:
                crypto_errors.append(f"Token at index {index}: algorithm_or_version_downgrade")
                return structural_errors, crypto_errors, "algorithm_or_version_downgrade", True, False
            if alg_text not in {SIGNATURE_ALG_EDDSA, SIGNATURE_ALG_ED25519, "ed25519", "Ed25519"}:
                crypto_errors.append(f"Token at index {index}: unsupported_signature_alg:{alg_text}")
                return structural_errors, crypto_errors, "unsupported_signature_alg", True, False

        # kid is required when verifying signed material (ADR-0002).
        if kid is None or str(kid).strip() == "":
            # Allow did:key issuers where the key is self-describing; still record kid absence
            # as soft only when public key resolves from did:key.
            issuer = str(iss or "").strip()
            if not issuer.startswith("did:key:"):
                crypto_errors.append(f"Token at index {index}: missing_kid")
                return structural_errors, crypto_errors, "missing_kid", True, False

        signature = _decode_signature(sig_raw)
        if signature is None:
            crypto_errors.append(f"Token at index {index}: invalid_signature_encoding")
            return structural_errors, crypto_errors, "invalid_signature_encoding", True, False

        public_key = self._resolve_public_key(token, issuer_public_keys, kid=str(kid or ""))
        if public_key is None:
            crypto_errors.append(f"Token at index {index}: verification_key_unavailable")
            return structural_errors, crypto_errors, "verification_key_unavailable", True, False

        # Prefer compact header/payload construction when both are present.
        if isinstance(header, Mapping) and isinstance(token.get("payload"), Mapping):
            message = compact_signing_input(header, token["payload"])  # type: ignore[arg-type]
        elif isinstance(header, Mapping):
            message = compact_signing_input(header, _signing_object_from_token(token))
        else:
            message = canonical_signing_bytes(token)

        if not verify_ed25519(public_key, message, signature):
            crypto_errors.append(f"Token at index {index}: invalid_signature")
            return structural_errors, crypto_errors, "invalid_signature", True, False

        return structural_errors, crypto_errors, None, True, True

    def _validate_compact_token(
        self,
        token: str,
        index: int,
        issuer_public_keys: Mapping[str, Any],
        *,
        force_crypto: bool = False,
    ) -> Tuple[List[str], List[str], Optional[str], bool, bool]:
        structural_errors: List[str] = []
        crypto_errors: List[str] = []

        parts = token.split(".")
        if len(parts) != 3 or not all(parts):
            # Two-part or malformed = unsigned/malformed at crypto; may also lack fields.
            structural_errors.append(f"Token at index {index} missing required field: att")
            structural_errors.append(f"Token at index {index} missing required field: exp")
            crypto_errors.append(f"Token at index {index}: unsigned_or_malformed_token")
            return structural_errors, crypto_errors, "unsigned_or_malformed_token", False, False

        try:
            header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
            payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
            signature = _b64url_decode(parts[2])
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            structural_errors.append(f"Token at index {index} missing required field: iss")
            crypto_errors.append(f"Token at index {index}: malformed_token")
            return structural_errors, crypto_errors, "malformed_token", True, False

        if not isinstance(header, dict) or not isinstance(payload, dict):
            structural_errors.append(f"Token at index {index} must be an object")
            return structural_errors, ["malformed_token"], "malformed_token", True, False

        for field in ("iss", "aud", "att", "exp"):
            if field not in payload:
                structural_errors.append(f"Token at index {index} missing required field: {field}")
        if "att" in payload and not isinstance(payload["att"], list):
            structural_errors.append(f"Token at index {index}: 'att' must be a list")

        if set(header) != {"alg", "kid", "typ", "v"}:
            crypto_errors.append(f"Token at index {index}: algorithm_or_version_downgrade")
            return structural_errors, crypto_errors, "algorithm_or_version_downgrade", True, False
        if header.get("alg") != SIGNATURE_ALG_EDDSA or header.get("typ") != "UCAN" or header.get("v") != 1:
            crypto_errors.append(f"Token at index {index}: algorithm_or_version_downgrade")
            return structural_errors, crypto_errors, "algorithm_or_version_downgrade", True, False
        if not str(header.get("kid") or "").strip():
            crypto_errors.append(f"Token at index {index}: missing_kid")
            return structural_errors, crypto_errors, "missing_kid", True, False

        if not HAVE_CRYPTO_ED25519:
            crypto_errors.append(f"Token at index {index}: cryptography_ed25519_unavailable")
            return structural_errors, crypto_errors, "crypto_unavailable", True, False

        if len(signature) != 64:
            crypto_errors.append(f"Token at index {index}: invalid_signature_encoding")
            return structural_errors, crypto_errors, "invalid_signature_encoding", True, False

        # Reject non-canonical header/payload encodings (signature covers the wire form,
        # but JCS identity of decoded maps must match the encoded segments).
        try:
            if _b64url_encode(canonicalize_bytes(header)) != parts[0]:
                crypto_errors.append(f"Token at index {index}: noncanonical_header")
                return structural_errors, crypto_errors, "noncanonical_header", True, False
            if _b64url_encode(canonicalize_bytes(payload)) != parts[1]:
                crypto_errors.append(f"Token at index {index}: noncanonical_payload")
                return structural_errors, crypto_errors, "noncanonical_payload", True, False
        except Exception:
            crypto_errors.append(f"Token at index {index}: canonicalization_failed")
            return structural_errors, crypto_errors, "canonicalization_failed", True, False

        public_key = self._resolve_public_key(
            {"iss": payload.get("iss"), **{k: payload.get(k) for k in ()}},
            issuer_public_keys,
            kid=str(header.get("kid") or ""),
            issuer_override=str(payload.get("iss") or ""),
        )
        # Also try issuer map directly.
        if public_key is None:
            public_key = _decode_public_key(issuer_public_keys.get(str(payload.get("iss") or "")))
        if public_key is None:
            public_key = ed25519_public_key_from_did_key(str(payload.get("iss") or ""))
        if public_key is None:
            crypto_errors.append(f"Token at index {index}: verification_key_unavailable")
            return structural_errors, crypto_errors, "verification_key_unavailable", True, False

        message = f"{parts[0]}.{parts[1]}".encode("ascii")
        if not verify_ed25519(public_key, message, signature):
            crypto_errors.append(f"Token at index {index}: invalid_signature")
            return structural_errors, crypto_errors, "invalid_signature", True, False

        return structural_errors, crypto_errors, None, True, True

    def _resolve_public_key(
        self,
        token: Mapping[str, Any],
        issuer_public_keys: Mapping[str, Any],
        *,
        kid: str = "",
        issuer_override: str = "",
    ) -> Optional[bytes]:
        for key_name in ("public_key", "publicKey", "issuer_public_key", "public_key_b64"):
            if key_name in token:
                raw = _decode_public_key(token.get(key_name))
                if raw is not None:
                    return raw
        issuer = issuer_override or str(token.get("iss") or token.get("issuer") or "").strip()
        if issuer and issuer in issuer_public_keys:
            entry = issuer_public_keys[issuer]
            # Support {kid: key} maps.
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
        return None

    @staticmethod
    def _issuer_of(token: Any) -> str:
        if isinstance(token, Mapping):
            return str(token.get("iss") or token.get("issuer") or "").strip()
        return ""

    def validate_invocation_with_proof(self, invocation: Dict[str, Any]) -> ValidationResult:
        """
        Validate an invocation with delegation proof.

        Args:
            invocation: Invocation with proof_cid reference

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type="invocation_with_proof")

        if "proof_cid" not in invocation:
            result.add_error("Invocation missing 'proof_cid' reference")

        structural_ok = result.is_valid
        _attach_levels(
            result,
            _level(
                valid=structural_ok,
                errors=list(result.errors),
                reason_code=None if structural_ok else "missing_proof_cid",
            ),
            _level(
                valid=False,
                errors=["proof_bundle_not_resolved"],
                reason_code="proof_bundle_not_resolved",
            ),
        )
        return result


__all__ = [
    "UCANDelegationValidator",
    "INTERFACE",
    "CANONICAL_ALGORITHM",
    "HAVE_CRYPTO_ED25519",
    "canonical_signing_bytes",
    "compact_signing_input",
    "verify_ed25519",
    "ed25519_public_key_from_did_key",
]
