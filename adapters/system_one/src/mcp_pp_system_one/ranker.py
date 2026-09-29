"""Two-pass tool rank. A Choice of none exposes nothing."""

import math
from typing import Any

from mcp_pp_system_one.cache import STAGE_TOOL_RANK, descriptor_cid_material, load_or_store
from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.jev_client import Abstain, JevClient
from mcp_pp_system_one.ports import (
    Prior,
    SliceReason,
    StageKind,
    StageOutcome,
    ToolSlice,
    ToolSliceRequest,
    reason,
)
from mcp_pp_system_one.questions import (
    TOKEN_ESTIMATE_LIMIT,
    estimate_tokens,
    merge_choice,
    pass1,
    pass2,
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _summary(desc: Any) -> str:
    text = _get(desc, "summary") or _get(desc, "description") or ""
    return str(text)[:160]


def _excerpt(desc: Any) -> str:
    text = _get(desc, "description") or _get(desc, "summary") or ""
    methods = _get(desc, "methods") or []
    names = []
    for method in methods:
        name = _get(method, "name")
        if name:
            names.append(str(name))
    joined = str(text)
    if names:
        joined = f"{joined} — {', '.join(names)}"
    return joined[:700]


def _view(desc: Any, prior: Prior, *, excerpt: bool) -> dict[str, Any]:
    cid = str(_get(desc, "interface_cid"))
    body = _excerpt(desc) if excerpt else _summary(desc)
    field = "excerpt" if excerpt else "summary"
    return {
        "id": cid,
        "name": str(_get(desc, "name") or ""),
        "namespace": str(_get(desc, "namespace") or ""),
        field: body,
        "cost_tokens": int(prior.cost_tokens.get(cid, 0)),
        "side_effect": prior.side_effect.get(cid, "write"),
    }


def _unit(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def _noul(answers: dict[str, Any], key: str) -> float | None:
    item = answers.get(key)
    if not isinstance(item, dict) or "noul" not in item:
        return None
    return _unit(item["noul"])


def chunk_gate(answers: dict[str, Any]) -> float | None:
    act = _noul(answers, "gate_act")
    procedure = _noul(answers, "gate_procedure")
    prose = _noul(answers, "gate_prose")
    if act is None or procedure is None or prose is None:
        return None
    return (act + procedure + (1.0 - prose)) / 3.0


def confidence_for(which: dict[str, Any]) -> float | None:
    if which.get("choice") == "none":
        return None
    return _unit(which.get("confidence"))


class ToolRanker:
    implementation_id = "system-one-ranker/v1"

    def __init__(self, config: SystemOneConfig, client: JevClient) -> None:
        self.config = config
        self.client = client

    def run(self, request: ToolSliceRequest, prior: Prior) -> StageOutcome:
        hint = (request.task_hint or "").strip()
        if not hint:
            return self._abstain(frozenset(), reason("missing_task_hint"))
        by_cid = {
            str(_get(desc, "interface_cid")): desc for desc in request.descriptors
        }
        ordered = [
            by_cid[cid]
            for cid in prior.pool
            if cid in by_cid and cid not in prior.excluded
        ]
        chunks, too_large = self._pack(hint, ordered, prior)
        excluded = set(too_large)
        reasons: list[SliceReason] = [
            reason("descriptor_too_large", cid) for cid in too_large
        ]
        shortlisted: list[str] = []
        for views in chunks:
            answers = self._ask(*pass1(hint, views), hint_cid=request.task_hint_cid)
            if isinstance(answers, Abstain):
                return self._abstain(frozenset(excluded), *reasons, reason(answers.code))
            for index, view in enumerate(views):
                score = _noul(answers, f"override[{index}]")
                if score is not None and score >= self.config.override_exclude:
                    excluded.add(view["id"])
                    reasons.append(reason("descriptor_override", view["id"]))
            gate = chunk_gate(answers)
            if gate is None or gate < self.config.gate:
                continue
            which = answers.get("which")
            if not isinstance(which, dict):
                return self._abstain(frozenset(excluded), *reasons, reason("malformed"))
            probs = which.get("probabilities") or {}
            ranked = sorted(
                (view["id"] for view in views if view["id"] not in excluded),
                key=lambda cid: -float(probs.get(cid, 0.0)),
            )
            for cid in ranked[:3]:
                if cid not in shortlisted:
                    shortlisted.append(cid)
        if not shortlisted:
            return self._empty(excluded, reasons)
        merge_views = [_view(by_cid[cid], prior, excerpt=False) for cid in shortlisted]
        answers = self._ask(*merge_choice(hint, merge_views), hint_cid=request.task_hint_cid)
        if isinstance(answers, Abstain):
            return self._abstain(frozenset(excluded), *reasons, reason(answers.code))
        which = answers.get("which") if isinstance(answers, dict) else None
        if not isinstance(which, dict) or which.get("choice") == "none":
            return self._empty(excluded, reasons)
        if confidence_for(which) is None and which.get("choice") != "none":
            return self._empty(excluded, reasons)
        probs = which.get("probabilities") or {}
        picked = str(which["choice"])
        ordered_ids = sorted(
            (cid for cid in shortlisted if cid not in excluded),
            key=lambda cid: (-float(probs.get(cid, 0.0)), cid != picked),
        )
        survivors = ordered_ids[: self.config.rerank_k]
        if picked in survivors:
            survivors = [picked] + [cid for cid in survivors if cid != picked]
            survivors = survivors[: self.config.rerank_k]
        if not survivors:
            return self._empty(excluded, reasons)
        pass2_views = [_view(by_cid[cid], prior, excerpt=True) for cid in survivors]
        answers = self._ask(*pass2(hint, pass2_views), hint_cid=request.task_hint_cid)
        if isinstance(answers, Abstain):
            return self._abstain(frozenset(excluded), *reasons, reason(answers.code))
        for index, view in enumerate(pass2_views):
            score = _noul(answers, f"override[{index}]")
            if score is not None and score >= self.config.override_exclude:
                excluded.add(view["id"])
                reasons.append(reason("descriptor_override", view["id"]))
        which = answers.get("which") if isinstance(answers, dict) else None
        if not isinstance(which, dict) or which.get("choice") == "none":
            return self._empty(excluded, reasons)
        fits_scores = [
            _noul(answers, f"fits[{index}]") for index in range(len(pass2_views))
        ]
        confidence = confidence_for(which)
        choice = str(which.get("choice"))
        winner_index = next(
            (index for index, view in enumerate(pass2_views) if view["id"] == choice),
            None,
        )
        winner_fits = (
            0.0
            if winner_index is None or fits_scores[winner_index] is None
            else fits_scores[winner_index]
        )
        if winner_fits < self.config.fits:
            return self._empty(excluded, reasons)
        packed: list[str] = []
        if (
            winner_index is not None
            and choice not in excluded
            and self.config.max_exposed >= 1
        ):
            floor = (
                self.config.read_confidence
                if prior.side_effect.get(choice) == "read"
                else self.config.write_confidence
            )
            if confidence is not None and confidence >= floor:
                packed.append(choice)
        used = float(sum(prior.cost_tokens.get(cid, 0) for cid in packed))
        tool_slice = ToolSlice(
            interface_cids=tuple(packed),
            reasons=tuple(reasons),
            implementation_id=self.implementation_id,
            budget_tokens_used=used,
            abstained=False,
        )
        return StageOutcome(
            kind=StageKind.HALT,
            slice=tool_slice,
            excluded=frozenset(excluded),
            reasons=tuple(reasons),
        )

    def _pack(
        self, task: str, descriptors: list[Any], prior: Prior
    ) -> tuple[list[list[dict[str, Any]]], list[str]]:
        chunks: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        too_large: list[str] = []
        for desc in descriptors:
            view = _view(desc, prior, excerpt=False)
            alone_state, alone_questions = pass1(task, [view])
            if estimate_tokens(alone_state, alone_questions) > TOKEN_ESTIMATE_LIMIT:
                too_large.append(view["id"])
                continue
            trial = current + [view]
            state, questions = pass1(task, trial)
            over_count = len(trial) > self.config.chunk
            over_tokens = estimate_tokens(state, questions) > TOKEN_ESTIMATE_LIMIT
            if current and (over_count or over_tokens):
                chunks.append(current)
                current = [view]
            else:
                current = trial
        if current:
            chunks.append(current)
        return chunks, too_large

    def _ask(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
        *,
        hint_cid: str | None,
    ) -> Any:
        descriptors = state.get("descriptors") or []
        ids = [str(item.get("id", "")) for item in descriptors if isinstance(item, dict)]
        if not isinstance(hint_cid, str) or hint_cid.strip() == "":
            return self.client.system_one(state=state, questions=questions)
        material = descriptor_cid_material(hint_cid, ",".join(ids))
        return load_or_store(
            self.config,
            stage=STAGE_TOOL_RANK,
            questions=questions,
            cid_material=material,
            fetch=lambda: self.client.system_one(state=state, questions=questions),
        )

    def _empty(self, excluded: set[str], reasons: list[SliceReason]) -> StageOutcome:
        return StageOutcome(
            kind=StageKind.HALT,
            slice=ToolSlice(
                interface_cids=(),
                reasons=tuple(reasons),
                implementation_id=self.implementation_id,
                budget_tokens_used=0.0,
                abstained=False,
            ),
            excluded=frozenset(excluded),
            reasons=tuple(reasons),
        )

    def _abstain(self, excluded: frozenset[str], *reasons: SliceReason) -> StageOutcome:
        return StageOutcome(
            kind=StageKind.ABSTAIN,
            slice=None,
            excluded=excluded,
            reasons=reasons,
        )
