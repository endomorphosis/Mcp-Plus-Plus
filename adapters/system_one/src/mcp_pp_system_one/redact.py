"""Redact secrets in a JSON body before it leaves the process."""

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

_SENSITIVE_KEY = re.compile(
    r"(?i)(secret|password|passwd|token|credential|authorization|cookie|"
    r"private_key|seed|mnemonic|api_key|payment_signature)"
)
_SIGNATURE_KEY = re.compile(r"(?i)^(signatures?|sigs?)$")
_CID = re.compile(r"^(?:Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$")
_PEM = re.compile(
    r"-----BEGIN [A-Z0-9][A-Z0-9 ]{0,60}-----"
    r".*?"
    r"-----END [A-Z0-9][A-Z0-9 ]{0,60}-----",
    re.DOTALL,
)
_PAYMENT = re.compile(
    r"(?i)\b(?:PAYMENT-SIGNATURE|PAYMENT-REQUIRED|PAYMENT-RESPONSE|"
    r"X-PAYMENT(?:-RESPONSE)?)\s*[:=]\s*[A-Za-z0-9+/=_-]{8,}"
)
_SEED_PHRASE = re.compile(
    r"(?i)\b(?:seed(?:\s+phrase)?|mnemonic|wallet\s+seed)\s*[:=]\s*"
    r"(?:[a-z]+(?:\s+[a-z]+){11,23})"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/=]+")
_SK = re.compile(r"\bsk-[A-Za-z0-9_\-]{4,}\b")
_JWT = re.compile(r"\b[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]{8,}){2}\b")
_UCAN_ARCHIVE = re.compile(r"(?i)\bucan(?::|/)[A-Za-z0-9+/=_.-]{16,}")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_DETACHED_SIG = re.compile(r"^[A-Za-z0-9+/=_-]{24,}$")
# A one- or two-character TYPESAFE_API_KEY would be stripped out of unrelated words.
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


def _sensitive_key(key: str) -> bool:
    folded = key.replace("-", "_")
    return _SENSITIVE_KEY.search(key) is not None or _SENSITIVE_KEY.search(folded) is not None


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
    text = _JWT.sub(lambda match: _token(match.group(0)), text)
    text = _UCAN_ARCHIVE.sub(lambda match: _token(match.group(0)), text)
    text = _SK.sub(lambda match: _token(match.group(0)), text)
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
    return _redact_text(text, api_key)


def _walk(value: Any, parent_key: str | None, api_key: str | None) -> Any:
    if parent_key is not None and _sensitive_key(parent_key):
        if value is None:
            return None
        return _token(_material(value))
    if isinstance(value, str):
        return _redact_string(value, parent_key, api_key)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            key: _walk(item, key if isinstance(key, str) else None, api_key)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        walked = [_walk(item, parent_key, api_key) for item in value]
        if isinstance(value, tuple):
            return tuple(walked)
        return walked
    raise TypeError(f"unsupported body value: {type(value).__name__}")


def redact_serialized(body: Any) -> Any:
    """Return a copy of ``body`` with secrets replaced.

    A ``str`` that is a JSON object or array is parsed, walked, and
    re-serialized compactly. Every other string is scanned in place,
    including nested instructions and criteria.
    """
    api_key = _api_key()
    if isinstance(body, str):
        stripped = body.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                return _redact_text(body, api_key)
            return json.dumps(
                _walk(parsed, None, api_key),
                separators=(",", ":"),
                ensure_ascii=False,
            )
        return _redact_text(body, api_key)
    return _walk(body, None, api_key)
