# Optional System One approximator

This note is not part of the MCP++ profile registry. It is not a wire type, not an `initialize` capability, and not a proof. Peers that never configure it keep baseline MCP and profiles A–H.

The code lives in `adapters/system_one`. Defaults leave the ranker unset and leave residual scoring and hazard screening off. `MCPPP_SYSTEM_ONE=0` leaves `enabled` false, and a false `enabled` drops the Jev middle stage even when a ranker or client object is installed. `MCPPP_SYSTEM_ONE_POLICY_RESIDUAL` and `MCPPP_SYSTEM_ONE_HAZARD` turn those two gates on only while `enabled` is also on. Importing the package does not import a vendor SDK.

Two local ports sit in front of the existing shapes:

- Tool selection follows `interfaces/select`. A structural filter narrows the pool. An optional ranker may only narrow it further. If the ranker is absent, the ranker abstains, or the tool deadline is already past, the last stage returns an empty slice (`abstain-empty/v1`). A low-confidence result, or a choice of none, is an empty ranker halt (`system-one-ranker/v1`). The deadline is checked once before the ranker runs. Unselected peer tools are not placed in the user model's tool list.
- Policy evaluation follows `mcp++/policy/evaluate`. Exact permissions, prohibitions, obligations, and time windows stay authoritative. Residual clauses are scored only when that switch is on. `MCPPP_SYSTEM_ONE_POLICY_RESIDUAL=0` deny-closes a residual prohibition. It does not ignore the clause. Hazard screening can hide a result. It does not rewrite the authorizing decision.

Jev output, when a caller configures it, is a probability witness. `verified` and `zero_knowledge` stay false. The witness is not a Profile D zero-knowledge certificate.

Closed arguments (enums, booleans, arrays of enums) can be filled locally. Open strings and numbers are not invented. A score does not raise a UCAN budget or an x402 amount.

A past policy deadline returns deny. `disable_jev()` drops an installed ranker and clears `enabled`, `tool_rank`, `policy_residual`, and `hazard` on the shared config, so a policy chain holding that same object stops calling out. The port types stay the same.
