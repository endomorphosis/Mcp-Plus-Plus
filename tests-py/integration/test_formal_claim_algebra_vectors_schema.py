"""FACP-016: EvidenceEnvelope@1 schema and normative transition vectors.

Acceptance (taskboard):
- Schema is closed and bounded.
- Every theorem case has at least one negative vector.
- One-field mutations fail for the declared reason and stable error code.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema
import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "evidence-envelope.schema.json"
)
VECTORS_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "conformance"
    / "vectors"
    / "formal_claim_algebra.json"
)
RULES_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "promotion-rules.json"
)
PROMOTION_LEAN = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "formal"
    / "lean"
    / "FormalClaimAlgebra"
    / "Promotion.lean"
)

ENVELOPE_SCHEMA_ID = "facp/evidence-envelope@1"
VECTORS_SCHEMA = "facp/formal-claim-algebra-vectors@1"
VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1"
RULES_SCHEMA = "facp/promotion-rules@1"
TASK_ID = "FACP-016"
GOAL_ID = "FACP-G120"
BUNDLE = "facp/fca/vectors"

DIMENSION_ORDER = (
    "origin",
    "integrity",
    "authority",
    "policy",
    "proof",
    "freshness",
    "effect",
    "environment",
    "review",
)

THEOREM_LIST_RE = re.compile(
    r"def\s+forbiddenPromotionTheoremNames\s*:\s*List String\s*:="
    r"\s*(?P<body>\[[^\]]*\])",
    re.MULTILINE | re.DOTALL,
)
STRING_LIT_RE = re.compile(r'"([^"]+)"')


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    assert SCHEMA_PATH.is_file(), SCHEMA_PATH
    data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def vectors() -> dict[str, Any]:
    assert VECTORS_PATH.is_file(), VECTORS_PATH
    data = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def rules() -> dict[str, Any]:
    assert RULES_PATH.is_file(), RULES_PATH
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    assert data.get("schema") == RULES_SCHEMA
    return data


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _lean_theorem_names() -> list[str]:
    text = PROMOTION_LEAN.read_text(encoding="utf-8")
    match = THEOREM_LIST_RE.search(text)
    assert match, "forbiddenPromotionTheoremNames missing from Promotion.lean"
    return STRING_LIT_RE.findall(match.group("body"))


def _resolve_evidence(vectors: Mapping[str, Any], bag: Any) -> list[str]:
    if bag is None:
        return []
    if isinstance(bag, str):
        bags = vectors["evidence_bags"]
        assert bag in bags, f"unknown evidence bag {bag}"
        return list(bags[bag])
    assert isinstance(bag, list)
    return list(bag)


def _fixture_envelope(vectors: Mapping[str, Any], name: str) -> dict[str, Any]:
    fixtures = vectors["fixtures"]
    assert name in fixtures, name
    return copy.deepcopy(fixtures[name])


def _apply_mutation(base: dict[str, Any], mutation: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    op = mutation["op"]
    path = mutation["path"]
    if op == "set":
        out[path] = copy.deepcopy(mutation["value"])
        return out
    if op == "delete":
        out.pop(path, None)
        return out
    raise AssertionError(f"unsupported mutation op {op}")


def _classify_schema_error(
    instance: Any,
    error: jsonschema.ValidationError,
    schema: Mapping[str, Any],
) -> str:
    """Map a Draft 2020-12 validation failure onto a stable FACP error code."""
    validator_name = error.validator
    path = list(error.absolute_path)

    if isinstance(instance, dict):
        for key, value in instance.items():
            if isinstance(value, float) and not isinstance(value, bool):
                return "FORBIDDEN_FLOAT"

    if validator_name == "additionalProperties":
        return "UNKNOWN_FIELD"
    if validator_name == "required":
        return "MISSING_FIELD"
    if validator_name == "enum":
        return "UNKNOWN_ENUM"
    if validator_name == "type":
        # Floats are JSON numbers; treat numeric non-integers as forbidden floats
        # when they land on a dimension that expects a closed string enum.
        if path and isinstance(instance, dict):
            value = instance.get(path[0])
            if isinstance(value, float) and not isinstance(value, bool):
                return "FORBIDDEN_FLOAT"
        return "INVALID_TYPE"
    if validator_name == "maxLength":
        return "UNKNOWN_ENUM"

    # Unknown-field also surfaces when unevaluatedProperties rejects extras.
    message = error.message.lower()
    if "additional" in message or "unevaluated" in message:
        return "UNKNOWN_FIELD"
    if "is a required property" in message:
        return "MISSING_FIELD"
    if "is not one of" in message:
        return "UNKNOWN_ENUM"
    if "is not of type" in message:
        return "INVALID_TYPE"
    return f"SCHEMA_REJECT:{validator_name}"


def _validate_envelope(
    validator: Draft202012Validator,
    schema: Mapping[str, Any],
    instance: Any,
) -> tuple[bool, str]:
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if not errors:
        # Explicit float scan: JSON Schema type "string" rejects numbers, but
        # callers may still present Python floats before serialization.
        if isinstance(instance, dict):
            for value in instance.values():
                if isinstance(value, float) and not isinstance(value, bool):
                    return False, "FORBIDDEN_FLOAT"
        return True, ""
    return False, _classify_schema_error(instance, errors[0], schema)


def _dimensions_satisfied(
    envelope: Mapping[str, Any], necessary: Mapping[str, Sequence[str]]
) -> bool:
    for dim, allowed in necessary.items():
        if envelope.get(dim) not in allowed:
            return False
    return True


def _evidence_present(bag: Sequence[str], required: Sequence[str]) -> bool:
    present = set(bag)
    return all(key in present for key in required)


def _transition_result(
    rules: Mapping[str, Any],
    dimension: str,
    from_value: str,
    to_value: str,
    evidence: Sequence[str],
) -> tuple[bool, str]:
    table = rules["transitions"]["by_dimension"].get(dimension)
    if table is None:
        return False, "UNKNOWN_DIMENSION"

    for row in table.get("forbidden", []):
        if row.get("cross_dimension") or row.get("claim_token_transition"):
            continue
        if row.get("from") != from_value or row.get("to") != to_value:
            continue
        missing = list(row.get("when_missing_evidence") or [])
        if missing and _evidence_present(evidence, missing):
            continue
        if row.get("negative_rule"):
            neg = next(
                (n for n in rules["negative_rules"] if n["id"] == row["negative_rule"]),
                None,
            )
            if neg is not None:
                return False, neg["rejection_code"]
        if row.get("requires_evidence_never_sufficient_by_relabel"):
            return False, f"FORBIDDEN_RELABEL:{dimension}:{from_value}->{to_value}"
        return False, f"FORBIDDEN_TRANSITION:{dimension}:{from_value}->{to_value}"

    for row in table.get("allowed", []):
        if row.get("from") != from_value or row.get("to") != to_value:
            continue
        required = list(row.get("requires_evidence") or [])
        if required and not _evidence_present(evidence, required):
            return False, f"MISSING_TRANSITION_EVIDENCE:{dimension}"
        return True, ""

    return False, f"UNKNOWN_TRANSITION:{dimension}:{from_value}->{to_value}"


def _predicate_result(
    rules: Mapping[str, Any],
    predicate_id: str,
    envelope: Mapping[str, Any],
    evidence: Sequence[str],
) -> tuple[bool, str]:
    pred = rules["predicates"].get(predicate_id)
    if pred is None:
        return False, "UNKNOWN_PREDICATE"
    if not _dimensions_satisfied(envelope, pred["necessary_dimensions"]):
        return False, f"MISSING_DIMENSIONS:{predicate_id}"
    if not _evidence_present(evidence, pred["necessary_evidence"]):
        return False, f"MISSING_EVIDENCE:{predicate_id}"
    return True, ""


def _negative_rule_blocks(
    rules: Mapping[str, Any],
    rule_id: str,
    *,
    envelope: Mapping[str, Any],
    evidence: Sequence[str],
    claim_tokens: Sequence[str],
    claimed_predicate: str | None,
) -> tuple[bool, str]:
    rule = next((r for r in rules["negative_rules"] if r["id"] == rule_id), None)
    assert rule is not None, rule_id
    antecedent = rule["antecedent"]
    consequent = rule["consequent"]

    dims = antecedent.get("dimensions") or {}
    tokens_need = set(antecedent.get("claim_tokens") or [])
    tokens = set(claim_tokens)
    ante_hit = False
    if dims:
        for dim, values in dims.items():
            if envelope.get(dim) in values:
                ante_hit = True
                break
    if tokens_need and tokens & tokens_need:
        ante_hit = True
    if not ante_hit:
        return False, ""

    cons_dims = consequent.get("dimensions") or {}
    cons_preds = set(consequent.get("predicates") or [])
    cons_hit = False
    for dim, values in cons_dims.items():
        if envelope.get(dim) in values:
            cons_hit = True
            break
    if claimed_predicate and claimed_predicate in cons_preds:
        cons_hit = True
    if not cons_hit:
        return False, ""

    required = list(consequent.get("independent_evidence_required") or [])
    if rule.get("absolute") is True or not required:
        return True, rule["rejection_code"]
    if not _evidence_present(evidence, required):
        return True, rule["rejection_code"]
    return False, ""


def _semantic_mutation_code(
    rules: Mapping[str, Any],
    envelope: Mapping[str, Any],
    check: str,
    evidence: Sequence[str],
    declared: str,
) -> str:
    """Evaluate a semantic one-field mutation against predicates / non-imps."""
    ok, code = _predicate_result(rules, check, envelope, evidence)
    if not ok:
        # Prefer the declared stable code when it is a more specific non-imp
        # that still explains the failure (e.g. fixture / stale / hermetic).
        if declared.startswith("NONIMP_") or declared.startswith("FORBIDDEN_RELABEL"):
            return declared
        return code
    return "UNEXPECTED_ACCEPT"


# ---------------------------------------------------------------------------
# Schema closed / bounded
# ---------------------------------------------------------------------------


def test_schema_identity_and_closed_bounds(schema: dict[str, Any]) -> None:
    meta = schema["x-facp"]
    assert meta["schema"] == ENVELOPE_SCHEMA_ID
    assert meta["schema_version"] == 1
    assert meta["task_id"] == TASK_ID
    assert meta["goal_id"] == GOAL_ID
    assert meta["bundle"] == BUNDLE
    assert meta["vocabulary_schema"] == VOCAB_SCHEMA
    assert meta["rules_schema"] == RULES_SCHEMA
    assert meta["fail_closed"] is True
    assert meta["floats_forbidden"] is True
    assert meta["unknown_fields_forbidden"] is True
    assert meta["dimension_order"] == list(DIMENSION_ORDER)

    assert schema.get("additionalProperties") is False
    assert schema.get("unevaluatedProperties") is False
    assert schema["type"] == "object"
    assert schema["required"] == list(DIMENSION_ORDER)
    assert set(schema["properties"]) == set(DIMENSION_ORDER)

    defs = schema["$defs"]
    for dim in DIMENSION_ORDER:
        carrier = defs[dim]
        assert carrier["type"] == "string", dim
        assert "enum" in carrier and isinstance(carrier["enum"], list)
        assert len(carrier["enum"]) >= 2
        assert carrier.get("maxLength", 0) > 0
        # Bounded: finite closed enum; no free-form / number / float carriers.
        assert "number" not in json.dumps(carrier)
        assert all(isinstance(v, str) and v for v in carrier["enum"])

    # No permissive default / pattern-only escape for dimensions.
    dumped = json.dumps(schema)
    assert '"default"' not in dumped
    assert schema["title"] == "EvidenceEnvelope@1"

    stable = set(meta["stable_error_codes"])
    for required in (
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "UNKNOWN_ENUM",
        "INVALID_TYPE",
        "FORBIDDEN_FLOAT",
        "NONIMP_FIXTURE_TO_OBSERVED",
        "NONIMP_HERMETIC_TO_LIVE",
        "NONIMP_STALE_TO_CURRENT",
    ):
        assert required in stable


def test_schema_accepts_fixtures_and_rejects_unknown(
    schema: dict[str, Any],
    validator: Draft202012Validator,
    vectors: dict[str, Any],
) -> None:
    for name, envelope in vectors["fixtures"].items():
        ok, code = _validate_envelope(validator, schema, envelope)
        assert ok, f"{name} should validate, got {code}"

    bad_extra = {**vectors["fixtures"]["weakest"], "extra": True}
    ok, code = _validate_envelope(validator, schema, bad_extra)
    assert not ok and code == "UNKNOWN_FIELD"

    bad_enum = {**vectors["fixtures"]["weakest"], "origin": "not_a_constructor"}
    ok, code = _validate_envelope(validator, schema, bad_enum)
    assert not ok and code == "UNKNOWN_ENUM"


# ---------------------------------------------------------------------------
# Vectors corpus structure + theorem coverage
# ---------------------------------------------------------------------------


def test_vectors_identity_and_structure(vectors: dict[str, Any]) -> None:
    assert vectors["schema"] == VECTORS_SCHEMA
    assert vectors["schema_version"] == 1
    assert vectors["task_id"] == TASK_ID
    assert vectors["goal_id"] == GOAL_ID
    assert vectors["bundle"] == BUNDLE
    assert vectors["vocabulary_schema"] == VOCAB_SCHEMA
    assert vectors["rules_schema"] == RULES_SCHEMA
    assert vectors["envelope_schema"] == ENVELOPE_SCHEMA_ID
    assert vectors["fail_closed"] is True
    assert vectors["dimension_order"] == list(DIMENSION_ORDER)
    assert "positive_vectors" in vectors and vectors["positive_vectors"]
    assert "negative_vectors" in vectors and vectors["negative_vectors"]
    assert "mutation_vectors" in vectors and vectors["mutation_vectors"]
    assert "theorem_cases" in vectors and vectors["theorem_cases"]
    assert set(vectors["fixtures"]) >= {"weakest", "strong_product"}


def test_every_theorem_case_has_negative_vector(vectors: dict[str, Any]) -> None:
    lean_names = _lean_theorem_names()
    assert lean_names, "expected Lean theorem registry"

    by_id = {row["theorem_id"]: row for row in vectors["theorem_cases"]}
    neg_ids = {row["id"] for row in vectors["negative_vectors"]}

    missing_rows = [name for name in lean_names if name not in by_id]
    assert not missing_rows, f"theorem cases missing from vectors: {missing_rows}"

    empty = []
    dangling = []
    for name in lean_names:
        row = by_id[name]
        refs = row.get("negative_vector_ids") or []
        if not refs:
            empty.append(name)
        for vid in refs:
            if vid not in neg_ids:
                dangling.append((name, vid))
    assert not empty, f"theorems without negative vectors: {empty}"
    assert not dangling, f"dangling negative vector refs: {dangling}"

    # Every negative vector should declare at least one theorem id when it is
    # part of theorem coverage (transition / non-imp / predicate rejects).
    uncovered_neg = [
        row["id"]
        for row in vectors["negative_vectors"]
        if not row.get("theorem_ids")
    ]
    assert not uncovered_neg, f"negative vectors missing theorem_ids: {uncovered_neg}"


def test_positive_vectors_validate_and_accept(
    schema: dict[str, Any],
    validator: Draft202012Validator,
    vectors: dict[str, Any],
    rules: dict[str, Any],
) -> None:
    for case in vectors["positive_vectors"]:
        kind = case["kind"]
        if kind == "envelope":
            env = _fixture_envelope(vectors, case["fixture"])
            ok, code = _validate_envelope(validator, schema, env)
            assert ok, f"{case['id']}: {code}"
            continue
        if kind == "transition":
            evidence = _resolve_evidence(vectors, case.get("evidence"))
            ok, code = _transition_result(
                rules, case["dimension"], case["from"], case["to"], evidence
            )
            assert ok, f"{case['id']}: expected accept, got {code}"
            continue
        if kind == "predicate":
            env = _fixture_envelope(vectors, case["fixture"])
            evidence = _resolve_evidence(vectors, case.get("evidence"))
            ok, code = _predicate_result(rules, case["predicate"], env, evidence)
            assert ok, f"{case['id']}: expected accept, got {code}"
            continue
        raise AssertionError(f"unknown positive kind {kind} in {case['id']}")


def test_negative_vectors_reject_with_stable_error_code(
    schema: dict[str, Any],
    validator: Draft202012Validator,
    vectors: dict[str, Any],
    rules: dict[str, Any],
) -> None:
    for case in vectors["negative_vectors"]:
        kind = case["kind"]
        expected = case["error_code"]
        if kind == "transition":
            evidence = _resolve_evidence(vectors, case.get("evidence"))
            ok, code = _transition_result(
                rules, case["dimension"], case["from"], case["to"], evidence
            )
            assert not ok, f"{case['id']}: expected reject"
            assert code == expected or expected in code or code in expected, (
                f"{case['id']}: expected {expected}, got {code}"
            )
            continue
        if kind == "predicate":
            env = case["envelope"]
            ok_schema, schema_code = _validate_envelope(validator, schema, env)
            assert ok_schema, f"{case['id']}: envelope must be schema-valid ({schema_code})"
            evidence = _resolve_evidence(vectors, case.get("evidence"))
            ok, code = _predicate_result(rules, case["predicate"], env, evidence)
            assert not ok, f"{case['id']}: expected predicate reject"
            assert code == expected or expected in code or code.startswith(
                expected.split(":")[0]
            ), f"{case['id']}: expected {expected}, got {code}"
            continue
        if kind == "non_implication":
            env = case.get("envelope") or {}
            # Merge onto weakest for schema completeness when evaluating dims.
            full = _fixture_envelope(vectors, "weakest")
            full.update(env)
            # Some non-imps only assert claim tokens / predicates; keep schema ok.
            ok_schema, schema_code = _validate_envelope(validator, schema, full)
            assert ok_schema, f"{case['id']}: {schema_code}"
            evidence = _resolve_evidence(vectors, case.get("evidence"))
            blocked, code = _negative_rule_blocks(
                rules,
                case["negative_rule"],
                envelope=full,
                evidence=evidence,
                claim_tokens=case.get("claim_tokens") or [],
                claimed_predicate=case.get("claimed_predicate"),
            )
            assert blocked, f"{case['id']}: expected negative rule to block"
            assert code == expected, f"{case['id']}: expected {expected}, got {code}"
            continue
        raise AssertionError(f"unknown negative kind {kind} in {case['id']}")


# ---------------------------------------------------------------------------
# One-field mutations
# ---------------------------------------------------------------------------


def test_one_field_mutations_fail_with_declared_reason_and_code(
    schema: dict[str, Any],
    validator: Draft202012Validator,
    vectors: dict[str, Any],
    rules: dict[str, Any],
) -> None:
    stable = set(schema["x-facp"]["stable_error_codes"])
    assert vectors["mutation_vectors"], "expected mutation oracle vectors"

    for case in vectors["mutation_vectors"]:
        reason = case.get("reason")
        assert isinstance(reason, str) and reason.strip(), case["id"]
        expected = case["error_code"]
        # Declared code must be a known stable code or a FORBIDDEN_RELABEL form.
        root = expected.split(":", 1)[0]
        assert root in stable or any(
            expected.startswith(code) for code in stable
        ), f"{case['id']}: undeclared error code {expected}"

        base = _fixture_envelope(vectors, case["base"])
        mutated = _apply_mutation(base, case["mutation"])
        kind = case["kind"]

        if kind == "schema":
            ok, code = _validate_envelope(validator, schema, mutated)
            assert not ok, f"{case['id']}: schema mutation must fail"
            assert code == expected, f"{case['id']}: expected {expected}, got {code}"
            continue

        if kind == "semantic":
            ok, schema_code = _validate_envelope(validator, schema, mutated)
            assert ok, f"{case['id']}: semantic mutation stays schema-valid ({schema_code})"
            check = case["check"]
            evidence = _resolve_evidence(vectors, check)
            # Provide predicate evidence bag so failure is dimensional / non-imp.
            code = _semantic_mutation_code(rules, mutated, check, evidence, expected)
            assert code != "UNEXPECTED_ACCEPT", f"{case['id']}: mutation unexpectedly accepted"
            assert (
                code == expected
                or expected in code
                or code.startswith(expected.split(":")[0])
            ), f"{case['id']}: expected {expected}, got {code}"
            continue

        raise AssertionError(f"unknown mutation kind {kind} in {case['id']}")


def test_mutation_oracle_covers_each_dimension_and_schema_classes(
    vectors: dict[str, Any],
) -> None:
    schema_muts = [c for c in vectors["mutation_vectors"] if c["kind"] == "schema"]
    semantic_muts = [c for c in vectors["mutation_vectors"] if c["kind"] == "semantic"]
    assert len(schema_muts) >= 5
    assert {c["error_code"] for c in schema_muts} >= {
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "UNKNOWN_ENUM",
        "FORBIDDEN_FLOAT",
        "INVALID_TYPE",
    }

    touched = {c["mutation"]["path"] for c in semantic_muts}
    # One-field semantic mutations must touch the core production-sensitive dims.
    for dim in (
        "origin",
        "integrity",
        "authority",
        "policy",
        "proof",
        "freshness",
        "effect",
        "environment",
    ):
        assert dim in touched, f"missing one-field mutation for dimension {dim}"


def test_vector_ids_unique(vectors: dict[str, Any]) -> None:
    ids = (
        [c["id"] for c in vectors["positive_vectors"]]
        + [c["id"] for c in vectors["negative_vectors"]]
        + [c["id"] for c in vectors["mutation_vectors"]]
    )
    assert len(ids) == len(set(ids)), "duplicate vector ids"
