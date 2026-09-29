"""Raw-leaf CIDs for policy documents and decision preimages."""

import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Any

POLICY_SCHEMA = "mcp++-adapter/policy-document/v1"
DECISION_SCHEMA = "mcp++-adapter/policy-decision/v1"
COMPILER_VERSION = "qset-2026-09-29"

_CID_VERSION = 0x01
_MULTIHASH_SHA256 = 0x12
_MULTIHASH_LEN = 0x20
_CODEC_RAW = 0x55


def canonical_json_bytes(document: Any) -> bytes:
    """Compact UTF-8 JSON with recursively sorted object keys."""
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_cid(document: Any, codec: int) -> str:
    """CIDv1 multibase base32 of the canonical JSON bytes.

    ``codec`` is one multicodec byte. ``0x55`` is raw (``bafkrei…``).
    ``0x70`` is only the dag-pb prefix over the same bytes, not a policy address.
    """
    if not isinstance(codec, int) or isinstance(codec, bool) or not 0 <= codec <= 0x7F:
        raise ValueError("codec must be a single-byte multicodec")
    digest = hashlib.sha256(canonical_json_bytes(document)).digest()
    if len(digest) != _MULTIHASH_LEN:
        raise RuntimeError("sha256 digest must be 32 bytes")
    raw = bytes((_CID_VERSION, codec, _MULTIHASH_SHA256, _MULTIHASH_LEN)) + digest
    encoded = base64.b32encode(raw).decode("ascii").lower().rstrip("=")
    return "b" + encoded


def cid_raw_leaf(document: Any) -> str:
    """CIDv1 raw leaf: ``0x01 0x55 0x12 0x20`` plus sha256, base32 ``bafkrei…``."""
    return content_cid(document, _CODEC_RAW)


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
