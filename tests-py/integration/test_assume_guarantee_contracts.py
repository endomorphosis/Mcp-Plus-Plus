"""FACP-048: publish and compose repository assume-guarantee contracts.

Acceptance (taskboard):
- Each assumption is supplied by a qualified guarantee or explicitly unresolved.
- Seeded integration failures name the exact violated boundary.
- Contract changes invalidate downstream capsules.

Normative records live in repository-contracts.json (MCP++ ownership). This
module evaluates that registry hermetically and must not import peer
repositories merely to discover their semantics.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "repository-contracts.json"
)

SCHEMA = "facp/repository-contracts@1"
BOUNDARIES_SCHEMA = "facp/composition-boundaries@1"
ASSUME_GUARANTEE_SCHEMA = "facp/assume-guarantee@1"
TASK_ID = "FACP-048"
GOAL_ID = "FACP-G620"
BUNDLE = "facp/composition/contracts"

REQUIRED_REPOSITORIES = (
    "ipfs_datasets_py",
    "ipfs_kit_py",
    "ipfs_accelerate_py",
    "swissknife",
)

EVIDENCE_FOCUS = {
    "ipfs_datasets_py": "pure_semantics",
    "ipfs_kit_py": "integrity_cas_role_separation",
    "ipfs_accelerate_py": "admission_execution_observation",
    "swissknife": "nonauthority_presentation",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def contract_digest(contract: Mapping[str, Any]) -> str:
    """Content digest for a single repository contract record."""
    return "sha256:" + hashlib.sha256(_canonical_bytes(contract)).hexdigest()


def registry_digest(registry: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(registry)).hexdigest()


def _load_registry() -> dict[str, Any]:
    assert CONTRACTS_PATH.is_file(), f"missing repository contracts: {CONTRACTS_PATH}"
    data = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _all_contracts(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    contracts = dict(registry["contracts"])
    external = registry.get("external_guarantees") or {}
    for repo_id, contract in external.items():
        contracts[repo_id] = contract
    return contracts


def _index_guarantees(
    contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for repo_id, contract in contracts.items():
        for guarantee in contract.get("guarantees") or []:
            gid = guarantee["id"]
            assert gid not in out, f"duplicate guarantee id: {gid}"
            row = dict(guarantee)
            row["repository_id"] = repo_id
            row["contract_id"] = contract["id"]
            out[gid] = row
    return out


def _index_assumptions(
    contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for repo_id, contract in contracts.items():
        for assumption in contract.get("assumptions") or []:
            aid = assumption["id"]
            assert aid not in out, f"duplicate assumption id: {aid}"
            row = dict(assumption)
            row["repository_id"] = repo_id
            row["contract_id"] = contract["id"]
            out[aid] = row
    return out


@dataclass(frozen=True)
class DischargeResult:
    assumption_id: str
    status: str
    guarantee_id: str | None
    boundary_id: str | None
    rejection_code: str | None = None
    unresolved_reason: str | None = None


@dataclass
class CompositionReport:
    discharges: list[DischargeResult] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class Capsule:
    capsule_id: str
    kind: str
    required_contract_ids: tuple[str, ...]
    required_contract_digests: Mapping[str, str]
    source_cids: tuple[str, ...] = ()

    def digest(self) -> str:
        payload = {
            "capsule_id": self.capsule_id,
            "kind": self.kind,
            "required_contract_ids": list(self.required_contract_ids),
            "required_contract_digests": dict(self.required_contract_digests),
            "source_cids": list(self.source_cids),
        }
        return "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()


class AssumeGuaranteeComposer:
    """Fail-closed composer for facp/repository-contracts@1."""

    def __init__(self, registry: Mapping[str, Any]) -> None:
        self.registry = registry
        self.contracts = _all_contracts(registry)
        self.guarantees = _index_guarantees(self.contracts)
        self.assumptions = _index_assumptions(self.contracts)
        self.boundaries = {
            row["id"]: row for row in registry["composition_boundaries"]
        }
        self.env_rules = {
            row["id"]: row for row in registry["environment_discharge_rules"]
        }
        self._unqualified: set[str] = set()
        self._extra_assumptions: list[dict[str, Any]] = []

    def mark_unqualified(self, *guarantee_ids: str) -> None:
        for gid in guarantee_ids:
            self._unqualified.add(gid)

    def inject_assumption(self, assumption: Mapping[str, Any]) -> None:
        self._extra_assumptions.append(dict(assumption))

    def _guarantee_qualified(self, guarantee_id: str) -> bool:
        if guarantee_id in self._unqualified:
            return False
        guarantee = self.guarantees.get(guarantee_id)
        if guarantee is None:
            return False
        status = (guarantee.get("qualification") or {}).get("status")
        return status == "qualified"

    def _boundary_for_assumption(self, assumption_id: str) -> dict[str, Any] | None:
        for boundary in self.boundaries.values():
            if boundary["assumption_id"] == assumption_id:
                return boundary
        return None

    def discharge_assumption(
        self, assumption: Mapping[str, Any]
    ) -> DischargeResult:
        aid = assumption["id"]
        boundary = self._boundary_for_assumption(aid)
        boundary_id = boundary["id"] if boundary else None

        if assumption.get("explicit_unresolved") is True:
            reason = assumption.get("unresolved_reason")
            if not isinstance(reason, str) or not reason.strip():
                return DischargeResult(
                    assumption_id=aid,
                    status="violated",
                    guarantee_id=None,
                    boundary_id=boundary_id,
                    rejection_code=self.env_rules[
                        "env-discharge:explicit-unresolved-allowed"
                    ]["rejection_code"],
                )
            if assumption.get("environment") is not True:
                return DischargeResult(
                    assumption_id=aid,
                    status="violated",
                    guarantee_id=None,
                    boundary_id=boundary_id,
                    rejection_code=self.env_rules[
                        "env-discharge:explicit-unresolved-allowed"
                    ]["rejection_code"],
                )
            return DischargeResult(
                assumption_id=aid,
                status="unresolved",
                guarantee_id=None,
                boundary_id=boundary_id,
                unresolved_reason=reason,
            )

        if assumption.get("environment") is True and not assumption.get(
            "explicit_unresolved"
        ):
            return DischargeResult(
                assumption_id=aid,
                status="violated",
                guarantee_id=None,
                boundary_id=boundary_id,
                rejection_code=self.env_rules[
                    "env-discharge:explicit-unresolved-allowed"
                ]["rejection_code"],
            )

        required = assumption.get("required_guarantee")
        provider = assumption.get("provider_repository")
        if not required or not provider:
            return DischargeResult(
                assumption_id=aid,
                status="violated",
                guarantee_id=required if isinstance(required, str) else None,
                boundary_id=boundary_id,
                rejection_code=self.env_rules[
                    "env-discharge:provider-before-composition"
                ]["rejection_code"],
            )

        guarantee = self.guarantees.get(required)
        if guarantee is None:
            return DischargeResult(
                assumption_id=aid,
                status="violated",
                guarantee_id=required,
                boundary_id=boundary_id,
                rejection_code=self.env_rules[
                    "env-discharge:provider-before-composition"
                ]["rejection_code"],
            )

        if guarantee["repository_id"] != provider:
            return DischargeResult(
                assumption_id=aid,
                status="violated",
                guarantee_id=required,
                boundary_id=boundary_id,
                rejection_code=self.env_rules[
                    "env-discharge:provider-before-composition"
                ]["rejection_code"],
            )

        if not self._guarantee_qualified(required):
            code = None
            if boundary is not None:
                code = boundary["violation_code"]
            else:
                code = self.env_rules["env-discharge:provider-before-composition"][
                    "rejection_code"
                ]
            return DischargeResult(
                assumption_id=aid,
                status="violated",
                guarantee_id=required,
                boundary_id=boundary_id,
                rejection_code=code,
            )

        if boundary is not None:
            if boundary["guarantee_id"] != required:
                return DischargeResult(
                    assumption_id=aid,
                    status="violated",
                    guarantee_id=required,
                    boundary_id=boundary_id,
                    rejection_code=boundary["violation_code"],
                )
            if boundary["provider_repository"] != provider:
                return DischargeResult(
                    assumption_id=aid,
                    status="violated",
                    guarantee_id=required,
                    boundary_id=boundary_id,
                    rejection_code=boundary["violation_code"],
                )

        return DischargeResult(
            assumption_id=aid,
            status="discharged",
            guarantee_id=required,
            boundary_id=boundary_id,
        )

    def compose(self) -> CompositionReport:
        report = CompositionReport()
        assumptions: list[Mapping[str, Any]] = list(self.assumptions.values())
        assumptions.extend(self._extra_assumptions)
        for assumption in assumptions:
            result = self.discharge_assumption(assumption)
            report.discharges.append(result)
            if result.status == "unresolved":
                report.unresolved.append(result.assumption_id)
            elif result.status == "violated":
                assert result.rejection_code, result
                report.violations.append(result.rejection_code)
        return report

    def apply_seeded_failure(
        self, seed: Mapping[str, Any]
    ) -> tuple[CompositionReport, str]:
        """Apply a seeded integration fault and return (report, named code)."""
        broken = seed.get("broken_guarantee_id")
        if isinstance(broken, str) and broken:
            self.mark_unqualified(broken)
        for extra in seed.get("also_unqualified_guarantee_ids") or ():
            self.mark_unqualified(extra)

        fault = seed.get("fault") or {}
        if fault.get("action") == "inject_undisclosed_environment_assumption":
            self.inject_assumption(
                {
                    "id": seed["broken_assumption_id"],
                    "proposition": "Undisclosed live backend qualification.",
                    "kind": "assumption",
                    "required_guarantee": None,
                    "provider_repository": None,
                    "environment": True,
                    "explicit_unresolved": False,
                }
            )

        report = self.compose()
        expected = seed["expected_violation_code"]
        return report, expected

    def published_contract_digests(self) -> dict[str, str]:
        digests: dict[str, str] = {}
        for repo_id in self.registry["repository_order"]:
            contract = self.contracts[repo_id]
            digests[contract["id"]] = contract_digest(contract)
        # Include MCP++ external guarantee contract.
        mcp = self.contracts["mcp_plus_plus"]
        digests[mcp["id"]] = contract_digest(mcp)
        return digests

    def build_consumer_capsule(
        self,
        *,
        capsule_id: str,
        kind: str,
        required_contract_ids: Sequence[str],
        digests: Mapping[str, str] | None = None,
    ) -> Capsule:
        published = digests or self.published_contract_digests()
        bound = {
            cid: published[cid]
            for cid in required_contract_ids
            if cid in published
        }
        missing = [cid for cid in required_contract_ids if cid not in bound]
        if missing:
            raise KeyError(f"unknown required contracts: {missing}")
        return Capsule(
            capsule_id=capsule_id,
            kind=kind,
            required_contract_ids=tuple(required_contract_ids),
            required_contract_digests=bound,
        )

    def invalidate_after_contract_change(
        self,
        *,
        capsules: Sequence[Capsule],
        changed_contract_id: str,
        new_contract: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Invalidate capsules that depend on a changed contract digest."""
        assert self.registry["contract_change_invalidates_downstream_capsules"] is True
        new_digest = contract_digest(new_contract)
        invalidated: list[dict[str, Any]] = []
        reused: list[str] = []
        for capsule in capsules:
            if changed_contract_id not in capsule.required_contract_ids:
                reused.append(capsule.capsule_id)
                continue
            prior = capsule.required_contract_digests[changed_contract_id]
            if prior == new_digest:
                reused.append(capsule.capsule_id)
                continue
            path = [
                changed_contract_id,
                f"digest:{prior}",
                f"digest:{new_digest}",
                capsule.capsule_id,
            ]
            invalidated.append(
                {
                    "capsule_id": capsule.capsule_id,
                    "kind": capsule.kind,
                    "action": "invalidate",
                    "changed_contract_id": changed_contract_id,
                    "prior_digest": prior,
                    "new_digest": new_digest,
                    "minimal_path": path,
                }
            )
        return {
            "changed_contract_id": changed_contract_id,
            "new_digest": new_digest,
            "invalidated": invalidated,
            "reused": reused,
        }


@pytest.fixture(scope="module")
def registry() -> dict[str, Any]:
    return _load_registry()


@pytest.fixture
def composer(registry: dict[str, Any]) -> AssumeGuaranteeComposer:
    return AssumeGuaranteeComposer(registry)


def test_registry_identifies_facp_048(registry: dict[str, Any]) -> None:
    assert registry["schema"] == SCHEMA
    assert registry["schema_version"] == 1
    assert registry["task_id"] == TASK_ID
    assert registry["goal_id"] == GOAL_ID
    assert registry["bundle"] == BUNDLE
    assert registry["composition_boundaries_schema"] == BOUNDARIES_SCHEMA
    assert registry["assume_guarantee_schema"] == ASSUME_GUARANTEE_SCHEMA
    assert registry["fail_closed"] is True
    assert registry["discovery_via_repository_import_forbidden"] is True
    assert registry["undisclosed_environmental_premise_forbidden"] is True
    assert registry["assume_away_component_defect_forbidden"] is True
    assert registry["normative_owner"] == "Mcp-Plus-Plus"
    assert registry["repositories_supply_evidence_not_rewritten_copies"] is True
    assert registry["contract_change_invalidates_downstream_capsules"] is True
    assert CONTRACTS_PATH.is_file()


def test_required_repositories_and_evidence_focus(registry: dict[str, Any]) -> None:
    assert list(registry["repository_order"]) == list(REQUIRED_REPOSITORIES)
    contracts = registry["contracts"]
    assert list(contracts) == list(REQUIRED_REPOSITORIES)
    for repo_id in REQUIRED_REPOSITORIES:
        contract = contracts[repo_id]
        assert contract["repository_id"] == repo_id
        assert contract["evidence_focus"] == EVIDENCE_FOCUS[repo_id]
        assert contract["id"] == f"contract:{repo_id}@1"
        assert contract["version"] == 1
        assert isinstance(contract["owns"], list) and contract["owns"]
        assert isinstance(contract["must_not_own"], list) and contract["must_not_own"]
        assert contract["guarantees"], repo_id
        assert contract["assumptions"], repo_id


def test_mcp_external_guarantee_is_normative_owner(registry: dict[str, Any]) -> None:
    mcp = registry["external_guarantees"]["mcp_plus_plus"]
    assert mcp["id"] == "contract:mcp_plus_plus@1"
    ids = {g["id"] for g in mcp["guarantees"]}
    assert "guarantee:mcp.normative_contract_registry" in ids


def test_each_assumption_discharged_or_explicitly_unresolved(
    composer: AssumeGuaranteeComposer,
) -> None:
    report = composer.compose()
    assert report.ok, report.violations
    by_id = {row.assumption_id: row for row in report.discharges}
    for assumption in composer.assumptions.values():
        result = by_id[assumption["id"]]
        if assumption.get("explicit_unresolved"):
            assert result.status == "unresolved"
            assert result.unresolved_reason
            assert assumption["id"] in report.unresolved
        else:
            assert result.status == "discharged", assumption["id"]
            assert result.guarantee_id == assumption["required_guarantee"]
            assert composer._guarantee_qualified(result.guarantee_id or "")


def test_qualified_guarantee_required_for_discharge(
    composer: AssumeGuaranteeComposer,
) -> None:
    target = "guarantee:accelerate.admission_token_consumption"
    composer.mark_unqualified(target)
    report = composer.compose()
    assert not report.ok
    assert any(
        code.startswith("BOUNDARY_VIOLATED:") for code in report.violations
    )
    related = [
        row
        for row in report.discharges
        if row.guarantee_id == target and row.status == "violated"
    ]
    assert related
    for row in related:
        assert row.rejection_code
        assert row.boundary_id
        assert row.rejection_code == (
            f"BOUNDARY_VIOLATED:{row.boundary_id}"
        )


def test_composition_boundaries_cover_every_non_unresolved_assumption(
    registry: dict[str, Any],
) -> None:
    contracts = _all_contracts(registry)
    assumptions = _index_assumptions(contracts)
    bounded = {
        row["assumption_id"] for row in registry["composition_boundaries"]
    }
    for assumption in assumptions.values():
        if assumption.get("explicit_unresolved"):
            continue
        assert assumption["id"] in bounded, assumption["id"]


def test_boundaries_match_assumption_guarantee_pairs(
    registry: dict[str, Any],
) -> None:
    contracts = _all_contracts(registry)
    assumptions = _index_assumptions(contracts)
    guarantees = _index_guarantees(contracts)
    for boundary in registry["composition_boundaries"]:
        assumption = assumptions[boundary["assumption_id"]]
        guarantee = guarantees[boundary["guarantee_id"]]
        assert assumption["required_guarantee"] == boundary["guarantee_id"]
        assert assumption["provider_repository"] == boundary["provider_repository"]
        assert assumption["repository_id"] == boundary["consumer_repository"]
        assert guarantee["repository_id"] == boundary["provider_repository"]
        assert boundary["violation_code"] == (
            f"BOUNDARY_VIOLATED:{boundary['id']}"
        )
        assert boundary["workflow_step"] in registry["terminal_workflow"] or (
            boundary["workflow_step"] == "normative_contract_resolution"
        )


def test_environment_discharge_rules_are_present(registry: dict[str, Any]) -> None:
    ids = {row["id"] for row in registry["environment_discharge_rules"]}
    assert "env-discharge:explicit-unresolved-allowed" in ids
    assert "env-discharge:provider-before-composition" in ids
    assert "env-discharge:no-assume-away-defect" in ids


@pytest.mark.parametrize(
    "seed_id",
    [
        "seed:browser-allow-as-admission",
        "seed:candidate-to-current",
        "seed:success-without-observation",
        "seed:datasets-external-effect-success",
        "seed:undisclosed-environment-premise",
    ],
)
def test_seeded_integration_failures_name_exact_boundary(
    registry: dict[str, Any],
    seed_id: str,
) -> None:
    seeds = {row["id"]: row for row in registry["seeded_integration_failures"]}
    seed = seeds[seed_id]
    composer = AssumeGuaranteeComposer(registry)
    report, expected = composer.apply_seeded_failure(seed)
    assert not report.ok, seed_id
    assert expected in report.violations, (
        seed_id,
        expected,
        report.violations,
    )
    if seed.get("violated_boundary_id"):
        assert expected == (
            f"BOUNDARY_VIOLATED:{seed['violated_boundary_id']}"
        )
        assert seed["expected_violation_code"] == expected
        matching = [
            row
            for row in report.discharges
            if row.boundary_id == seed["violated_boundary_id"]
            and row.status == "violated"
        ]
        assert matching, seed_id
        assert all(row.rejection_code == expected for row in matching)
    else:
        assert expected == "ENV_UNDISCLOSED_PREMISE"
        assert seed.get("environment_rule_id") == (
            "env-discharge:explicit-unresolved-allowed"
        )


def test_seeded_failures_do_not_assume_away_component_defect(
    registry: dict[str, Any],
) -> None:
    """A broken guarantee stays broken; composition cannot drop it silently."""
    seed = next(
        row
        for row in registry["seeded_integration_failures"]
        if row["id"] == "seed:success-without-observation"
    )
    composer = AssumeGuaranteeComposer(registry)
    report, expected = composer.apply_seeded_failure(seed)
    assert expected in report.violations
    # Refining assumptions (counterexample path) may add unresolved notes, but
    # must not clear the violated boundary by deleting the required guarantee.
    assert composer.guarantees[seed["broken_guarantee_id"]]["id"] == (
        seed["broken_guarantee_id"]
    )
    assert seed["broken_guarantee_id"] in composer._unqualified


def test_contract_changes_invalidate_downstream_capsules(
    registry: dict[str, Any],
    composer: AssumeGuaranteeComposer,
) -> None:
    digests = composer.published_contract_digests()
    examples = registry["capsule_invalidation"]["examples"]
    capsules: list[Capsule] = []
    for example in examples:
        capsules.append(
            composer.build_consumer_capsule(
                capsule_id=example["consumer_capsule_id"],
                kind=example["consumer_kind"],
                required_contract_ids=[example["producer_contract_id"]],
                digests=digests,
            )
        )
    # Unrelated capsule must remain reusable.
    unrelated = composer.build_consumer_capsule(
        capsule_id="capsule:unrelated.mcp@1",
        kind="contract",
        required_contract_ids=["contract:mcp_plus_plus@1"],
        digests=digests,
    )
    capsules.append(unrelated)

    target_example = examples[0]
    producer_id = target_example["producer_contract_id"]
    # Locate the mutable contract body among primary repositories.
    original = None
    repo_key = None
    for key, contract in registry["contracts"].items():
        if contract["id"] == producer_id:
            original = contract
            repo_key = key
            break
    assert original is not None and repo_key is not None

    mutated = copy.deepcopy(original)
    mutated["version"] = int(mutated["version"]) + 1
    mutated["guarantees"][0]["proposition"] = (
        mutated["guarantees"][0]["proposition"] + " [contract revision]"
    )
    assert contract_digest(mutated) != digests[producer_id]

    result = composer.invalidate_after_contract_change(
        capsules=capsules,
        changed_contract_id=producer_id,
        new_contract=mutated,
    )
    invalidated_ids = {row["capsule_id"] for row in result["invalidated"]}
    assert target_example["consumer_capsule_id"] in invalidated_ids
    assert unrelated.capsule_id in result["reused"]
    assert unrelated.capsule_id not in invalidated_ids

    for row in result["invalidated"]:
        assert row["action"] == "invalidate"
        assert row["changed_contract_id"] == producer_id
        assert row["prior_digest"] == digests[producer_id]
        assert row["new_digest"] == result["new_digest"]
        assert row["minimal_path"][0] == producer_id
        assert row["minimal_path"][-1] == row["capsule_id"]


def test_second_contract_example_also_invalidates(
    registry: dict[str, Any],
    composer: AssumeGuaranteeComposer,
) -> None:
    digests = composer.published_contract_digests()
    example = registry["capsule_invalidation"]["examples"][1]
    capsule = composer.build_consumer_capsule(
        capsule_id=example["consumer_capsule_id"],
        kind=example["consumer_kind"],
        required_contract_ids=[example["producer_contract_id"]],
        digests=digests,
    )
    producer_id = example["producer_contract_id"]
    original = next(
        c for c in registry["contracts"].values() if c["id"] == producer_id
    )
    mutated = copy.deepcopy(original)
    mutated["evidence_focus"] = mutated["evidence_focus"] + "_rev"
    result = composer.invalidate_after_contract_change(
        capsules=[capsule],
        changed_contract_id=producer_id,
        new_contract=mutated,
    )
    assert len(result["invalidated"]) == 1
    assert result["invalidated"][0]["capsule_id"] == capsule.capsule_id


def test_evaluation_flags_match_acceptance(registry: dict[str, Any]) -> None:
    evaluation = registry["evaluation"]
    assert evaluation["every_assumption_discharged_or_explicit_unresolved"] is True
    assert evaluation["qualified_guarantee_required_for_discharge"] is True
    assert evaluation["seeded_failure_must_name_exact_boundary"] is True
    assert evaluation["contract_digest_binds_capsules"] is True
    assert evaluation["forbid_repository_import_for_discovery"] is True


def test_prohibited_effects_enumerated(registry: dict[str, Any]) -> None:
    prohibited = set(registry["prohibited_effects"])
    assert "assume_away_component_defect" in prohibited
    assert "undisclosed_environmental_premise" in prohibited
    assert "repository_import_for_contract_discovery" in prohibited


def test_guarantee_and_assumption_ids_are_unique(registry: dict[str, Any]) -> None:
    contracts = _all_contracts(registry)
    guarantees = _index_guarantees(contracts)
    assumptions = _index_assumptions(contracts)
    assert guarantees
    assert assumptions
    # Explicit unresolved environmental assumptions must not invent providers.
    for assumption in assumptions.values():
        if assumption.get("explicit_unresolved"):
            assert assumption.get("required_guarantee") is None
            assert assumption.get("provider_repository") is None
            assert assumption.get("environment") is True


def test_registry_digest_is_stable_for_unchanged_bytes(
    registry: dict[str, Any],
) -> None:
    first = registry_digest(registry)
    second = registry_digest(_load_registry())
    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64


def test_module_does_not_import_peer_repositories_for_discovery() -> None:
    """Static guard: this test module must stay hermetic to MCP++ contracts."""
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    forbidden_roots = {
        "ipfs_datasets",
        "ipfs_datasets_py",
        "ipfs_kit",
        "ipfs_kit_py",
        "ipfs_accelerate",
        "ipfs_accelerate_py",
        "swissknife",
    }
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert imported.isdisjoint(forbidden_roots), imported & forbidden_roots
