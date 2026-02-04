# Profile D: Temporal Deontic Policy Evaluation

**Status:** Draft

This document expands the MCP++ temporal deontic policy profile: how policies are derived, represented, delegated, evaluated, and turned into immutable decisions and receipts.

## 1. Where the policy engine fits

Temporal deontic logic is used at two points:

1) **Prompt → Delegation**: interpret user intent into a policy and mint delegations.
2) **Intent → Decision → Receipt**: evaluate whether the proposed action is allowed *right now*, and what obligations it creates.

## 2. Policy Representation (`policy_cid`)

A policy MUST be content-addressed to a `policy_cid` and SHOULD be versioned.

Policies express:
- **Permissions** (what is allowed)
- **Prohibitions** (what is forbidden)
- **Obligations** (what must be done, often with deadlines)
- **Temporal constraints** (validity windows, deadlines, revocations)

The project does not need to standardize one policy language immediately, but it MUST standardize:
- canonicalization rules,
- how `policy_cid` is referenced from delegations and intents,
- minimum decision semantics.

## 3. Minimal Logic Interface (Non-Normative)

A common representation uses operators:

- $P(action, t)$ — permitted at time $t$
- $F(action, t)$ — forbidden at time $t$
- $O(outcome, deadline)$ — obligated before deadline

A compiled policy may encode clauses such as:

- Permission: $P(actor, action(resource), t \in [t_0,t_1])$
- Prohibition: $F(actor, action(resource), condition)$
- Obligation: $O(actor, produce(receipt\_cid), deadline)$

## 4. Prompt → Policy Extraction → Delegation

Given a prompt like:

> “Have model B summarize this dataset, but only for these topics, only for 24 hours, and don’t exfiltrate.”

A planner extracts *normative clauses* (actors, resources, actions, time bounds, constraints), compiles them into a formal/compiled policy, and stores:

- `policy_cid`: formal text + compiled executable form

Then a delegation token is minted that:
- encodes the hard “who can do what” authority,
- references `policy_cid` for richer constraints and audit.

## 5. Runtime: Intent → Decision

When a peer wants to execute an action, it submits:

- `intent_cid`
- `ucan_proofs[]` (or equivalent delegation chain)
- `context_cids[]` (state snapshots, prior events)

Evaluators MUST:

1. Validate delegation proofs (cryptographic chain validity)
2. Evaluate policy *against the `intent_cid` and the current context*
3. Produce a `decision_cid` that records:
   - verdict (`allow` / `deny` / `allow_with_obligations`)
   - proofs checked
   - policy version
   - obligations spawned

Decisions SHOULD be signed by evaluators.

## 6. Execution → Receipt → Obligations

Execution emits a `receipt_cid` that binds:
- the `intent_cid`
- produced `output_cid`
- observed side effects
- the `decision_cid`

Receipts become the audit substrate for:
- disputes and rollbacks
- risk scoring
- compliance proofs

## 7. Violations and Compensating Obligations

Temporal deontic systems are useful because they can model:
- missed deadlines (obligation violations)
- compensating obligations (e.g., “if exfiltration occurs, rotate secrets and notify within 1 hour”)

MCP++ should standardize how violations are recorded in:
- `decision_cid` (as detected)
- `event_cid` / receipts (as observed)

## 8. Delegation Chains and “Speaks-For”

Delegation often looks like:

User → Planner model → Worker model → Tool peer

Implementations MAY model “on behalf of” / “speaks-for” relationships as part of policy evaluation, but this is non-normative until a concrete interoperable representation is chosen.

## 9. Security Considerations

- Authorization MUST be checked at execution time, not just at delegation time.
- Evaluators MUST have access to sufficient context (via `context_cids[]`) to make a correct decision.
- Policy evaluation should be sandboxed and resource-limited.
