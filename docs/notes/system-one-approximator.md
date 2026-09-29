# Optional System One approximator

This note is not part of the MCP++ profile registry. It is not a wire type, not an `initialize` capability, and not a proof. Peers that never configure it keep baseline MCP and profiles A–H.

The code lives in `adapters/system_one`. It is off unless a process sets `MCPPP_SYSTEM_ONE`. Importing the package does not import a vendor SDK.

Two local ports sit in front of the existing shapes:

- Tool selection follows `interfaces/select`. A structural filter narrows the pool. An optional ranker may only narrow it further. If the ranker is absent, slow, or low-confidence, the last stage returns an empty slice (`abstain-empty/v1`). Unselected peer tools are not placed in the user model's tool list.
- Policy evaluation follows `mcp++/policy/evaluate`. Exact permissions, prohibitions, obligations, and time windows stay authoritative. Residual clauses are scored only when that switch is on. `MCPPP_SYSTEM_ONE_POLICY_RESIDUAL=0` deny-closes a residual prohibition. It does not ignore the clause. Hazard screening can hide a result. It does not rewrite the authorizing decision.

Jev output, when a caller configures it, is a probability witness. `verified` and `zero_knowledge` stay false. The witness is not a Profile D zero-knowledge certificate.

Closed arguments (enums, booleans, arrays of enums) can be filled locally. Open strings and numbers are not invented. A score does not raise a UCAN budget or an x402 amount.

A past tool deadline returns an empty slice. A past policy deadline returns deny. `disable_jev()` removes the optional middle stage without changing the port types.
