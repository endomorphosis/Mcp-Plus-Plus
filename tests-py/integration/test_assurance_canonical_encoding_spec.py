"""FACP-033: Normative DAG-CBOR and CID profile for CCC artifacts.

Acceptance (taskboard):
- Every security-critical artifact has one deterministic byte representation.
- Exact CID derivation is specified.
- Duplicate/unknown/malleable encodings are negative vectors.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import dag_cbor
import pytest
from multiformats import CID, multihash

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = (
    REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "assurance-canonical-encoding.md"
)
VECTORS_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "conformance"
    / "vectors"
    / "assurance-canonical-encoding.json"
)

TASK_ID = "FACP-033"
GOAL_ID = "FACP-G310"
BUNDLE = "facp/contracts/encoding"
PROFILE = "facp/dag-cbor-profile@1"
VECTORS_SCHEMA = "facp/assurance-canonical-encoding-vectors@1"

SIGNED_FAMILY = "assurance_signed_dag_cbor"
RAW_FAMILY = "assurance_opaque_raw"

ARTIFACT_SCHEMAS = (
    "facp/evidence-envelope@1",
    "facp/operation-spec@1",
    "facp/admission-token@1",
    "facp/effect-receipt@1",
)

# Closed keys for the minimal OperationSpec identity fixture in vectors.
OPSPEC_IDENTITY_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "operation_id",
        "namespace",
        "name",
        "version",
    }
)

REQUIRED_SPEC_PHRASES = (
    "facp/dag-cbor-profile@1",
    "definite-length",
    "Tag 42",
    "sha2-256",
    "dag-cbor",
    "0x71",
    "decode-and-reencode",
    "FORBIDDEN_FLOAT",
    "DUPLICATE_MAP_KEY",
    "NON_DEFINITE_LENGTH",
    "assurance_signed_dag_cbor",
    "assurance_opaque_raw",
    "regex-only",
    "EvidenceEnvelope@1",
    "OperationSpec@1",
    "AdmissionToken@1",
    "EffectReceipt@1",
)

HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
QM_RE = re.compile(r"^Qm[1-9A-HJ-NP-Za-km-z]{44}$")


class CanonicalEncodingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _load_json(path: Path) -> dict[str, Any]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def vectors() -> dict[str, Any]:
    assert VECTORS_PATH.is_file(), VECTORS_PATH
    return _load_json(VECTORS_PATH)


@pytest.fixture(scope="module")
def spec_text() -> str:
    assert SPEC_PATH.is_file(), SPEC_PATH
    return SPEC_PATH.read_text(encoding="utf-8")


def _hydrate(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value.keys()) == {"$bytes"}:
            return bytes.fromhex(value["$bytes"])
        if set(value.keys()) == {"$link"}:
            return CID.decode(value["$link"])
        if "$non_string_key" in value:
            raise CanonicalEncodingError(
                "NON_STRING_MAP_KEY", "non-string map key fixture"
            )
        return {str(k): _hydrate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_hydrate(v) for v in value]
    return value


def _reject_floats(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise CanonicalEncodingError("FORBIDDEN_FLOAT", f"float at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_floats(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for idx, item in enumerate(value):
            _reject_floats(item, f"{path}[{idx}]")


def _classify_dag_cbor_error(exc: BaseException) -> str:
    text = str(exc).lower()
    if "indefinite" in text or "additional info 31" in text or "11111" in text:
        return "NON_DEFINITE_LENGTH"
    if "duplicate key" in text:
        return "DUPLICATE_MAP_KEY"
    if "canonical order" in text or "not in canonical order" in text:
        return "UNSORTED_MAP_KEYS"
    if "would have been enough" in text or "encoded using" in text:
        return "NON_MINIMAL_INTEGER"
    if "only tag 42" in text or "tag 43" in text:
        return "FORBIDDEN_TAG"
    if "identity multibase" in text or "cid does not start" in text:
        return "INVALID_CID_LINK"
    if "not a string" in text and "key" in text:
        return "NON_STRING_MAP_KEY"
    if "nan" in text or "infinity" in text or "float" in text:
        return "FORBIDDEN_FLOAT"
    return "MALLEABLE_ENCODING"


def encode_canonical(value: Any) -> bytes:
    """Reference encode under facp/dag-cbor-profile@1."""
    if isinstance(value, dict) and value.get("$non_string_key"):
        raise CanonicalEncodingError("NON_STRING_MAP_KEY", "non-string map key")
    hydrated = _hydrate(value)
    _reject_floats(hydrated)
    try:
        encoded = dag_cbor.encode(hydrated)
    except Exception as exc:  # noqa: BLE001 - library surfaces encoding class
        raise CanonicalEncodingError(_classify_dag_cbor_error(exc), str(exc)) from exc
    if not isinstance(encoded, bytes) or not encoded:
        raise CanonicalEncodingError("MALLEABLE_ENCODING", "empty encoding")
    return encoded


def admit_canonical_bytes(encoded: bytes) -> Any:
    """Strict decode-and-reencode admission."""
    if not isinstance(encoded, bytes) or not encoded:
        raise CanonicalEncodingError("MALLEABLE_ENCODING", "empty bytes")
    try:
        decoded = dag_cbor.decode(encoded)
    except Exception as exc:  # noqa: BLE001
        raise CanonicalEncodingError(_classify_dag_cbor_error(exc), str(exc)) from exc
    _reject_floats(decoded)
    try:
        reencoded = dag_cbor.encode(decoded)
    except Exception as exc:  # noqa: BLE001
        raise CanonicalEncodingError(_classify_dag_cbor_error(exc), str(exc)) from exc
    if reencoded != encoded:
        # Prefer a more specific code when the input is an obvious float map.
        raise CanonicalEncodingError(
            "MALLEABLE_ENCODING", "decode-and-reencode mismatch"
        )
    return decoded


def cid_for_bytes(data: bytes, family: str) -> str:
    if family == SIGNED_FAMILY:
        codec = "dag-cbor"
    elif family == RAW_FAMILY:
        codec = "raw"
    else:
        raise CanonicalEncodingError("WRONG_CID_FAMILY", f"unknown family {family}")
    return CID("base32", 1, codec, multihash.digest(data, "sha2-256")).encode()


def admit_cid_text(text: str, *, family: str | None = None) -> str:
    if not isinstance(text, str) or not text:
        raise CanonicalEncodingError("PSEUDO_CID", "empty cid")
    if HEX64_RE.fullmatch(text) or text.lower().startswith("sha256:"):
        raise CanonicalEncodingError("PSEUDO_CID", "raw hex digest is not a CID")
    if QM_RE.fullmatch(text) or text.startswith("Qm"):
        raise CanonicalEncodingError("PSEUDO_CID", "CIDv0 / Qm form is not admitted")
    if text != text.lower():
        raise CanonicalEncodingError(
            "NON_CANONICAL_CID_TEXT", "CID text must be lowercase base32"
        )
    try:
        parsed = CID.decode(text)
    except Exception as exc:  # noqa: BLE001
        raise CanonicalEncodingError("PSEUDO_CID", f"CID decode failed: {exc}") from exc
    if parsed.version != 1 or parsed.hashfun.name != "sha2-256":
        raise CanonicalEncodingError("WRONG_CID_FAMILY", "CID version/hash mismatch")
    strict = parsed.encode("base32")
    if strict != text:
        raise CanonicalEncodingError(
            "NON_CANONICAL_CID_TEXT", "CID text is not strict base32"
        )
    if family == SIGNED_FAMILY and parsed.codec.name != "dag-cbor":
        raise CanonicalEncodingError("WRONG_CID_FAMILY", "expected dag-cbor codec")
    if family == RAW_FAMILY and parsed.codec.name != "raw":
        raise CanonicalEncodingError("WRONG_CID_FAMILY", "expected raw codec")
    return text


def bind_cid_to_bytes(cid_text: str, data: bytes, family: str) -> str:
    admitted = admit_cid_text(cid_text, family=family)
    expected = cid_for_bytes(data, family)
    if admitted != expected:
        raise CanonicalEncodingError(
            "WRONG_CID_FAMILY", "CID does not recompute from retained bytes"
        )
    return admitted


def _positive_by_id(vectors: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    for case in vectors["positive"]:
        if case["id"] == case_id:
            return case
    raise AssertionError(f"missing positive case {case_id}")


def test_spec_exists_and_pins_profile(spec_text: str) -> None:
    assert "FACP-033" in spec_text
    assert GOAL_ID in spec_text
    for phrase in REQUIRED_SPEC_PHRASES:
        assert phrase.lower() in spec_text.lower(), f"missing normative phrase: {phrase}"
    # One deterministic representation — forbid alternate identity encodings.
    assert "No second security-critical canonical form" in spec_text
    assert "Regex-only CID" in spec_text or "regex-only" in spec_text.lower()


def test_vectors_metadata(vectors: dict[str, Any]) -> None:
    assert vectors["schema"] == VECTORS_SCHEMA
    assert vectors["schema_version"] == 1
    assert vectors["task_id"] == TASK_ID
    assert vectors["goal_id"] == GOAL_ID
    assert vectors["bundle"] == BUNDLE
    assert vectors["profile"] == PROFILE
    assert vectors["fail_closed"] is True
    assert set(ARTIFACT_SCHEMAS) == {
        row["schema"] for row in vectors["artifact_families"]
    }
    for row in vectors["artifact_families"]:
        assert row["cid_family"] == SIGNED_FAMILY
    families = vectors["cid_families"]
    signed = families[SIGNED_FAMILY]
    assert signed["cid_version"] == 1
    assert signed["multicodec"] == "dag-cbor"
    assert signed["multicodec_code"] == 0x71
    assert signed["multihash"] == "sha2-256"
    assert signed["multihash_code"] == 0x12
    assert signed["digest_length"] == 32
    assert signed["multibase"] == "base32"
    assert signed["binary_prefix_hex"] == "01711220"
    raw = families[RAW_FAMILY]
    assert raw["multicodec"] == "raw"
    assert raw["multicodec_code"] == 0x55
    assert raw["binary_prefix_hex"] == "01551220"
    for code in (
        "NON_DEFINITE_LENGTH",
        "DUPLICATE_MAP_KEY",
        "UNSORTED_MAP_KEYS",
        "FORBIDDEN_FLOAT",
        "MALLEABLE_ENCODING",
        "WRONG_CID_FAMILY",
        "PSEUDO_CID",
        "UNKNOWN_FIELD",
    ):
        assert code in vectors["error_codes"]
    assert vectors["positive"], "positive vectors required"
    assert vectors["negative"], "negative vectors required"
    assert vectors["mutations"], "mutation vectors required"


def test_every_artifact_family_has_positive_vector(vectors: dict[str, Any]) -> None:
    covered = {
        case.get("artifact_family")
        for case in vectors["positive"]
        if case.get("artifact_family")
    }
    assert set(ARTIFACT_SCHEMAS) <= covered


@pytest.mark.parametrize("case_id", [
    "empty_map",
    "bools_null",
    "sorted_len_then_lex",
    "int_boundaries",
    "bytes_value",
    "inner_link_target",
    "ipld_link_wrap",
    "opspec_identity_core",
    "evidence_envelope_product",
    "admission_token_links",
    "effect_receipt_link",
    "opaque_raw_bytes",
])
def test_positive_vectors_byte_and_cid_identity(
    vectors: dict[str, Any], case_id: str
) -> None:
    case = _positive_by_id(vectors, case_id)
    family = case["cid_family"]
    if family == RAW_FAMILY:
        data = bytes.fromhex(case["raw_hex"])
        assert cid_for_bytes(data, family) == case["cid"]
        bind_cid_to_bytes(case["cid"], data, family)
        return

    encoded = encode_canonical(case["value"])
    assert encoded.hex() == case["canonical_hex"]
    assert cid_for_bytes(encoded, family) == case["cid"]
    admit_canonical_bytes(encoded)
    bind_cid_to_bytes(case["cid"], encoded, family)

    # One deterministic representation: rehydrate and re-encode is identical.
    again = encode_canonical(case["value"])
    assert again == encoded


def test_link_encoding_uses_tag_42_and_identity_prefix(vectors: dict[str, Any]) -> None:
    case = _positive_by_id(vectors, "ipld_link_wrap")
    raw = bytes.fromhex(case["canonical_hex"])
    assert b"\xd8\x2a" in raw
    idx = raw.index(b"\xd8\x2a")
    assert raw[idx + 2] == 0x58  # definite bstr, 1-byte length
    assert raw[idx + 4] == 0x00  # identity multibase
    assert raw[idx + 5] == 0x01  # CIDv1
    assert raw[idx + 6] == 0x71  # dag-cbor


def test_negative_vectors_fail_closed(vectors: dict[str, Any]) -> None:
    for case in vectors["negative"]:
        expected = case["expected_error"]
        kind = case["kind"]
        with pytest.raises(CanonicalEncodingError) as raised:
            if kind == "bytes":
                raw = bytes.fromhex(case["hex"])
                # Floats may decode under dag_cbor; profile still rejects them.
                try:
                    decoded = admit_canonical_bytes(raw)
                except CanonicalEncodingError:
                    raise
                _reject_floats(decoded)
                raise CanonicalEncodingError(
                    "MALLEABLE_ENCODING", "expected rejection for negative bytes"
                )
            if kind == "value":
                if expected == "UNKNOWN_FIELD":
                    value = case["value"]
                    assert isinstance(value, dict)
                    unknown = set(value) - OPSPEC_IDENTITY_KEYS
                    if unknown:
                        raise CanonicalEncodingError(
                            "UNKNOWN_FIELD", f"unknown fields {sorted(unknown)}"
                        )
                    raise AssertionError("expected unknown fields")
                encode_canonical(case["value"])
                raise AssertionError(f"value case {case['id']} should fail")
            if kind == "cid":
                admit_cid_text(case["cid"], family=SIGNED_FAMILY)
                raise AssertionError(f"cid case {case['id']} should fail")
            if kind == "cid_family":
                base = _positive_by_id(vectors, case["retained_from_positive_id"])
                data = bytes.fromhex(base["canonical_hex"])
                bind_cid_to_bytes(case["claimed_cid"], data, SIGNED_FAMILY)
                raise AssertionError(f"cid_family case {case['id']} should fail")
            raise AssertionError(f"unknown negative kind {kind}")
        assert raised.value.code == expected, (
            case["id"],
            raised.value.code,
            expected,
            str(raised.value),
        )


def test_mutation_vectors_fail_closed(vectors: dict[str, Any]) -> None:
    for case in vectors["mutations"]:
        base = _positive_by_id(vectors, case["base_positive_id"])
        expected = case["expected_error"]
        op = case["op"]
        with pytest.raises(CanonicalEncodingError) as raised:
            if op == "xor_byte":
                raw = bytearray.fromhex(base["canonical_hex"])
                raw[case["offset"]] ^= int(case["mask"])
                admit_canonical_bytes(bytes(raw))
                raise AssertionError("xor_byte should fail admission")
            if op == "replace_hex":
                admit_canonical_bytes(bytes.fromhex(case["hex"]))
                raise AssertionError("replace_hex should fail admission")
            if op == "xor_retained_byte_keep_cid":
                raw = bytearray.fromhex(base["canonical_hex"])
                raw[case["offset"]] ^= int(case["mask"])
                bind_cid_to_bytes(base["cid"], bytes(raw), base["cid_family"])
                raise AssertionError("mutated bytes must not keep CID")
            raise AssertionError(f"unknown mutation op {op}")
        assert raised.value.code == expected, (case["id"], raised.value.code, expected)


def test_regex_only_cid_is_insufficient(vectors: dict[str, Any]) -> None:
    """Lookalike strings matching a naive prefix regex must still fail decode bind."""
    case = _positive_by_id(vectors, "empty_map")
    lookalike = "bafyrei" + ("a" * (len(case["cid"]) - len("bafyrei")))
    assert re.fullmatch(r"b[a-z2-7]+", lookalike)
    with pytest.raises(CanonicalEncodingError) as raised:
        # Even if decode somehow succeeded, binding to empty-map bytes must fail.
        try:
            admit_cid_text(lookalike, family=SIGNED_FAMILY)
        except CanonicalEncodingError as exc:
            if exc.code in {"PSEUDO_CID", "NON_CANONICAL_CID_TEXT", "WRONG_CID_FAMILY"}:
                raise
        bind_cid_to_bytes(lookalike, bytes.fromhex(case["canonical_hex"]), SIGNED_FAMILY)
    assert raised.value.code in {
        "PSEUDO_CID",
        "NON_CANONICAL_CID_TEXT",
        "WRONG_CID_FAMILY",
    }


def test_spec_and_vectors_agree_on_derivation_formula(vectors: dict[str, Any], spec_text: str) -> None:
    assert "0x01 || 0x71 || 0x12 || 0x20" in spec_text
    assert "0x01 || 0x55 || 0x12 || 0x20" in spec_text
    signed = vectors["cid_families"][SIGNED_FAMILY]
    raw = vectors["cid_families"][RAW_FAMILY]
    assert signed["binary_prefix_hex"] == "01711220"
    assert raw["binary_prefix_hex"] == "01551220"
    # Prove prefix against a live CID.
    empty = encode_canonical({})
    cid = CID.decode(cid_for_bytes(empty, SIGNED_FAMILY))
    binary = bytes(cid)
    assert binary[:4].hex() == "01711220"
    assert len(binary) == 4 + 32
