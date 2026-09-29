"""Policy verdicts. Hazard can hide a result. It cannot change the verdict."""

from dataclasses import dataclass
from typing import Any

from mcp_pp_system_one.cache import STAGE_POLICY, load_or_store, policy_cid_material
from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.exact_policy import ExactReport, ExactStage, Policy, clause_document
from mcp_pp_system_one.hazard import (
    HazardReport,
    _finite,
    _unit_interval,
    hazard_questions,
    hazard_slice,
)
from mcp_pp_system_one.jev_client import Abstain, JevClient
from mcp_pp_system_one.metrics import Metrics
from mcp_pp_system_one.redact import redact_serialized
from mcp_pp_system_one.residual import compile_residual, residual_state
from mcp_pp_system_one.witness import (
    canonical_json_bytes,
    decision_preimage,
    question_set_hash,
    seal_decision_witness,
)

PRECEDENCE = ("exact_deny", "unresolved", "prohibition_deny", "severity", "review")
POLICY_IMPLEMENTATION_ID = "system-one-policy/v1"


@dataclass
class PolicyDecision:
    decision: str
    allowed: bool
    obligations: list[Any]
    policy_cid: str | None
    witness: dict[str, Any]
    decision_cid: str | None = None


@dataclass(frozen=True)
class GateAdmission:
    show: bool
    authorizing: PolicyDecision
    display_cause: str


@dataclass
class FuzzyReport:
    nouls: dict[str, float]
    severity: float | None


def _thresholds(cfg: SystemOneConfig) -> dict[str, float]:
    return {
        "prohibition_review": cfg.prohibition_review,
        "prohibition_deny": cfg.prohibition_deny,
        "permission_allow": cfg.permission_allow,
        "severity_block": cfg.severity_block,
    }


def _policy_stamp(cfg: SystemOneConfig, questions: dict[str, Any]) -> dict[str, str]:
    # config.model is the request pin. The response model is not a witness field.
    return {
        "implementation_id": POLICY_IMPLEMENTATION_ID,
        "model_id": cfg.model,
        "question_set_hash": question_set_hash(questions),
    }


def _seal(exact: ExactReport, cfg: SystemOneConfig, **fields: Any) -> dict[str, Any]:
    preimage = decision_preimage(
        decision=fields["decision"],
        allowed=fields["allowed"],
        obligations=fields.get("obligations") or [],
        policy_cid=exact.policy_cid or "",
        policy_version=exact.policy_version,
        intent_cid=exact.intent_cid,
        proofs_checked=exact.proofs_checked,
        gate=exact.gate,
        now=exact.now,
        thresholds=_thresholds(cfg),
        clauses=exact.clauses,
        input_cid=exact.input_cid,
        output_cid=exact.output_cid,
        implementation_id=fields.get("implementation_id"),
        model_id=fields.get("model_id"),
        question_set_hash=fields.get("question_set_hash"),
        severity=fields.get("severity"),
        disposition=fields.get("disposition"),
        cause=fields.get("cause"),
    )
    return seal_decision_witness(preimage)


def deny_for(
    kind: str,
    exact: ExactReport,
    cfg: SystemOneConfig,
    severity: float | None = None,
    *,
    stamp: dict[str, str] | None = None,
) -> PolicyDecision:
    disposition = "review" if kind == "review" else "deny"
    cause = "policy" if kind == "review" else kind
    witness = _seal(
        exact,
        cfg,
        decision="deny",
        allowed=False,
        obligations=[],
        disposition=disposition,
        cause=cause,
        severity=severity,
        **(stamp or {}),
    )
    return PolicyDecision(
        decision="deny",
        allowed=False,
        obligations=[],
        policy_cid=exact.policy_cid,
        witness=witness,
        decision_cid=witness["decision_cid"],
    )


def allow(
    exact: ExactReport,
    cfg: SystemOneConfig,
    *,
    stamp: dict[str, str] | None = None,
) -> PolicyDecision:
    witness = _seal(
        exact,
        cfg,
        decision="allow",
        allowed=True,
        obligations=[],
        disposition="allow",
        cause="exact",
        **(stamp or {}),
    )
    return PolicyDecision(
        decision="allow",
        allowed=True,
        obligations=[],
        policy_cid=exact.policy_cid,
        witness=witness,
        decision_cid=witness["decision_cid"],
    )


def allow_with_obligations(
    exact: ExactReport,
    cfg: SystemOneConfig,
    *,
    stamp: dict[str, str] | None = None,
) -> PolicyDecision:
    witness = _seal(
        exact,
        cfg,
        decision="allow_with_obligations",
        allowed=True,
        obligations=list(exact.obligations),
        disposition="allow",
        cause="exact",
        **(stamp or {}),
    )
    return PolicyDecision(
        decision="allow_with_obligations",
        allowed=True,
        obligations=list(exact.obligations),
        policy_cid=exact.policy_cid,
        witness=witness,
        decision_cid=witness["decision_cid"],
    )


def _stamp(exact: ExactReport, clause_id: str, disposition: str, noul: float | None) -> None:
    for record in exact.clauses:
        if record.get("clause_id") == clause_id:
            record["disposition"] = disposition
            record["noul"] = noul
            return
    exact.clauses.append({"clause_id": clause_id, "disposition": disposition, "noul": noul})


def noul_of(fuzzy: FuzzyReport | Abstain | None, clause_id: str) -> float | None:
    if not isinstance(fuzzy, FuzzyReport):
        return None
    return _unit_interval(fuzzy.nouls.get(clause_id))


def combine_policy(
    exact: ExactReport,
    fuzzy: FuzzyReport | Abstain | None,
    cfg: SystemOneConfig,
    *,
    residual_enabled: bool,
    stamp: dict[str, str] | None = None,
) -> PolicyDecision:
    signals: list[str] = []
    if _final_exact_deny(exact):
        signals.append("exact_deny")
    if exact.redaction_withheld:
        signals.append("unresolved")
    for clause in exact.residual:
        if clause.policy_type != "prohibition":
            continue
        score = noul_of(fuzzy, clause.clause_id) if residual_enabled else None
        if score is None:
            signals.append("unresolved")
            _stamp(exact, clause.clause_id, "unresolved", None)
        elif score >= cfg.prohibition_deny:
            signals.append("prohibition_deny")
            _stamp(exact, clause.clause_id, "prohibition_deny", score)
        elif score >= cfg.prohibition_review:
            signals.append("review")
            _stamp(exact, clause.clause_id, "review", score)
        else:
            _stamp(exact, clause.clause_id, "clear", score)
    severity = _finite(fuzzy.severity) if isinstance(fuzzy, FuzzyReport) else None
    if "review" in signals and severity is not None and severity >= cfg.severity_block:
        signals.append("severity")
    for kind in PRECEDENCE:
        if kind in signals:
            return deny_for(kind, exact, cfg, severity=severity, stamp=stamp)
    grants = list(exact.grants)
    if residual_enabled and isinstance(fuzzy, FuzzyReport):
        for clause in exact.residual:
            if clause.policy_type != "permission":
                continue
            score = noul_of(fuzzy, clause.clause_id)
            if score is not None and score >= cfg.permission_allow:
                grants.append(clause)
                _stamp(exact, clause.clause_id, "grant", score)
            else:
                _stamp(exact, clause.clause_id, "clear", score)
    if not grants:
        return deny_for("closed_world", exact, cfg, severity=severity, stamp=stamp)
    if exact.obligations:
        return allow_with_obligations(exact, cfg, stamp=stamp)
    return allow(exact, cfg, stamp=stamp)


def reduce_display(
    authorizing: PolicyDecision,
    hazard: HazardReport | Abstain | None,
    cfg: SystemOneConfig,
) -> GateAdmission:
    witness = authorizing.witness
    if authorizing.decision == "deny" and witness.get("disposition") != "review":
        return GateAdmission(False, authorizing, str(witness["cause"]))
    if isinstance(hazard, HazardReport) and any(
        score >= cfg.hazard_action for score in hazard.nouls.values()
    ):
        return GateAdmission(False, authorizing, "hazard")
    if (
        isinstance(hazard, HazardReport)
        and hazard.severity is not None
        and hazard.severity >= cfg.severity_block
        and any(score >= cfg.prohibition_review for score in hazard.nouls.values())
    ):
        return GateAdmission(False, authorizing, "severity")
    if witness.get("disposition") == "review":
        return GateAdmission(False, authorizing, "review")
    if authorizing.decision in ("allow", "allow_with_obligations"):
        return GateAdmission(True, authorizing, "allow")
    return GateAdmission(False, authorizing, "deny")


def _fuzzy_from(answers: dict[str, Any] | None, residual: list[Policy]) -> FuzzyReport | Abstain:
    if not isinstance(answers, dict):
        return Abstain("malformed")
    nouls: dict[str, float] = {}
    for index, clause in enumerate(residual):
        item = answers.get(f"c{index}")
        if not isinstance(item, dict) or "noul" not in item:
            continue
        score = _unit_interval(item["noul"])
        if score is None:
            continue
        nouls[clause.clause_id] = score
    severity = None
    item = answers.get("severity")
    if isinstance(item, dict) and "score" in item:
        severity = _finite(item["score"])
    return FuzzyReport(nouls=nouls, severity=severity)


class PolicyConformanceChain:
    def __init__(
        self,
        config: SystemOneConfig | None = None,
        client: JevClient | None = None,
        exact: ExactStage | None = None,
        display: Any = None,
    ) -> None:
        self.config = config or SystemOneConfig()
        self.client = client
        self.exact = exact or ExactStage()
        self.display = display or reduce_display
        self.metrics = Metrics()
        self.clock = None
        self.started_at = 0.0

    def evaluate(self, request: Any) -> PolicyDecision:
        try:
            return self.admit(request).authorizing
        except Exception:
            return self._deny_unresolved(request)

    def admit(self, request: Any) -> GateAdmission:
        authorizing: PolicyDecision | None = None
        # False until assigned below. An exception before that leaves the witness null.
        residual_on = False
        hazard_on = False
        questions: dict[str, Any] = {}
        stamp: dict[str, str] | None = None
        try:
            if self.clock is not None and self.clock() - self.started_at > self.config.policy_deadline_s:
                self.metrics.inc("system_one_stage_total", stage="policy", result="deny")
                return GateAdmission(False, self._deny_unresolved(request), "deadline")
            if request.gate == "output" and _redaction_removed(
                request.payload, fail_closed=True
            ):
                request.secret_in_output = True
            exact = self.exact.classify(request)
            _withhold_redacted_prohibitions(request, exact)
            if _final_exact_deny(exact):
                authorizing = combine_policy(exact, None, self.config, residual_enabled=False)
                return self.display(authorizing, None, self.config)
            master = self.config.enabled and self.client is not None
            residual_on = bool(master and self.config.policy_residual and exact.residual)
            hazard_on = bool(master and self.config.hazard)
            if not residual_on and not hazard_on:
                authorizing = combine_policy(exact, None, self.config, residual_enabled=False)
                return self.display(authorizing, None, self.config)
            state: dict[str, Any] = {"payload": request.payload}
            if residual_on:
                questions.update(compile_residual(exact.residual))
                state = residual_state(request.payload, exact.residual)
            if hazard_on:
                questions.update(hazard_questions(request.gate))
            stamp = _policy_stamp(self.config, questions)
            content = (
                getattr(request, "output_cid", None)
                if getattr(request, "gate", "") == "output"
                else getattr(request, "input_cid", None)
            )
            content_cid = None if content is None else str(content)
            # None and a blank CID share one cache suffix, so do not store either.
            if content_cid is None or content_cid.strip() == "":
                answers = self.client.system_one(state=state, questions=questions)
            else:
                material = policy_cid_material(
                    canonical_json_bytes(
                        [clause_document(clause) for clause in exact.residual]
                    ),
                    content_cid,
                )
                answers = load_or_store(
                    self.config,
                    stage=STAGE_POLICY,
                    questions=questions,
                    cid_material=material,
                    fetch=lambda: self.client.system_one(state=state, questions=questions),
                )
            fuzzy = _fuzzy_from(answers, exact.residual) if residual_on else None
            hazard = hazard_slice(answers, request.gate) if hazard_on else None
            authorizing = combine_policy(
                exact, fuzzy, self.config, residual_enabled=residual_on, stamp=stamp
            )
            if hazard_on and not isinstance(hazard, HazardReport):
                return GateAdmission(False, authorizing, "hazard_unresolved")
            return self.display(authorizing, hazard, self.config)
        except Exception:
            if authorizing is None:
                if stamp is None and (residual_on or hazard_on):
                    stamp = _policy_stamp(self.config, questions)
                authorizing = self._deny_unresolved(request, stamp=stamp)
            return GateAdmission(False, authorizing, "admit_exception")

    def _deny_unresolved(
        self,
        request: Any,
        stamp: dict[str, str] | None = None,
    ) -> PolicyDecision:
        exact = ExactReport(
            policy_cid=getattr(request, "policy_cid", None),
            now=getattr(getattr(request, "now", None), "isoformat", lambda: "")(),
            gate=getattr(request, "gate", "input"),
        )
        exact.unknown_policy = True
        return deny_for("unresolved", exact, self.config, stamp=stamp)


def _final_exact_deny(exact: ExactReport) -> bool:
    return bool(
        exact.denies
        or exact.invalid_prohibitions
        or exact.invalid_obligations
        or exact.unknown_policy
        or exact.empty_policy
        or exact.authority_unverified
        or exact.secret_in_output
        or exact.policy_cid_mismatch
    )


def _marked(value: Any) -> bool:
    if isinstance(value, str):
        return "[REDACTED:" in value
    if isinstance(value, dict):
        return any(_marked(key) or _marked(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_marked(item) for item in value)
    return False


def _redaction_removed(payload: Any, *, fail_closed: bool = False) -> bool:
    # Input withhold keeps the default: an unreadable body did not remove a secret.
    try:
        return _marked(redact_serialized(payload))
    except (TypeError, ValueError):
        return fail_closed


def _withhold_redacted_prohibitions(request: Any, exact: ExactReport) -> None:
    if getattr(request, "gate", "input") == "output":
        return
    if not _redaction_removed(getattr(request, "payload", None)):
        return
    kept: list[Policy] = []
    withheld = False
    for clause in exact.residual:
        if clause.policy_type == "prohibition":
            withheld = True
            _stamp(exact, clause.clause_id, "redaction_withheld_judgement", None)
        else:
            kept.append(clause)
    if withheld:
        exact.redaction_withheld = True
        exact.residual = kept
