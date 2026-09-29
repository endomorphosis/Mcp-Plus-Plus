"""Raw-leaf CIDs for policy documents and decision preimages."""

import base64
import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

# Same bound RFC 8785 uses for integers that fit in an IEEE-754 binary64.
_SAFE_INTEGER = 9007199254740991

POLICY_SCHEMA = "mcp++-adapter/policy-document/v1"
DECISION_SCHEMA = "mcp++-adapter/policy-decision/v1"
COMPILER_VERSION = "qset-2026-09-29"

_CID_VERSION = 0x01
_MULTIHASH_SHA256 = 0x12
_CODEC_RAW = 0x55


def _whole_numbers(value: Any) -> Any:
    """Encode whole-number floats as integers so ``2.0`` and ``2`` share a CID.

    The validator ``mcpp-jcs-v1`` helper is not on this package's import path.
    """
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("NaN and Infinity are not JSON numbers")
        if value == 0.0:
            return 0
        as_int = int(value)
        if as_int == value and abs(as_int) <= _SAFE_INTEGER:
            return as_int
        return value
    if isinstance(value, Mapping):
        return {key: _whole_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_whole_numbers(item) for item in value]
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json_bytes(document: Any) -> bytes:
    """Compact UTF-8 JSON, keys sorted. Whole-number floats encode as integers."""
    return json.dumps(
        _whole_numbers(document),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def cid_raw_leaf(document: Any) -> str:
    """CIDv1 raw leaf: ``0x01 0x55 0x12 0x20`` plus sha256, base32 ``bafkrei…``."""
    digest = hashlib.sha256(canonical_json_bytes(document)).digest()
    raw = bytes((_CID_VERSION, _CODEC_RAW, _MULTIHASH_SHA256, len(digest))) + digest
    encoded = base64.b32encode(raw).decode("ascii").lower().rstrip("=")
    return "b" + encoded


def is_raw_leaf_cid(value: Any) -> bool:
    """True when ``value`` decodes to the same CIDv1 raw-leaf prefix ``cid_raw_leaf`` writes."""
    if not isinstance(value, str) or len(value) != 59 or not value.startswith("b"):
        return False
    body = value[1:].upper()
    if any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for char in body):
        return False
    pad = "=" * ((8 - len(body) % 8) % 8)
    try:
        raw = base64.b32decode(body + pad, casefold=False)
    except ValueError:
        return False
    prefix = bytes((_CID_VERSION, _CODEC_RAW, _MULTIHASH_SHA256, 32))
    return len(raw) == 36 and raw[:4] == prefix


def question_set_hash(questions: Mapping[str, Any]) -> str:
    """Hash the canonical question map, including ``COMPILER_VERSION``."""
    payload = {"compiler_version": COMPILER_VERSION, "questions": questions}
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return "sha256:" + digest


def _json_copy(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    )


def policy_preimage(policy_version: str, clauses: list[Any]) -> dict[str, Any]:
    """Policy document bytes. ``policy_cid`` is not a field of the preimage."""
    return {
        "schema": POLICY_SCHEMA,
        "policy_version": policy_version,
        "clauses": _json_copy(list(clauses)),
    }


def policy_document_cid(preimage: Mapping[str, Any]) -> str:
    if "policy_cid" in preimage:
        raise ValueError("policy preimage must omit policy_cid")
    return cid_raw_leaf(preimage)


def decision_preimage(
    *,
    decision: str,
    allowed: bool,
    obligations: list[Any],
    policy_cid: str,
    policy_version: str,
    intent_cid: str | None,
    proofs_checked: list[Any],
    gate: str,
    now: str,
    thresholds: Mapping[str, Any],
    clauses: list[Any],
    input_cid: str | None = None,
    output_cid: str | None = None,
    implementation_id: str | None = None,
    model_id: str | None = None,
    question_set_hash: str | None = None,
    severity: Any = None,
    disposition: str | None = None,
    cause: str | None = None,
) -> dict[str, Any]:
    """Authorizing witness before ``decision_cid`` exists.

    ``not_a_proof``, ``verified``, and ``zero_knowledge`` are constants.
    """
    return {
        "schema": DECISION_SCHEMA,
        "decision": decision,
        "allowed": allowed,
        "obligations": _json_copy(list(obligations)),
        "policy_cid": policy_cid,
        "policy_version": policy_version,
        "intent_cid": intent_cid,
        "input_cid": input_cid,
        "output_cid": output_cid,
        "proofs_checked": _json_copy(list(proofs_checked)),
        "gate": gate,
        "now": now,
        "implementation_id": implementation_id,
        "model_id": model_id,
        "question_set_hash": question_set_hash,
        "thresholds": _json_copy(dict(thresholds)),
        "clauses": _json_copy(list(clauses)),
        "severity": _json_copy(severity),
        "disposition": disposition,
        "cause": cause,
        "not_a_proof": True,
        "zero_knowledge": False,
        "verified": False,
    }


def seal_decision_witness(preimage: Mapping[str, Any]) -> dict[str, Any]:
    """Hash the preimage, then copy ``decision_cid`` onto the stored witness."""
    if "decision_cid" in preimage:
        raise ValueError("decision preimage must omit decision_cid")
    body = _json_copy(dict(preimage))
    if not isinstance(body, dict):
        raise TypeError("decision preimage must be an object")
    body["not_a_proof"] = True
    body["zero_knowledge"] = False
    body["verified"] = False
    sealed = _json_copy(body)
    sealed["decision_cid"] = cid_raw_leaf(body)
    return sealed
