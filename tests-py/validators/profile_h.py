"""Profile H 1.0 canonical DAG-JSON and x402 v2 codecs.

The module deliberately has no wallet or network dependencies.  It validates
the immutable/public representation used for CIDs and the decoded x402 objects
used at HTTP and Profile E boundaries.  Cryptographic signature verification
belongs to the seller runtime; this codec only enforces the wire encoding and
all pre-crypto bounds.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

MAX_SAFE = 9_007_199_254_740_991
DEFAULT_LIMITS = {
    "max_artifact_bytes": 1_048_576,
    "max_x402_bytes": 32_768,
    "max_requirements": 8,
    "max_depth": 16,
    "max_string_bytes": 8_192,
    "max_parents": 32,
    "max_quote_lifetime_ms": 300_000,
}
HARD_LIMITS = {
    "max_artifact_bytes": 16_777_216,
    "max_x402_bytes": 262_144,
    "max_requirements": 32,
    "max_depth": 32,
    "max_string_bytes": 65_536,
    "max_parents": 256,
    "max_quote_lifetime_ms": 3_600_000,
}

SCHEMAS = {
    "PaidCapability": "paid-capability",
    "PaymentQuote": "payment-quote",
    "PaymentAuthorization": "payment-authorization",
    "PaymentVerification": "payment-verification",
    "SettlementReceipt": "settlement-receipt",
    "PaidEntitlement": "paid-entitlement",
    "UsageRecord": "usage-record",
    "RefundRecord": "refund-record",
    "AccessReceipt": "access-receipt",
}
FIELDS = {
    "PaidCapability": "serverDid descriptorCid interfaceCid operationKind operationName httpMethod httpRoute catalogVersion ability policyCid termsCid scheme network asset amount payee validFrom expiresAt settlementTiming sellerDid signatureAlg signature",
    "PaymentQuote": "capabilityCid catalogCid descriptorCid requestCid requirements nonce expiresAt idempotencyKey sellerDid signatureAlg signature",
    "PaymentAuthorization": "quoteCid requestCid requirementIndex paymentPayloadCid payerCommitment signedPayloadCommitment signatureCommitment",
    "PaymentVerification": "authorizationCid verifierDid decision reasonCode verifiedAt expiresAt evidenceCid",
    "SettlementReceipt": "verificationCid outcome amount network networkReferenceCommitment disclosurePolicy paymentResponseCid settledAt",
    "PaidEntitlement": "settlementCid subjectCommitment capabilityCid quotaUnits consumedUnits unit expiresAt",
    "UsageRecord": "entitlementCid unit inputCid outputCid units recordedAt",
    "RefundRecord": "settlementCid requestCid decision outcome evidenceCid requestedAt decidedAt",
    "AccessReceipt": "operationName requestCid ucanDecisionCid policyDecisionCid leaseDecisionCid commercialEvidenceCid decision resultCid reasonCode decidedAt",
}
FIELDS = {key: value.split() for key, value in FIELDS.items()}
COMMON_FIELDS = ("schema", "createdAt", "parents", "correlationId")
FORBIDDEN_KEYS = {
    "privatekey", "seedphrase", "mnemonic", "authenticationcookie",
    "fullucan", "requestarguments", "paymentsignature", "paymentpayload",
    "facilitatorresponse", "walletaddress", "transactionhash", "rawsignature",
}
CID_RE = re.compile(r"b[a-z2-7]+")
CAIP2_RE = re.compile(r"[a-z0-9-]{3,8}:[A-Za-z0-9_-]{1,32}")
AMOUNT_RE = re.compile(r"(?:0|[1-9][0-9]{0,77})")
DID_RE = re.compile(r"did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?")


@dataclass
class ProfileHValidationError(ValueError):
    code: str
    path: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code} at {self.path or '/'}: {self.detail}"


def _fail(path: str, detail: str, code: str = "H_INVALID_PAYMENT_MESSAGE") -> None:
    raise ProfileHValidationError(code, path, detail)


def _object(value: Any, path: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _string(value: Any, path: str, limit: int = 8_192, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value) or "\x00" in value or len(value.encode("utf-8")) > limit:
        _fail(path, "invalid string")
    return value


def _integer(value: Any, path: str, low: int = 0, high: int = MAX_SAFE) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        _fail(path, f"must be an integer in [{low}, {high}]")
    return value


def _enum(value: Any, path: str, choices: tuple[str, ...]) -> str:
    result = _string(value, path)
    if result not in choices:
        _fail(path, "unsupported value")
    return result


def _limits(overrides: Mapping[str, int] | None) -> dict[str, int]:
    result = dict(DEFAULT_LIMITS)
    if overrides:
        unknown = set(overrides) - set(result)
        if unknown:
            _fail("/limits", f"unknown limit {sorted(unknown)[0]}")
        for key, value in overrides.items():
            _integer(value, f"/limits/{key}", 1, HARD_LIMITS[key])
            result[key] = value
    return result


def _walk_json(value: Any, limits: Mapping[str, int], path: str = "", depth: int = 0) -> None:
    if depth > limits["max_depth"]:
        _fail(path, "JSON nesting exceeds negotiated bound", "H_LIMIT_EXCEEDED")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        _integer(value, path, -MAX_SAFE, MAX_SAFE)
        return
    if isinstance(value, float):
        _fail(path, "floats are not canonical DAG-JSON")
    if isinstance(value, str):
        if len(value.encode("utf-8")) > limits["max_string_bytes"] or "\x00" in value:
            _fail(path, "string exceeds negotiated bound", "H_LIMIT_EXCEEDED")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_json(item, limits, f"{path}/{index}", depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(path, "object key must be a string")
            _walk_json(item, limits, f"{path}/{key}", depth + 1)
        return
    _fail(path, "not a JSON value")


def canonical_profile_h_bytes(value: Any, limits: Mapping[str, int] | None = None) -> bytes:
    negotiated = _limits(limits)
    _walk_json(value, negotiated)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def profile_h_artifact_cid(value: Any, limits: Mapping[str, int] | None = None) -> str:
    digest = hashlib.sha256(canonical_profile_h_bytes(value, limits)).digest()
    # CIDv1 + dag-json (0x0129) + sha2-256 multihash.
    raw = b"\x01\xa9\x02\x12\x20" + digest
    return "b" + base64.b32encode(raw).decode("ascii").lower().rstrip("=")


def _read_varint(raw: bytes, offset: int) -> tuple[int, int]:
    value = shift = 0
    while offset < len(raw) and shift < 56:
        byte = raw[offset]
        offset += 1
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    _fail("", "invalid CID")


def _cid(value: Any, path: str) -> None:
    text = _string(value, path, 128)
    if not CID_RE.fullmatch(text):
        _fail(path, "CID must be lowercase base32 CIDv1")
    try:
        raw = base64.b32decode(text[1:].upper() + "=" * ((8 - len(text[1:]) % 8) % 8))
    except (binascii.Error, ValueError):
        _fail(path, "invalid CID")
    version, cursor = _read_varint(raw, 0)
    codec, cursor = _read_varint(raw, cursor)
    multihash, cursor = _read_varint(raw, cursor)
    length, cursor = _read_varint(raw, cursor)
    if (version, codec, multihash, length) != (1, 0x129, 0x12, 32) or cursor + length != len(raw):
        _fail(path, "CID must be CIDv1 dag-json sha2-256")


def _did(value: Any, path: str) -> None:
    if not DID_RE.fullmatch(_string(value, path, 512)):
        _fail(path, "invalid DID")


def _amount(value: Any, path: str) -> None:
    if not isinstance(value, str) or not AMOUNT_RE.fullmatch(value):
        _fail(path, "amount must be a canonical non-negative atomic decimal", "H_AMOUNT_MISMATCH")


def _network(value: Any, path: str) -> None:
    if not CAIP2_RE.fullmatch(_string(value, path, 64)):
        _fail(path, "network must be a canonical CAIP-2 identifier", "H_UNSUPPORTED_NETWORK")


def _signature(value: Any, path: str) -> None:
    text = _string(value, path, 128)
    if "=" in text or not re.fullmatch(r"[A-Za-z0-9_-]{86}", text):
        _fail(path, "signature must be unpadded base64url Ed25519 bytes", "H_VERIFICATION_FAILED")
    try:
        if len(base64.urlsafe_b64decode(text + "==")) != 64:
            raise ValueError
    except (binascii.Error, ValueError):
        _fail(path, "invalid signature encoding", "H_VERIFICATION_FAILED")


def _redaction_scan(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized in FORBIDDEN_KEYS:
                _fail(f"{path}/{key}", "sensitive field is forbidden in a Profile H artifact", "H_INVALID_PAYMENT_MESSAGE")
            _redaction_scan(item, f"{path}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _redaction_scan(item, f"{path}/{index}")


def validate_profile_h_artifact(kind: str, value: Any, limits: Mapping[str, int] | None = None, *, now_ms: int | None = None) -> str:
    negotiated = _limits(limits)
    if kind not in SCHEMAS:
        _fail("/kind", "unknown Profile H artifact kind")
    obj = _object(value)
    allowed = set(COMMON_FIELDS + tuple(FIELDS[kind]))
    for key in obj:
        if key not in allowed:
            _fail(f"/{key}", "unknown field")
    for key in allowed:
        if key not in obj:
            _fail(f"/{key}", "required field missing")
    if obj["schema"] != f"mcp++/profile-h/{SCHEMAS[kind]}@1.0":
        _fail("/schema", "wrong schema marker")
    _integer(obj["createdAt"], "/createdAt")
    parents = obj["parents"]
    if not isinstance(parents, list) or len(parents) > negotiated["max_parents"]:
        _fail("/parents", "parent count exceeds negotiated bound", "H_LIMIT_EXCEEDED")
    for index, parent in enumerate(parents):
        _cid(parent, f"/parents/{index}")
        if index and parents[index - 1].encode() >= parent.encode():
            _fail(f"/parents/{index}", "parents must be UTF-8 sorted and unique")
    _string(obj["correlationId"], "/correlationId", 128)
    _redaction_scan(obj)
    _validate_artifact_specific(kind, obj, negotiated, now_ms)
    if len(canonical_profile_h_bytes(obj, negotiated)) > negotiated["max_artifact_bytes"]:
        _fail("", "artifact exceeds negotiated bound", "H_LIMIT_EXCEEDED")
    return profile_h_artifact_cid(obj, negotiated)


def _validate_artifact_specific(kind: str, obj: dict[str, Any], limits: Mapping[str, int], now_ms: int | None) -> None:
    c = lambda name: _cid(obj[name], f"/{name}")
    s = lambda name, size=8_192: _string(obj[name], f"/{name}", size)
    i = lambda name, low=0, high=MAX_SAFE: _integer(obj[name], f"/{name}", low, high)
    if kind == "PaidCapability":
        _did(obj["serverDid"], "/serverDid"); c("descriptorCid"); c("interfaceCid")
        _enum(obj["operationKind"], "/operationKind", ("tool", "resource", "prompt", "http")); s("operationName", 256)
        if obj["httpMethod"] is not None: _enum(obj["httpMethod"], "/httpMethod", ("GET", "POST", "PUT", "PATCH", "DELETE"))
        if obj["httpRoute"] is not None: s("httpRoute", 512)
        s("catalogVersion", 64); s("ability", 256); c("policyCid"); c("termsCid"); s("scheme", 64); _network(obj["network"], "/network")
        s("asset", 256); _amount(obj["amount"], "/amount"); s("payee", 256); i("validFrom"); i("expiresAt")
        if obj["expiresAt"] <= obj["validFrom"]: _fail("/expiresAt", "expiry must follow validity start", "H_QUOTE_EXPIRED")
        _enum(obj["settlementTiming"], "/settlementTiming", ("immediate", "metered", "batched")); _did(obj["sellerDid"], "/sellerDid"); _enum(obj["signatureAlg"], "/signatureAlg", ("Ed25519",)); _signature(obj["signature"], "/signature")
    elif kind == "PaymentQuote":
        for name in ("capabilityCid", "catalogCid", "descriptorCid", "requestCid"): c(name)
        requirements = obj["requirements"]
        if not isinstance(requirements, list) or not 1 <= len(requirements) <= limits["max_requirements"]:
            _fail("/requirements", "requirements count exceeds negotiated bound", "H_LIMIT_EXCEEDED")
        for index, requirement in enumerate(requirements): _validate_requirement(requirement, f"/requirements/{index}")
        s("nonce", 128); i("expiresAt"); s("idempotencyKey", 128); _did(obj["sellerDid"], "/sellerDid"); _enum(obj["signatureAlg"], "/signatureAlg", ("Ed25519",)); _signature(obj["signature"], "/signature")
        if obj["expiresAt"] <= obj["createdAt"] or obj["expiresAt"] - obj["createdAt"] > limits["max_quote_lifetime_ms"] or (now_ms is not None and now_ms >= obj["expiresAt"]):
            _fail("/expiresAt", "quote is expired or exceeds negotiated lifetime", "H_QUOTE_EXPIRED")
    elif kind == "PaymentAuthorization":
        c("quoteCid"); c("requestCid"); i("requirementIndex", 0, limits["max_requirements"] - 1)
        for name in ("paymentPayloadCid", "payerCommitment", "signedPayloadCommitment", "signatureCommitment"): c(name)
    elif kind == "PaymentVerification":
        c("authorizationCid"); _did(obj["verifierDid"], "/verifierDid"); _enum(obj["decision"], "/decision", ("verified", "rejected")); s("reasonCode", 128); i("verifiedAt"); i("expiresAt"); c("evidenceCid")
        if obj["expiresAt"] <= obj["verifiedAt"] or (now_ms is not None and now_ms >= obj["expiresAt"]): _fail("/expiresAt", "verification freshness expired", "H_VERIFICATION_FAILED")
    elif kind == "SettlementReceipt":
        c("verificationCid"); _enum(obj["outcome"], "/outcome", ("settled", "failed", "pending", "reconciliation-required", "refunded")); _amount(obj["amount"], "/amount"); _network(obj["network"], "/network"); c("networkReferenceCommitment"); _enum(obj["disclosurePolicy"], "/disclosurePolicy", ("commitment-only", "authorized", "public")); c("paymentResponseCid"); i("settledAt")
    elif kind == "PaidEntitlement":
        c("settlementCid"); c("subjectCommitment"); c("capabilityCid"); i("quotaUnits"); i("consumedUnits"); s("unit", 128); i("expiresAt")
        if obj["consumedUnits"] > obj["quotaUnits"]: _fail("/consumedUnits", "entitlement quota exhausted", "H_ENTITLEMENT_EXHAUSTED")
        if now_ms is not None and now_ms >= obj["expiresAt"]: _fail("/expiresAt", "entitlement expired", "H_ENTITLEMENT_EXHAUSTED")
    elif kind == "UsageRecord":
        c("entitlementCid"); s("unit", 128); c("inputCid"); c("outputCid"); i("units", 1); i("recordedAt")
    elif kind == "RefundRecord":
        c("settlementCid"); c("requestCid"); _enum(obj["decision"], "/decision", ("requested", "approved", "denied")); _enum(obj["outcome"], "/outcome", ("pending", "refunded", "failed", "not-applicable")); c("evidenceCid"); i("requestedAt"); i("decidedAt")
        if obj["decidedAt"] < obj["requestedAt"]: _fail("/decidedAt", "decision precedes request")
    else:
        s("operationName", 256); c("requestCid")
        for name in ("ucanDecisionCid", "policyDecisionCid", "leaseDecisionCid", "commercialEvidenceCid"): 
            if obj[name] is not None: c(name)
        _enum(obj["decision"], "/decision", ("allow", "deny"))
        if obj["resultCid"] is not None: c("resultCid")
        s("reasonCode", 128); i("decidedAt")
        if obj["decision"] == "allow" and (obj["commercialEvidenceCid"] is None or obj["resultCid"] is None): _fail("/commercialEvidenceCid", "allow requires commercial evidence and result")


def _validate_requirement(value: Any, path: str) -> None:
    obj = _object(value, path)
    required = {"scheme", "network", "asset", "amount", "payTo", "maxTimeoutSeconds", "extra"}
    if set(obj) != required:
        _fail(path, "invalid x402 requirement fields")
    _string(obj["scheme"], path + "/scheme", 64); _network(obj["network"], path + "/network"); _string(obj["asset"], path + "/asset", 256); _amount(obj["amount"], path + "/amount"); _string(obj["payTo"], path + "/payTo", 256); _integer(obj["maxTimeoutSeconds"], path + "/maxTimeoutSeconds", 1, 3600); _object(obj["extra"], path + "/extra")


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("/" + key, "duplicate JSON object key")
        result[key] = value
    return result


def decode_x402_header(kind: str, encoded: str, limits: Mapping[str, int] | None = None) -> dict[str, Any]:
    negotiated = _limits(limits)
    if not isinstance(encoded, str) or not encoded or re.search(r"\s", encoded) or len(encoded) > ((negotiated["max_x402_bytes"] + 2) // 3) * 4:
        _fail("/header", "invalid or oversized base64", "H_LIMIT_EXCEEDED" if isinstance(encoded, str) and encoded else "H_INVALID_PAYMENT_MESSAGE")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        _fail("/header", "invalid base64")
    if len(raw) > negotiated["max_x402_bytes"]:
        _fail("/header", "decoded x402 object exceeds negotiated bound", "H_LIMIT_EXCEEDED")
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(text, object_pairs_hook=_no_duplicate_pairs, parse_float=lambda _: _fail("", "floats are forbidden"), parse_constant=lambda _: _fail("", "non-finite number"))
    except UnicodeDecodeError:
        _fail("/header", "invalid UTF-8")
    except json.JSONDecodeError:
        _fail("/header", "invalid JSON")
    _walk_json(value, negotiated)
    obj = _object(value)
    _validate_x402_object(kind, obj, negotiated)
    if canonical_profile_h_bytes(obj, negotiated) != raw:
        _fail("/header", "x402 JSON is not canonically encoded")
    return obj


def encode_x402_header(kind: str, value: Any, limits: Mapping[str, int] | None = None) -> str:
    negotiated = _limits(limits)
    obj = _object(value)
    _validate_x402_object(kind, obj, negotiated)
    raw = canonical_profile_h_bytes(obj, negotiated)
    if len(raw) > negotiated["max_x402_bytes"]:
        _fail("", "decoded x402 object exceeds negotiated bound", "H_LIMIT_EXCEEDED")
    return base64.b64encode(raw).decode("ascii")


def _validate_x402_object(kind: str, obj: dict[str, Any], limits: Mapping[str, int]) -> None:
    if kind == "PaymentRequired":
        allowed, required = {"x402Version", "error", "resource", "accepts", "extensions"}, {"x402Version", "accepts"}
    elif kind == "PaymentPayload":
        allowed, required = {"x402Version", "resource", "accepted", "payload", "extensions"}, {"x402Version", "accepted", "payload"}
    elif kind == "SettlementResponse":
        allowed, required = {"success", "errorReason", "transaction", "network", "payer", "extensions"}, {"success", "network"}
    else:
        _fail("/kind", "unknown x402 object kind")
    if not required <= set(obj) or set(obj) - allowed:
        _fail("", "invalid x402 object fields")
    if kind != "SettlementResponse":
        if obj["x402Version"] != 2:
            _fail("/x402Version", "only x402 v2 is supported", "H_UNSUPPORTED_X402_VERSION")
    if kind == "PaymentRequired":
        accepts = obj["accepts"]
        if not isinstance(accepts, list) or not 1 <= len(accepts) <= limits["max_requirements"]:
            _fail("/accepts", "requirements count exceeds negotiated bound", "H_LIMIT_EXCEEDED")
        for index, requirement in enumerate(accepts): _validate_requirement(requirement, f"/accepts/{index}")
    elif kind == "PaymentPayload":
        _validate_requirement(obj["accepted"], "/accepted"); _object(obj["payload"], "/payload")
    else:
        if not isinstance(obj["success"], bool): _fail("/success", "must be boolean")
        _network(obj["network"], "/network")
        if obj.get("transaction") is not None: _string(obj["transaction"], "/transaction", 512)


def validate_request_binding(expected_request_cid: str, artifact: Mapping[str, Any]) -> None:
    _cid(expected_request_cid, "/expectedRequestCid")
    if artifact.get("requestCid") != expected_request_cid:
        _fail("/requestCid", "payment is bound to a different request", "H_REQUEST_MISMATCH")


def validate_replay(seen_commitments: set[str], commitment: str) -> None:
    _cid(commitment, "/commitment")
    if commitment in seen_commitments:
        _fail("/commitment", "payment authorization was already consumed", "H_PAYMENT_REPLAY")


__all__ = [
    "DEFAULT_LIMITS", "HARD_LIMITS", "ProfileHValidationError",
    "canonical_profile_h_bytes", "profile_h_artifact_cid",
    "validate_profile_h_artifact", "decode_x402_header", "encode_x402_header",
    "validate_request_binding", "validate_replay",
]
