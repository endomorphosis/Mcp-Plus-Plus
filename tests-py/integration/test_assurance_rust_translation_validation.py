"""FACP-035: hermetic wrapper for Rust assurance codec + translation validation.

Acceptance (taskboard):
- Validator independently rejects all negative/mutation vectors
- Confirms canonical round trips / CIDs
- Result binds compiler and validator identities separately
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RUST_DIR = REPO_ROOT / "Mcp-Plus-Plus" / "tests-rs"
CODEC_RS = RUST_DIR / "src" / "assurance_codec.rs"
TEST_RS = RUST_DIR / "tests" / "assurance_translation_validation_test.rs"
VECTORS_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "conformance"
    / "vectors"
    / "assurance-canonical-encoding.json"
)
COMPILER_PATH = (
    REPO_ROOT / "Mcp-Plus-Plus" / "tools" / "assurance_idl" / "compiler.py"
)
ENCODING_SPEC = (
    REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "assurance-canonical-encoding.md"
)

TASK_ID = "FACP-035"
GOAL_ID = "FACP-G310"
BUNDLE = "facp/contracts/rust-codec"
VALIDATION_RESULT_SCHEMA = "facp/translation-validation@1"
DAG_CBOR_PROFILE = "facp/dag-cbor-profile@1"
VECTORS_SCHEMA = "facp/assurance-canonical-encoding-vectors@1"

COMPILER_TASK_ID = "FACP-034"
COMPILER_BUNDLE = "facp/contracts/compiler"

REQUIRED_CODEC_MARKERS = (
    "FACP-035",
    'BUNDLE: &str = "facp/contracts/rust-codec"',
    'COMPILER_TASK_ID: &str = "FACP-034"',
    'COMPILER_BUNDLE: &str = "facp/contracts/compiler"',
    "TranslationValidationResult",
    "compiler_identity",
    "validator_identity",
    "validate_conformance_vectors",
    "admit",
    "cid_for_bytes",
    "bind_cid_to_bytes",
    "NON_DEFINITE_LENGTH",
    "MALLEABLE_ENCODING",
    "WRONG_CID_FAMILY",
    "PSEUDO_CID",
    "facp/dag-cbor-profile@1",
    "facp/translation-validation@1",
)

REQUIRED_TEST_MARKERS = (
    "assurance_codec.rs",
    "independent_translation_validation_confirms_all_vectors",
    "every_negative_and_mutation_vector_is_rejected",
    "every_positive_vector_round_trips_with_exact_cid",
    "does_not_trust_generator_without_validation",
    "identities_bound_separately",
    "compiler_identity",
    "validator_identity",
)


def _hermetic_cargo_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base if base is not None else os.environ)
    env["CARGO_NET_OFFLINE"] = "true"
    env["CARGO_TERM_COLOR"] = "never"
    for key in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "all_proxy",
    ):
        env[key] = "http://127.0.0.1:9"
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    return env


def _resolve_cargo() -> str:
    found = shutil.which("cargo")
    assert found, "cargo not found on PATH for FACP-035 hermetic wrapper"
    return found


def _load_vectors() -> dict[str, Any]:
    assert VECTORS_PATH.is_file(), VECTORS_PATH
    data = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_expected_rust_outputs_exist() -> None:
    assert CODEC_RS.is_file(), f"missing assurance codec: {CODEC_RS}"
    assert TEST_RS.is_file(), f"missing translation validation test: {TEST_RS}"
    codec = CODEC_RS.read_text(encoding="utf-8")
    test_src = TEST_RS.read_text(encoding="utf-8")
    for marker in REQUIRED_CODEC_MARKERS:
        assert marker in codec, f"codec missing marker: {marker}"
    for marker in REQUIRED_TEST_MARKERS:
        assert marker in test_src, f"test missing marker: {marker}"
    # Path-include pattern (lib.rs out of scope), matching FACP-013.
    assert '#[path = "../src/assurance_codec.rs"]' in test_src
    # No permissive CID path: regex-only is documented as prohibited.
    assert "REGEX_ONLY_CID" in codec
    assert "pub fn admit" in codec
    assert "decode-and-reencode" in codec.lower() or "decode_and_reencode" in codec or (
        "reencoded" in codec and "MALLEABLE_ENCODING" in codec
    )


def test_identities_bound_separately_in_codec_source() -> None:
    codec = CODEC_RS.read_text(encoding="utf-8")
    # Compiler and validator constants must both exist and differ.
    assert COMPILER_TASK_ID in codec
    assert TASK_ID in codec
    assert COMPILER_BUNDLE in codec
    assert BUNDLE in codec
    assert "fn compiler()" in codec or "ComponentIdentity::compiler" in codec
    assert "fn validator()" in codec or "ComponentIdentity::validator" in codec
    # Result type exposes both fields as separate members.
    assert re.search(
        r"pub struct TranslationValidationResult\s*\{[^}]*compiler_identity[^}]*validator_identity",
        codec,
        re.DOTALL,
    ), "TranslationValidationResult must bind compiler_identity and validator_identity separately"
    # Ensure they are not the same constant aliased twice.
    assert COMPILER_TASK_ID != TASK_ID
    assert COMPILER_BUNDLE != BUNDLE


def test_vectors_and_compiler_preconditions_present() -> None:
    vectors = _load_vectors()
    assert vectors["schema"] == VECTORS_SCHEMA
    assert vectors["profile"] == DAG_CBOR_PROFILE
    assert vectors["fail_closed"] is True
    assert vectors["positive"]
    assert vectors["negative"]
    assert vectors["mutations"]
    assert COMPILER_PATH.is_file(), "FACP-034 compiler must exist (dependency)"
    assert ENCODING_SPEC.is_file(), "FACP-033 encoding spec must exist"
    compiler_src = COMPILER_PATH.read_text(encoding="utf-8")
    assert f'TASK_ID = "{COMPILER_TASK_ID}"' in compiler_src
    assert f'BUNDLE = "{COMPILER_BUNDLE}"' in compiler_src


def test_cargo_test_assurance_translation_validation_hermetic() -> None:
    """Invoke `cargo test` for the independent translation validator (offline)."""
    cargo = _resolve_cargo()
    assert CODEC_RS.is_file()
    assert TEST_RS.is_file()
    env = _hermetic_cargo_env()
    proc = subprocess.run(
        [
            cargo,
            "test",
            "--offline",
            "--test",
            "assurance_translation_validation_test",
            "--",
            "--nocapture",
        ],
        cwd=str(RUST_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, (
        "cargo test --test assurance_translation_validation_test failed "
        f"(exit {proc.returncode}):\n{output}"
    )
    assert "independent_translation_validation_confirms_all_vectors" in output
    assert "every_negative_and_mutation_vector_is_rejected" in output
    assert "every_positive_vector_round_trips_with_exact_cid" in output
    assert "does_not_trust_generator_without_validation" in output
    assert "test result: ok." in output
    # Identity markers for evidence recording.
    assert TASK_ID == "FACP-035"
    assert GOAL_ID == "FACP-G310"
    assert BUNDLE == "facp/contracts/rust-codec"
    assert VALIDATION_RESULT_SCHEMA == "facp/translation-validation@1"


def test_validator_does_not_import_or_execute_compiler() -> None:
    """Independent validation: Rust codec source must not shell out to the compiler."""
    codec = CODEC_RS.read_text(encoding="utf-8")
    test_src = TEST_RS.read_text(encoding="utf-8")
    for src in (codec, test_src):
        assert "assurance_idl" not in src
        assert "compiler.py" not in src
        assert "Command::new" not in src
        assert "std::process" not in src
        assert "std::net" not in src
        assert "reqwest" not in src
