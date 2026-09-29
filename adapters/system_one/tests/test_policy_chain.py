"""Policy chain. One scripted call per gate. Hazard does not rewrite the verdict."""

from datetime import datetime, timezone

from mcp_pp_system_one.combiner import PolicyConformanceChain
from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.exact_policy import Policy, Temporal, clause_document
from mcp_pp_system_one.jev_client import JevClient
from mcp_pp_system_one.project_runtime_clause import project_runtime_clause
from mcp_pp_system_one.witness import policy_document_cid, policy_preimage
from tests.fakes import ScriptedCaller

NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)
MODEL = "jev-1.13.0"


def _policy_cid(clauses) -> str | None:
    if not clauses:
        return None
    return policy_document_cid(
        policy_preimage("v1", [clause_document(clause) for clause in clauses])
    )


def _request(**overrides):
    class Request:
        pass

    request = Request()
    clauses = overrides.get("clauses", ())
    request.clauses = clauses
    if "policy_cid" in overrides:
        request.policy_cid = overrides["policy_cid"]
    else:
        request.policy_cid = _policy_cid(clauses)
    request.policy_version = "v1"
    request.now = NOW
    request.gate = overrides.get("gate", "input")
    request.payload = overrides.get("payload", "read the dataset")
    request.action = overrides.get("action", "dataset.read")
    request.subject = overrides.get("subject", "did:key:worker")
    request.resource = overrides.get("resource", None)
    request.intent_cid = "bafkreiintent"
    request.input_cid = "bafkreiinput"
    request.output_cid = overrides.get("output_cid")
    request.proofs_checked = overrides.get("proofs_checked", [])
    request.require_proofs = overrides.get("require_proofs", False)
    request.interface_cid = None
    request.method = None
    request.size_bytes = None
    request.secret_in_output = False
    return request


def _prohibition(**conditions):
    return Policy(
        policy_type="prohibition",
        action="dataset.read",
        subject="did:key:worker",
        conditions=conditions or None,
        clause_id="c0",
    )


def _permission():
    return Policy(
        policy_type="permission",
        action="dataset.read",
        subject="did:key:worker",
        clause_id="p0",
    )


def _response(answers):
    return {"model": MODEL, "answers": answers}


def _chain(steps, **config):
    caller = ScriptedCaller(steps)
    fields = {"hazard": True, "policy_residual": True}
    fields.update(config)
    cfg = SystemOneConfig(**fields)
    client = JevClient(cfg, caller=caller)
    return PolicyConformanceChain(cfg, client), caller


def test_exact_deny_is_not_flipped_by_a_residual_permission():
    chain, caller = _chain(
        [
            _response(
                {
                    "c0": {"noul": 0.99},
                    "severity": {"score": 0.0},
                    "jailbreak": {"noul": 0.0},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                }
            )
        ]
    )
    clauses = (
        Policy(
            policy_type="prohibition",
            action="dataset.read",
            subject="did:key:worker",
            clause_id="ban",
        ),
        Policy(
            policy_type="permission",
            action="dataset.read",
            subject="did:key:worker",
            conditions={"semantic": "within the topics"},
            clause_id="c0",
        ),
    )
    admission = chain.admit(_request(clauses=clauses))
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "exact_deny"
    assert caller.calls == []


def test_exact_allow_plus_jailbreak_stays_allow_and_hides():
    chain, caller = _chain(
        [
            _response(
                {
                    "jailbreak": {"noul": 0.95},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                    "severity": {"score": 0.2},
                }
            )
        ]
    )
    admission = chain.admit(_request(clauses=(_permission(),)))
    assert admission.authorizing.decision == "allow"
    assert isinstance(admission.authorizing.witness, dict)
    assert admission.show is False
    assert admission.display_cause == "hazard"
    assert len(caller.calls) == 1
    assert "decision_cid" in admission.authorizing.witness
    assert admission.authorizing.witness["clauses"][0]["clause_id"] == "p0"


def test_residual_off_is_one_hazard_call_and_unresolved():
    chain, caller = _chain(
        [
            _response(
                {
                    "jailbreak": {"noul": 0.1},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                    "severity": {"score": 0.0},
                }
            )
        ],
        policy_residual=False,
    )
    admission = chain.admit(
        _request(clauses=(_prohibition(semantic="outside the topics"),))
    )
    assert len(caller.calls) == 1
    assert "c0" not in caller.calls[0]["questions"]
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "unresolved"


def test_review_band_plus_severity_does_not_read_jailbreak():
    chain, caller = _chain(
        [
            _response(
                {
                    "c0": {"noul": 0.40},
                    "severity": {"score": 2.5},
                    "jailbreak": {"noul": 0.95},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                }
            )
        ]
    )
    admission = chain.admit(
        _request(clauses=(_prohibition(semantic="outside the topics"),))
    )
    assert len(caller.calls) == 1
    assert "`clauses[0]`" in caller.calls[0]["questions"]["c0"]["instructions"]
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.allowed is False
    assert admission.authorizing.witness["cause"] == "severity"
    assert admission.display_cause == "severity"


def test_review_band_with_jailbreak_hides_but_stays_review():
    chain, _caller = _chain(
        [
            _response(
                {
                    "c0": {"noul": 0.40},
                    "severity": {"score": 0.0},
                    "jailbreak": {"noul": 0.95},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                }
            )
        ]
    )
    admission = chain.admit(
        _request(clauses=(_prohibition(semantic="outside the topics"),))
    )
    assert admission.authorizing.witness["disposition"] == "review"
    assert admission.authorizing.decision == "deny"
    assert admission.display_cause == "hazard"


def test_exception_after_allow_keeps_the_decision():
    chain, _caller = _chain([], hazard=False, policy_residual=False)

    def boom(authorizing, hazard, cfg):
        raise RuntimeError("display failed")

    chain.display = boom
    admission = chain.admit(_request(clauses=(_permission(),)))
    assert admission.authorizing.decision == "allow"
    assert admission.show is False
    assert admission.display_cause == "admit_exception"


def test_exception_before_a_decision_denies():
    class Boom:
        def classify(self, request):
            raise RuntimeError("before")

    chain = PolicyConformanceChain(SystemOneConfig(), exact=Boom())
    admission = chain.admit(_request())
    assert admission.authorizing.decision == "deny"
    assert admission.show is False


def test_secret_output_denies_without_a_call():
    chain, caller = _chain([])
    admission = chain.admit(
        _request(gate="output", payload="Bearer sk-test-secret", clauses=(_permission(),))
    )
    assert caller.calls == []
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "exact_deny"


def test_project_runtime_clause_rejects_iso_and_unknown_metadata():
    assert project_runtime_clause(
        {
            "clause_type": "prohibition",
            "action": "dataset.read",
            "valid_from": "2026-01-01T00:00:00Z",
        }
    ) is None
    assert project_runtime_clause(
        {
            "clause_type": "permission",
            "action": "dataset.read",
            "metadata": {"unknown": 1},
        }
    ) is None
    projected = project_runtime_clause(
        {
            "clause_type": "prohibition",
            "actor": "did:key:worker",
            "action": "dataset.read",
            "valid_from": 1_700_000_000,
            "metadata": {"semantic": "outside"},
        }
    )
    assert projected is not None
    assert projected.policy_type == "prohibition"
    assert projected.temporal is not None
    assert projected.temporal.not_before.endswith("+00:00")


def _quiet():
    return _chain([], hazard=False, policy_residual=False)


def test_nan_prohibition_does_not_fall_through_to_an_exact_grant():
    chain, _caller = _chain(
        [
            _response(
                {
                    "c0": {"noul": float("nan")},
                    "severity": {"score": 0.0},
                    "jailbreak": {"noul": 0.0},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                }
            )
        ]
    )
    clauses = (
        _permission(),
        _prohibition(semantic="outside the topics"),
    )
    admission = chain.admit(_request(clauses=clauses))
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "unresolved"


def test_nan_jailbreak_hides_an_exact_allow():
    chain, _caller = _chain(
        [
            _response(
                {
                    "jailbreak": {"noul": float("nan")},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                    "severity": {"score": 0.0},
                }
            )
        ]
    )
    admission = chain.admit(_request(clauses=(_permission(),)))
    assert admission.authorizing.decision == "allow"
    assert admission.show is False
    assert admission.display_cause == "hazard_unresolved"


def test_overdue_obligation_denies_beside_a_permission():
    chain, caller = _quiet()
    obligation = Policy(
        policy_type="obligation",
        action="dataset.read",
        subject="did:key:worker",
        temporal=Temporal(not_after="2020-01-01T00:00:00+00:00"),
        clause_id="o0",
    )
    admission = chain.admit(_request(clauses=(_permission(), obligation)))
    assert caller.calls == []
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "exact_deny"


def test_expired_duration_does_not_grant():
    chain, caller = _quiet()
    permission = Policy(
        policy_type="permission",
        action="dataset.read",
        subject="did:key:worker",
        temporal=Temporal(not_before="2020-01-01T00:00:00+00:00", duration="P1D"),
        clause_id="p0",
    )
    admission = chain.admit(_request(clauses=(permission,)))
    assert caller.calls == []
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "closed_world"


def test_glob_method_is_an_invalid_prohibition():
    chain, caller = _quiet()
    ban = Policy(
        policy_type="prohibition",
        action="dataset.read",
        subject="did:key:worker",
        conditions={"method": "repo.*"},
        clause_id="ban",
    )
    admission = chain.admit(_request(clauses=(_permission(), ban)))
    assert caller.calls == []
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "exact_deny"


def test_json_canonicalization_is_not_a_secret():
    chain, caller = _chain(
        [
            _response(
                {
                    "jailbreak": {"noul": 0.0},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_emission": {"noul": 0.0},
                    "broke_policy": {"noul": 0.0},
                    "override": {"noul": 0.0},
                    "severity": {"score": 0.0},
                }
            )
        ]
    )
    admission = chain.admit(
        _request(gate="output", payload='{"note": "fine"}', clauses=(_permission(),))
    )
    assert admission.authorizing.decision == "allow"
    assert caller.calls != []


def test_input_secret_withholds_a_residual_prohibition():
    chain, caller = _chain(
        [
            _response(
                {
                    "severity": {"score": 0.0},
                    "jailbreak": {"noul": 0.0},
                    "harm_or_crime": {"noul": 0.0},
                    "secret_request": {"noul": 0.0},
                }
            )
        ]
    )
    admission = chain.admit(
        _request(
            payload="Bearer sk-test-secret",
            clauses=(_permission(), _prohibition(semantic="outside the topics")),
        )
    )
    assert admission.authorizing.decision == "deny"
    assert admission.authorizing.witness["cause"] == "unresolved"
    assert caller.calls
    assert "c0" not in caller.calls[0]["questions"]


def test_undecodable_policy_cid_denies_with_no_call():
    chain, caller = _chain([])
    admission = chain.admit(
        _request(clauses=(_permission(),), policy_cid="bafyreiinvalidcidvalue")
    )
    assert caller.calls == []
    assert admission.authorizing.decision == "deny"


def test_non_finite_timestamp_projects_to_none():
    assert (
        project_runtime_clause(
            {
                "clause_type": "prohibition",
                "action": "dataset.read",
                "valid_from": float("nan"),
            }
        )
        is None
    )
