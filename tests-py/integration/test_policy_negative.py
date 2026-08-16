"""
Policy version, stale context, revocation-before-execution, and conflict tests
(MCPP-048).

Interface: PolicyVector@1
Vectors: conformance/vectors/policy

Acceptance:
  Every listed case has an expected decision.
  Conflicting policies resolve by a documented deterministic rule.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_MCPPLUS = Path(__file__).resolve().parents[2]
_VECTORS = _MCPPLUS / "conformance" / "vectors" / "policy"
_TESTS_PY = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(_TESTS_PY))


def _load_vector_module(name: str, filename: str) -> ModuleType:
    """Load a module from the policy vector directory without path collisions.

    The crypto adversarial suite also ships an ``evaluate.py``; importing by
    bare name is ambiguous when multiple vector roots are on ``sys.path``.
    """
    path = _VECTORS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Register under a unique name so dataclasses / nested imports resolve.
    sys.modules[name] = module
    # Policy evaluate imports generate_fixtures by bare name; put the vector
    # root first only for this load, then restore.
    previous = list(sys.path)
    try:
        sys.path.insert(0, str(_VECTORS))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous
    return module


_gen = _load_vector_module("mcpp_policy_generate_fixtures", "generate_fixtures.py")
_eval = _load_vector_module("mcpp_policy_evaluate", "evaluate.py")

CONFLICT_RESOLUTION_RULE = _eval.CONFLICT_RESOLUTION_RULE
INTERFACE = _eval.INTERFACE
REQUIRED_CASE_IDS = _eval.REQUIRED_CASE_IDS
evaluate_all = _eval.evaluate_all
evaluate_case = _eval.evaluate_case
load_fixture = _eval.load_fixture
load_manifest = _eval.load_manifest
reason_matches_expected = _eval.reason_matches_expected
generate_fixtures = _gen.generate


@pytest.fixture(scope="module", autouse=True)
def _ensure_fixtures():
    """Materialize fixtures from recipes before the suite runs."""
    generate_fixtures()


class TestPolicyNegativeVectors:
    """Shared PolicyVector@1 suite — every listed case has an expected decision."""

    def test_manifest_covers_required_cases(self):
        manifest = load_manifest()
        assert manifest["interface"] == INTERFACE
        assert manifest["task_id"] == "MCPP-048"
        ids = {c["id"] for c in manifest["cases"]}
        assert ids == set(REQUIRED_CASE_IDS)
        required = set(manifest["acceptance"]["cases_required"])
        assert required == set(REQUIRED_CASE_IDS)
        for case in manifest["cases"]:
            assert case["expected_decision"] in {
                "allow",
                "deny",
                "allow_with_obligations",
            }
            fixture_path = _VECTORS / case["file"]
            assert fixture_path.is_file(), f"missing fixture {fixture_path}"

    def test_recipes_index_matches_required_cases(self):
        recipes = json.loads((_VECTORS / "recipes.json").read_text(encoding="utf-8"))
        case_ids = {r["case"] for r in recipes["recipes"]}
        assert case_ids == set(REQUIRED_CASE_IDS)
        assert "conflict_resolution_rule" in recipes
        assert "prohibition" in recipes["conflict_resolution_rule"].lower()

    def test_conflict_resolution_rule_is_documented(self):
        manifest = load_manifest()
        readme = (_VECTORS / "README.md").read_text(encoding="utf-8")
        assert "prohibition" in manifest["conflict_resolution_rule"].lower()
        assert "prohibition" in CONFLICT_RESOLUTION_RULE.lower()
        assert "Deterministic conflict resolution" in readme
        assert "most restrictive" in readme.lower() or "prohibition" in readme.lower()

    def test_every_case_matches_expected_decision(self):
        results = evaluate_all()
        failures = []
        for case_id in REQUIRED_CASE_IDS:
            verdict = results[case_id]
            if not reason_matches_expected(verdict):
                failures.append(f"{case_id}: {verdict.failures} {verdict.to_dict()}")
        assert not failures, "policy vector mismatches:\n" + "\n".join(failures)

    @pytest.mark.parametrize("case_id", REQUIRED_CASE_IDS)
    def test_case_expected_decision_parametrized(self, case_id: str):
        fixture = load_fixture(case_id)
        assert fixture.get("expected") or fixture.get("expected_decision")
        verdict = evaluate_case(case_id, fixture)
        assert verdict.case_id == case_id
        assert verdict.ok, (
            f"{case_id}: expected={fixture.get('expected')} "
            f"got decision={verdict.decision} reason={verdict.reason_code} "
            f"failures={verdict.failures}"
        )

    def test_policy_version_mismatch_denies(self):
        verdict = evaluate_case("policy_version_mismatch")
        assert verdict.decision == "deny"
        assert verdict.reason_code == "policy_version_mismatch"
        assert verdict.ok

    def test_missing_context_denies(self):
        verdict = evaluate_case("missing_context")
        assert verdict.decision == "deny"
        assert verdict.reason_code == "missing_context"
        assert verdict.ok

    def test_stale_root_denies(self):
        verdict = evaluate_case("stale_root")
        assert verdict.decision == "deny"
        assert verdict.reason_code == "stale_root"
        assert verdict.ok

    def test_deadline_window_denies(self):
        verdict = evaluate_case("deadline")
        assert verdict.decision == "deny"
        assert verdict.reason_code == "no_matching_permission"
        assert verdict.ok

    def test_revoked_before_execution_denies(self):
        verdict = evaluate_case("revoked_before_execution")
        assert verdict.decision == "deny"
        assert verdict.reason_code == "revoked_before_execution"
        assert verdict.ok

    def test_allow_with_obligations(self):
        verdict = evaluate_case("allow_with_obligations")
        assert verdict.decision == "allow_with_obligations"
        assert verdict.granted is True
        assert len(verdict.metadata.get("obligations") or []) >= 1
        assert verdict.ok

    def test_unsatisfied_obligation_is_overdue(self):
        verdict = evaluate_case("unsatisfied_obligation")
        assert verdict.decision == "allow_with_obligations"
        statuses = {o.get("status") for o in (verdict.metadata.get("obligations") or [])}
        assert "overdue" in statuses
        assert verdict.ok

    def test_compensating_action_recorded(self):
        verdict = evaluate_case("compensating_action")
        assert verdict.decision == "allow_with_obligations"
        compensation = verdict.metadata.get("compensation") or []
        assert compensation
        actions = []
        for item in compensation:
            comp = item.get("compensation")
            if isinstance(comp, dict):
                actions.append(comp.get("action"))
            else:
                actions.append(comp)
        assert "rotate_secrets" in actions
        assert verdict.ok

    def test_conflicting_policies_prohibition_wins(self):
        """Documented deterministic rule: prohibition across the set wins."""
        verdict = evaluate_case("conflicting_policies")
        assert verdict.decision == "deny"
        assert verdict.reason_code == "prohibition_matched"
        assert "prohibition" in CONFLICT_RESOLUTION_RULE.lower()
        assert verdict.ok

    def test_decision_cid_deterministic_for_same_inputs(self):
        """Same logical inputs yield the same decision_cid (PolicyEvaluator@1)."""
        a = evaluate_case("policy_version_mismatch")
        b = evaluate_case("policy_version_mismatch")
        assert a.metadata["decision_cid"]
        assert a.metadata["decision_cid"] == b.metadata["decision_cid"]
