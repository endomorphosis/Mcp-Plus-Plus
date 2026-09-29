"""Redact secrets in a JSON body before it leaves the process."""

import base64
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

# Normalized key names. ``token`` stays unanchored so ``access_token`` matches.
_SENSITIVE_KEY = re.compile(
    r"(x_payment_response|x_payment|payment_context_payload|payment_signature|"
    r"payment_required|payment_response|private_key|api_key|secret|password|"
    r"passwd|token|credential|authorization|cookie|seed|mnemonic)"
)
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SIGNATURE_KEY = re.compile(r"(?i)^(signatures?|sigs?)$")
# CIDv1 base32 is exactly 59 characters. A longer blob is not an address.
_CID = re.compile(r"^(?:Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")
_PEM = re.compile(
    r"-----BEGIN [A-Z0-9][A-Z0-9 ]{0,60}-----"
    r".*?"
    r"-----END [A-Z0-9][A-Z0-9 ]{0,60}-----",
    re.DOTALL,
)
# Inline v1 X-PAYMENT blobs are not object keys, so the key check does not see them.
_PAYMENT = re.compile(
    r"(?i)\b(?:PAYMENT-SIGNATURE|PAYMENT-REQUIRED|PAYMENT-RESPONSE|"
    r"X-PAYMENT(?:-RESPONSE)?)\s*[:=]\s*[A-Za-z0-9+/=_-]{8,}"
)
# A colon or equals binds the phrase even with no space.
# A bare run fails inside the pattern when a word is short or a function word,
# so the search can resume at a later label instead of consuming the span.
_SEED_CONTENT_WORD = (
    r"(?!(?i:the|that|this|with|from|have|were|been)\b)[A-Za-z]{3,}"
)
_SEED_PHRASE = re.compile(
    r"(?i:\b(?:wallet\s+seed|seed(?:\s+phrase)?|mnemonic)\b)"
    r"(?:"
    r"\s*[:=]\s*[A-Za-z]+(?:\s+[A-Za-z]+){11,23}"
    r"|\s+"
    + _SEED_CONTENT_WORD
    + r"(?:\s+"
    + _SEED_CONTENT_WORD
    + r"){11,23}"
    r")"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/=]+")
_SK = re.compile(r"\bsk-[A-Za-z0-9_\-.]{4,}\b")
_SK_CID_TAIL = re.compile(r"\.?(b[a-z2-7]{58})$")
# Header must start like base64url of ``{"``. Short or empty payload and signature are allowed.
_JWT_CANDIDATE = re.compile(r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*")
_UCAN_ARCHIVE = re.compile(r"(?i)\bucan(?::|/)[A-Za-z0-9+/=_.-]{16,}")
# Continuous PAN, 4-4-4-4, or Amex 4-6-5. Not a separator between every digit.
_CARD = re.compile(
    r"(?<!\d)(?<![\d][ -])(?:"
    r"\d{13,19}"
    r"|\d{4}(?:-\d{4}){3}"
    r"|\d{4}(?: \d{4}){3}"
    r"|\d{4}-\d{6}-\d{5}"
    r"|\d{4} \d{6} \d{5}"
    r")(?!\d)(?![ -]\d)"
)
_DETACHED_SIG = re.compile(r"^[A-Za-z0-9+/=_-]{24,}$")
# Below 8 characters, substring replacement of TYPESAFE_API_KEY hits unrelated text.
_MIN_SUBSTRING_SECRET = 8


def _token(secret: str) -> str:
    prefix = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:8]
    return f"[REDACTED:{prefix}]"


def _material(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return type(value).__name__


def _normalize_key(key: str) -> str:
    folded = key.replace("-", "_")
    folded = _CAMEL_BOUNDARY.sub("_", folded)
    return folded.lower().replace(".", "_")


def _sensitive_key(key: str, parent_key: str | None) -> bool:
    normalized = _normalize_key(key)
    if _SENSITIVE_KEY.search(normalized):
        return True
    if parent_key is None:
        return False
    # ``payment_context.payload`` is the payment blob even when the parent is not a secret key.
    return _normalize_key(parent_key) == "payment_context" and normalized == "payload"


def _luhn_ok(digits: str) -> bool:
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = ord(char) - 48
        if index % 2 == 1:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def _redact_card(match: re.Match[str]) -> str:
    text = match.group(0)
    digits = re.sub(r"[ -]", "", text)
    if not _luhn_ok(digits):
        return text
    return _token(text)


def _redact_sk(match: re.Match[str]) -> str:
    span = match.group(0)
    tail = _SK_CID_TAIL.search(span)
    # A trailing CID is an address. Keep it and the dot that introduces it.
    if tail is not None and tail.start() > 0:
        return _token(span[: tail.start()]) + tail.group(0)
    return _token(span)


def _jwt_header_has_alg(segment: str) -> bool:
    padding = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + padding)
        header = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(header, dict) and "alg" in header


def _redact_jwt(match: re.Match[str]) -> str:
    span = match.group(0)
    header = span.split(".", 2)[0]
    if not _jwt_header_has_alg(header):
        return span
    return _token(span)


def _api_key() -> str | None:
    raw = os.environ.get("TYPESAFE_API_KEY")
    if raw is None or raw == "":
        return None
    return raw


def _redact_text(text: str, api_key: str | None) -> str:
    if api_key is not None and text == api_key:
        return _token(text)
    text = _PEM.sub(lambda match: _token(match.group(0)), text)
    text = _PAYMENT.sub(lambda match: _token(match.group(0)), text)
    text = _SEED_PHRASE.sub(lambda match: _token(match.group(0)), text)
    text = _BEARER.sub(lambda match: _token(match.group(0)), text)
    text = _JWT_CANDIDATE.sub(_redact_jwt, text)
    text = _UCAN_ARCHIVE.sub(lambda match: _token(match.group(0)), text)
    text = _SK.sub(_redact_sk, text)
    text = _CARD.sub(_redact_card, text)
    # Shaped tokens are already gone. This catches a key that matches none of them.
    if api_key is not None and len(api_key) >= _MIN_SUBSTRING_SECRET and api_key in text:
        text = text.replace(api_key, _token(api_key))
    return text


def _redact_string(text: str, parent_key: str | None, api_key: str | None) -> str:
    # CID strings are addresses, not UCAN signature material.
    if parent_key is not None and _SIGNATURE_KEY.fullmatch(parent_key):
        if _CID.fullmatch(text):
            return text
        if _DETACHED_SIG.fullmatch(text):
            return _token(text)
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return _redact_text(text, api_key)
        if isinstance(parsed, (dict, list)):
            return json.dumps(
                _walk(parsed, parent_key, api_key),
                separators=(",", ":"),
                ensure_ascii=False,
            )
    return _redact_text(text, api_key)


def _walk(value: Any, parent_key: str | None, api_key: str | None) -> Any:
    if isinstance(value, str):
        return _redact_string(value, parent_key, api_key)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                redacted[key] = _walk(item, None, api_key)
                continue
            # Sensitivity uses the original key. The stored key is still span-scanned.
            if _sensitive_key(key, parent_key):
                stored: Any = None if item is None else _token(_material(item))
            else:
                stored = _walk(item, key, api_key)
            redacted[_redact_text(key, api_key)] = stored
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        walked = [_walk(item, parent_key, api_key) for item in value]
        if isinstance(value, tuple):
            return tuple(walked)
        return walked
    raise TypeError(f"unsupported body value: {type(value).__name__}")


def redact_serialized(body: Any) -> Any:
    """Return a copy of ``body`` with secrets replaced.

    A string that is a JSON object or array is parsed, walked, and
    re-serialized. Every other string is scanned in place, including
    nested instructions, criteria, and object keys.
    """
    api_key = _api_key()
    if isinstance(body, str):
        return _redact_string(body, None, api_key)
    return _walk(body, None, api_key)
