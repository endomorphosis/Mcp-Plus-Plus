#!/usr/bin/env python3
"""Materialize PolicyVector@1 fixtures from compact recipes.json.

Recipes remain the source of truth; fixtures are stable case envelopes for
evaluators and language runners. Run:

  python conformance/vectors/policy/generate_fixtures.py
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Mapping

VECTOR_ROOT = Path(__file__).resolve().parent
RECIPES_PATH = VECTOR_ROOT / "recipes.json"
FIXTURES = VECTOR_ROOT / "fixtures"
INTERFACE = "PolicyVector@1"
LANGUAGES = ["python", "typescript", "go", "rust"]


def load_recipes() -> Dict[str, Any]:
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))


def materialize_inputs(recipe: Mapping[str, Any], shared: Mapping[str, Any]) -> Dict[str, Any]:
    """Expand recipe input shorthand into PolicyEvaluator.evaluate kwargs."""
    raw = dict(recipe.get("inputs") or {})
    out: Dict[str, Any] = {}

    if raw.get("use_shared_intent"):
        out["intent"] = deepcopy(shared["intent"])
    if "intent" in raw:
        out["intent"] = deepcopy(raw["intent"])

    if raw.get("use_shared_permission_policy"):
        out["policy"] = deepcopy(shared["permission_policy"])
    if "policy" in raw:
        out["policy"] = deepcopy(raw["policy"])
    if "policies" in raw:
        out["policies"] = deepcopy(raw["policies"])

    for key in (
        "delegation",
        "context_roots",
        "expected_context_roots",
        "required_context_keys",
        "logical_time",
        "prior_events",
        "policy_version",
        "signature",
    ):
        if key in raw:
            out[key] = deepcopy(raw[key])

    if "logical_time" not in out and shared.get("logical_time"):
        out["logical_time"] = shared["logical_time"]

    return out


def build_fixture(recipe: Mapping[str, Any], shared: Mapping[str, Any]) -> Dict[str, Any]:
    case_id = str(recipe["case"])
    expected = dict(recipe.get("expected") or {})
    return {
        "id": case_id,
        "interface": INTERFACE,
        "task_id": "MCPP-048",
        "polarity": recipe.get("polarity") or "negative",
        "layer": recipe.get("layer") or "gate",
        "description": recipe.get("description") or "",
        "languages": list(LANGUAGES),
        "inputs": materialize_inputs(recipe, shared),
        "expected": expected,
        "expected_decision": expected.get("decision"),
        "expected_reason_code": expected.get("reason_code"),
        "conflict_resolution_rule": (
            "When multiple policies are supplied, any matching prohibition "
            "across the entire set wins (most restrictive)."
            if case_id == "conflicting_policies"
            else None
        ),
    }


def generate() -> List[str]:
    data = load_recipes()
    shared = data.get("shared") or {}
    FIXTURES.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for recipe in data.get("recipes") or []:
        fixture = build_fixture(recipe, shared)
        # Drop null conflict rule for non-conflict cases.
        if fixture.get("conflict_resolution_rule") is None:
            fixture.pop("conflict_resolution_rule", None)
        path = FIXTURES / f"{fixture['id']}.json"
        path.write_text(
            json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        written.append(str(path.relative_to(VECTOR_ROOT)))
    return written


def main() -> int:
    written = generate()
    print(f"generated {len(written)} fixtures under {FIXTURES}")
    for rel in written:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
