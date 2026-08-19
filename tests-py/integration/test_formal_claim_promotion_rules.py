"""FACP-010: executable promotion predicates and compatibility rules.

Acceptance (taskboard):
- Each predicate names necessary dimensions and evidence.
- Non-implications such as digest-to-truth, payment-to-authority,
  hermetic-to-live, and fixture-to-observed are executable negative rules.

This module evaluates promotion-rules.json directly (fail-closed). It does not
claim Lean-checked proofs (FACP-011/012) or language projections (FACP-013+).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "promotion-rules.json"
)
SPEC_PATH = REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "formal-claim-algebra-v1.md"
BASELINE = (
    REPO_ROOT
    / "implementation_plan"
    / "formal_assurance_control_plane"
    / "baseline"
)
CLAIM_INVENTORY_PATH = BASELINE / "claim_inventory.json"

RULES_SCHEMA = "facp/promotion-rules@1"
VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1"
TASK_ID = "FACP-010"
GOAL_ID = "FACP-G110"

REQUIRED_PREDICATES = (
    "production_supported",
    "effect_successful",
    "proof_reusable",
    "receipt_authoritative",
    "release_admissible",
)

REQUIRED_NEGATIVE_RULES = (
    "digest-to-truth",
    "payment-to-authority",
    "hermetic-to-live",
    "fixture-to-observed",
)

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


def _load_rules() -> dict[str, Any]:
    assert RULES_PATH.is_file(), f"missing promotion rules: {RULES_PATH}"
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _load_inventory() -> dict[str, Any]:
    assert CLAIM_INVENTORY_PATH.is_file(), CLAIM_INVENTORY_PATH
    return json.loads(CLAIM_INVENTORY_PATH.read_text(encoding="utf-8"))


def _as_set(values: Iterable[str] | None) -> set[str]:
    return set(values or ())


class PromotionRulesEngine:
    """Fail-closed evaluator for facp/promotion-rules@1."""

    def __init__(self, rules: Mapping[str, Any]) -> None:
        self.rules = rules
        self.predicates: Mapping[str, Any] = rules["predicates"]
        self.negative_rules = {
            row["id"]: row for row in rules["negative_rules"]
        }
        self.transitions = rules["transitions"]["by_dimension"]
        self.compat = rules["compatibility_rules"]
        self.eval_cfg = rules["evaluation"]

    def evidence_present(
        self, evidence: Mapping[str, Any] | None, required: Sequence[str]
    ) -> bool:
        bag = evidence or {}
        for key in required:
            if not bag.get(key):
                return False
        return True

    def dimensions_satisfied(
        self,
        envelope: Mapping[str, Any],
        necessary: Mapping[str, Sequence[str]],
    ) -> bool:
        for dim, allowed in necessary.items():
            value = envelope.get(dim)
            if value not in allowed:
                return False
        return True

    def predicate_holds(
        self,
        predicate_id: str,
        envelope: Mapping[str, Any],
        evidence: Mapping[str, Any] | None = None,
        claim_tokens: Sequence[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """Return (holds, rejection_codes)."""
        if predicate_id not in self.predicates:
            return False, ["UNKNOWN_PREDICATE"]

        pred = self.predicates[predicate_id]
        codes: list[str] = []

        if not self.dimensions_satisfied(envelope, pred["necessary_dimensions"]):
            codes.append(f"MISSING_DIMENSIONS:{predicate_id}")

        if self.eval_cfg["predicate_requires_all_necessary_evidence"]:
            if not self.evidence_present(evidence, pred["necessary_evidence"]):
                codes.append(f"MISSING_EVIDENCE:{predicate_id}")

        # Absolute and evidence-gated negative rules that would block this claim.
        for rule_id in pred.get("blocked_by_negative_rules", []):
            blocked, code = self.negative_rule_blocks(
                rule_id,
                envelope=envelope,
                evidence=evidence,
                claim_tokens=claim_tokens,
                claimed_predicate=predicate_id,
            )
            if blocked:
                codes.append(code)

        # Legacy ladder / single-dimension tokens never satisfy alone.
        tokens = set(claim_tokens or ())
        if tokens & {"legacy_total_ladder_rank", "single_dimension_value"}:
            if self.compat["legacy_total_ladder_rank_alone_never_satisfies_predicates"]:
                # Only reject when the product is not independently satisfied.
                if codes:
                    codes.append("NONIMP_SINGLE_DIMENSION_TO_PRODUCT")

        return (len(codes) == 0), codes

    def _antecedent_matches(
        self,
        antecedent: Mapping[str, Any],
        envelope: Mapping[str, Any],
        claim_tokens: Sequence[str] | None,
    ) -> bool:
        dims = antecedent.get("dimensions") or {}
        for dim, values in dims.items():
            if envelope.get(dim) in values:
                return True
        tokens = set(claim_tokens or ())
        claim_need = set(antecedent.get("claim_tokens") or ())
        if claim_need and tokens & claim_need:
            return True
        # Antecedent with neither matching dims nor tokens does not fire.
        if dims or claim_need:
            return False
        return False

    def _consequent_claimed(
        self,
        consequent: Mapping[str, Any],
        envelope: Mapping[str, Any],
        claimed_predicate: str | None,
    ) -> bool:
        dims = consequent.get("dimensions") or {}
        for dim, values in dims.items():
            if envelope.get(dim) in values:
                return True
        preds = set(consequent.get("predicates") or ())
        if claimed_predicate and claimed_predicate in preds:
            return True
        return False

    def negative_rule_blocks(
        self,
        rule_id: str,
        *,
        envelope: Mapping[str, Any],
        evidence: Mapping[str, Any] | None = None,
        claim_tokens: Sequence[str] | None = None,
        claimed_predicate: str | None = None,
        attempted_consequent_envelope: Mapping[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Return (blocked, rejection_code) for an executable negative rule."""
        rule = self.negative_rules.get(rule_id)
        if rule is None:
            return True, "UNKNOWN_NEGATIVE_RULE"

        assert rule.get("executable") is True, rule_id
        target = attempted_consequent_envelope or envelope
        antecedent = rule["antecedent"]
        consequent = rule["consequent"]

        if not self._antecedent_matches(antecedent, envelope, claim_tokens):
            # For absolute transition-style checks, allow evaluating against
            # the attempted consequent alone when antecedent is a prior state
            # encoded via claim_tokens or explicit prior envelope fields.
            if not self._antecedent_matches(antecedent, target, claim_tokens):
                return False, ""

        if not self._consequent_claimed(consequent, target, claimed_predicate):
            return False, ""

        required = list(consequent.get("independent_evidence_required") or [])
        if rule.get("absolute") is True or not required:
            # Absolute non-implication: no evidence bag bridges the gap.
            return True, rule["rejection_code"]

        if not self.evidence_present(evidence, required):
            return True, rule["rejection_code"]

        return False, ""

    def transition_allowed(
        self,
        dimension: str,
        from_value: str,
        to_value: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> tuple[bool, str]:
        table = self.transitions.get(dimension)
        if table is None:
            return False, "UNKNOWN_DIMENSION"

        for row in table.get("forbidden", []):
            if row.get("cross_dimension") or row.get("claim_token_transition"):
                continue
            if row["from"] == from_value and row["to"] == to_value:
                when_missing = row.get("when_missing_evidence")
                if when_missing is not None:
                    if self.evidence_present(evidence, when_missing):
                        continue
                    return False, self.negative_rules[row["negative_rule"]][
                        "rejection_code"
                    ]
                if row.get("requires_evidence_never_sufficient_by_relabel"):
                    return False, f"FORBIDDEN_RELABEL:{dimension}:{from_value}->{to_value}"
                code = self.negative_rules.get(row.get("negative_rule", ""), {}).get(
                    "rejection_code",
                    f"FORBIDDEN_TRANSITION:{dimension}",
                )
                return False, code

        for row in table.get("allowed", []):
            if row["from"] == from_value and row["to"] == to_value:
                required = row.get("requires_evidence") or []
                if required and not self.evidence_present(evidence, required):
                    return False, f"MISSING_TRANSITION_EVIDENCE:{dimension}"
                return True, ""

        # Fail closed on unknown transitions.
        assert self.rules["unknown_transition_policy"] == "reject"
        return False, f"UNKNOWN_TRANSITION:{dimension}:{from_value}->{to_value}"

    def legacy_mapping_satisfies_predicate(
        self, mapping_id: str, predicate_id: str
    ) -> bool:
        for row in self.compat["mappings"]:
            if row["id"] == mapping_id:
                if predicate_id in (row.get("satisfies_predicates") or []):
                    return True
                if predicate_id in (row.get("forbidden_predicates") or []):
                    return False
                return False
        return False


@pytest.fixture(scope="module")
def rules() -> dict[str, Any]:
    return _load_rules()


@pytest.fixture(scope="module")
def engine(rules: dict[str, Any]) -> PromotionRulesEngine:
    return PromotionRulesEngine(rules)


@pytest.fixture(scope="module")
def inventory() -> dict[str, Any]:
    return _load_inventory()


def _weak_envelope(**overrides: str) -> dict[str, str]:
    base = {
        "origin": "absent",
        "integrity": "unchecked",
        "authority": "unchecked",
        "policy": "unchecked",
        "proof": "none",
        "freshness": "stale",
        "effect": "not_started",
        "environment": "hermetic",
        "review": "unreviewed",
    }
    base.update(overrides)
    return base


def _strong_production_envelope() -> dict[str, str]:
    return {
        "origin": "live_observed",
        "integrity": "signature_valid",
        "authority": "valid",
        "policy": "allowed",
        "proof": "verified",
        "freshness": "current",
        "effect": "observed",
        "environment": "live",
        "review": "human_reviewed",
    }


def _all_evidence_for(rules: Mapping[str, Any]) -> dict[str, bool]:
    bag: dict[str, bool] = {}
    for pred in rules["predicates"].values():
        for key in pred["necessary_evidence"]:
            bag[key] = True
    # Extra independent-evidence keys referenced by negative rules / transitions.
    extras = [
        "argument_bound_delegation",
        "non_revoked_ucan",
        "canonical_digest_match",
        "authentic_signature",
        "obligations_discharged",
        "human_legal_clearance",
        "independent_effect_observation",
        "named_current_verifier",
        "verifier_admission_closure",
        "live_qualification_receipt",
        "current_capability_admission",
        "authenticated_host_policy_decision",
    ]
    for key in extras:
        bag[key] = True
    return bag


def test_rules_artifact_identifies_facp_010(rules: dict[str, Any]) -> None:
    assert rules["schema"] == RULES_SCHEMA
    assert rules["schema_version"] == 1
    assert rules["task_id"] == TASK_ID
    assert rules["goal_id"] == GOAL_ID
    assert rules["vocabulary_schema"] == VOCAB_SCHEMA
    assert rules["fail_closed"] is True
    assert rules["unknown_transition_policy"] == "reject"
    assert rules["label_only_promotion_forbidden"] is True
    assert rules["permissive_unknown_transition_forbidden"] is True
    assert RULES_PATH.is_file()


def test_predicates_match_vocabulary_and_inventory(
    rules: dict[str, Any], inventory: dict[str, Any]
) -> None:
    expected = inventory["canonical_claim_vocabulary"]["promotion_predicates"]
    assert list(rules["predicate_order"]) == list(REQUIRED_PREDICATES)
    assert list(rules["predicates"]) == list(REQUIRED_PREDICATES)
    assert expected == list(REQUIRED_PREDICATES)
    assert list(rules["dimension_order"]) == list(DIMENSION_ORDER)


def test_each_predicate_names_necessary_dimensions_and_evidence(
    rules: dict[str, Any], inventory: dict[str, Any]
) -> None:
    dim_values = inventory["canonical_claim_vocabulary"]["evidence_dimensions"]
    for pred_id in REQUIRED_PREDICATES:
        pred = rules["predicates"][pred_id]
        assert pred["id"] == pred_id
        assert isinstance(pred["reading"], str) and pred["reading"].strip()
        necessary = pred["necessary_dimensions"]
        assert isinstance(necessary, dict) and necessary, pred_id
        for dim, values in necessary.items():
            assert dim in DIMENSION_ORDER, f"{pred_id}:{dim}"
            assert values, f"{pred_id}:{dim} empty"
            allowed = set(dim_values[dim])
            for value in values:
                assert value in allowed, f"{pred_id}:{dim}={value}"
        evidence = pred["necessary_evidence"]
        assert isinstance(evidence, list) and evidence, pred_id
        assert len(evidence) == len(set(evidence)), pred_id
        for key in evidence:
            assert isinstance(key, str) and key.strip() == key and key
        blocked = pred["blocked_by_negative_rules"]
        assert isinstance(blocked, list) and blocked, pred_id
        for rule_id in blocked:
            assert any(r["id"] == rule_id for r in rules["negative_rules"]), rule_id


def test_required_negative_rules_are_executable(rules: dict[str, Any]) -> None:
    by_id = {row["id"]: row for row in rules["negative_rules"]}
    assert list(rules["required_negative_rule_ids"]) == list(REQUIRED_NEGATIVE_RULES)
    for rule_id in REQUIRED_NEGATIVE_RULES:
        row = by_id[rule_id]
        assert row["kind"] == "non_implication"
        assert row["executable"] is True
        assert row["rejection_code"]
        assert "antecedent" in row and "consequent" in row
        assert "independent_evidence_required" in row["consequent"]


def test_all_negative_rules_are_executable_and_unique(rules: dict[str, Any]) -> None:
    ids = [row["id"] for row in rules["negative_rules"]]
    assert len(ids) == len(set(ids))
    codes = [row["rejection_code"] for row in rules["negative_rules"]]
    assert len(codes) == len(set(codes))
    for row in rules["negative_rules"]:
        assert row["executable"] is True
        assert row["kind"] == "non_implication"
        assert isinstance(row.get("absolute"), bool)


def test_digest_to_truth_negative_rule_is_executable(
    engine: PromotionRulesEngine,
) -> None:
    # Digest authenticity alone must not imply verified proof.
    prior = _weak_envelope(integrity="digest_valid", proof="candidate")
    attempted = dict(prior)
    attempted["proof"] = "verified"
    blocked, code = engine.negative_rule_blocks(
        "digest-to-truth",
        envelope=prior,
        evidence={},
        attempted_consequent_envelope=attempted,
    )
    assert blocked is True
    assert code == "NONIMP_DIGEST_TO_TRUTH"

    # Independent verifier evidence may admit verified without treating digest as truth.
    blocked2, _ = engine.negative_rule_blocks(
        "digest-to-truth",
        envelope=prior,
        evidence={
            "named_current_verifier": True,
            "verifier_admission_closure": True,
        },
        attempted_consequent_envelope=attempted,
    )
    assert blocked2 is False

    holds, codes = engine.predicate_holds(
        "proof_reusable",
        envelope=_weak_envelope(
            integrity="digest_valid",
            proof="verified",
            freshness="current",
        ),
        evidence={},
    )
    assert holds is False
    assert any("MISSING_EVIDENCE" in c or "NONIMP" in c for c in codes)


def test_payment_to_authority_negative_rule_is_executable(
    engine: PromotionRulesEngine,
) -> None:
    prior = _weak_envelope(authority="absent")
    attempted = dict(prior)
    attempted["authority"] = "valid"
    blocked, code = engine.negative_rule_blocks(
        "payment-to-authority",
        envelope=prior,
        claim_tokens=["payment_or_confirmation"],
        evidence={},
        attempted_consequent_envelope=attempted,
    )
    assert blocked is True
    assert code == "NONIMP_PAYMENT_TO_AUTHORITY"

    # Payment still blocked for receipt_authoritative without real delegation.
    holds, codes = engine.predicate_holds(
        "receipt_authoritative",
        envelope=_weak_envelope(
            origin="live_observed",
            integrity="signature_valid",
            authority="valid",
            policy="allowed",
            freshness="current",
        ),
        evidence={"signed_receipt": True},
        claim_tokens=["payment_or_confirmation"],
    )
    assert holds is False
    assert "NONIMP_PAYMENT_TO_AUTHORITY" in codes


def test_hermetic_to_live_negative_rule_is_executable(
    engine: PromotionRulesEngine,
) -> None:
    prior = _weak_envelope(environment="hermetic")
    attempted = dict(prior)
    attempted["environment"] = "live"
    blocked, code = engine.negative_rule_blocks(
        "hermetic-to-live",
        envelope=prior,
        evidence={"live_qualification_receipt": True},
        attempted_consequent_envelope=attempted,
    )
    assert blocked is True
    assert code == "NONIMP_HERMETIC_TO_LIVE"

    allowed, tcode = engine.transition_allowed(
        "environment", "hermetic", "live", evidence={"live_qualification_receipt": True}
    )
    assert allowed is False
    assert tcode == "NONIMP_HERMETIC_TO_LIVE"

    holds, codes = engine.predicate_holds(
        "production_supported",
        envelope=_strong_production_envelope(),
        evidence=_all_evidence_for(engine.rules),
        claim_tokens=[],
    )
    # Strong live envelope should hold when not starting from hermetic antecedent.
    assert holds is True
    assert codes == []

    # Same product values claimed while still carrying hermetic antecedent token path:
    hermetic_claim = dict(_strong_production_envelope())
    hermetic_claim["environment"] = "live"
    blocked2, code2 = engine.negative_rule_blocks(
        "hermetic-to-live",
        envelope=_weak_envelope(environment="hermetic"),
        attempted_consequent_envelope=hermetic_claim,
    )
    assert blocked2 is True
    assert code2 == "NONIMP_HERMETIC_TO_LIVE"


def test_fixture_to_observed_negative_rule_is_executable(
    engine: PromotionRulesEngine,
) -> None:
    prior = _weak_envelope(origin="fixture", effect="not_started")
    attempted = dict(prior)
    attempted["origin"] = "live_observed"
    attempted["effect"] = "observed"
    blocked, code = engine.negative_rule_blocks(
        "fixture-to-observed",
        envelope=prior,
        evidence={"independent_effect_observation": True},
        attempted_consequent_envelope=attempted,
    )
    assert blocked is True
    assert code == "NONIMP_FIXTURE_TO_OBSERVED"

    allowed, tcode = engine.transition_allowed(
        "origin", "fixture", "live_observed"
    )
    assert allowed is False
    assert tcode == "NONIMP_FIXTURE_TO_OBSERVED"

    holds, codes = engine.predicate_holds(
        "effect_successful",
        envelope=_weak_envelope(
            origin="fixture",
            integrity="digest_valid",
            authority="valid",
            policy="allowed",
            freshness="current",
            effect="observed",
        ),
        evidence={
            "independent_effect_observation": True,
            "admission_token": True,
        },
    )
    assert holds is False
    assert "NONIMP_FIXTURE_TO_OBSERVED" in codes or any(
        "MISSING_DIMENSIONS" in c for c in codes
    )


def test_predicate_positive_path_requires_full_product(
    engine: PromotionRulesEngine, rules: dict[str, Any]
) -> None:
    evidence = _all_evidence_for(rules)
    envelope = _strong_production_envelope()

    for pred_id in REQUIRED_PREDICATES:
        holds, codes = engine.predicate_holds(pred_id, envelope, evidence)
        assert holds is True, (pred_id, codes)

    # Drop one necessary dimension -> fail closed.
    broken = dict(envelope)
    broken["freshness"] = "stale"
    for pred_id in REQUIRED_PREDICATES:
        holds, codes = engine.predicate_holds(pred_id, broken, evidence)
        assert holds is False, pred_id
        assert codes


def test_each_predicate_fails_without_named_evidence(
    engine: PromotionRulesEngine, rules: dict[str, Any]
) -> None:
    envelope = _strong_production_envelope()
    full = _all_evidence_for(rules)
    for pred_id, pred in rules["predicates"].items():
        for key in pred["necessary_evidence"]:
            bag = dict(full)
            bag[key] = False
            holds, codes = engine.predicate_holds(pred_id, envelope, bag)
            assert holds is False, f"{pred_id} should require {key}"
            assert f"MISSING_EVIDENCE:{pred_id}" in codes


def test_unknown_transition_is_rejected(engine: PromotionRulesEngine) -> None:
    allowed, code = engine.transition_allowed(
        "freshness", "withdrawn", "current"
    )
    assert allowed is False
    assert code == "NONIMP_STALE_TO_CURRENT"

    allowed2, code2 = engine.transition_allowed(
        "origin", "live_observed", "fixture"
    )
    assert allowed2 is False
    assert code2.startswith("UNKNOWN_TRANSITION:")


def test_compatibility_rules_never_satisfy_predicates_alone(
    engine: PromotionRulesEngine, rules: dict[str, Any]
) -> None:
    compat = rules["compatibility_rules"]
    assert compat["legacy_total_ladder_rank_alone_never_satisfies_predicates"] is True
    assert compat["unsafe_promotion_default"] is False
    assert compat["conservative_legacy_mappings"] is True
    assert compat["discovery_is_not_completion"] is True
    assert set(compat["forbidden_generic_fields"]) == {
        "success",
        "available",
        "supported",
        "verified",
        "proven",
    }

    for row in compat["mappings"]:
        assert row["unsafe_promotion"] is False
        assert row.get("satisfies_predicates") == []
        for pred_id in REQUIRED_PREDICATES:
            assert engine.legacy_mapping_satisfies_predicate(row["id"], pred_id) is False


def test_spec_non_implications_are_covered_by_executable_rules(
    rules: dict[str, Any],
) -> None:
    assert SPEC_PATH.is_file()
    spec = SPEC_PATH.read_text(encoding="utf-8")
    # Spot-check that the normative prose and FACP-010 artifact stay aligned.
    for needle in (
        "digest",
        "payment",
        "hermetic",
        "fixture",
        "production_supported",
        "FACP-010",
    ):
        assert needle.lower() in spec.lower()

    ids = {row["id"] for row in rules["negative_rules"]}
    for required in REQUIRED_NEGATIVE_RULES:
        assert required in ids


def test_evaluation_contract_is_fail_closed(rules: dict[str, Any]) -> None:
    evaluation = rules["evaluation"]
    assert evaluation["predicate_requires_all_necessary_dimensions"] is True
    assert evaluation["predicate_requires_all_necessary_evidence"] is True
    assert evaluation["negative_rules_are_fail_closed"] is True
    assert evaluation["legacy_mapping_cannot_satisfy_predicates_alone"] is True
    assert tuple(evaluation["envelope_fields"]) == DIMENSION_ORDER


def test_transition_tables_cover_all_dimensions(rules: dict[str, Any]) -> None:
    by_dim = rules["transitions"]["by_dimension"]
    assert set(by_dim) == set(DIMENSION_ORDER)
    assert rules["transitions"]["unknown_policy"] == "reject"
    for dim, table in by_dim.items():
        assert "allowed" in table and "forbidden" in table
        # Every forbidden row that names a negative_rule must resolve.
        for row in table["forbidden"]:
            rule_id = row.get("negative_rule")
            if rule_id:
                assert any(r["id"] == rule_id for r in rules["negative_rules"]), (
                    dim,
                    rule_id,
                )


def test_candidate_proof_cannot_become_reusable_without_verifier(
    engine: PromotionRulesEngine,
) -> None:
    envelope = _weak_envelope(
        integrity="digest_valid",
        proof="verified",
        freshness="current",
    )
    holds, codes = engine.predicate_holds(
        "proof_reusable",
        envelope,
        evidence={},
        claim_tokens=[],
    )
    assert holds is False
    assert f"MISSING_EVIDENCE:proof_reusable" in codes

    # Transition candidate -> verified without verifier evidence is rejected.
    allowed, code = engine.transition_allowed(
        "proof", "candidate", "verified", evidence={}
    )
    assert allowed is False
    assert code in {
        "NONIMP_CANDIDATE_TO_VERIFIED",
        "MISSING_TRANSITION_EVIDENCE:proof",
    }


def test_release_admissible_requires_rights_and_immutable_closure(
    engine: PromotionRulesEngine, rules: dict[str, Any]
) -> None:
    envelope = _strong_production_envelope()
    evidence = _all_evidence_for(rules)
    holds, _ = engine.predicate_holds("release_admissible", envelope, evidence)
    assert holds is True

    blocked, code = engine.negative_rule_blocks(
        "mutable-dependency-to-release",
        envelope=envelope,
        claim_tokens=["mutable_vcs_dependency"],
        evidence={},
        claimed_predicate="release_admissible",
    )
    assert blocked is True
    assert code == "NONIMP_MUTABLE_DEP_TO_RELEASE"

    blocked2, code2 = engine.negative_rule_blocks(
        "license-conflict-to-release",
        envelope=envelope,
        claim_tokens=["license_conflict"],
        evidence={"rights_resolution": False},
        claimed_predicate="release_admissible",
    )
    assert blocked2 is True
    assert code2 == "NONIMP_LICENSE_TO_RELEASE"
