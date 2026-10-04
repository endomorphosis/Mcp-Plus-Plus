"""Cross-language Profile H vectors (Python side)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from validators.profile_h import (
    ProfileHValidationError,
    canonical_profile_h_bytes,
    decode_x402_header,
    encode_x402_header,
    validate_profile_h_artifact,
    validate_replay,
    validate_request_binding,
)

VECTORS = Path(__file__).parents[2] / "conformance" / "vectors"


def load(name: str):
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


VALID = load("profile_h_artifacts_valid.json")
TRANSPORT = load("profile_h_transport_valid.json")
INVALID = load("profile_h_invalid.json")
BY_ID = {case["id"]: case for case in VALID["cases"]}


@pytest.mark.parametrize("case", VALID["cases"], ids=lambda case: case["id"])
def test_artifact_vector(case):
    assert validate_profile_h_artifact(case["kind"], case["payload"], now_ms=case.get("now_ms")) == VALID["expected_cids"][case["id"]]
    assert canonical_profile_h_bytes(case["payload"]).decode("utf-8") == json.dumps(case["payload"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@pytest.mark.parametrize("case", TRANSPORT["cases"], ids=lambda case: case["id"])
def test_transport_vector(case):
    expected = TRANSPORT.get("expected_outputs", {}).get(case["id"], {})
    canonical = case["expected_canonical"] or expected["canonical"]
    header = case["expected_header"] or expected["header"]
    assert canonical_profile_h_bytes(case["payload"]).decode() == canonical
    assert encode_x402_header(case["kind"], case["payload"]) == header
    assert decode_x402_header(case["kind"], header) == case["payload"]


def invoke_invalid(case):
    operation = case["operation"]
    if operation == "decode":
        decode_x402_header(case["kind"], case["encoded"])
        return
    if operation == "replay":
        validate_replay({case["commitment"]}, case["commitment"])
        return
    source = copy.deepcopy(BY_ID[case.get("source", "")])
    payload = source.get("payload")
    if operation == "artifact-mutate":
        payload[case["mutation"]["path"]] = case["mutation"]["value"]
    if operation == "artifact-redaction":
        payload["requirements"][0]["extra"]["walletAddress"] = "0xsecret"
    if case.get("append_requirement"):
        payload["requirements"].append(copy.deepcopy(payload["requirements"][0]))
    if operation in ("artifact", "artifact-mutate", "artifact-redaction"):
        validate_profile_h_artifact(source["kind"], payload, case.get("limits"), now_ms=case.get("now_ms"))
    elif operation == "binding":
        validate_request_binding(case["expected_request_cid"], payload)


@pytest.mark.parametrize("case", INVALID["cases"], ids=lambda case: case["id"])
def test_invalid_vector(case):
    with pytest.raises(ProfileHValidationError) as raised:
        invoke_invalid(case)
    assert (raised.value.code, raised.value.path) == (case["expected_error"], case["expected_path"])
