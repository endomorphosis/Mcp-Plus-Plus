"""FACP-034: Assurance IDL compiler core.

Acceptance (taskboard):
- Same source produces byte-identical outputs across repeated clean runs.
- Invalid contracts fail before generation with stable errors.
- Compiler reads no credentials/network.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPILER_PATH = (
    REPO_ROOT / "Mcp-Plus-Plus" / "tools" / "assurance_idl" / "compiler.py"
)

TASK_ID = "FACP-034"
GOAL_ID = "FACP-G310"
BUNDLE = "facp/contracts/compiler"

CID_A = "bafkreifxone36h5jwjwulvkf27le3lmwon7jz65tzo27luipw55q7tcevu"
CID_B = "bafkreify4h4axvyk4b4ey6cvurixgg3ul7o3m52j2i7wg67jbavxl2kxlm"
CID_C = "bafkreigtrlsydtivo7l5hzgxu7eo5d633crbdjd44pdn63nkxkbsvsso2q"


def _load_compiler():
    assert COMPILER_PATH.is_file(), COMPILER_PATH
    spec = importlib.util.spec_from_file_location(
        "assurance_idl_compiler_facp034", COMPILER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def compiler():
    return _load_compiler()


def _base_spec(**overrides: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "schema": "facp/operation-spec@1",
        "schema_version": 1,
        "operation_id": "datasets.download",
        "namespace": "ipfs_datasets_py",
        "name": "download",
        "version": 1,
        "input_schema_cid": CID_A,
        "output_schema_cid": CID_B,
        "error_codes": ["unavailable", "rejected", "failed", "unknown_effect"],
        "effect_class": "write",
        "idempotency_class": "at_most_once",
        "reversibility_class": "compensatable",
        "authority_obligation": "capability_verified",
        "policy_obligation": "host_policy_required",
        "confirmation_obligation": "none",
        "lease_obligation": "lease_required",
        "observation_obligation": "independent_observation_required",
        "evidence_class": "live",
        "allowed_outcomes": [
            "Unavailable",
            "Rejected",
            "Attempted",
            "Unknown",
            "Observed",
            "Verified",
            "Failed",
            "Compensated",
        ],
        "resource_bounds": {
            "max_input_bytes": 1048576,
            "max_output_bytes": 67108864,
            "max_duration_ms": 60000,
            "max_memory_bytes": 268435456,
            "max_cpu_ms": 30000,
            "max_effect_retries": 1,
        },
    }
    spec.update(overrides)
    return spec


def _pure_spec(**overrides: Any) -> dict[str, Any]:
    spec = _base_spec(
        operation_id="swissknife.present_evidence",
        namespace="swissknife",
        name="present_evidence",
        effect_class="pure",
        idempotency_class="pure_idempotent",
        reversibility_class="reversible",
        authority_obligation="none",
        policy_obligation="none",
        confirmation_obligation="none",
        lease_obligation="none",
        observation_obligation="none",
        evidence_class="none",
        error_codes=["unavailable", "rejected"],
        allowed_outcomes=["Unavailable", "Rejected", "Observed"],
        input_schema_cid=CID_B,
        output_schema_cid=CID_C,
    )
    spec.update(overrides)
    return spec


def _contract_set(*ops: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "facp/assurance-idl-contract-set@1",
        "schema_version": 1,
        "operations": list(ops),
    }


# ---------------------------------------------------------------------------
# Identity / surface
# ---------------------------------------------------------------------------


def test_compiler_module_identity(compiler) -> None:
    assert compiler.TASK_ID == TASK_ID
    assert compiler.GOAL_ID == GOAL_ID
    assert compiler.BUNDLE == BUNDLE
    assert compiler.OPERATION_SPEC_SCHEMA == "facp/operation-spec@1"
    assert set(compiler.GENERATION_TARGETS) == {
        "schema",
        "code",
        "vector",
        "error",
        "docs",
        "formal_skeleton",
    }
    for code in (
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "UNKNOWN_ENUM",
        "FORBIDDEN_FLOAT",
        "INVALID_CID",
        "FREE_FORM_AUTHORITY",
        "FREE_FORM_OUTCOME",
        "FORBIDDEN_SUCCESS_BOOLEAN",
        "DUPLICATE_OPERATION_ID",
        "SEMANTIC_CONFLICT",
    ):
        assert code in compiler.STABLE_ERROR_CODES


# ---------------------------------------------------------------------------
# Happy path + byte identity
# ---------------------------------------------------------------------------


def test_compile_single_operation_deterministic(compiler) -> None:
    source = json.dumps(_base_spec(), separators=(",", ":"), ensure_ascii=False)
    first = compiler.compile(source)
    second = compiler.compile(source)
    third = compiler.compile(_base_spec())

    assert len(first.operations) == 1
    assert first.operations[0].operation_id == "datasets.download"
    assert first.operations[0].cid.startswith("b")
    assert first.generation_inputs.keys() == set(compiler.GENERATION_TARGETS)

    for target in compiler.GENERATION_TARGETS:
        assert first.generation_inputs[target] == second.generation_inputs[target]
        assert first.digests[target] == second.digests[target]
        assert first.generation_inputs[target] == third.generation_inputs[target]

    assert first.artifact_bytes() == second.artifact_bytes() == third.artifact_bytes()
    assert first.operations[0].canonical_dag_cbor == second.operations[0].canonical_dag_cbor
    assert first.operations[0].cid == second.operations[0].cid


def test_compile_contract_set_stable_ordering(compiler) -> None:
    # Intentionally reverse input order; output must sort by operation_id.
    ops = [
        _base_spec(operation_id="kit.storage_select", namespace="ipfs_kit_py", name="storage_select"),
        _base_spec(
            operation_id="accelerate.inference",
            namespace="ipfs_accelerate_py",
            name="inference",
            effect_class="process",
        ),
        _pure_spec(),
        _base_spec(),
    ]
    result = compiler.compile(_contract_set(*ops))
    ids = [op.operation_id for op in result.operations]
    assert ids == sorted(ids)
    assert ids == [
        "accelerate.inference",
        "datasets.download",
        "kit.storage_select",
        "swissknife.present_evidence",
    ]

    # Error codes / outcomes normalized for byte stability.
    download = next(op for op in result.operations if op.operation_id == "datasets.download")
    assert download.normalized["error_codes"] == sorted(download.normalized["error_codes"])
    outcomes = list(download.normalized["allowed_outcomes"])
    assert outcomes == [o for o in compiler.CLOSED_OUTCOMES if o in outcomes]


def test_repeated_clean_runs_byte_identical_across_shuffles(compiler) -> None:
    base_ops = [
        _base_spec(),
        _pure_spec(),
        _base_spec(
            operation_id="datasets.get",
            name="get",
            effect_class="read",
            idempotency_class="idempotent",
            reversibility_class="reversible",
            lease_obligation="none",
            evidence_class="conditional",
            allowed_outcomes=["Unavailable", "Rejected", "Observed", "Verified", "Failed"],
            input_schema_cid=CID_C,
            output_schema_cid=CID_A,
        ),
    ]
    artifacts: list[bytes] = []
    digests: list[dict[str, str]] = []
    for order in (base_ops, list(reversed(base_ops)), [base_ops[1], base_ops[0], base_ops[2]]):
        result = compiler.compile(_contract_set(*copy.deepcopy(order)))
        artifacts.append(result.artifact_bytes())
        digests.append(dict(result.digests))
        for target in compiler.GENERATION_TARGETS:
            # Re-run generation path via fresh compile.
            assert isinstance(result.generation_inputs[target], (bytes, bytearray))
            assert len(result.generation_inputs[target]) > 0

    assert artifacts[0] == artifacts[1] == artifacts[2]
    assert digests[0] == digests[1] == digests[2]


def test_compile_from_bytes_and_list(compiler) -> None:
    payload = _contract_set(_base_spec(), _pure_spec())
    as_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    from_bytes = compiler.compile(as_bytes)
    from_list = compiler.compile([_pure_spec(), _base_spec()])
    assert from_bytes.artifact_bytes() == from_list.artifact_bytes()


def test_generation_inputs_are_not_executed(compiler) -> None:
    result = compiler.compile(_base_spec())
    # formal_skeleton and docs are text; code/schema/vector/error are JSON.
    formal = result.generation_inputs["formal_skeleton"].decode("utf-8")
    assert "inductive EffectClass" in formal
    assert "exec" not in formal.lower()
    code_doc = json.loads(result.generation_inputs["code"].decode("utf-8"))
    assert code_doc["languages"] == ["python", "typescript", "rust", "go"]
    vector_doc = json.loads(result.generation_inputs["vector"].decode("utf-8"))
    assert vector_doc["negative_recipes"]
    assert all("error" in recipe for recipe in vector_doc["negative_recipes"])


# ---------------------------------------------------------------------------
# Fail-closed before generation
# ---------------------------------------------------------------------------


def _assert_fails(compiler, source: Any, code: str) -> None:
    with pytest.raises(compiler.CompilerError) as excinfo:
        compiler.compile(source)
    err = excinfo.value
    assert err.code == code
    assert err.code in compiler.STABLE_ERROR_CODES
    assert err.diagnostics
    assert all(d.code in compiler.STABLE_ERROR_CODES for d in err.diagnostics)


def test_invalid_unknown_field_fails_before_generation(compiler) -> None:
    bad = _base_spec()
    bad["extra_field"] = "nope"
    _assert_fails(compiler, bad, "UNKNOWN_FIELD")


def test_invalid_missing_field_fails_before_generation(compiler) -> None:
    bad = _base_spec()
    del bad["operation_id"]
    _assert_fails(compiler, bad, "MISSING_FIELD")


def test_invalid_unknown_enum_fails_before_generation(compiler) -> None:
    _assert_fails(compiler, _base_spec(effect_class="explode"), "UNKNOWN_ENUM")


def test_forbidden_float_fails_before_generation(compiler) -> None:
    bad = _base_spec()
    bad["version"] = 1.5  # type: ignore[assignment]
    _assert_fails(compiler, bad, "FORBIDDEN_FLOAT")

    bad_bounds = _base_spec()
    bad_bounds["resource_bounds"] = dict(bad_bounds["resource_bounds"])
    bad_bounds["resource_bounds"]["max_duration_ms"] = 1.25  # type: ignore[index]
    _assert_fails(compiler, bad_bounds, "FORBIDDEN_FLOAT")


def test_free_form_authority_and_outcome_fail(compiler) -> None:
    bad_auth = _base_spec()
    bad_auth["authority"] = "admin"
    _assert_fails(compiler, bad_auth, "FREE_FORM_AUTHORITY")

    bad_outcome = _base_spec(allowed_outcomes=["Success"])  # type: ignore[list-item]
    _assert_fails(compiler, bad_outcome, "FREE_FORM_OUTCOME")

    bad_success = _base_spec()
    bad_success["success"] = True
    _assert_fails(compiler, bad_success, "FORBIDDEN_SUCCESS_BOOLEAN")


def test_invalid_cid_fails(compiler) -> None:
    _assert_fails(
        compiler,
        _base_spec(input_schema_cid="QmNotAValidAssuranceCid000000000000000000000"),
        "INVALID_CID",
    )
    _assert_fails(
        compiler,
        _base_spec(output_schema_cid="not-a-cid"),
        "INVALID_CID",
    )


def test_duplicate_operation_id_fails(compiler) -> None:
    _assert_fails(
        compiler,
        _contract_set(_base_spec(), _base_spec()),
        "DUPLICATE_OPERATION_ID",
    )


def test_empty_contract_set_fails(compiler) -> None:
    _assert_fails(compiler, {"schema": "facp/assurance-idl-contract-set@1", "schema_version": 1, "operations": []}, "EMPTY_CONTRACT_SET")
    _assert_fails(compiler, [], "EMPTY_CONTRACT_SET")


def test_semantic_conflicts_fail(compiler) -> None:
    # pure with capability authority
    _assert_fails(
        compiler,
        _pure_spec(authority_obligation="capability_verified"),
        "SEMANTIC_CONFLICT",
    )
    # Verified with evidence none
    _assert_fails(
        compiler,
        _pure_spec(allowed_outcomes=["Unavailable", "Verified"]),
        "SEMANTIC_CONFLICT",
    )
    # irreversible effect without irreversible reversibility
    _assert_fails(
        compiler,
        _base_spec(effect_class="irreversible", reversibility_class="compensatable"),
        "SEMANTIC_CONFLICT",
    )


def test_malformed_json_fails_with_stable_error(compiler) -> None:
    _assert_fails(compiler, "{not json", "INVALID_JSON")


def test_try_compile_returns_error_without_result(compiler) -> None:
    result, err = compiler.try_compile(_base_spec(effect_class="nope"))
    assert result is None
    assert err is not None
    assert err.code == "UNKNOWN_ENUM"
    # Ensure no generation leaked via partial result.
    ok, err2 = compiler.try_compile(_base_spec())
    assert err2 is None
    assert ok is not None
    assert set(ok.generation_inputs) == set(compiler.GENERATION_TARGETS)


def test_negative_recipe_roundtrip_from_generation_vector(compiler) -> None:
    """Invalid mutations described by vector recipes fail closed with declared codes."""
    result = compiler.compile(_base_spec())
    vector = json.loads(result.generation_inputs["vector"].decode("utf-8"))
    base = copy.deepcopy(vector["positive"][0]["operation"])

    for recipe in vector["negative_recipes"]:
        if recipe["id"] == "duplicate_operation_id":
            source = _contract_set(base, copy.deepcopy(base))
            _assert_fails(compiler, source, recipe["error"])
            continue
        mutated = copy.deepcopy(base)
        if "mutate" in recipe:
            mutated.update(recipe["mutate"])
        if "drop" in recipe:
            mutated.pop(recipe["drop"], None)
        if "set" in recipe:
            mutated.update(recipe["set"])
        _assert_fails(compiler, mutated, recipe["error"])


# ---------------------------------------------------------------------------
# Hermetic: no credentials / network
# ---------------------------------------------------------------------------


def test_compiler_source_has_no_network_or_credential_imports(compiler) -> None:
    import ast

    text = COMPILER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden_roots = {
        "url" + "lib",
        "req" + "uests",
        "httpx",
        "aio" + "http",
        "soc" + "ket",
        "s" + "sl",
        "bot" + "o3",
        "para" + "miko",
        "sub" + "process",
    }
    assert imported.isdisjoint(forbidden_roots), imported & forbidden_roots

    # No dynamic code execution primitives in source.
    for token in ("eval(", "exec(", "__import__("):
        assert token not in text, token

    # No credential env reads.
    assert "os.environ" not in text
    assert "getenv" not in text
    compiler.assert_hermetic_module_source(text)


def test_compile_does_not_read_credentials_or_network(compiler, monkeypatch) -> None:
    # Poison credential-like env vars; compiler must not consult them.
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "should-never-be-read")
    monkeypatch.setenv("OPENAI_API_KEY", "should-never-be-read")
    monkeypatch.setenv("IPFS_ACCELERATE_API_TOKEN", "should-never-be-read")

    def blocked_getenv(*_a, **_k):
        raise AssertionError("compiler must not call os.getenv")

    def blocked_environ_get(*_a, **_k):
        raise AssertionError("compiler must not call os.environ.get")

    monkeypatch.setattr(os, "getenv", blocked_getenv)
    monkeypatch.setattr(os.environ, "get", blocked_environ_get)

    # Ensure networking modules are not newly imported as a side effect of compile.
    net_prefixes = ("url" + "lib", "req" + "uests", "http.client", "soc" + "ket")
    before = {name for name in sys.modules if name.startswith(net_prefixes)}
    baseline = dict(sys.modules)
    result = compiler.compile(_base_spec())
    after = {name for name in sys.modules if name.startswith(net_prefixes)}
    assert after == before
    assert result.operations

    compiler.assert_hermetic_module_source()
    compiler.assert_hermetic_runtime(baseline=baseline)


def test_dag_cbor_identity_roundtrip(compiler) -> None:
    result = compiler.compile(_base_spec())
    op = result.operations[0]
    admitted = compiler.encode_operation_dag_cbor(dict(op.normalized))
    assert admitted == op.canonical_dag_cbor
    assert compiler.cid_for_dag_cbor(admitted) == op.cid


def test_diagnostics_are_stable_across_runs(compiler) -> None:
    bad = _base_spec()
    bad["mystery"] = 1
    _, err1 = compiler.try_compile(bad)
    _, err2 = compiler.try_compile(bad)
    assert err1 is not None and err2 is not None
    assert err1.to_dict() == err2.to_dict()
    assert err1.code == "UNKNOWN_FIELD"
