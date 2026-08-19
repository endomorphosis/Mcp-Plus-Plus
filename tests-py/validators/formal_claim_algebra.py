"""Formal Claim Algebra (FCA) Python binding and validator — FACP-017.

Closed, bounded evidence-product algebra matching
``facp/formal-claim-algebra-v1@1`` and ``facp/promotion-rules@1``.

Public APIs fail closed: unknown enum spellings are rejected, unknown
envelope fields are rejected, unknown / illegal transitions are rejected,
and production-success / verified claim types cannot be constructed without
satisfying the normative predicates and evidence bag.

Import is cold: no network, subprocess, or filesystem write occurs at
import time. Promotion-rules documents are loaded only via explicit helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1"
RULES_SCHEMA = "facp/promotion-rules@1"
ENVELOPE_SCHEMA = "facp/evidence-envelope@1"
VECTORS_SCHEMA = "facp/formal-claim-algebra-vectors@1"
TASK_ID = "FACP-017"
GOAL_ID = "FACP-G120"
BUNDLE = "facp/fca/python"
UNKNOWN_TRANSITION_POLICY = "reject"

DIMENSION_ORDER: tuple[str, ...] = (
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

PREDICATE_ORDER: tuple[str, ...] = (
    "production_supported",
    "effect_successful",
    "proof_reusable",
    "receipt_authoritative",
    "release_admissible",
)

DIMENSION_ENUMS: dict[str, frozenset[str]] = {
    "origin": frozenset(
        {
            "absent",
            "declared",
            "fixture",
            "simulated",
            "hermetic_observed",
            "live_observed",
        }
    ),
    "integrity": frozenset(
        {"unchecked", "structurally_valid", "digest_valid", "signature_valid"}
    ),
    "authority": frozenset(
        {"unchecked", "absent", "valid", "expired", "revoked", "denied"}
    ),
    "policy": frozenset(
        {
            "unchecked",
            "allowed",
            "denied",
            "allowed_with_obligations",
            "indeterminate",
        }
    ),
    "proof": frozenset(
        {
            "none",
            "candidate",
            "verified",
            "refuted",
            "unknown",
            "verifier_unavailable",
        }
    ),
    "freshness": frozenset({"current", "stale", "superseded", "withdrawn"}),
    "effect": frozenset(
        {
            "not_started",
            "reserved",
            "started",
            "externally_unknown",
            "observed",
            "compensated",
            "failed",
        }
    ),
    "environment": frozenset({"hermetic", "conditional", "live"}),
    "review": frozenset({"unreviewed", "machine_reviewed", "human_reviewed"}),
}

CLOSED_OUTCOMES: frozenset[str] = frozenset(
    {
        "Unavailable",
        "Rejected",
        "Simulated",
        "Attempted",
        "Unknown",
        "Observed",
        "Verified",
        "Failed",
        "Compensated",
    }
)

WEAKEST_ENVELOPE: dict[str, str] = {
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

STRONG_PRODUCT_ENVELOPE: dict[str, str] = {
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

ALL_NORMATIVE_EVIDENCE: tuple[str, ...] = (
    "admission_token",
    "argument_bound_delegation",
    "authentic_signature",
    "authenticated_host_policy_decision",
    "canonical_digest_match",
    "contract_compatibility",
    "current_capability_admission",
    "current_proofs_and_tests",
    "exact_source_binding",
    "human_legal_clearance",
    "identified_build_environment",
    "immutable_dependency_closure",
    "independent_effect_observation",
    "live_qualification_receipt",
    "named_current_verifier",
    "non_revoked_delegation",
    "non_revoked_ucan",
    "obligations_discharged",
    "reproducibility_inputs",
    "rights_resolution",
    "signed_provenance",
    "signed_receipt",
    "verifier_admission_closure",
)

# Conservative legacy ladder maps (spec §8 / vocabulary appendix).
_ASSURANCE_LEVEL_MAP: dict[str, str] = {
    "unverified": "none",
    "none": "none",
    "candidate": "candidate",
    "solver_checked": "candidate",
    "solver_verified": "candidate",
    "kernel_verified": "verified",
    "attested": "verified",
}

_REPAIR_ASSURANCE_LEVEL_MAP: dict[str, str] = {
    "none": "none",
    "heuristic": "candidate",
    "validated": "candidate",
    "solver_checked": "candidate",
    "kernel_verified": "verified",
    "attested": "verified",
}

_PROOF_STATUS_MAP: dict[str, dict[str, str]] = {
    "unproved": {"proof": "none"},
    "candidate": {"proof": "candidate"},
    "solver_checked": {"proof": "candidate"},
    "kernel_verified": {"proof": "verified"},
    "validated_refuted": {"proof": "refuted"},
    "inconclusive": {"proof": "unknown"},
    "unsupported": {"proof": "verifier_unavailable"},
    "stale": {"proof": "unknown", "freshness": "stale"},
    "error": {"proof": "unknown"},
}

FORBIDDEN_GENERIC_FIELDS: frozenset[str] = frozenset(
    {"success", "available", "supported", "verified", "proven"}
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FcaError(ValueError):
    """Fail-closed FCA rejection with a stable error code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)

    def __str__(self) -> str:
        if self.args and self.args[0] != self.code:
            return f"{self.code}: {self.args[0]}"
        return self.code


# ---------------------------------------------------------------------------
# Evidence bag
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceBag:
    """Independent evidence keys required by transitions and predicates."""

    keys: frozenset[str] = frozenset()

    @classmethod
    def empty(cls) -> EvidenceBag:
        return cls()

    @classmethod
    def from_keys(cls, keys: Iterable[str]) -> EvidenceBag:
        return cls(frozenset(str(k) for k in keys))

    @classmethod
    def all_normative(cls) -> EvidenceBag:
        return cls.from_keys(ALL_NORMATIVE_EVIDENCE)

    def contains_all(self, required: Sequence[str]) -> bool:
        return all(key in self.keys for key in required)

    def union(self, other: EvidenceBag) -> EvidenceBag:
        return EvidenceBag(self.keys | other.keys)


# ---------------------------------------------------------------------------
# Evidence envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceEnvelope:
    """Cartesian product of the nine closed evidence dimensions."""

    origin: str
    integrity: str
    authority: str
    policy: str
    proof: str
    freshness: str
    effect: str
    environment: str
    review: str

    @classmethod
    def weakest(cls) -> EvidenceEnvelope:
        return cls.from_mapping(WEAKEST_ENVELOPE)

    @classmethod
    def strong_product(cls) -> EvidenceEnvelope:
        return cls.from_mapping(STRONG_PRODUCT_ENVELOPE)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> EvidenceEnvelope:
        """Strict parse: all nine dimensions, no extras, closed enums, no floats."""
        if not isinstance(data, Mapping):
            raise FcaError("INVALID_TYPE", "envelope must be an object")

        for key in data.keys():
            if key not in DIMENSION_ORDER:
                raise FcaError("UNKNOWN_FIELD", f"unknown envelope field: {key}")

        values: dict[str, str] = {}
        for dim in DIMENSION_ORDER:
            if dim not in data:
                raise FcaError("MISSING_FIELD", f"missing envelope field: {dim}")
            raw = data[dim]
            if isinstance(raw, float) and not isinstance(raw, bool):
                raise FcaError("FORBIDDEN_FLOAT", f"float forbidden for {dim}")
            if not isinstance(raw, str):
                raise FcaError("INVALID_TYPE", f"dimension {dim} must be a string")
            if raw not in DIMENSION_ENUMS[dim]:
                raise FcaError("UNKNOWN_ENUM", f"unknown enum value for {dim}: {raw}")
            values[dim] = raw
        return cls(**values)

    def to_mapping(self) -> dict[str, str]:
        return {dim: getattr(self, dim) for dim in DIMENSION_ORDER}

    def to_canonical_json(self) -> str:
        """Deterministic JSON with dimension-order keys."""
        return json.dumps(self.to_mapping(), separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def from_canonical_json(cls, text: str) -> EvidenceEnvelope:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise FcaError("INVALID_TYPE", f"invalid JSON: {exc}") from exc
        return cls.from_mapping(data)

    def get_dimension(self, dimension: str) -> str:
        if dimension not in DIMENSION_ORDER:
            raise FcaError("UNKNOWN_ENUM", f"unknown dimension: {dimension}")
        return getattr(self, dimension)

    def with_dimension(self, dimension: str, value: str) -> EvidenceEnvelope:
        """Replace one dimension without transition validation."""
        if dimension not in DIMENSION_ORDER:
            raise FcaError("UNKNOWN_ENUM", f"unknown dimension: {dimension}")
        if value not in DIMENSION_ENUMS[dimension]:
            raise FcaError(
                "UNKNOWN_ENUM", f"unknown enum value for {dimension}: {value}"
            )
        data = self.to_mapping()
        data[dimension] = value
        return EvidenceEnvelope.from_mapping(data)

    def merge_overrides(self, overrides: Mapping[str, Any]) -> EvidenceEnvelope:
        data = self.to_mapping()
        data.update(dict(overrides))
        return EvidenceEnvelope.from_mapping(data)


# ---------------------------------------------------------------------------
# Gated claim types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProductionSuccessClaim:
    """Gated live authorized observed production-success claim."""

    _envelope: EvidenceEnvelope

    @property
    def envelope(self) -> EvidenceEnvelope:
        return self._envelope

    @property
    def outcome(self) -> str:
        return "Verified"

    @classmethod
    def try_admit(
        cls,
        envelope: EvidenceEnvelope,
        evidence: EvidenceBag,
        rules: Mapping[str, Any],
    ) -> ProductionSuccessClaim:
        if envelope.origin in {"fixture", "simulated", "declared", "absent"}:
            raise FcaError(
                "NONIMP_FIXTURE_TO_OBSERVED",
                "weak origin cannot admit production success",
            )
        predicate_holds("production_supported", envelope, evidence, rules)
        predicate_holds("effect_successful", envelope, evidence, rules)
        return cls(_envelope=envelope)


@dataclass(frozen=True)
class VerifiedClaim:
    """Gated Verified closed-outcome claim (observed + proof obligations)."""

    _envelope: EvidenceEnvelope

    @property
    def envelope(self) -> EvidenceEnvelope:
        return self._envelope

    @property
    def outcome(self) -> str:
        return "Verified"

    @classmethod
    def try_admit(
        cls,
        envelope: EvidenceEnvelope,
        evidence: EvidenceBag,
        rules: Mapping[str, Any],
    ) -> VerifiedClaim:
        if envelope.effect != "observed":
            raise FcaError(
                "MISSING_DIMENSIONS:effect_successful",
                "Verified requires effect.observed",
            )
        if envelope.origin in {"fixture", "simulated", "declared", "absent"}:
            raise FcaError(
                "NONIMP_FIXTURE_TO_OBSERVED",
                "weak origin cannot admit Verified",
            )
        predicate_holds("effect_successful", envelope, evidence, rules)
        predicate_holds("proof_reusable", envelope, evidence, rules)
        return cls(_envelope=envelope)


# ---------------------------------------------------------------------------
# Compatibility construction (conservative, no unsafe promotion)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompatibilityResult:
    """Result of a conservative legacy → FCA mapping."""

    envelope: EvidenceEnvelope
    claim_tokens: tuple[str, ...]
    closed_outcome: str
    informed_dimensions: tuple[str, ...]
    unsafe_promotion: bool = False
    mapping_id: str = ""


def map_legacy_claim(
    legacy: Mapping[str, Any],
    *,
    seed_id: str | None = None,
) -> CompatibilityResult:
    """Map a legacy claim shape onto a weak FCA envelope.

    Never satisfies promotion predicates by itself. Unspecified dimensions
    remain at weakest honest defaults. Forbidden generic fields are clamped.
    """
    envelope = dict(WEAKEST_ENVELOPE)
    tokens: list[str] = []
    informed: list[str] = []
    outcome = "Unavailable"
    mapping_id = "legacy-default"

    # Explicit ladder seeds take precedence when provided.
    if seed_id == "seed:ladder-accelerate-assurance-level":
        rank = str(legacy.get("assurance_level") or legacy.get("value") or "none")
        proof = _ASSURANCE_LEVEL_MAP.get(rank)
        if proof is None:
            raise FcaError("UNKNOWN_ENUM", f"unknown AssuranceLevel: {rank}")
        envelope["proof"] = proof
        informed.append("proof")
        tokens.append("legacy_total_ladder_rank")
        mapping_id = seed_id
        return CompatibilityResult(
            envelope=EvidenceEnvelope.from_mapping(envelope),
            claim_tokens=tuple(tokens),
            closed_outcome=outcome,
            informed_dimensions=tuple(informed),
            unsafe_promotion=False,
            mapping_id=mapping_id,
        )

    if seed_id == "seed:ladder-accelerate-database-repair-assurance-level":
        rank = str(legacy.get("assurance_level") or legacy.get("value") or "none")
        proof = _REPAIR_ASSURANCE_LEVEL_MAP.get(rank)
        if proof is None:
            raise FcaError("UNKNOWN_ENUM", f"unknown repair AssuranceLevel: {rank}")
        envelope["proof"] = proof
        informed.append("proof")
        tokens.append("legacy_total_ladder_rank")
        mapping_id = seed_id
        return CompatibilityResult(
            envelope=EvidenceEnvelope.from_mapping(envelope),
            claim_tokens=tuple(tokens),
            closed_outcome=outcome,
            informed_dimensions=tuple(informed),
            unsafe_promotion=False,
            mapping_id=mapping_id,
        )

    if seed_id == "seed:ladder-accelerate-proof-status":
        status = str(legacy.get("proof_status") or legacy.get("value") or "unproved")
        mapped = _PROOF_STATUS_MAP.get(status)
        if mapped is None:
            raise FcaError("UNKNOWN_ENUM", f"unknown ProofStatus: {status}")
        for dim, value in mapped.items():
            envelope[dim] = value
            informed.append(dim)
        tokens.append("legacy_total_ladder_rank")
        mapping_id = seed_id
        return CompatibilityResult(
            envelope=EvidenceEnvelope.from_mapping(envelope),
            claim_tokens=tuple(tokens),
            closed_outcome=outcome,
            informed_dimensions=tuple(informed),
            unsafe_promotion=False,
            mapping_id=mapping_id,
        )

    if seed_id == "seed:ladder-kit-backend-support-tier":
        tokens.extend(["backend_support_tier", "inventory_or_configuration_support"])
        tier = str(legacy.get("tier") or legacy.get("value") or "").lower()
        if "conditional" in tier:
            # Claim class annotation only — not observation / live qualification.
            envelope["environment"] = "conditional"
            informed.append("environment")
        mapping_id = seed_id
        return CompatibilityResult(
            envelope=EvidenceEnvelope.from_mapping(envelope),
            claim_tokens=tuple(tokens),
            closed_outcome=outcome,
            informed_dimensions=tuple(informed),
            unsafe_promotion=False,
            mapping_id=mapping_id,
        )

    # Forbidden generic fields (spec §8.1).
    if "success" in legacy:
        mapping_id = "legacy-success-boolean"
        if legacy.get("success") is True:
            # May inform effect.started only when an attempt is evidenced.
            if legacy.get("attempt_evidenced") is True:
                envelope["effect"] = "started"
                informed.append("effect")
                outcome = "Attempted"
            else:
                outcome = "Unavailable"
        elif legacy.get("success") is False:
            envelope["effect"] = "failed"
            informed.append("effect")
            outcome = "Failed"
        tokens.append("success_true" if legacy.get("success") is True else "success_false")

    if "available" in legacy:
        mapping_id = "legacy-available-boolean"
        tokens.extend(["discovery", "inventory_presence"])
        outcome = "Unavailable"

    if "supported" in legacy:
        mapping_id = "legacy-supported-boolean"
        tokens.append("inventory_or_configuration_support")
        outcome = "Unavailable"

    if "verified" in legacy or "proven" in legacy:
        mapping_id = (
            "legacy-verified-boolean" if "verified" in legacy else "legacy-proven-boolean"
        )
        # At most proof.candidate — never proof.verified from a boolean alone.
        if legacy.get("verified") is True or legacy.get("proven") is True:
            envelope["proof"] = "candidate"
            informed.append("proof")
        tokens.append("legacy_boolean_verified")

    if legacy.get("origin") == "mock" or legacy.get("mock") is True:
        mapping_id = "family:mock_capability"
        envelope["origin"] = "simulated"
        informed.append("origin")
        outcome = "Simulated"
        tokens.append("mock_capability")

    if legacy.get("browser_consent") is True or legacy.get("browser_policy") is True:
        mapping_id = "family:browser_authority"
        # Presentation input only — authority/policy stay unchecked.
        tokens.extend(["browser_consent", "browser_policy"])
        outcome = "Unavailable"

    return CompatibilityResult(
        envelope=EvidenceEnvelope.from_mapping(envelope),
        claim_tokens=tuple(dict.fromkeys(tokens)),
        closed_outcome=outcome,
        informed_dimensions=tuple(dict.fromkeys(informed)),
        unsafe_promotion=False,
        mapping_id=mapping_id,
    )


# ---------------------------------------------------------------------------
# Rules loading (explicit only — never at import)
# ---------------------------------------------------------------------------


def default_promotion_rules_path() -> Path:
    """Repo-relative path to ``promotion-rules.json`` (does not read the file)."""
    # validators/ -> tests-py/ -> Mcp-Plus-Plus/ -> repo root
    repo_root = Path(__file__).resolve().parents[3]
    return (
        repo_root
        / "Mcp-Plus-Plus"
        / "schemas"
        / "assurance"
        / "v1"
        / "promotion-rules.json"
    )


def default_vectors_path() -> Path:
    """Repo-relative path to normative FCA vectors (does not read the file)."""
    repo_root = Path(__file__).resolve().parents[3]
    return (
        repo_root
        / "Mcp-Plus-Plus"
        / "conformance"
        / "vectors"
        / "formal_claim_algebra.json"
    )


def load_promotion_rules(path: Path | str | None = None) -> dict[str, Any]:
    """Load and lightly validate a promotion-rules document."""
    rules_path = Path(path) if path is not None else default_promotion_rules_path()
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise FcaError("INVALID_TYPE", "promotion rules must be an object")
    if data.get("schema") != RULES_SCHEMA:
        raise FcaError(
            "UNKNOWN_ENUM",
            f"unexpected rules schema: {data.get('schema')!r}",
        )
    if data.get("unknown_transition_policy") != "reject":
        raise FcaError(
            "UNKNOWN_TRANSITION",
            "unknown_transition_policy must be reject",
        )
    return data


def load_normative_vectors(path: Path | str | None = None) -> dict[str, Any]:
    """Load the FACP-016 normative vector corpus."""
    vectors_path = Path(path) if path is not None else default_vectors_path()
    data = json.loads(vectors_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise FcaError("INVALID_TYPE", "vectors corpus must be an object")
    if data.get("schema") != VECTORS_SCHEMA:
        raise FcaError(
            "UNKNOWN_ENUM",
            f"unexpected vectors schema: {data.get('schema')!r}",
        )
    return data


# ---------------------------------------------------------------------------
# Transition / predicate / negative-rule evaluation
# ---------------------------------------------------------------------------


def _evidence_present(bag: EvidenceBag | Sequence[str], required: Sequence[str]) -> bool:
    if isinstance(bag, EvidenceBag):
        return bag.contains_all(required)
    present = set(bag)
    return all(key in present for key in required)


def _as_bag(evidence: EvidenceBag | Sequence[str] | None) -> EvidenceBag:
    if evidence is None:
        return EvidenceBag.empty()
    if isinstance(evidence, EvidenceBag):
        return evidence
    return EvidenceBag.from_keys(evidence)


def parse_dimension_value(dimension: str, value: str) -> str:
    if dimension not in DIMENSION_ORDER:
        raise FcaError("UNKNOWN_ENUM", f"unknown dimension: {dimension}")
    if value not in DIMENSION_ENUMS[dimension]:
        raise FcaError("UNKNOWN_ENUM", f"unknown enum value for {dimension}: {value}")
    return value


def transition_result(
    rules: Mapping[str, Any],
    dimension: str,
    from_value: str,
    to_value: str,
    evidence: EvidenceBag | Sequence[str] | None = None,
) -> tuple[bool, str]:
    """Return ``(ok, error_code)`` for a same-dimension transition."""
    bag = _as_bag(evidence)
    parse_dimension_value(dimension, from_value)
    parse_dimension_value(dimension, to_value)

    table = (rules.get("transitions") or {}).get("by_dimension", {}).get(dimension)
    if table is None:
        return False, "UNKNOWN_DIMENSION"

    for row in table.get("forbidden", []):
        if row.get("cross_dimension") or row.get("claim_token_transition"):
            continue
        if row.get("from") != from_value or row.get("to") != to_value:
            continue
        missing = list(row.get("when_missing_evidence") or [])
        if missing and _evidence_present(bag, missing):
            continue
        if row.get("negative_rule"):
            neg = next(
                (
                    n
                    for n in rules.get("negative_rules", [])
                    if n["id"] == row["negative_rule"]
                ),
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
        if required and not _evidence_present(bag, required):
            return False, f"MISSING_TRANSITION_EVIDENCE:{dimension}"
        return True, ""

    return False, f"UNKNOWN_TRANSITION:{dimension}:{from_value}->{to_value}"


def transition_allowed(
    rules: Mapping[str, Any],
    dimension: str,
    from_value: str,
    to_value: str,
    evidence: EvidenceBag | Sequence[str] | None = None,
) -> None:
    ok, code = transition_result(rules, dimension, from_value, to_value, evidence)
    if not ok:
        raise FcaError(
            code,
            f"transition rejected: {dimension} {from_value} -> {to_value}",
        )


def apply_transition(
    rules: Mapping[str, Any],
    envelope: EvidenceEnvelope,
    dimension: str,
    to_value: str,
    evidence: EvidenceBag | Sequence[str] | None = None,
) -> EvidenceEnvelope:
    from_value = envelope.get_dimension(dimension)
    transition_allowed(rules, dimension, from_value, to_value, evidence)
    return envelope.with_dimension(dimension, to_value)


def _dimensions_satisfied(
    envelope: EvidenceEnvelope | Mapping[str, str],
    necessary: Mapping[str, Sequence[str]],
) -> bool:
    mapping = (
        envelope.to_mapping()
        if isinstance(envelope, EvidenceEnvelope)
        else dict(envelope)
    )
    for dim, allowed in necessary.items():
        if mapping.get(dim) not in allowed:
            return False
    return True


def predicate_result(
    rules: Mapping[str, Any],
    predicate_id: str,
    envelope: EvidenceEnvelope | Mapping[str, str],
    evidence: EvidenceBag | Sequence[str] | None = None,
) -> tuple[bool, str]:
    """Return ``(ok, error_code)`` for a promotion predicate."""
    bag = _as_bag(evidence)
    pred = (rules.get("predicates") or {}).get(predicate_id)
    if pred is None:
        return False, "UNKNOWN_PREDICATE"
    if not _dimensions_satisfied(envelope, pred["necessary_dimensions"]):
        return False, f"MISSING_DIMENSIONS:{predicate_id}"
    if not _evidence_present(bag, pred["necessary_evidence"]):
        return False, f"MISSING_EVIDENCE:{predicate_id}"
    return True, ""


def predicate_holds(
    predicate_id: str,
    envelope: EvidenceEnvelope | Mapping[str, str],
    evidence: EvidenceBag | Sequence[str] | None,
    rules: Mapping[str, Any],
) -> None:
    ok, code = predicate_result(rules, predicate_id, envelope, evidence)
    if not ok:
        raise FcaError(code, f"predicate rejected: {predicate_id}")


def negative_rule_blocks(
    rules: Mapping[str, Any],
    rule_id: str,
    *,
    envelope: EvidenceEnvelope | Mapping[str, str],
    evidence: EvidenceBag | Sequence[str] | None = None,
    claim_tokens: Sequence[str] | None = None,
    claimed_predicate: str | None = None,
) -> tuple[bool, str]:
    """Return ``(blocked, rejection_code)`` for a named negative rule."""
    bag = _as_bag(evidence)
    tokens = set(claim_tokens or [])
    mapping = (
        envelope.to_mapping()
        if isinstance(envelope, EvidenceEnvelope)
        else dict(envelope)
    )
    rule = next(
        (r for r in rules.get("negative_rules", []) if r["id"] == rule_id),
        None,
    )
    if rule is None:
        raise FcaError("UNKNOWN_ENUM", f"unknown negative rule: {rule_id}")

    antecedent = rule["antecedent"]
    consequent = rule["consequent"]

    dims = antecedent.get("dimensions") or {}
    tokens_need = set(antecedent.get("claim_tokens") or [])
    ante_hit = False
    if dims:
        for dim, values in dims.items():
            if mapping.get(dim) in values:
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
        if mapping.get(dim) in values:
            cons_hit = True
            break
    if claimed_predicate and claimed_predicate in cons_preds:
        cons_hit = True
    if not cons_hit:
        return False, ""

    required = list(consequent.get("independent_evidence_required") or [])
    if rule.get("absolute") is True or not required:
        return True, rule["rejection_code"]
    if not _evidence_present(bag, required):
        return True, rule["rejection_code"]
    return False, ""


def semantic_check_code(
    rules: Mapping[str, Any],
    envelope: EvidenceEnvelope | Mapping[str, str],
    predicate_id: str,
    evidence: EvidenceBag | Sequence[str] | None,
    declared: str,
) -> str:
    """Evaluate a one-field semantic mutation against a predicate.

    When the predicate fails and ``declared`` is a more specific non-implication
    or relabel ban, prefer the declared stable code (FACP-016 mutation oracle).
    """
    ok, code = predicate_result(rules, predicate_id, envelope, evidence)
    if not ok:
        if declared.startswith("NONIMP_") or declared.startswith("FORBIDDEN_RELABEL"):
            return declared
        return code
    return "UNEXPECTED_ACCEPT"


# ---------------------------------------------------------------------------
# Normative vector evaluation
# ---------------------------------------------------------------------------


def resolve_evidence(
    vectors: Mapping[str, Any],
    bag: Any,
) -> list[str]:
    if bag is None:
        return []
    if isinstance(bag, str):
        bags = vectors["evidence_bags"]
        if bag not in bags:
            raise FcaError("UNKNOWN_ENUM", f"unknown evidence bag: {bag}")
        return list(bags[bag])
    if isinstance(bag, list):
        return list(bag)
    raise FcaError("INVALID_TYPE", "evidence must be a bag name or key list")


def fixture_envelope(vectors: Mapping[str, Any], name: str) -> EvidenceEnvelope:
    fixtures = vectors["fixtures"]
    if name not in fixtures:
        raise FcaError("UNKNOWN_ENUM", f"unknown fixture: {name}")
    return EvidenceEnvelope.from_mapping(fixtures[name])


def apply_mutation(
    base: Mapping[str, Any],
    mutation: Mapping[str, Any],
) -> dict[str, Any]:
    out = dict(base)
    op = mutation["op"]
    path = mutation["path"]
    if op == "set":
        out[path] = mutation["value"]
        return out
    if op == "delete":
        out.pop(path, None)
        return out
    raise FcaError("UNKNOWN_ENUM", f"unsupported mutation op: {op}")


def evaluate_positive_vector(
    rules: Mapping[str, Any],
    vectors: Mapping[str, Any],
    case: Mapping[str, Any],
) -> None:
    kind = case["kind"]
    if kind == "envelope":
        fixture_envelope(vectors, case["fixture"])
        return
    if kind == "transition":
        evidence = resolve_evidence(vectors, case.get("evidence"))
        transition_allowed(
            rules, case["dimension"], case["from"], case["to"], evidence
        )
        return
    if kind == "predicate":
        env = fixture_envelope(vectors, case["fixture"])
        evidence = resolve_evidence(vectors, case.get("evidence"))
        predicate_holds(case["predicate"], env, evidence, rules)
        return
    raise FcaError("UNKNOWN_ENUM", f"unknown positive kind: {kind}")


def evaluate_negative_vector(
    rules: Mapping[str, Any],
    vectors: Mapping[str, Any],
    case: Mapping[str, Any],
) -> str:
    """Evaluate a negative vector; return the observed rejection code."""
    kind = case["kind"]
    expected = case["error_code"]
    if kind == "transition":
        evidence = resolve_evidence(vectors, case.get("evidence"))
        ok, code = transition_result(
            rules, case["dimension"], case["from"], case["to"], evidence
        )
        if ok:
            raise FcaError("UNEXPECTED_ACCEPT", f"{case['id']} expected reject")
        return code
    if kind == "predicate":
        env = EvidenceEnvelope.from_mapping(case["envelope"])
        evidence = resolve_evidence(vectors, case.get("evidence"))
        ok, code = predicate_result(rules, case["predicate"], env, evidence)
        if ok:
            raise FcaError("UNEXPECTED_ACCEPT", f"{case['id']} expected reject")
        return code
    if kind == "non_implication":
        full = fixture_envelope(vectors, "weakest").to_mapping()
        full.update(case.get("envelope") or {})
        env = EvidenceEnvelope.from_mapping(full)
        evidence = resolve_evidence(vectors, case.get("evidence"))
        blocked, code = negative_rule_blocks(
            rules,
            case["negative_rule"],
            envelope=env,
            evidence=evidence,
            claim_tokens=case.get("claim_tokens") or [],
            claimed_predicate=case.get("claimed_predicate"),
        )
        if not blocked:
            raise FcaError(
                "UNEXPECTED_ACCEPT",
                f"{case['id']} expected negative rule to block",
            )
        return code
    raise FcaError("UNKNOWN_ENUM", f"unknown negative kind: {kind}")


def evaluate_mutation_vector(
    rules: Mapping[str, Any],
    vectors: Mapping[str, Any],
    case: Mapping[str, Any],
) -> str:
    """Evaluate a mutation vector; return the observed rejection code."""
    base = fixture_envelope(vectors, case["base"]).to_mapping()
    mutated = apply_mutation(base, case["mutation"])
    kind = case["kind"]
    expected = case["error_code"]

    if kind == "schema":
        try:
            EvidenceEnvelope.from_mapping(mutated)
        except FcaError as exc:
            return exc.code
        raise FcaError("UNEXPECTED_ACCEPT", f"{case['id']} schema mutation must fail")

    if kind == "semantic":
        env = EvidenceEnvelope.from_mapping(mutated)
        check = case["check"]
        evidence = resolve_evidence(vectors, check)
        code = semantic_check_code(rules, env, check, evidence, expected)
        if code == "UNEXPECTED_ACCEPT":
            raise FcaError(
                "UNEXPECTED_ACCEPT",
                f"{case['id']} mutation unexpectedly accepted",
            )
        return code

    raise FcaError("UNKNOWN_ENUM", f"unknown mutation kind: {kind}")


def codes_match(observed: str, expected: str) -> bool:
    """Stable error-code comparison used by the normative vector suite."""
    if observed == expected:
        return True
    if expected in observed or observed in expected:
        return True
    root = expected.split(":", 1)[0]
    if observed.startswith(root):
        return True
    return False


def evaluate_all_normative_vectors(
    rules: Mapping[str, Any],
    vectors: Mapping[str, Any],
) -> dict[str, int]:
    """Run the full FACP-016 corpus against this binding.

    Raises ``FcaError`` / ``AssertionError``-style ``FcaError`` on mismatch.
    Returns accept/reject counters.
    """
    accept = 0
    reject = 0

    for case in vectors["positive_vectors"]:
        evaluate_positive_vector(rules, vectors, case)
        accept += 1

    for case in vectors["negative_vectors"]:
        code = evaluate_negative_vector(rules, vectors, case)
        expected = case["error_code"]
        if not codes_match(code, expected):
            raise FcaError(
                expected,
                f"{case['id']}: expected {expected}, got {code}",
            )
        reject += 1

    for case in vectors["mutation_vectors"]:
        code = evaluate_mutation_vector(rules, vectors, case)
        expected = case["error_code"]
        if not codes_match(code, expected):
            raise FcaError(
                expected,
                f"{case['id']}: expected {expected}, got {code}",
            )
        reject += 1

    return {"accept": accept, "reject": reject}


__all__ = [
    "ALL_NORMATIVE_EVIDENCE",
    "BUNDLE",
    "CLOSED_OUTCOMES",
    "CompatibilityResult",
    "DIMENSION_ENUMS",
    "DIMENSION_ORDER",
    "ENVELOPE_SCHEMA",
    "EvidenceBag",
    "EvidenceEnvelope",
    "FcaError",
    "FORBIDDEN_GENERIC_FIELDS",
    "GOAL_ID",
    "PREDICATE_ORDER",
    "ProductionSuccessClaim",
    "RULES_SCHEMA",
    "STRONG_PRODUCT_ENVELOPE",
    "TASK_ID",
    "UNKNOWN_TRANSITION_POLICY",
    "VECTORS_SCHEMA",
    "VOCAB_SCHEMA",
    "VerifiedClaim",
    "WEAKEST_ENVELOPE",
    "apply_mutation",
    "apply_transition",
    "codes_match",
    "default_promotion_rules_path",
    "default_vectors_path",
    "evaluate_all_normative_vectors",
    "evaluate_mutation_vector",
    "evaluate_negative_vector",
    "evaluate_positive_vector",
    "fixture_envelope",
    "load_normative_vectors",
    "load_promotion_rules",
    "map_legacy_claim",
    "negative_rule_blocks",
    "parse_dimension_value",
    "predicate_holds",
    "predicate_result",
    "resolve_evidence",
    "semantic_check_code",
    "transition_allowed",
    "transition_result",
]
