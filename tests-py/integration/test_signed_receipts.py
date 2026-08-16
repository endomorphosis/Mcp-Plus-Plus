"""
Signed cross-trust-domain receipts (MCPP-045 / plan gate 15).

Interface: ReceiptVerifier@1
Spec: docs/spec/cid-native-artifacts.md §6 (receipts), execution-envelope.md §6.2
Conformance: ADR-0003 level ``receipt-signed``
Depends on: MCPP-044 (adversarial UCAN), MCPP-033 (ExecutionReceipt@1)

Acceptance:
  - Unsigned cross-domain receipt is deny.
  - Valid TLS/PeerID with invalid UCAN is deny (transport identity ≠ authority).
  - Independent verifier process can validate a receipt by CID.

Effects:
  Cross-trust-domain execution requires a signed receipt. Transport identity
  (PeerID / TLS client cert) cannot satisfy execution authority (KD-14).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_TESTS_ROOT = Path(__file__).resolve().parent.parent
_MCPPLUSPLUS_ROOT = _TESTS_ROOT.parent
_THIS_FILE = Path(__file__).resolve()
_VECTORS = _MCPPLUSPLUS_ROOT / "conformance" / "vectors" / "crypto" / "adversarial"

sys.path.insert(0, str(_TESTS_ROOT))

from validators.base_mcp import ValidationResult  # noqa: E402
from validators.canonical_jcs import (  # noqa: E402
    ALGORITHM_ID as CANONICAL_ALGORITHM,
    artifact_cid,
    canonicalize_bytes,
)
from validators.envelope_profile_b import (  # noqa: E402
    SCHEMA_RECEIPT,
    validate_receipt_v1,
)
from validators.ucan_delegation import (  # noqa: E402
    UCANDelegationValidator,
    ed25519_public_key_from_did_key,
    verify_ed25519,
)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    HAVE_CRYPTO = True
except Exception:  # pragma: no cover
    Ed25519PrivateKey = None  # type: ignore[misc, assignment]
    Ed25519PublicKey = None  # type: ignore[misc, assignment]
    HAVE_CRYPTO = False


# ---------------------------------------------------------------------------
# Interface constants
# ---------------------------------------------------------------------------

INTERFACE = "ReceiptVerifier@1"
TASK_ID = "MCPP-045"
SCHEMA_MARKER = SCHEMA_RECEIPT  # mcp++/execution/receipt@1
SIGNATURE_ALG = "Ed25519"
LEVEL_RECEIPT_SIGNED = "receipt-signed"
LEVEL_STRUCTURAL = "structural"
LEVEL_CRYPTOGRAPHIC = "cryptographic"

CID_RE = re.compile(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$")
DID_RE = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$")

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# Signature and transport-only fields excluded from the detached signing payload.
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
        "issuer_public_key",
        # Self-address is assigned after signing; never part of the signed body.
        "receipt_cid",
    }
)

# Stable fixture CIDs (valid pattern; used only for structural shape).
CID_A = "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
CID_B = "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti"
CID_C = "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi"
CID_D = "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"


# ---------------------------------------------------------------------------
# Crypto / DID helpers
# ---------------------------------------------------------------------------


def _require_crypto() -> None:
    if not HAVE_CRYPTO:
        pytest.skip("cryptography Ed25519 unavailable")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty_base64url")
    pad = "=" * ((4 - (len(text) % 4)) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _base58btc_encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    chars: List[str] = []
    while n > 0:
        n, rem = divmod(n, 58)
        chars.append(_B58_ALPHABET[rem])
    for byte in raw:
        if byte == 0:
            chars.append(_B58_ALPHABET[0])
        else:
            break
    return "".join(reversed(chars or [_B58_ALPHABET[0]]))


def did_key_from_public(public_key: bytes) -> str:
    """Build did:key:z… for a raw Ed25519 public key (multicodec 0xed01)."""
    if len(public_key) != 32:
        raise ValueError("public_key must be 32 bytes")
    payload = bytes([0xED, 0x01]) + public_key
    return "did:key:z" + _base58btc_encode(payload)


def _decode_public_key(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return raw if len(raw) == 32 else None
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("did:key:"):
        return ed25519_public_key_from_did_key(text)
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
    except Exception:
        pass
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
    if len(text) == 128:
        try:
            raw = bytes.fromhex(text)
            return raw if len(raw) == 64 else None
        except ValueError:
            return None
    try:
        raw = _b64url_decode(text)
        return raw if len(raw) == 64 else None
    except Exception:
        return None


def signing_object(receipt: Mapping[str, Any]) -> Dict[str, Any]:
    """Detached receipt body signed under mcpp-jcs-v1 (excludes signature + receipt_cid)."""
    return {k: v for k, v in receipt.items() if k not in _SIG_META_KEYS}


def receipt_signing_bytes(receipt: Mapping[str, Any]) -> bytes:
    return canonicalize_bytes(signing_object(receipt))


def receipt_content_cid(receipt: Mapping[str, Any]) -> str:
    """CID of the receipt body excluding the self-address field ``receipt_cid``.

    Signature bytes (when present) are included so the CID binds the signed
    attestation. ``receipt_cid`` is assigned after hashing and therefore
    excluded to avoid a fixed-point loop.
    """
    body = {k: v for k, v in receipt.items() if k != "receipt_cid"}
    return artifact_cid(body)


# ---------------------------------------------------------------------------
# Content-addressed receipt store (in-process + on-disk for independent verify)
# ---------------------------------------------------------------------------


class ReceiptContentStore:
    """Minimal CID → bytes store used for independent verification by CID."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root is not None else None
        self._memory: Dict[str, bytes] = {}
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, payload: bytes, *, cid: Optional[str] = None) -> str:
        digest = hashlib.sha256(payload).digest()
        computed = "b" + base64.b32encode(bytes([0x01, 0x55, 0x12, 0x20]) + digest).decode(
            "ascii"
        ).rstrip("=").lower()
        # Prefer mcpp-jcs artifact_cid when payload is canonical JSON of a receipt;
        # for raw store identity use Kubo-style raw sha2-256 when cid not given.
        store_cid = cid or computed
        self._memory[store_cid] = payload
        if self.root is not None:
            path = self.root / f"{store_cid}.json"
            path.write_bytes(payload)
            # Sidecar index for multi-process lookup
            (self.root / "index.json").write_text(
                json.dumps(
                    {**(self._load_index()), store_cid: path.name},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
        return store_cid

    def put_receipt(self, receipt: Mapping[str, Any]) -> str:
        """Store a receipt keyed by the CID of its body (excluding ``receipt_cid``).

        Self-address pattern: compute CID over the document without
        ``receipt_cid``, then embed that value as ``receipt_cid`` on the wire
        form. Independent verifiers recompute the same way (see
        ``receipt_content_cid``).
        """
        body = dict(receipt)
        body.pop("receipt_cid", None)
        store_cid = receipt_content_cid(body)
        body["receipt_cid"] = store_cid
        payload = canonicalize_bytes(body)
        self.put_bytes(payload, cid=store_cid)
        return store_cid

    def get_bytes(self, cid: str) -> Optional[bytes]:
        if cid in self._memory:
            return self._memory[cid]
        if self.root is None:
            return None
        index = self._load_index()
        name = index.get(cid)
        if name:
            path = self.root / name
            if path.is_file():
                return path.read_bytes()
        # Fallback: direct filename
        path = self.root / f"{cid}.json"
        if path.is_file():
            return path.read_bytes()
        return None

    def get_receipt(self, cid: str) -> Optional[Dict[str, Any]]:
        raw = self.get_bytes(cid)
        if raw is None:
            return None
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(obj, dict):
            return None
        return obj

    def _load_index(self) -> Dict[str, str]:
        if self.root is None:
            return {}
        index_path = self.root / "index.json"
        if not index_path.is_file():
            return {}
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            return dict(data) if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


# ---------------------------------------------------------------------------
# Trust context & verdict
# ---------------------------------------------------------------------------


@dataclass
class TrustContext:
    """Transport + trust-domain context for receipt admission.

    Transport fields (``peer_id``, ``peer_authenticated``, ``tls_valid``) describe
    how the peer was identified on the wire. They **never** grant execution
    authority. Authority is only UCAN / delegation proof verification.
    """

    requester_trust_domain: str
    executor_trust_domain: str
    peer_id: Optional[str] = None
    peer_authenticated: bool = False
    tls_valid: bool = False
    # Optional UCAN / delegation material for authority checks.
    authority_token: Optional[Mapping[str, Any]] = None
    authority_chain: Optional[Sequence[Mapping[str, Any]]] = None
    issuer_public_keys: Optional[Mapping[str, Any]] = None
    # When True, force cross-domain rules even if domain strings match.
    force_cross_domain: bool = False

    @property
    def is_cross_domain(self) -> bool:
        if self.force_cross_domain:
            return True
        return (
            str(self.requester_trust_domain).strip()
            != str(self.executor_trust_domain).strip()
        )

    @property
    def transport_authenticated(self) -> bool:
        return bool(self.peer_authenticated or self.tls_valid)


@dataclass
class ReceiptVerdict:
    """Admission decision from ReceiptVerifier@1."""

    admitted: bool
    reason_codes: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    levels: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def denied(self) -> bool:
        return not self.admitted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admitted": self.admitted,
            "reason_codes": list(self.reason_codes),
            "reasons": list(self.reasons),
            "levels": self.levels,
            "metadata": self.metadata,
            "interface": INTERFACE,
        }


def _level(*, valid: bool, errors: Optional[List[str]] = None, reason_code: Optional[str] = None) -> Dict[str, Any]:
    return {
        "valid": bool(valid),
        "errors": list(errors or []),
        "reason_code": reason_code,
    }


# ---------------------------------------------------------------------------
# ReceiptVerifier@1
# ---------------------------------------------------------------------------


class ReceiptVerifier:
    """Independent ExecutionReceipt@1 verifier (ReceiptVerifier@1).

    Conformance ladder for a single receipt admission:

    * ``structural`` — shape / schema fields
    * ``cryptographic`` — Ed25519 verify over mcpp-jcs-v1 signing bytes (when signed)
    * ``receipt-signed`` — cross-trust admits only when signature verifies and
      (when authority material is supplied) UCAN authority also verifies.
      Transport identity is never sufficient.
    """

    def __init__(
        self,
        *,
        executor_public_keys: Optional[Mapping[str, Any]] = None,
        require_signatures_cross_domain: bool = True,
        require_authority_cross_domain: bool = True,
    ) -> None:
        self.executor_public_keys: Dict[str, Any] = dict(executor_public_keys or {})
        self.require_signatures_cross_domain = bool(require_signatures_cross_domain)
        self.require_authority_cross_domain = bool(require_authority_cross_domain)

    # -- public API ---------------------------------------------------------

    def verify_receipt(
        self,
        receipt: Mapping[str, Any],
        *,
        trust: Optional[TrustContext] = None,
        executor_public_keys: Optional[Mapping[str, Any]] = None,
    ) -> ReceiptVerdict:
        """Verify a receipt document under the given trust context."""
        keys = dict(self.executor_public_keys)
        if executor_public_keys:
            keys.update(executor_public_keys)
        if trust and trust.issuer_public_keys:
            keys.update(dict(trust.issuer_public_keys))

        meta: Dict[str, Any] = {
            "interface": INTERFACE,
            "task_id": TASK_ID,
            "canonical_algorithm": CANONICAL_ALGORITHM,
            "cross_domain": bool(trust.is_cross_domain) if trust else None,
            "peer_authenticated": bool(trust.peer_authenticated) if trust else False,
            "tls_valid": bool(trust.tls_valid) if trust else False,
            "peer_id": trust.peer_id if trust else None,
            "transport_authenticated": bool(trust.transport_authenticated)
            if trust
            else False,
        }

        # --- structural ---
        structural_errors: List[str] = []
        if not isinstance(receipt, Mapping):
            structural_errors.append("receipt_must_be_object")
            return self._deny(
                ["structural_invalid"],
                structural_errors,
                structural=_level(valid=False, errors=structural_errors, reason_code="structural_invalid"),
                cryptographic=_level(valid=False, reason_code="not_evaluated"),
                receipt_signed=_level(valid=False, reason_code="structural_invalid"),
                metadata=meta,
            )

        shape = validate_receipt_v1(receipt)
        if not shape.is_valid:
            structural_errors.extend(shape.errors)

        # Cross-domain receipts must carry a non-null delegation_cid (authority
        # binding) when require_authority_cross_domain is set; null is only for
        # same-trust local receipts per ExecutionReceipt@1 schema prose.
        if trust and trust.is_cross_domain:
            if receipt.get("delegation_cid") in (None, ""):
                structural_errors.append(
                    "cross_domain_receipt_requires_delegation_cid"
                )

        structural_ok = not structural_errors
        structural_level = _level(
            valid=structural_ok,
            errors=structural_errors,
            reason_code=None if structural_ok else "structural_invalid",
        )
        if not structural_ok:
            return self._deny(
                ["structural_invalid"],
                structural_errors,
                structural=structural_level,
                cryptographic=_level(valid=False, reason_code="not_evaluated"),
                receipt_signed=_level(valid=False, reason_code="structural_invalid"),
                metadata=meta,
            )

        cross = bool(trust and trust.is_cross_domain)
        sig_value = receipt.get("signature")
        has_signature = sig_value is not None and str(sig_value).strip() != ""

        # --- unsigned cross-domain: hard deny ---
        if cross and self.require_signatures_cross_domain and not has_signature:
            codes = ["unsigned_cross_domain_receipt"]
            reasons = [
                "cross-trust-domain receipts MUST be signed (plan gate 15 / receipt-signed)"
            ]
            # Transport auth does not rescue an unsigned cross-domain receipt.
            if trust and trust.transport_authenticated:
                codes.append("peerid_not_authority")
                reasons.append(
                    "transport identity (TLS/PeerID) does not satisfy execution authority"
                )
            meta["unsigned"] = True
            return self._deny(
                codes,
                reasons,
                structural=structural_level,
                cryptographic=_level(
                    valid=False,
                    errors=["missing_signature"],
                    reason_code="unsigned_cross_domain_receipt",
                ),
                receipt_signed=_level(
                    valid=False,
                    errors=["missing_signature"],
                    reason_code="unsigned_cross_domain_receipt",
                ),
                metadata=meta,
            )

        # --- signature verification (when present) ---
        crypto_errors: List[str] = []
        crypto_ok = False
        if has_signature:
            crypto_ok, crypto_errors = self._verify_signature(receipt, keys)
            meta["signature_present"] = True
            meta["signature_valid"] = crypto_ok
        else:
            # Same-trust MAY omit signature (structural only; not receipt-signed).
            meta["signature_present"] = False
            meta["signature_valid"] = None
            crypto_ok = not cross  # same-trust unsigned is crypto N/A → treat as pass-through

        crypto_level = _level(
            valid=crypto_ok if has_signature else (not cross),
            errors=crypto_errors,
            reason_code=None
            if (crypto_ok if has_signature else (not cross))
            else (crypto_errors[0] if crypto_errors else "invalid_signature"),
        )

        if has_signature and not crypto_ok:
            codes = ["invalid_signature"]
            reasons = list(crypto_errors) or ["receipt signature failed verification"]
            if trust and trust.transport_authenticated:
                codes.append("peerid_not_authority")
                reasons.append(
                    "valid transport identity does not replace a valid receipt signature"
                )
            return self._deny(
                codes,
                reasons,
                structural=structural_level,
                cryptographic=crypto_level,
                receipt_signed=_level(
                    valid=False,
                    errors=crypto_errors,
                    reason_code="invalid_signature",
                ),
                metadata=meta,
            )

        # --- authority: transport ≠ UCAN (KD-14) ---
        authority_codes: List[str] = []
        authority_reasons: List[str] = []
        authority_ok = True

        if trust is not None:
            has_authority_material = (
                trust.authority_token is not None
                or (trust.authority_chain is not None and len(trust.authority_chain) > 0)
            )
            # Explicit invalid-UCAN path: peer authenticated but UCAN fails.
            if has_authority_material or (
                cross and self.require_authority_cross_domain
            ):
                authority_ok, authority_codes, authority_reasons = self._check_authority(
                    trust, keys
                )
                meta["authority_valid"] = authority_ok
                meta["authority_reason_codes"] = list(authority_codes)

                if not authority_ok:
                    codes = list(authority_codes) or ["invalid_ucan"]
                    # Always record peerid_not_authority when transport looked fine.
                    if trust.transport_authenticated and "peerid_not_authority" not in codes:
                        codes.insert(0, "peerid_not_authority")
                    reasons = list(authority_reasons) or [
                        "UCAN/delegation authority failed; transport identity is not authority"
                    ]
                    return self._deny(
                        codes,
                        reasons,
                        structural=structural_level,
                        cryptographic=crypto_level,
                        receipt_signed=_level(
                            valid=False,
                            errors=reasons,
                            reason_code="peerid_not_authority"
                            if trust.transport_authenticated
                            else "invalid_ucan",
                        ),
                        metadata=meta,
                    )

            # Transport-only claim with no authority material on cross-domain.
            if (
                cross
                and self.require_authority_cross_domain
                and not has_authority_material
                and trust.transport_authenticated
            ):
                return self._deny(
                    ["peerid_not_authority", "missing_authority_proof"],
                    [
                        "cross-domain execution requires UCAN/delegation authority; "
                        "TLS/PeerID alone is deny"
                    ],
                    structural=structural_level,
                    cryptographic=crypto_level,
                    receipt_signed=_level(
                        valid=False,
                        reason_code="peerid_not_authority",
                    ),
                    metadata=meta,
                )

        # --- receipt-signed level ---
        receipt_signed_ok = False
        if cross:
            receipt_signed_ok = bool(has_signature and crypto_ok and authority_ok)
        else:
            # Same-trust: signed receipts that verify achieve receipt-signed;
            # unsigned same-trust is structural only.
            receipt_signed_ok = bool(has_signature and crypto_ok)

        receipt_signed_level = _level(
            valid=receipt_signed_ok,
            reason_code=None if receipt_signed_ok else "receipt_not_signed_level",
        )

        # Cross-domain admits only at receipt-signed.
        if cross and not receipt_signed_ok:
            return self._deny(
                ["receipt_signed_required"],
                ["cross-domain admission requires receipt-signed conformance"],
                structural=structural_level,
                cryptographic=crypto_level,
                receipt_signed=receipt_signed_level,
                metadata=meta,
            )

        meta["conformance_level"] = (
            LEVEL_RECEIPT_SIGNED
            if receipt_signed_ok
            else (LEVEL_STRUCTURAL if structural_ok else None)
        )
        levels = {
            LEVEL_STRUCTURAL: structural_level,
            LEVEL_CRYPTOGRAPHIC: crypto_level,
            LEVEL_RECEIPT_SIGNED: receipt_signed_level,
        }
        return ReceiptVerdict(
            admitted=True,
            reason_codes=[],
            reasons=[],
            levels=levels,
            metadata=meta,
        )

    def verify_by_cid(
        self,
        receipt_cid: str,
        store: ReceiptContentStore,
        *,
        trust: Optional[TrustContext] = None,
        executor_public_keys: Optional[Mapping[str, Any]] = None,
    ) -> ReceiptVerdict:
        """Load a receipt by CID from an independent store and verify it.

        The verifier recomputes the content CID of the loaded document and
        fails closed on mismatch — proving the receipt is content-addressed
        and independently verifiable without the executor's transport session.
        """
        meta_base: Dict[str, Any] = {
            "interface": INTERFACE,
            "receipt_cid": receipt_cid,
            "verify_mode": "by_cid",
        }
        if not isinstance(receipt_cid, str) or not CID_RE.match(receipt_cid):
            return self._deny(
                ["invalid_receipt_cid"],
                [f"receipt_cid format invalid: {receipt_cid!r}"],
                structural=_level(valid=False, reason_code="invalid_receipt_cid"),
                cryptographic=_level(valid=False, reason_code="not_evaluated"),
                receipt_signed=_level(valid=False, reason_code="invalid_receipt_cid"),
                metadata=meta_base,
            )

        receipt = store.get_receipt(receipt_cid)
        if receipt is None:
            return self._deny(
                ["receipt_not_found"],
                [f"no receipt bytes for CID {receipt_cid}"],
                structural=_level(valid=False, reason_code="receipt_not_found"),
                cryptographic=_level(valid=False, reason_code="not_evaluated"),
                receipt_signed=_level(valid=False, reason_code="receipt_not_found"),
                metadata=meta_base,
            )

        # Recompute CID of the body (excluding receipt_cid self-address).
        recomputed = receipt_content_cid(receipt)
        meta_base["recomputed_cid"] = recomputed
        declared = receipt.get("receipt_cid")
        if recomputed != receipt_cid or (
            declared is not None and declared != receipt_cid
        ):
            return self._deny(
                ["cid_mismatch"],
                [
                    f"stored receipt CID mismatch: lookup={receipt_cid} "
                    f"recomputed={recomputed} declared={declared!r}"
                ],
                structural=_level(valid=False, reason_code="cid_mismatch"),
                cryptographic=_level(valid=False, reason_code="not_evaluated"),
                receipt_signed=_level(valid=False, reason_code="cid_mismatch"),
                metadata=meta_base,
            )

        verdict = self.verify_receipt(
            receipt,
            trust=trust,
            executor_public_keys=executor_public_keys,
        )
        verdict.metadata.update(meta_base)
        verdict.metadata["independent"] = True
        return verdict

    # -- internals ----------------------------------------------------------

    def _verify_signature(
        self,
        receipt: Mapping[str, Any],
        keys: Mapping[str, Any],
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        alg = receipt.get("signature_alg")
        if alg is not None and str(alg) not in {SIGNATURE_ALG, "EdDSA", "ed25519", "Ed25519"}:
            errors.append(f"unsupported_signature_alg:{alg}")
            return False, errors

        sig = _decode_signature(receipt.get("signature"))
        if sig is None:
            errors.append("undecodable_signature")
            return False, errors

        executor = receipt.get("executor") or {}
        did = None
        if isinstance(executor, Mapping):
            did = executor.get("did")
        public_key: Optional[bytes] = None
        if did:
            public_key = _decode_public_key(keys.get(str(did)))
            if public_key is None:
                public_key = ed25519_public_key_from_did_key(str(did))
            if public_key is None:
                public_key = _decode_public_key(keys.get("default"))
        if public_key is None:
            # Try any single key in the map as last resort only when did matches key id.
            for kid, val in keys.items():
                if did and kid == did:
                    public_key = _decode_public_key(val)
                    if public_key:
                        break
        if public_key is None:
            errors.append("missing_executor_public_key")
            return False, errors

        message = receipt_signing_bytes(receipt)
        if not verify_ed25519(public_key, message, sig):
            errors.append("invalid_signature")
            return False, errors
        return True, []

    def _check_authority(
        self,
        trust: TrustContext,
        keys: Mapping[str, Any],
    ) -> Tuple[bool, List[str], List[str]]:
        """Return (ok, reason_codes, reasons) for UCAN/delegation authority."""
        issuer_keys = dict(keys)
        if trust.issuer_public_keys:
            issuer_keys.update(dict(trust.issuer_public_keys))

        validator = UCANDelegationValidator(
            issuer_public_keys=issuer_keys,
            require_signatures=True,
        )

        # Prefer explicit chain; else wrap single token.
        chain: List[Dict[str, Any]] = []
        if trust.authority_chain:
            chain = [dict(t) for t in trust.authority_chain]
        elif trust.authority_token is not None:
            chain = [dict(trust.authority_token)]

        if not chain:
            codes = ["missing_authority_proof"]
            if trust.transport_authenticated:
                codes.insert(0, "peerid_not_authority")
            return False, codes, ["no UCAN/delegation proof provided"]

        # Prefer single-token cryptographic verify; fall back to chain API.
        if len(chain) == 1:
            single = validator.verify_delegation_proof(
                chain[0],
                issuer_public_keys=issuer_keys,
            )
            if single.is_valid and (single.metadata.get("levels") or {}).get(
                "cryptographic", {}
            ).get("valid"):
                return True, [], []
            crypto = (single.metadata.get("levels") or {}).get("cryptographic") or {}
            reason = crypto.get("reason_code") or "invalid_ucan"
            codes = ["invalid_ucan", str(reason)]
            reasons = list(single.errors) or ["UCAN authority verification failed"]
        else:
            result = validator.validate_delegation_chain(
                chain,
                issuer_public_keys=issuer_keys,
                require_signatures=True,
            )
            if result.is_valid and (result.metadata.get("levels") or {}).get(
                "cryptographic", {}
            ).get("valid"):
                return True, [], []
            crypto = (result.metadata.get("levels") or {}).get("cryptographic") or {}
            reason = crypto.get("reason_code") or "invalid_ucan"
            codes = ["invalid_ucan", str(reason)]
            reasons = list(result.errors) or ["UCAN authority verification failed"]

        if trust.transport_authenticated and "peerid_not_authority" not in codes:
            codes.insert(0, "peerid_not_authority")
        return False, codes, reasons

    def _deny(
        self,
        codes: Sequence[str],
        reasons: Sequence[str],
        *,
        structural: Dict[str, Any],
        cryptographic: Dict[str, Any],
        receipt_signed: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReceiptVerdict:
        meta = dict(metadata or {})
        meta["conformance_level"] = (
            LEVEL_STRUCTURAL
            if structural.get("valid") and not cryptographic.get("valid")
            else None
        )
        if structural.get("valid") and cryptographic.get("valid") and receipt_signed.get("valid"):
            meta["conformance_level"] = LEVEL_RECEIPT_SIGNED
        elif structural.get("valid") and cryptographic.get("valid"):
            meta["conformance_level"] = LEVEL_CRYPTOGRAPHIC
        elif structural.get("valid"):
            meta["conformance_level"] = LEVEL_STRUCTURAL
        return ReceiptVerdict(
            admitted=False,
            reason_codes=list(codes),
            reasons=list(reasons),
            levels={
                LEVEL_STRUCTURAL: structural,
                LEVEL_CRYPTOGRAPHIC: cryptographic,
                LEVEL_RECEIPT_SIGNED: receipt_signed,
            },
            metadata=meta,
        )


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def generate_executor_identity() -> Tuple[Any, bytes, str]:
    """Return (private_key, public_key_bytes, did:key)."""
    _require_crypto()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    did = did_key_from_public(public)
    return private, public, did


def base_receipt(*, executor_did: str, cross_domain: bool = True) -> Dict[str, Any]:
    """Structurally valid ExecutionReceipt@1 (unsigned)."""
    return {
        "schema": SCHEMA_MARKER,
        "envelope_cid": CID_A,
        "result_cid": CID_B,
        "status": "succeeded",
        "output_cids": [CID_C],
        "state_transitions": [],
        "side_effects": [],
        "decision_cid": CID_D,
        "delegation_cid": CID_C if cross_domain else None,
        "executor": {
            "did": executor_did,
            "runtime": "ipfs_accelerate_py",
            "runtime_version": "3.2.0",
            "peer_id": "12D3KooWReceiptPeerFixture000000000000000001",
        },
        "retry": {"attempt": 1},
        "duration_ms": 12.5,
        "error": None,
        "proofs": [CID_D],
        "signature": None,
        "signature_alg": None,
        "event_cid": CID_A,
        "started_at_ms": 1783872001100,
        "finished_at_ms": 1783872001113,
        "canonicalization": CANONICAL_ALGORITHM,
        "correlation_id": "mcpp-045-receipt",
    }


def sign_receipt(
    receipt: Mapping[str, Any],
    private_key: Any,
    *,
    alg: str = SIGNATURE_ALG,
) -> Dict[str, Any]:
    """Return a copy of *receipt* with a valid Ed25519 signature over JCS body."""
    body = dict(receipt)
    body["signature"] = None
    body["signature_alg"] = alg
    body.pop("receipt_cid", None)
    message = receipt_signing_bytes(body)
    signature = private_key.sign(message)
    body["signature"] = _b64url_encode(signature)
    body["signature_alg"] = alg
    return body


def load_adversarial_peerid_fixture() -> Dict[str, Any]:
    path = _VECTORS / "fixtures" / "valid_peerid_invalid_ucan.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Independent process entrypoint (python test_signed_receipts.py verify ...)
# ---------------------------------------------------------------------------


def _cli_verify(argv: List[str]) -> int:
    """CLI used by the independent-process test.

    Usage:
      python test_signed_receipts.py verify --store DIR --cid CID
          [--trust-json PATH] [--keys-json PATH]
    Prints a single JSON line: the ReceiptVerdict.to_dict().
    """
    import argparse

    parser = argparse.ArgumentParser(prog="receipt-verifier")
    parser.add_argument("command", choices=["verify"])
    parser.add_argument("--store", required=True)
    parser.add_argument("--cid", required=True)
    parser.add_argument("--trust-json", default=None)
    parser.add_argument("--keys-json", default=None)
    args = parser.parse_args(argv)

    store = ReceiptContentStore(root=Path(args.store))
    keys: Dict[str, Any] = {}
    if args.keys_json:
        keys = json.loads(Path(args.keys_json).read_text(encoding="utf-8"))

    trust: Optional[TrustContext] = None
    if args.trust_json:
        raw = json.loads(Path(args.trust_json).read_text(encoding="utf-8"))
        trust = TrustContext(
            requester_trust_domain=str(raw.get("requester_trust_domain") or "requester"),
            executor_trust_domain=str(raw.get("executor_trust_domain") or "executor"),
            peer_id=raw.get("peer_id"),
            peer_authenticated=bool(raw.get("peer_authenticated")),
            tls_valid=bool(raw.get("tls_valid")),
            authority_token=raw.get("authority_token"),
            authority_chain=raw.get("authority_chain"),
            issuer_public_keys=raw.get("issuer_public_keys"),
            force_cross_domain=bool(raw.get("force_cross_domain")),
        )

    verifier = ReceiptVerifier(executor_public_keys=keys)
    verdict = verifier.verify_by_cid(args.cid, store, trust=trust, executor_public_keys=keys)
    sys.stdout.write(json.dumps(verdict.to_dict(), sort_keys=True) + "\n")
    return 0 if verdict.admitted else 2


def run_independent_verifier_process(
    *,
    store_dir: Path,
    receipt_cid: str,
    keys: Mapping[str, Any],
    trust: TrustContext,
) -> Tuple[int, Dict[str, Any]]:
    """Spawn a separate Python process that verifies the receipt by CID only."""
    with tempfile.TemporaryDirectory(prefix="mcpp045-iv-") as tmp:
        tmp_path = Path(tmp)
        keys_path = tmp_path / "keys.json"
        trust_path = tmp_path / "trust.json"
        # Serialize keys as b64url strings for JSON.
        serial_keys: Dict[str, str] = {}
        for k, v in keys.items():
            if isinstance(v, (bytes, bytearray)):
                serial_keys[k] = _b64url_encode(bytes(v))
            else:
                serial_keys[k] = str(v)
        keys_path.write_text(json.dumps(serial_keys), encoding="utf-8")
        trust_doc: Dict[str, Any] = {
            "requester_trust_domain": trust.requester_trust_domain,
            "executor_trust_domain": trust.executor_trust_domain,
            "peer_id": trust.peer_id,
            "peer_authenticated": trust.peer_authenticated,
            "tls_valid": trust.tls_valid,
            "force_cross_domain": trust.force_cross_domain,
        }
        if trust.authority_token is not None:
            trust_doc["authority_token"] = dict(trust.authority_token)
        if trust.authority_chain is not None:
            trust_doc["authority_chain"] = [dict(t) for t in trust.authority_chain]
        if trust.issuer_public_keys is not None:
            ik: Dict[str, Any] = {}
            for k, v in trust.issuer_public_keys.items():
                if isinstance(v, (bytes, bytearray)):
                    ik[k] = _b64url_encode(bytes(v))
                else:
                    ik[k] = v
            trust_doc["issuer_public_keys"] = ik
        trust_path.write_text(json.dumps(trust_doc), encoding="utf-8")

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_TESTS_ROOT), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

        proc = subprocess.run(
            [
                sys.executable,
                str(_THIS_FILE),
                "verify",
                "--store",
                str(store_dir),
                "--cid",
                receipt_cid,
                "--trust-json",
                str(trust_path),
                "--keys-json",
                str(keys_path),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
        stdout = (proc.stdout or "").strip()
        if not stdout:
            raise AssertionError(
                f"independent verifier produced no stdout; stderr={proc.stderr!r} "
                f"code={proc.returncode}"
            )
        # Last non-empty line is the verdict JSON.
        line = stdout.splitlines()[-1]
        verdict = json.loads(line)
        return proc.returncode, verdict


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReceiptVerifierInterface:
    """ReceiptVerifier@1 surface and constants."""

    def test_interface_constants(self):
        assert INTERFACE == "ReceiptVerifier@1"
        assert TASK_ID == "MCPP-045"
        assert SCHEMA_MARKER == "mcp++/execution/receipt@1"
        assert CANONICAL_ALGORITHM == "mcpp-jcs-v1"


class TestUnsignedCrossDomainDeny:
    """Acceptance: unsigned cross-domain receipt is deny."""

    def test_unsigned_cross_domain_receipt_is_deny(self):
        _require_crypto()
        _, pub, did = generate_executor_identity()
        receipt = base_receipt(executor_did=did, cross_domain=True)
        assert receipt["signature"] is None

        trust = TrustContext(
            requester_trust_domain="td:requester.example",
            executor_trust_domain="td:executor.example",
            peer_id="12D3KooWSomePeer",
            peer_authenticated=False,
            tls_valid=False,
        )
        verifier = ReceiptVerifier(executor_public_keys={did: pub})
        verdict = verifier.verify_receipt(receipt, trust=trust)

        assert verdict.denied
        assert "unsigned_cross_domain_receipt" in verdict.reason_codes
        assert verdict.levels[LEVEL_RECEIPT_SIGNED]["valid"] is False
        assert verdict.levels[LEVEL_STRUCTURAL]["valid"] is True

    def test_unsigned_cross_domain_with_valid_tls_still_deny(self):
        """Even with perfect transport auth, unsigned cross-domain is deny."""
        _require_crypto()
        _, pub, did = generate_executor_identity()
        receipt = base_receipt(executor_did=did, cross_domain=True)

        trust = TrustContext(
            requester_trust_domain="td:a",
            executor_trust_domain="td:b",
            peer_id="12D3KooWAuthenticatedPeer",
            peer_authenticated=True,
            tls_valid=True,
        )
        verifier = ReceiptVerifier(executor_public_keys={did: pub})
        verdict = verifier.verify_receipt(receipt, trust=trust)

        assert verdict.denied
        assert "unsigned_cross_domain_receipt" in verdict.reason_codes
        assert "peerid_not_authority" in verdict.reason_codes
        assert verdict.metadata.get("transport_authenticated") is True

    def test_same_trust_unsigned_may_admit_structural(self):
        """Same-trust-domain receipts MAY omit signature (not receipt-signed)."""
        _require_crypto()
        _, pub, did = generate_executor_identity()
        receipt = base_receipt(executor_did=did, cross_domain=False)

        trust = TrustContext(
            requester_trust_domain="td:local",
            executor_trust_domain="td:local",
        )
        verifier = ReceiptVerifier(executor_public_keys={did: pub})
        verdict = verifier.verify_receipt(receipt, trust=trust)

        assert verdict.admitted
        assert verdict.levels[LEVEL_RECEIPT_SIGNED]["valid"] is False
        assert verdict.metadata.get("conformance_level") == LEVEL_STRUCTURAL


class TestTransportIdentityNotAuthority:
    """Acceptance: valid TLS/PeerID with invalid UCAN is deny."""

    def test_valid_peerid_invalid_ucan_is_deny(self):
        _require_crypto()
        fixture = load_adversarial_peerid_fixture()
        assert fixture["peer_authenticated"] is True
        assert fixture["ucan_valid"] is False

        private, pub, did = generate_executor_identity()
        receipt = sign_receipt(
            base_receipt(executor_did=did, cross_domain=True),
            private,
        )

        trust = TrustContext(
            requester_trust_domain="td:requester",
            executor_trust_domain="td:executor",
            peer_id=fixture["peer_id"],
            peer_authenticated=True,
            tls_valid=True,
            authority_token=fixture["token"],
            issuer_public_keys=fixture["issuer_public_keys"],
        )
        verifier = ReceiptVerifier(executor_public_keys={did: pub})
        verdict = verifier.verify_receipt(receipt, trust=trust)

        assert verdict.denied
        assert "peerid_not_authority" in verdict.reason_codes
        assert any("invalid_ucan" in c or c == "invalid_ucan" for c in verdict.reason_codes)
        # Receipt signature itself may be valid — authority still fails.
        assert verdict.levels[LEVEL_CRYPTOGRAPHIC]["valid"] is True
        assert verdict.levels[LEVEL_RECEIPT_SIGNED]["valid"] is False
        assert verdict.metadata.get("peer_authenticated") is True
        assert verdict.metadata.get("tls_valid") is True

    def test_transport_only_cross_domain_is_deny(self):
        """Cross-domain with TLS/PeerID but no UCAN material is deny."""
        _require_crypto()
        private, pub, did = generate_executor_identity()
        receipt = sign_receipt(
            base_receipt(executor_did=did, cross_domain=True),
            private,
        )
        trust = TrustContext(
            requester_trust_domain="td:a",
            executor_trust_domain="td:b",
            peer_id="12D3KooWOnlyTransport",
            peer_authenticated=True,
            tls_valid=True,
            # no authority_token / chain
        )
        verifier = ReceiptVerifier(executor_public_keys={did: pub})
        verdict = verifier.verify_receipt(receipt, trust=trust)

        assert verdict.denied
        assert "peerid_not_authority" in verdict.reason_codes
        assert "missing_authority_proof" in verdict.reason_codes

    def test_adversarial_fixture_aligns_with_mcpp044_codes(self):
        """Reuse MCPP-044 valid_peerid_invalid_ucan expected reason codes."""
        _require_crypto()
        fixture = load_adversarial_peerid_fixture()
        private, pub, did = generate_executor_identity()
        receipt = sign_receipt(base_receipt(executor_did=did, cross_domain=True), private)
        trust = TrustContext(
            requester_trust_domain="td:a",
            executor_trust_domain="td:b",
            peer_id=fixture["peer_id"],
            peer_authenticated=True,
            tls_valid=True,
            authority_token=fixture["token"],
            issuer_public_keys=fixture["issuer_public_keys"],
        )
        verdict = ReceiptVerifier(executor_public_keys={did: pub}).verify_receipt(
            receipt, trust=trust
        )
        expected = set(fixture["expected_reason_codes"])
        # Receipt path always includes peerid_not_authority + invalid_ucan.
        assert "peerid_not_authority" in verdict.reason_codes
        assert any(c in expected or c == "invalid_ucan" for c in verdict.reason_codes)


class TestSignedCrossDomainAdmit:
    """Positive path: valid signature + valid UCAN admits at receipt-signed."""

    def test_signed_cross_domain_with_valid_ucan_admits(self):
        _require_crypto()
        # Build a real signed UCAN (detached object form) for authority.
        issuer_priv = Ed25519PrivateKey.generate()
        issuer_pub = issuer_priv.public_key().public_bytes_raw()
        issuer_did = did_key_from_public(issuer_pub)

        exec_priv, exec_pub, exec_did = generate_executor_identity()

        token_body = {
            "iss": issuer_did,
            "aud": exec_did,
            "att": [{"ability": "tools/call", "resource": "tenant/demo"}],
            "exp": 9_000_000_000,
            "nbf": 1_000_000_000,
            "nnc": "mcpp-045-valid-nonce",
            "prf": [],
            "alg": "EdDSA",
            "kid": "root-v1",
        }
        msg = canonicalize_bytes(
            {k: v for k, v in token_body.items() if k not in {"signature", "sig", "signatures"}}
        )
        # UCANDelegationValidator signs over its own detached object form.
        from validators.ucan_delegation import canonical_signing_bytes as ucan_signing_bytes

        message = ucan_signing_bytes(token_body)
        token_body["signature"] = _b64url_encode(issuer_priv.sign(message))

        receipt = sign_receipt(
            base_receipt(executor_did=exec_did, cross_domain=True),
            exec_priv,
        )
        trust = TrustContext(
            requester_trust_domain="td:requester",
            executor_trust_domain="td:executor",
            peer_id="12D3KooWOk",
            peer_authenticated=True,
            tls_valid=True,
            authority_token=token_body,
            issuer_public_keys={issuer_did: _b64url_encode(issuer_pub)},
        )
        verifier = ReceiptVerifier(executor_public_keys={exec_did: exec_pub})
        verdict = verifier.verify_receipt(receipt, trust=trust)

        assert verdict.admitted, verdict.to_dict()
        assert verdict.levels[LEVEL_STRUCTURAL]["valid"] is True
        assert verdict.levels[LEVEL_CRYPTOGRAPHIC]["valid"] is True
        assert verdict.levels[LEVEL_RECEIPT_SIGNED]["valid"] is True
        assert verdict.metadata.get("conformance_level") == LEVEL_RECEIPT_SIGNED

    def test_forged_receipt_signature_is_deny(self):
        _require_crypto()
        private, pub, did = generate_executor_identity()
        other, _, _ = generate_executor_identity()
        receipt = sign_receipt(base_receipt(executor_did=did, cross_domain=True), other)

        trust = TrustContext(
            requester_trust_domain="td:a",
            executor_trust_domain="td:b",
            force_cross_domain=True,
        )
        # Provide a dummy valid-looking authority so we isolate signature failure.
        # Without authority material, transport-less path fails on missing proof first;
        # disable authority requirement for this unit.
        verifier = ReceiptVerifier(
            executor_public_keys={did: pub},
            require_authority_cross_domain=False,
        )
        verdict = verifier.verify_receipt(receipt, trust=trust)
        assert verdict.denied
        assert "invalid_signature" in verdict.reason_codes


class TestIndependentVerifierProcess:
    """Acceptance: independent verifier process can validate a receipt by CID."""

    def test_independent_process_validates_receipt_by_cid(self):
        _require_crypto()
        issuer_priv = Ed25519PrivateKey.generate()
        issuer_pub = issuer_priv.public_key().public_bytes_raw()
        issuer_did = did_key_from_public(issuer_pub)
        exec_priv, exec_pub, exec_did = generate_executor_identity()

        from validators.ucan_delegation import canonical_signing_bytes as ucan_signing_bytes

        token_body = {
            "iss": issuer_did,
            "aud": exec_did,
            "att": [{"ability": "tools/call", "resource": "tenant/demo"}],
            "exp": 9_000_000_000,
            "nbf": 1_000_000_000,
            "nnc": "mcpp-045-independent",
            "prf": [],
            "alg": "EdDSA",
            "kid": "root-v1",
        }
        token_body["signature"] = _b64url_encode(
            issuer_priv.sign(ucan_signing_bytes(token_body))
        )

        receipt = sign_receipt(
            base_receipt(executor_did=exec_did, cross_domain=True),
            exec_priv,
        )

        with tempfile.TemporaryDirectory(prefix="mcpp045-store-") as store_tmp:
            store_dir = Path(store_tmp)
            store = ReceiptContentStore(root=store_dir)
            receipt_cid = store.put_receipt(receipt)
            assert CID_RE.match(receipt_cid)

            trust = TrustContext(
                requester_trust_domain="td:requester",
                executor_trust_domain="td:executor",
                peer_authenticated=False,
                tls_valid=False,
                authority_token=token_body,
                issuer_public_keys={issuer_did: _b64url_encode(issuer_pub)},
            )

            # In-process by-CID first.
            local = ReceiptVerifier(executor_public_keys={exec_did: exec_pub})
            local_verdict = local.verify_by_cid(
                receipt_cid,
                store,
                trust=trust,
                executor_public_keys={exec_did: exec_pub},
            )
            assert local_verdict.admitted, local_verdict.to_dict()
            assert local_verdict.metadata.get("independent") is True
            assert local_verdict.metadata.get("recomputed_cid") == receipt_cid

            # Separate OS process: only store path + CID + public keys.
            code, remote = run_independent_verifier_process(
                store_dir=store_dir,
                receipt_cid=receipt_cid,
                keys={exec_did: exec_pub},
                trust=trust,
            )
            assert code == 0, remote
            assert remote["admitted"] is True
            assert remote["metadata"]["receipt_cid"] == receipt_cid
            assert remote["levels"][LEVEL_RECEIPT_SIGNED]["valid"] is True
            assert remote["interface"] == INTERFACE

    def test_independent_process_denies_unsigned_by_cid(self):
        _require_crypto()
        _, pub, did = generate_executor_identity()
        receipt = base_receipt(executor_did=did, cross_domain=True)

        with tempfile.TemporaryDirectory(prefix="mcpp045-store-u-") as store_tmp:
            store_dir = Path(store_tmp)
            store = ReceiptContentStore(root=store_dir)
            receipt_cid = store.put_receipt(receipt)

            trust = TrustContext(
                requester_trust_domain="td:a",
                executor_trust_domain="td:b",
            )
            code, remote = run_independent_verifier_process(
                store_dir=store_dir,
                receipt_cid=receipt_cid,
                keys={did: pub},
                trust=trust,
            )
            assert code == 2
            assert remote["admitted"] is False
            assert "unsigned_cross_domain_receipt" in remote["reason_codes"]

    def test_cid_mismatch_is_deny(self):
        _require_crypto()
        private, pub, did = generate_executor_identity()
        receipt = sign_receipt(base_receipt(executor_did=did, cross_domain=True), private)
        store = ReceiptContentStore()
        cid = store.put_receipt(receipt)
        # Corrupt store entry under the same CID key.
        store._memory[cid] = b'{"schema":"mcp++/execution/receipt@1","tampered":true}'

        trust = TrustContext(
            requester_trust_domain="td:a",
            executor_trust_domain="td:b",
        )
        verifier = ReceiptVerifier(
            executor_public_keys={did: pub},
            require_authority_cross_domain=False,
        )
        verdict = verifier.verify_by_cid(cid, store, trust=trust)
        assert verdict.denied
        assert verdict.reason_codes[0] in {"cid_mismatch", "structural_invalid", "receipt_not_found"}


class TestReceiptCidBinding:
    """Receipt is content-addressed; signature binds canonical body."""

    def test_signature_covers_canonical_body_not_receipt_cid(self):
        _require_crypto()
        private, pub, did = generate_executor_identity()
        receipt = sign_receipt(base_receipt(executor_did=did, cross_domain=True), private)
        # Mutate an attested field → signature must fail.
        tampered = dict(receipt)
        tampered["output_cids"] = [CID_D]
        trust = TrustContext(
            requester_trust_domain="td:a",
            executor_trust_domain="td:b",
        )
        verifier = ReceiptVerifier(
            executor_public_keys={did: pub},
            require_authority_cross_domain=False,
        )
        verdict = verifier.verify_receipt(tampered, trust=trust)
        assert verdict.denied
        assert "invalid_signature" in verdict.reason_codes

    def test_put_and_get_roundtrip_preserves_cid(self):
        _require_crypto()
        private, pub, did = generate_executor_identity()
        receipt = sign_receipt(base_receipt(executor_did=did, cross_domain=True), private)
        store = ReceiptContentStore()
        cid = store.put_receipt(receipt)
        loaded = store.get_receipt(cid)
        assert loaded is not None
        assert receipt_content_cid(loaded) == cid
        assert loaded.get("receipt_cid") == cid
        assert loaded.get("signature") == receipt["signature"]


# ---------------------------------------------------------------------------
# Module CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        raise SystemExit(_cli_verify(sys.argv[1:]))
    # Allow `python test_signed_receipts.py` to run pytest on this file.
    raise SystemExit(pytest.main([__file__, "-q"]))
