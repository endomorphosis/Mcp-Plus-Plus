"""Exact P/F/O decisions. Residual text is not decided here."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp_pp_system_one.witness import is_raw_leaf_cid, policy_document_cid, policy_preimage

STRUCTURAL_KEYS = frozenset({"interface_cid", "method", "max_bytes", "cid_allowlist"})
RESIDUAL_KEYS = frozenset({"semantic", "nl", "uncompiled"})

_WEEKS = re.compile(r"^P(\d+)W$")
_DURATION = re.compile(
    r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
)


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
    redaction_withheld: bool = False
    policy_cid: str | None = None
    policy_version: str = "v1"
    clauses: list[dict[str, Any]] = field(default_factory=list)
    now: str = ""
    gate: str = "input"
    intent_cid: str | None = None
    input_cid: str | None = None
    output_cid: str | None = None
    proofs_checked: list[Any] = field(default_factory=list)


def clause_document(clause: Policy) -> dict[str, Any]:
    """Policy-document clause. ``clause_id`` is not part of the CID preimage."""
    temporal = clause.temporal
    return {
        "policy_type": clause.policy_type,
        "action": clause.action,
        "subject": clause.subject,
        "resource": clause.resource,
        "temporal": None
        if temporal is None
        else {
            "not_before": temporal.not_before,
            "not_after": temporal.not_after,
            "duration": temporal.duration,
        },
        "conditions": clause.conditions,
    }


def _match_token(pattern: str | None, value: str | None) -> bool:
    if pattern is None or pattern == "*":
        return True
    return pattern == value


def _glob(text: Any) -> bool:
    return isinstance(text, str) and "*" in text and text != "*"


def _invalid_pattern(action: str, subject: str | None, resource: str | None, conditions: dict | None) -> bool:
    if _glob(action) or _glob(subject) or _glob(resource):
        return True
    if not conditions:
        return False
    if any(key not in STRUCTURAL_KEYS | RESIDUAL_KEYS for key in conditions):
        return True
    for key in ("method", "interface_cid"):
        if key not in conditions:
            continue
        value = conditions[key]
        if value is None:
            continue
        if not isinstance(value, str) or _glob(value):
            return True
    if "max_bytes" in conditions:
        size = conditions["max_bytes"]
        if isinstance(size, bool) or not isinstance(size, int):
            return True
    allowlist = conditions.get("cid_allowlist")
    if allowlist is not None:
        if not isinstance(allowlist, (list, tuple)):
            return True
        if any(not isinstance(item, str) or _glob(item) for item in allowlist):
            return True
    return False


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_duration(text: str) -> tuple[int, int, int, int, int, int, int] | None:
    """Years, months, weeks, days, hours, minutes, seconds. None if not ISO-8601."""
    if not isinstance(text, str) or text in {"P", "PT"}:
        return None
    weeks = _WEEKS.fullmatch(text)
    if weeks:
        return (0, 0, int(weeks.group(1)), 0, 0, 0, 0)
    match = _DURATION.fullmatch(text)
    if match is None:
        return None
    if "T" in text and not any(match.group(index) for index in (4, 5, 6)):
        return None
    years, months, days, hours, minutes, seconds = (
        int(group) if group else 0 for group in match.groups()
    )
    if not any((years, months, days, hours, minutes, seconds)):
        return None
    return (years, months, 0, days, hours, minutes, seconds)


def _add_duration(start: datetime, parts: tuple[int, int, int, int, int, int, int]) -> datetime:
    years, months, weeks, days, hours, minutes, seconds = parts
    month_index = start.month - 1 + months
    year = start.year + years + month_index // 12
    month = month_index % 12 + 1
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=start.tzinfo)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=start.tzinfo)
    last_day = (next_month - timedelta(days=1)).day
    anchored = start.replace(year=year, month=month, day=min(start.day, last_day))
    return anchored + timedelta(
        weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds
    )


def _resolved_window(temporal: Temporal | None, now: datetime) -> tuple[str, str | None]:
    """Return ``(status, deadline)``. Status is ``ok``, ``before``, ``after``, or ``invalid``."""
    if temporal is None:
        return "ok", None
    try:
        start = _parse_time(temporal.not_before)
        end = _parse_time(temporal.not_after)
    except ValueError:
        return "invalid", None
    deadline = temporal.not_after
    if temporal.duration:
        parts = _parse_duration(temporal.duration)
        if parts is None or start is None:
            return "invalid", None
        if end is None:
            end = _add_duration(start, parts)
            deadline = end.isoformat()
    if start is not None and now < start:
        return "before", deadline
    if end is not None and now > end:
        return "after", deadline
    return "ok", deadline


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
        if not is_raw_leaf_cid(request.policy_cid):
            report.unknown_policy = True
            return report
        clauses = list(request.clauses)
        if not clauses:
            report.empty_policy = True
            return report
        document = policy_preimage(
            report.policy_version, [clause_document(clause) for clause in clauses]
        )
        if policy_document_cid(document) != request.policy_cid:
            report.policy_cid_mismatch = True
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
                self._stamp(report, clause_id, "invalid")
                continue
            status, deadline = _resolved_window(clause.temporal, request.now)
            if status == "invalid":
                self._invalid(report, clause, clause_id)
                self._stamp(report, clause_id, "invalid")
                continue
            if not _match_token(clause.action, request.action):
                self._stamp(report, clause_id, "inapplicable")
                continue
            if not _match_token(clause.subject, request.subject):
                self._stamp(report, clause_id, "inapplicable")
                continue
            if not _match_token(clause.resource, request.resource):
                self._stamp(report, clause_id, "inapplicable")
                continue
            if not self._structural(conditions, request):
                self._stamp(report, clause_id, "inapplicable")
                continue
            if status == "before":
                self._stamp(report, clause_id, "inapplicable")
                continue
            if clause.policy_type == "obligation":
                self._obligation(report, clause, clause_id, status, deadline)
                continue
            if status == "after":
                self._stamp(report, clause_id, "inapplicable")
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
                self._stamp(report, clause_id, "residual")
                continue
            if clause.policy_type == "prohibition":
                report.denies.append(clause_id)
                self._stamp(report, clause_id, "exact_deny")
            elif clause.policy_type == "permission":
                report.grants.append(clause)
                self._stamp(report, clause_id, "grant")
            else:
                self._invalid(report, clause, clause_id)
                self._stamp(report, clause_id, "invalid")
        return report

    def _obligation(
        self,
        report: ExactReport,
        clause: Policy,
        clause_id: str,
        status: str,
        deadline: str | None,
    ) -> None:
        # A matched obligation past its deadline denies. Expiry is not "does not apply".
        if deadline is None:
            report.invalid_obligations.append(clause_id)
            self._stamp(report, clause_id, "invalid")
            return
        if status == "after":
            report.denies.append(clause_id)
            self._stamp(report, clause_id, "exact_deny")
            return
        report.obligations.append(
            {
                "type": "obligation",
                "action": clause.action,
                "subject": clause.subject,
                "resource": clause.resource,
                "deadline": deadline,
            }
        )
        self._stamp(report, clause_id, "obligation")

    def _stamp(self, report: ExactReport, clause_id: str, disposition: str) -> None:
        report.clauses.append({"clause_id": clause_id, "disposition": disposition, "noul": None})

    def _invalid(self, report: ExactReport, clause: Policy, clause_id: str) -> None:
        if clause.policy_type == "permission":
            return
        if clause.policy_type == "obligation":
            report.invalid_obligations.append(clause_id)
        else:
            report.invalid_prohibitions.append(clause_id)

    def _structural(self, conditions: dict[str, Any], request: Any) -> bool:
        if "interface_cid" in conditions and not _match_token(
            conditions["interface_cid"], request.interface_cid
        ):
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
