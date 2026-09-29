"""Exact P/F/O decisions. Residual text is not decided here."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

STRUCTURAL_KEYS = frozenset({"interface_cid", "method", "max_bytes", "cid_allowlist"})
RESIDUAL_KEYS = frozenset({"semantic", "nl", "uncompiled"})


@dataclass(frozen=True)
class Temporal:
    not_before: str | None = None
    not_after: str | None = None
    duration: str | None = None


@dataclass(frozen=True)
class Policy:
    policy_type: str
    action: str
    subject: str | None = None
    resource: str | None = None
    temporal: Temporal | None = None
    conditions: dict[str, Any] | None = None
    clause_id: str = ""


@dataclass
class ExactReport:
    denies: list[str] = field(default_factory=list)
    grants: list[Policy] = field(default_factory=list)
    obligations: list[dict[str, Any]] = field(default_factory=list)
    residual: list[Policy] = field(default_factory=list)
    invalid_prohibitions: list[str] = field(default_factory=list)
    invalid_obligations: list[str] = field(default_factory=list)
    unknown_policy: bool = False
    empty_policy: bool = False
    authority_unverified: bool = False
    secret_in_output: bool = False
    policy_cid_mismatch: bool = False
    policy_cid: str | None = None
    policy_version: str = "v1"
    clauses: list[dict[str, Any]] = field(default_factory=list)
    now: str = ""
    gate: str = "input"
    intent_cid: str | None = None
    input_cid: str | None = None
    output_cid: str | None = None
    proofs_checked: list[Any] = field(default_factory=list)


def _match_token(pattern: str | None, value: str | None) -> bool:
    if pattern is None or pattern == "*":
        return True
    return pattern == value


def _invalid_pattern(action: str, subject: str | None, resource: str | None, conditions: dict | None) -> bool:
    for text in (action, subject, resource):
        if isinstance(text, str) and ("*" in text and text != "*"):
            return True
    if not conditions:
        return False
    return any(key not in STRUCTURAL_KEYS | RESIDUAL_KEYS for key in conditions)


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _window_holds(temporal: Temporal | None, now: datetime) -> bool | None:
    """True when the window contains now. None means the temporal fields are invalid."""
    if temporal is None:
        return True
    try:
        start = _parse_time(temporal.not_before)
        end = _parse_time(temporal.not_after)
    except ValueError:
        return None
    if temporal.duration and start is None:
        return None
    if start is not None and now < start:
        return False
    if end is not None and now > end:
        return False
    return True


class ExactStage:
    def classify(self, request: Any) -> ExactReport:
        report = ExactReport(
            policy_cid=request.policy_cid,
            policy_version=getattr(request, "policy_version", "v1") or "v1",
            now=request.now.isoformat(),
            gate=request.gate,
            intent_cid=request.intent_cid,
            input_cid=request.input_cid,
            output_cid=request.output_cid,
            proofs_checked=list(request.proofs_checked or []),
        )
        if request.policy_cid is None:
            report.unknown_policy = True
            return report
        clauses = list(request.clauses)
        if not clauses:
            report.empty_policy = True
            return report
        if request.gate == "output" and request.require_proofs and request.proofs_checked is None:
            report.authority_unverified = True
        if getattr(request, "secret_in_output", False):
            report.secret_in_output = True
        for index, clause in enumerate(clauses):
            clause_id = clause.clause_id or f"c{index}"
            conditions = clause.conditions or {}
            if _invalid_pattern(clause.action, clause.subject, clause.resource, conditions):
                self._invalid(report, clause, clause_id)
                continue
            window = _window_holds(clause.temporal, request.now)
            if window is None:
                self._invalid(report, clause, clause_id)
                continue
            if not window:
                continue
            if not _match_token(clause.action, request.action):
                continue
            if not _match_token(clause.subject, request.subject):
                continue
            if not _match_token(clause.resource, request.resource):
                continue
            if not self._structural(conditions, request):
                continue
            residual_bits = {
                key: conditions[key] for key in RESIDUAL_KEYS if key in conditions
            }
            if residual_bits:
                report.residual.append(
                    Policy(
                        policy_type=clause.policy_type,
                        action=clause.action,
                        subject=clause.subject,
                        resource=clause.resource,
                        temporal=clause.temporal,
                        conditions=residual_bits,
                        clause_id=clause_id,
                    )
                )
                continue
            if clause.policy_type == "prohibition":
                report.denies.append(clause_id)
            elif clause.policy_type == "permission":
                report.grants.append(clause)
            elif clause.policy_type == "obligation":
                deadline = clause.temporal.not_after if clause.temporal else None
                if deadline is None:
                    report.invalid_obligations.append(clause_id)
                else:
                    end = _parse_time(deadline)
                    if end is not None and request.now > end:
                        report.denies.append(clause_id)
                    else:
                        report.obligations.append(
                            {
                                "type": "obligation",
                                "action": clause.action,
                                "subject": clause.subject,
                                "resource": clause.resource,
                                "deadline": deadline,
                            }
                        )
            else:
                self._invalid(report, clause, clause_id)
        return report

    def _invalid(self, report: ExactReport, clause: Policy, clause_id: str) -> None:
        if clause.policy_type == "permission":
            return
        if clause.policy_type == "obligation":
            report.invalid_obligations.append(clause_id)
        else:
            report.invalid_prohibitions.append(clause_id)

    def _structural(self, conditions: dict[str, Any], request: Any) -> bool:
        if "interface_cid" in conditions and conditions["interface_cid"] != request.interface_cid:
            return False
        method = conditions.get("method")
        if method not in (None, "*") and method != request.method:
            return False
        if "max_bytes" in conditions and request.size_bytes is not None:
            if int(request.size_bytes) > int(conditions["max_bytes"]):
                return False
        allowlist = conditions.get("cid_allowlist")
        if allowlist is not None:
            target = request.output_cid if request.gate == "output" else request.input_cid
            if target not in allowlist:
                return False
        return True
