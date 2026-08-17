#!/usr/bin/env python3
"""PolicyVector@1 evaluator (shared by integration tests and direct runs).

Loads recipes/fixtures under this directory and asserts every required case
matches its expected decision using real PolicyEvaluator@1 code — no mocks.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

VECTOR_ROOT = Path(__file__).resolve().parent
FIXTURES = VECTOR_ROOT / "fixtures"
MANIFEST_PATH = VECTOR_ROOT / "manifest.json"
RECIPES_PATH = VECTOR_ROOT / "recipes.json"

_TESTS_PY = VECTOR_ROOT.parents[3] / "tests-py"
if str(_TESTS_PY) not in sys.path:
    sys.path.insert(0, str(_TESTS_PY))

from validators.policy_evaluation import PolicyEvaluator  # noqa: E402

def _load_generate_fixtures():
    """Import sibling generate_fixtures without colliding with other suites."""
    import importlib.util

    path = VECTOR_ROOT / "generate_fixtures.py"
    # Prefer already-registered unique module name (integration harness).
    existing = sys.modules.get("mcpp_policy_generate_fixtures")
    if existing is not None:
        return existing
    name = "mcpp_policy_generate_fixtures"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_gen = _load_generate_fixtures()
build_fixture = _gen.build_fixture
load_recipes = _gen.load_recipes
materialize_inputs = _gen.materialize_inputs

REQUIRED_CASE_IDS: Tuple[str, ...] = (
    "policy_version_mismatch",
    "missing_context",
    "stale_root",
    "deadline",
    "revoked_before_execution",
    "allow_with_obligations",
    "unsatisfied_obligation",
    "compensating_action",
    "conflicting_policies",
)

INTERFACE = "PolicyVector@1"
CONFLICT_RESOLUTION_RULE = (
    "When multiple policies are supplied, any matching prohibition across the "
    "entire set wins (most restrictive). Permissions and obligations are unioned "
    "with stable ordering by (clause_id, clause_type, action, source_index)."
)


@dataclass
class PolicyVectorVerdict:
    """Decision match result for one PolicyVector@1 case."""

    case_id: str
    decision: str
    granted: bool
    reason_code: Optional[str] = None
    matched_expected: bool = False
    failures: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    language: str = "python"

    @property
    def ok(self) -> bool:
        return self.matched_expected and not self.failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface": INTERFACE,
            "case_id": self.case_id,
            "decision": self.decision,
            "granted": self.granted,
            "reason_code": self.reason_code,
            "matched_expected": self.matched_expected,
            "ok": self.ok,
            "failures": list(self.failures),
            "language": self.language,
            "metadata": dict(self.metadata),
        }


def load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_fixture(case_id: str) -> Dict[str, Any]:
    path = FIXTURES / f"{case_id}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    # Fall back to materializing from recipes when fixtures are absent.
    data = load_recipes()
    shared = data.get("shared") or {}
    for recipe in data.get("recipes") or []:
        if recipe.get("case") == case_id:
            return build_fixture(recipe, shared)
    raise FileNotFoundError(f"missing policy fixture/recipe: {case_id}")


def load_all_recipes() -> List[Dict[str, Any]]:
    data = load_recipes()
    shared = data.get("shared") or {}
    return [build_fixture(r, shared) for r in (data.get("recipes") or [])]


def _evaluate_inputs(inputs: Mapping[str, Any]) -> Any:
    evaluator = PolicyEvaluator()
    kwargs: Dict[str, Any] = {}
    for key in (
        "policy",
        "policies",
        "delegation",
        "context_roots",
        "expected_context_roots",
        "required_context_keys",
        "logical_time",
        "prior_events",
        "policy_version",
        "signature",
    ):
        if key in inputs:
            kwargs[key] = inputs[key]
    return evaluator.evaluate(inputs.get("intent"), **kwargs)


def _compensation_action(item: Mapping[str, Any]) -> str:
    comp = item.get("compensation")
    if isinstance(comp, Mapping):
        return str(comp.get("action") or comp.get("type") or "")
    if isinstance(comp, str):
        return comp
    return ""


def evaluate_case(case_id: str, fixture: Optional[Mapping[str, Any]] = None) -> PolicyVectorVerdict:
    """Evaluate one PolicyVector@1 case against its expected decision."""
    data = dict(fixture or load_fixture(case_id))
    cid = str(data.get("id") or case_id)
    expected = dict(data.get("expected") or {})
    if not expected and data.get("expected_decision"):
        expected = {
            "decision": data.get("expected_decision"),
            "reason_code": data.get("expected_reason_code"),
        }

    inputs = dict(data.get("inputs") or {})
    # Recipes may still be unexpanded if fixture was hand-written with flags.
    if inputs.get("use_shared_intent") or inputs.get("use_shared_permission_policy"):
        recipes = load_recipes()
        for recipe in recipes.get("recipes") or []:
            if recipe.get("case") == cid:
                inputs = materialize_inputs(recipe, recipes.get("shared") or {})
                break

    decision_obj = _evaluate_inputs(inputs)
    decision = str(decision_obj.decision)
    granted = bool(decision_obj.granted)
    reason_code = decision_obj.reason_code
    failures: List[str] = []

    exp_decision = expected.get("decision")
    if exp_decision is not None and decision != exp_decision:
        failures.append(f"decision expected={exp_decision!r} got={decision!r}")

    if "granted" in expected and granted != bool(expected["granted"]):
        failures.append(f"granted expected={expected['granted']!r} got={granted!r}")

    exp_reason = expected.get("reason_code")
    if exp_reason is not None and reason_code != exp_reason:
        failures.append(f"reason_code expected={exp_reason!r} got={reason_code!r}")

    obligations = list(decision_obj.obligations or ())
    if expected.get("obligation_count_min") is not None:
        if len(obligations) < int(expected["obligation_count_min"]):
            failures.append(
                f"obligation_count expected>={expected['obligation_count_min']} got={len(obligations)}"
            )

    if expected.get("obligation_actions"):
        got_actions = {str(o.get("action")) for o in obligations}
        for act in expected["obligation_actions"]:
            if act not in got_actions:
                failures.append(f"missing obligation action {act!r} in {sorted(got_actions)}")

    if expected.get("obligation_status"):
        statuses = {str(o.get("status")) for o in obligations}
        if expected["obligation_status"] not in statuses:
            failures.append(
                f"obligation_status expected={expected['obligation_status']!r} got={sorted(statuses)}"
            )

    deadlines = list(decision_obj.deadlines or ())
    if expected.get("deadline_status"):
        d_statuses = {str(d.get("status")) for d in deadlines}
        if expected["deadline_status"] not in d_statuses:
            failures.append(
                f"deadline_status expected={expected['deadline_status']!r} got={sorted(d_statuses)}"
            )

    compensation = list(decision_obj.compensation or ())
    if expected.get("compensation_count_min") is not None:
        if len(compensation) < int(expected["compensation_count_min"]):
            failures.append(
                f"compensation_count expected>={expected['compensation_count_min']} "
                f"got={len(compensation)}"
            )

    if expected.get("compensation_actions"):
        got_comp = {_compensation_action(c) for c in compensation}
        for act in expected["compensation_actions"]:
            if act not in got_comp:
                failures.append(f"missing compensation action {act!r} in {sorted(got_comp)}")

    if cid == "conflicting_policies":
        # Documented deterministic rule: prohibition across the set wins.
        if decision != "deny" or reason_code != "prohibition_matched":
            failures.append(
                "conflict resolution rule violated: expected prohibition_matched deny"
            )

    meta = {
        "expected": expected,
        "justification": decision_obj.justification,
        "decision_cid": decision_obj.decision_cid,
        "policy_cid": decision_obj.policy_cid,
        "obligations": obligations,
        "deadlines": deadlines,
        "compensation": compensation,
        "fired_rules": list(decision_obj.fired_rules or ()),
        "conflict_resolution_rule": CONFLICT_RESOLUTION_RULE,
    }

    return PolicyVectorVerdict(
        case_id=cid,
        decision=decision,
        granted=granted,
        reason_code=reason_code,
        matched_expected=not failures,
        failures=failures,
        metadata=meta,
    )


def evaluate_all() -> Dict[str, PolicyVectorVerdict]:
    results: Dict[str, PolicyVectorVerdict] = {}
    for case_id in REQUIRED_CASE_IDS:
        results[case_id] = evaluate_case(case_id)
    return results


def reason_matches_expected(verdict: PolicyVectorVerdict) -> bool:
    return verdict.ok


def main() -> int:
    # Ensure fixtures exist for language runners / offline inspection.
    try:
        _gen.generate()
    except Exception as exc:  # pragma: no cover
        print(f"fixture generation warning: {exc}", file=sys.stderr)

    results = evaluate_all()
    failures = []
    for case_id in REQUIRED_CASE_IDS:
        v = results[case_id]
        status = "OK" if v.ok else "FAIL"
        reason = v.reason_code or "-"
        print(f"{status:4} {case_id:28} decision={v.decision:24} reason={reason}")
        if not v.ok:
            failures.append(f"{case_id}: {v.failures}")
    if failures:
        print("\nfailures:")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"\nall {len(REQUIRED_CASE_IDS)} PolicyVector@1 cases matched expected decisions")
    print(f"conflict rule: {CONFLICT_RESOLUTION_RULE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
