"""Tool-slice chain. Ranker is optional and defaults to absent."""

from dataclasses import replace
from typing import Any

from mcp_pp_system_one.abstain import AbstainEmpty
from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.ports import (
    Prior,
    StageKind,
    StageOutcome,
    ToolSlice,
    ToolSliceRequest,
)
from mcp_pp_system_one.metrics import Metrics
from mcp_pp_system_one.structural import StructuralSlicer


def intersect_halt(outcome: StageOutcome, prior: Prior) -> ToolSlice:
    assert outcome.kind is StageKind.HALT and outcome.slice is not None
    banned = prior.excluded | outcome.excluded
    kept = tuple(
        cid
        for cid in outcome.slice.interface_cids
        if cid in prior.pool and cid not in banned
    )
    return replace(outcome.slice, interface_cids=kept)


class ToolSliceChain:
    def __init__(
        self,
        structural: Any = None,
        ranker: Any = None,
        config: SystemOneConfig | None = None,
    ) -> None:
        self.config = config or SystemOneConfig()
        self.structural = (
            structural if structural is not None else StructuralSlicer(self.config)
        )
        self.ranker = ranker
        self.abstain = AbstainEmpty()
        self.metrics = Metrics()
        self.clock = None
        self.started_at = 0.0

    def disable_jev(self) -> None:
        self.ranker = None
        self.config = replace(
            self.config,
            enabled=False,
            tool_rank=False,
            policy_residual=False,
            hazard=False,
        )

    def _past_tool_deadline(self) -> bool:
        if self.clock is None:
            return False
        return self.clock() - self.started_at > self.config.tool_deadline_s

    def select(self, request: ToolSliceRequest) -> ToolSlice:
        if self._past_tool_deadline():
            self.metrics.inc("system_one_stage_total", stage="tool", result="abstain")
            return self.abstain.halt(
                Prior((), frozenset(), (), {}, {})
            )
        prior = Prior(
            pool=(),
            excluded=frozenset(),
            reasons=(),
            side_effect={},
            cost_tokens={},
        )
        try:
            prior = self.structural.filter(request)
            if self.ranker is None:
                return self.abstain.halt(prior)
            outcome = self.ranker.run(request, prior)
            if outcome.kind is StageKind.ABSTAIN:
                stuck = replace(
                    prior,
                    excluded=prior.excluded | outcome.excluded,
                    reasons=prior.reasons + outcome.reasons,
                )
                return self.abstain.halt(stuck)
            return intersect_halt(outcome, prior)
        except Exception:  # noqa: BLE001 - every failure fails over to an empty slice
            return self.abstain.halt(prior)
