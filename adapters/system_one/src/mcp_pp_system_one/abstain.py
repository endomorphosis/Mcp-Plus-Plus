"""Last tool stage. Empty slice; excluded CIDs are not put back."""

from mcp_pp_system_one.ports import Prior, ToolSlice, reason


class AbstainEmpty:
    implementation_id = "abstain-empty/v1"

    def halt(self, prior: Prior) -> ToolSlice:
        return ToolSlice(
            interface_cids=(),
            reasons=prior.reasons + (reason("ranker_absent_or_abstain"),),
            implementation_id=self.implementation_id,
            budget_tokens_used=0,
            abstained=True,
        )
