# Profile H: x402 Payments and Paid Capability Access

**Status:** Draft interoperability candidate 1.0  
**Profile key:** `mcp++/x402-payments`  
**Profile version:** `1.0`  
**Upstream protocol:** x402 v2  
**Interface:** `PaymentAuthorizationBoundary@1`

## 1. Scope and conformance

Profile H adds an optional commercial condition to an MCP operation. It uses
upstream x402 v2 at HTTP boundaries and carries the same decoded x402 objects
over Profile E sessions. It does not create currency, execution authority, a
wallet custody model, or a second payment protocol. The interface
`PaymentAuthorizationBoundary@1` (Section 2) is the normative split between
payment success and execution authorization; a settled payment is commercial
evidence only and MUST NEVER be treated as a UCAN, policy grant, or lease.

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to
be interpreted as described by RFC 2119 and RFC 8174 when capitalized.

There are two distinct conformance claims:

- **x402 HTTP v2 conformance** means that the status, headers, encoding, and
  decoded x402 objects at an HTTP boundary conform to the pinned upstream x402
  specification in Section 16.
- **MCP++ Profile H conformance** means that negotiation, authorization
  composition, request binding, lifecycle, receipts, limits, and the Profile E
  representation in this chapter are implemented.

The Profile E representation is an MCP++ transport binding. It is **not** part
of upstream x402 and an implementation MUST NOT describe libp2p support as
upstream x402 HTTP conformance. A gateway MAY claim both forms only when its
HTTP side passes upstream vectors and its object translation passes Profile H
parity vectors.

The first release profile is testnet-only, fixed-price `exact`, and immediate
settlement. `upto`, usage-based charging, reusable entitlements, refunds, and
EVM `batch-settlement` are extensions: they MUST be explicitly negotiated and
MUST fail closed when not negotiated. Nothing in this chapter authorizes
mainnet use.

## 2. PaymentAuthorizationBoundary@1

Readers and implementers MUST treat payment success and execution authority as
independent layers. Success or failure at the commercial layer MUST NOT be
inferred from, or substituted for, success or failure at the execution-
authority layer (and the reverse). This section defines the interface
`PaymentAuthorizationBoundary@1`.

```text
┌──────────────────────────────────────────────────────────────────┐
│ Layer A — Execution authority (Profiles C / D / domain / G)      │
│   UCAN · policy · tenancy · safety · license · lease/fence       │
├──────────────────────────────────────────────────────────────────┤
│ Layer H — Commercial condition (this profile)                    │
│   quote · payment payload · verify · settle · entitlement        │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 Terms

- **paid capability**: an immutable, signed catalog entry attaching commercial
  terms to one canonical operation.
- **request commitment**: the CID of canonical, price-relevant request data,
  including operation identity and arguments, with secrets committed by digest.
- **quote**: an expiring, request-bound choice of x402 payment requirements.
- **payment authorization** (artifact `PaymentAuthorization` / x402
  `PaymentPayload`): buyer-signed payment authority for a selected
  requirement. It is **payment authority only** and MUST NEVER be treated as
  execution authority.
- **settlement**: the irreversible or externally durable transfer outcome
  (`SettlementReceipt`). Settlement proves commercial transfer; it does not
  authorize execution.
- **entitlement**: an optional, bounded commercial grant derived from a
  settlement (`PaidEntitlement`). An entitlement is **not** a UCAN, policy
  decision, or Profile G lease.
- **commercial evidence**: a settlement receipt CID, verified entitlement CID,
  or equivalent durable commercial proof linked from an `AccessReceipt`.
- **access receipt**: the final allow/deny record for an attempted operation.
  Allow requires independent layer-A and layer-H satisfaction when both apply.
- **facilitator**: a replaceable verifier/settler. No particular provider or
  hosted account is required by Profile H.
- **paid-but-unauthorized**: commercial evidence is present (or settlement
  succeeded) while Profile C authority, Profile D/domain policy, or a required
  Profile G lease is missing, invalid, expired, or deny. MUST deny execution.
- **authorized-but-unpaid**: Profile C/D (and G when required) would permit the
  invocation, but the protected operation's Profile H commercial condition is
  unsatisfied (no valid quote-bound settlement or usable entitlement). MUST
  deny execution of the protected side effect.

### 2.2 Decision invariant (normative)

For a protected operation, the seller's allow decision MUST be the intersection
of every required layer:

```text
capability exists
AND Profile C authority is valid          (layer A)
AND Profile D and domain policy permit    (layer A)
AND Profile G claim/lease is valid when scheduled  (layer A)
AND Profile H commercial condition is satisfied    (layer H)
```

Payment is evidence for the final term only. It MUST NOT grant identity,
tenancy, dataset entitlement, a license, safety approval, UCAN authority, or a
Profile G lease. A settled quote is not a capability token. A payer may differ
from the execution subject and NEVER becomes the subject by paying.

Free operations (not in the signed paid catalog, or catalog-marked free) still
require layer A when the operation is otherwise protected by Profiles C/D/G;
absence of a commercial condition MUST NOT skip authority checks.

### 2.3 Non-substitution rules (normative)

1. **Payment success is not execution authorization.** A verified or settled
   payment, a non-exhausted entitlement, a valid `PAYMENT-RESPONSE`, or a
   `payment_context.response` MUST NOT, by itself, allow the protected
   operation's side effect.
2. **Execution authorization is not payment.** A valid UCAN, policy allow,
   dataset entitlement, human approval, or Profile G lease MUST NOT, by itself,
   satisfy a required Profile H commercial condition.
3. **Transport identity is neither.** PeerID, TLS client cert, and HTTP session
   cookies are neither payment authority nor execution authority.
4. **Facilitator opinion is not authority.** Facilitator verify/settle outcomes
   are commercial evidence inputs. They MUST NOT mint UCANs, rewrite policy, or
   raise budgets.
5. **Receipt knowledge is not authority.** Possession of an `AccessReceipt`,
   settlement, or entitlement CID is not bearer authorization to execute,
   retrieve secrets, or replay a side effect.

### 2.4 Mandatory dual-denial cases (normative)

When Profile H is negotiated and the operation is in the paid catalog (or
otherwise requires a commercial condition), both of the following MUST fail
closed **before** the protected side-effect boundary:

| Case | Layer A | Layer H | Required outcome | Stable code |
|---|---|---|---|---|
| **paid-but-unauthorized** | missing, invalid, expired, or deny | satisfied (settled / entitlement usable) | deny; no side effect; retain settled-but-unfulfilled / refund path when funds moved | `H_PAYMENT_POLICY_DENIED` |
| **authorized-but-unpaid** | allow | unsatisfied (no matching settlement or usable entitlement) | deny; no side effect; issue quote / `H_PAYMENT_REQUIRED` when eligible | `H_PAYMENT_REQUIRED` |

Additional normative consequences:

- Paid-but-unauthorized MUST emit `paid_access_denied` (or equivalent Profile F
  event) with independent C/D/G decision CIDs recorded when available. The
  seller MUST NOT claim execution succeeded, MUST NOT invent layer-A allow from
  settlement, and MUST enter the declared refund or reconciliation workflow
  when settlement already completed.
- Authorized-but-unpaid MUST NOT settle, consume entitlement, or execute. When
  the caller is otherwise eligible, the seller returns an expiring request-bound
  quote (HTTP `402` + `PAYMENT-REQUIRED`, or Profile E `H_PAYMENT_REQUIRED`)
  without the protected operation's side effects.
- Concurrent or replayed attempts MUST re-evaluate both layers against current
  state. A prior allow cannot be reconstructed from payment artifacts alone, and
  a prior payment cannot override a new layer-A deny.

### 2.5 AccessReceipt and validator requirements (normative)

`AccessReceipt` is the durable composition of layers A and H for one attempt.
Validators (schema, codec, and seller runtime) MUST reject structurally
incoherent receipts and MUST enforce the dual-denial cases above.

| `decision` | Required evidence | Forbidden configurations |
|---|---|---|
| `allow` | Non-null `commercialEvidenceCid` and `resultCid` when the operation required Profile H; non-null `ucanDecisionCid` and `policyDecisionCid` when Profiles C and D apply to the operation; non-null `leaseDecisionCid` when Profile G scheduling applies | `allow` with missing required layer-A decision CIDs (**paid-but-unauthorized** shape); `allow` with null `commercialEvidenceCid` when Profile H was required (**authorized-but-unpaid** shape); `allow` with null `resultCid` |
| `deny` | Truthful `reasonCode`; may record whichever of commercial or layer-A evidence was evaluated | `deny` that asserts execution success; rewriting deny into allow because settlement later completed without re-running layer A |

Structural codec rules for Profile H 1.0 artifacts (see
`schemas/profile-h/1.0` and `tests-py/validators/profile_h.py`):

- An `AccessReceipt` with `decision: "allow"` MUST fail validation when
  `commercialEvidenceCid` is null or `resultCid` is null for a Profile H
  protected allow path.
- Seller and adapter validators that compose Profile C/D/G decisions with
  Profile H MUST additionally reject **paid-but-unauthorized** allow attempts
  (commercial evidence present, execution authority absent or deny) and
  **authorized-but-unpaid** allow attempts (execution authority present,
  commercial evidence absent when required). Rejection MUST use the stable
  codes in Section 2.4, never silent allow.
- Payment artifacts (`PaymentAuthorization`, `PaymentVerification`,
  `SettlementReceipt`, `PaidEntitlement`) MUST NOT be accepted as substitutes
  for UCAN, policy, or lease decision CIDs on an `AccessReceipt`.
- Codec modules MUST remain free of wallet/network side effects; they enforce
  wire shape and the structural half of this boundary. Seller runtimes enforce
  live C/D/G evaluation and durable commercial satisfaction.

Implementations that advertise Profile H MUST keep the payment path and the
authority path in separate modules or clearly separated stages so that payment
code cannot mint or broaden capabilities (conflict policy for MCPP-G140).

## 3. Negotiation and advertisement

### 3.1 Client offer

A client requests Profile H in MCP `initialize` using one of:

```json
{"capabilities":{"experimental":{"mcp++/x402-payments":true}}}
```

or a structured offer:

```json
{
  "capabilities": {
    "experimental": {
      "mcp++/x402-payments": {
        "profileVersions": ["1.0"],
        "x402Versions": [2],
        "schemes": ["exact"],
        "networks": ["eip155:84532"],
        "features": ["redacted-receipts"],
        "maxPaymentRequiredBytes": 32768,
        "maxPaymentSignatureBytes": 32768
      }
    }
  }
}
```

The boolean offer is shorthand for Profile H `1.0`, x402 v2, `exact`, and the
client's locally configured test networks; it does not opt into extensions or
mainnet. A client MUST NOT send payment merely because it offered the profile.

### 3.2 Server selection

A server accepts with a structured value at the same capability key:

```json
{
  "profileVersion": "1.0",
  "x402Version": 2,
  "schemes": ["exact"],
  "networks": ["eip155:84532"],
  "assets": ["eip155:84532/erc20:0x0000000000000000000000000000000000000000"],
  "facilitatorModes": ["remote"],
  "features": ["redacted-receipts"],
  "catalogCid": "baguq...",
  "descriptorCid": "baguq...",
  "quoteTtlSecondsMax": 300,
  "amountAtomicMax": "1000000",
  "maxPaymentRequiredBytes": 32768,
  "maxPaymentSignatureBytes": 32768,
  "maxPaymentResponseBytes": 32768,
  "settlement": "immediate",
  "environment": "testnet"
}
```

The server selection MUST be a subset of the structured client offer. With a
boolean offer, the client MUST validate every selected network and asset against
local wallet policy before approval. Amounts are base-10 strings containing an
integer number of the asset's smallest unit; JSON numbers and negative,
fractional, exponent, leading-plus, or leading-zero forms MUST be rejected
(except the single value `"0"` where a schema permits it). Networks MUST be
CAIP-2 identifiers. Asset identifiers and decimals MUST be unambiguous in the
signed catalog; display decimals MUST NOT be used for settlement arithmetic.

A server MUST omit the key unless every advertised Profile H dispatch path is
enforced before side effects, durable replay/recovery state is available, and
receipt retrieval remains available. Negotiation does not make all operations
paid: the signed catalog identifies protected operations. Unknown profile or
x402 versions, schemes, networks, assets, or features MUST NOT be silently
downgraded. Absence or rejection leaves baseline MCP available for free
operations and denies paid operations without executing them.

## 4. Canonical operation and artifacts

A paid capability MUST bind `serverDid`, `descriptorCid`, `interfaceCid`,
`operationKind`, canonical operation name, catalog version, Profile C ability,
Profile D policy CID, terms CID, scheme, CAIP-2 network, asset identifier,
atomic amount or maximum, payee, validity interval, settlement timing, and a
seller signature. HTTP routes additionally bind the normalized method and
route template. Catalog changes produce a new catalog CID and MUST NOT mutate
an outstanding quote.

Profile H artifacts are closed, versioned CIDv1 DAG-JSON records. Canonical
encoding MUST follow MCP++ DAG-JSON rules: UTF-8, lexicographically sorted
object keys, no duplicate keys, no floats, and explicit schema/version markers.
Unknown fields MUST be rejected unless a negotiated extension owns them. Links
MUST be IPLD links in canonical blocks. Section 15 limits apply before CID or
signature work.

| Artifact | Minimum commitment |
|---|---|
| `PaidCapability` | operation, seller, price/asset/network, authority/policy, terms and validity |
| `PaymentQuote` | capability/catalog/descriptor CIDs, request commitment, requirements, nonce, expiry and idempotency key |
| `PaymentAuthorization` | quote/request CIDs, selected requirement and redacted signed-payload commitment |
| `PaymentVerification` | authorization, verifier identity, decision, reason, freshness and evidence commitment |
| `SettlementReceipt` | verification, outcome, atomic amount, network reference policy, x402 response commitment and time |
| `PaidEntitlement` | settlement, subject/capability scope, quota, consumed units and expiry |
| `UsageRecord` | entitlement, deterministic unit definition, input/output commitments and units |
| `RefundRecord` | settlement, request/decision/outcome and network evidence commitment |
| `AccessReceipt` | operation/request, C/D/G decisions, commercial evidence, allow/deny, result/receipt and reason |

Exact schemas and codecs are versioned under
[`schemas/profile-h/1.0`](../../schemas/profile-h/1.0), with the generated
[Profile H 1.0 schema reference](../generated/profile-h-schemas-1.0.md) and
shared vectors under `conformance/vectors/profile_h_*.json`. A runtime MUST
pass those vectors but still MUST NOT advertise Profile H until its protected
seller and buyer paths pass the release gates. Raw private keys, seed
phrases, authentication cookies, full UCAN tokens, unredacted request arguments,
or request-controlled facilitator URLs MUST NOT appear in these artifacts.

## 5. Authorization and settlement ordering

Every seller MUST perform this order for each attempt. The order implements
`PaymentAuthorizationBoundary@1` (Section 2): layer A and layer H are both
required, and neither is inferred from the other.

1. Normalize the operation and compute its request commitment.
2. Authenticate and perform the non-payment Profile C, Profile D, tenancy,
   safety, license, and domain checks needed to decide whether pricing may be
   disclosed. A denial ends the attempt (**paid-but-unauthorized** path if a
   prior payment exists; otherwise ordinary authority deny).
3. Resolve the paid capability. `free` continues with layer A only; `denied`
   ends; unavailable verifier, ledger, or pricing state fails closed.
4. For an unpaid request on a paid capability, issue an expiring request-bound
   quote without the protected operation's side effects
   (**authorized-but-unpaid** → `H_PAYMENT_REQUIRED` when layer A still holds).
5. On retry, validate negotiated version, bounds, quote, catalog/descriptor,
   expiry, nonce, idempotency key, operation, request, seller, payee, scheme,
   network, asset, and amount before cryptographic verification.
6. Re-run all non-payment authorization and policy checks against current state.
   A known layer-A denial MUST occur before settlement and MUST remain deny
   after settlement (**paid-but-unauthorized**).
7. Atomically reserve the payment-authorization commitment in the durable
   ledger, verify, and settle it or prove a scoped entitlement. Never settle
   twice. This step produces commercial evidence only.
8. Atomically mark commercial satisfaction and reserve one execution. Re-run
   time-sensitive policy and Profile G lease/fence checks immediately before
   the side-effect boundary. If layer A now denies, stop
   (**paid-but-unauthorized**); do not execute.
9. Execute at most once, persist output/`AccessReceipt`, emit Profile F events,
   and return the prior outcome for an identical retry. An `allow` receipt MUST
   satisfy Section 2.5.

After any denial, the protected operation's side effect MUST NOT occur. If
policy changes between settlement and execution, the seller MUST deny, retain
a truthful settled-but-unfulfilled state, and enter the declared refund or
reconciliation workflow; it MUST NOT claim execution succeeded.

### 5.1 Composition with Profiles C through G

- **C (UCAN):** validate capability/delegation at price-disclosure time and
  again at execution. A payer may differ from the subject but never becomes it.
  Payment artifacts MUST NOT be accepted as UCAN proofs.
- **D (policy):** payment proposal, approval, amount, asset, network, seller,
  facilitator, budgets, and result are policy inputs. Human-confirmation
  obligations MUST be discharged before signing. Settlement MUST NOT override a
  policy deny.
- **E (transport):** HTTP and `/mcp+p2p/1.0.0` carry identical decoded x402
  objects. Transport identity is neither payment nor execution authority.
- **F (provenance):** Section 11 events link catalog, quote, authorization,
  verification, settlement, access, execution and output without secrets, and
  MUST distinguish commercial success from access-allowed/executed.
- **G (scheduling):** a claim cannot sign, change price, raise a budget, or
  transfer entitlement. Workers receive a scoped entitlement CID or evidence,
  never a wallet key. Profile G fencing supplements Profile H idempotency.
  Payment MUST NOT mint or extend a lease.

## 6. HTTP x402 v2 binding

At an HTTP boundary, upstream x402 v2 behavior is normative:

1. An otherwise eligible unpaid request receives HTTP `402 Payment Required`
   and `PAYMENT-REQUIRED: <base64-json>` with a v2 `PaymentRequired` object.
2. The buyer selects one requirement and retries the **same** method, target,
   and committed body with `PAYMENT-SIGNATURE: <base64-json>` containing the v2
   `PaymentPayload`.
3. Whenever verification or settlement was attempted, the response includes
   `PAYMENT-RESPONSE: <base64-json>` containing the v2 settlement response,
   successful or failed. Application status/body remain truthful about
   execution; settlement alone is not application success.

Header values use standard padded base64 of UTF-8 JSON as required by the
pinned transport. Receivers MUST strictly decode base64, reject non-UTF-8,
duplicate keys, invalid v2 objects, and decoded values over negotiated limits.
Proxies and logs MUST treat `PAYMENT-SIGNATURE` as sensitive.

The v1 headers `X-PAYMENT` and `X-PAYMENT-RESPONSE` MUST NOT be emitted or
accepted as Profile H. An inbound legacy header MUST produce
`H_UNSUPPORTED_X402_VERSION` (or HTTP 400 where no MCP body is possible), never
implicit translation. Profile H errors SHOULD use normal MCP JSON-RPC errors
with the Section 12 symbolic value in `error.data.code`.

## 7. Profile E libp2p binding

Profile E has no status or headers. The normal MCP request is used. An unpaid
request returns a JSON-RPC error with:

```json
{
  "code": "H_PAYMENT_REQUIRED",
  "profile": "mcp++/x402-payments",
  "profileVersion": "1.0",
  "x402Version": 2,
  "paymentRequired": {"x402Version": 2, "accepts": []},
  "quoteCid": "baguq...",
  "requestCommitment": "baguq..."
}
```

The client retries the same method and logical params, adding the reserved
top-level params member:

```json
{
  "payment_context": {
    "profileVersion": "1.0",
    "x402Version": 2,
    "payload": {"x402Version": 2, "accepted": {}, "payload": {}},
    "quoteCid": "baguq...",
    "idempotencyKey": "018f..."
  }
}
```

After attempted verification/settlement, result or error `data` includes
`payment_context.response`, the decoded upstream settlement response, plus
available `settlementReceiptCid`, `accessReceiptCid`, and `reconciliationCid`.
The reserved member is removed before operation schema validation/execution but
remains committed via the selected quote and payload commitment.

Gateways MUST base64-encode/decode mechanically and MUST NOT change fields,
numbers, array order, or meanings in upstream objects. One logical request on
both transports MUST yield the same decoded objects, symbolic decision, request
commitment, and receipt CIDs. Profile E frame limits also apply. This framing
is MCP++ Profile H, explicitly not upstream x402 HTTP.

## 8. Methods and discovery

Normal paid calls remain normal tool/resource/prompt methods; no bespoke
execute endpoint is required.

| Purpose | JSON-RPC method | HTTP binding |
|---|---|---|
| negotiated profile | `mcp++/payments/profile` | `GET /mcp/payments/profile` |
| signed catalog | `mcp++/payments/catalog` | `GET /mcp/payments/catalog` |
| request-bound quote | `mcp++/payments/quote` | `POST /mcp/payments/quote` |
| verify only | `mcp++/payments/verify` | `POST /mcp/payments/verify` |
| settle | `mcp++/payments/settle` | `POST /mcp/payments/settle` |
| receipt lookup | `mcp++/payments/receipt/get` | `GET /mcp/payments/receipts/{cid}` |
| entitlement lookup | `mcp++/payments/entitlement/get` | `GET /mcp/payments/entitlements/{cid}` |
| usage lookup | `mcp++/payments/usage/get` | `GET /mcp/payments/usage/{cid}` |
| request refund | `mcp++/payments/refund/request` | `POST /mcp/payments/refunds` |
| operator recovery | `mcp++/payments/reconcile` | `POST /mcp/payments/reconcile` |

`verify` MUST NOT execute, settle, consume entitlement, or imply access.
`settle` MUST NOT execute and MUST NOT grant layer-A authority. Lookups MUST
enforce subject/disclosure policy; knowledge of a CID is not authorization.
Optional methods MUST NOT be advertised unless implemented durably. No method
in this table converts commercial success into a UCAN or policy allow.

## 9. Buyer approval and wallet boundary

The wallet signer MUST be isolated from prompts, remote servers, renderers, and
ordinary agent/tool code. No private key or seed phrase may be returned or
persisted in Profile H artifacts. Before signing, the buyer MUST validate the
quote signature/expiry and show or policy-check seller, operation/request,
payee, atomic and displayed amount, asset, network, scheme, facilitator,
settlement timing, expiry, terms, and changes from prior approval.

Autopay is opt-in. Limits MUST live outside model-controlled input and include
seller, capability, payee, network, asset, per-request and rolling/daily amount,
quote age, and risk class. Unknown sellers, changed payees/networks, price
increases, `upto`, batch settlement, and mismatch require fresh explicit
approval. An agent MAY request approval but MUST NOT alter policy or interpret
prompt text as approval.

## 10. Idempotency, settlement, and recovery

Every paid mutation and expensive read MUST have a cryptographically random
idempotency key and request commitment. Sellers MUST enforce uniqueness on
`(seller, idempotencyKey)`, payload commitment, and network settlement reference.
Reusing a key with a different request returns `H_REQUEST_MISMATCH`.

```text
quoted -> authorized -> verified -> settling -> settled -> execution_reserved
       -> executing -> executed
```

Side/terminal states are `declined`, `expired`, `verification_failed`,
`settlement_failed`, `denied_after_settlement`, `execution_failed`,
`refund_pending`, `refunded`, and `reconciliation_required`. Transitions MUST be
durable, monotonic, fenced, and auditable. External calls MUST NOT be held in a
long database transaction.

Identical concurrent/replayed requests MUST join or return the existing outcome
and MUST NOT verify, settle, consume, or execute again. An unknown external
outcome enters `reconciliation_required` and blocks execution. A crash after
settlement recovers the execution reservation and executes at most once or
records settled-but-unfulfilled. Lost responses are recovered through an
authorized receipt lookup. A pause MUST stop new quotes/settlements while
retaining recovery, receipt lookup, refund, and valid entitlement handling.

## 11. Profile F evidence

Implementations MUST emit causally linked, redacted Profile F events:

`payment_catalog_published`, `payment_quote_issued`,
`payment_approval_requested`, `payment_authorized`, `payment_verified`,
`payment_settlement_started`, `payment_settled`, `payment_failed`,
`entitlement_issued`, `entitlement_consumed`, `paid_access_allowed`,
`paid_access_denied`, `usage_recorded`, `refund_requested`, `refund_recorded`,
and `payment_reconciled`.

Events MUST link relevant artifact/prior-event CIDs and distinguish verified,
settled, access-allowed, executed, and completed. Failed events include a stable
code and redacted reason. Metrics/traces MUST NOT contain payment signatures,
wallet secrets, private arguments, bearer entitlements, or credentials.

## 12. Stable error registry

Errors are stable symbolic values in JSON-RPC `error.data.code`. Numeric server
codes MAY vary; clients MUST branch on the symbolic code.

| Code | Meaning and retry rule |
|---|---|
| `H_PAYMENT_REQUIRED` | eligible operation needs payment (**authorized-but-unpaid**); retry only with approved matching payload |
| `H_PAYMENT_DECLINED` | buyer/provider declined; new approval is required |
| `H_QUOTE_EXPIRED` | obtain a new quote; never reuse the signature |
| `H_UNSUPPORTED_X402_VERSION` | not v2 or a legacy header; do not downgrade |
| `H_UNSUPPORTED_SCHEME` | scheme was not negotiated |
| `H_UNSUPPORTED_NETWORK` | network was not negotiated/allowed |
| `H_UNSUPPORTED_ASSET` | asset was not negotiated/allowed |
| `H_AMOUNT_MISMATCH` | amount/maximum differs; do not settle |
| `H_REQUEST_MISMATCH` | operation, args, seller, descriptor, quote, or key differs |
| `H_PAYMENT_REPLAY` | consumed/bound elsewhere; retrieve original receipt if authorized |
| `H_VERIFICATION_FAILED` | evidence invalid; do not settle |
| `H_SETTLEMENT_FAILED` | definitively failed; retry only under returned recovery policy |
| `H_ENTITLEMENT_EXHAUSTED` | quota/expiry does not cover request |
| `H_PAYMENT_POLICY_DENIED` | commercial or non-payment policy denies; payment cannot override; covers **paid-but-unauthorized** |
| `H_FACILITATOR_UNAVAILABLE` | unavailable before unknown outcome; bounded retry allowed |
| `H_RECONCILIATION_REQUIRED` | ambiguous outcome; do not pay/execute until reconciled |
| `H_LIMIT_EXCEEDED` | encoded object, lifetime, count, amount, or rate exceeds bound |
| `H_INVALID_PAYMENT_MESSAGE` | base64, UTF-8, JSON, schema, CAIP, or canonical value invalid |

Errors MUST NOT disclose hidden catalog entries. When settlement may have
occurred, return `H_RECONCILIATION_REQUIRED`, not definitive failure. Unknown
errors fail closed and MUST NOT trigger signing, settlement, or execution.

## 13. Threat model and required controls

Assume hostile callers/prompts, replay, malicious gateways/peers, crashes at
every boundary, dishonest/unavailable facilitators, and readable ordinary logs.
A compromised signer, seller key, or ledger cannot be repaired by this profile.

| Threat | Normative control |
|---|---|
| price/payee/operation/argument substitution | signed catalog, request-bound quote, strict equality and approval diff |
| replay/double settlement | nonce, expiry, payload commitment, key, durable uniqueness, facilitator evidence |
| double execution | request commitment, execution reservation, result recovery, Profile G fence |
| overcharge/unit confusion | atomic decimal strings, explicit asset/network/unit, maxima, no floats |
| facilitator compromise/failure | configured trust, TLS, response validation, evidence, circuit breaker/reconciliation |
| wallet exfiltration | isolated non-exporting signer, least privilege, hardware/external option |
| prompt-induced spend | policy outside model context, hard budgets/allowlists, approval, global pause |
| payment as auth bypass | `PaymentAuthorizationBoundary@1`; repeat C/D/domain checks before settlement and execution; reject paid-but-unauthorized and authorized-but-unpaid |
| receipt privacy leak | selective disclosure, encryption, authorized lookup, transaction redaction |
| stale quote/catalog | signed CID binding, nonce/expiry, seller/network/payee revalidation |
| settle-then-crash/lost response | durable states, fencing, receipt lookup and reconciliation |
| facilitator SSRF | operator allowlist, HTTPS/egress policy, no request-selected URL |
| parser exhaustion | strict parsing and Section 15 byte/count/depth/rate bounds |
| downgrade/cross-transport confusion | v2-only, reject v1, mechanical parity/domain separation |
| dependency compromise | exact locks/integrity, SBOM/review, scans and vectors |

Profile H does not provide anonymity, chargebacks, tax/regulatory compliance,
or guaranteed refunds. These properties MUST NOT be inferred from settlement.

## 14. Privacy and data handling

Catalog visibility and price may reveal sensitive facts; authorize before
disclosure. Public CID publication is opt-in. Wallet addresses, transaction
references, facilitator payloads, request data, and payer identity SHOULD be
salted/domain-separated commitments or selectively disclosed when possible.
Sensitive recovery material MUST be encrypted and retention-bounded.

`PAYMENT-SIGNATURE` and `payment_context.payload` MUST be redacted from logs,
errors, analytics, prompts, events, and traces. Receipts MUST state disclosure
policy and MUST NOT be bearer authorization; retrieval and consumption require
current authorization.

## 15. Required bounds and abuse resistance

Implementations MUST advertise limits no larger than capacity. Profile 1.0
defaults and hard maxima are:

| Item | Default | Hard maximum |
|---|---:|---:|
| decoded `PaymentRequired` | 32 KiB | 256 KiB |
| decoded `PaymentPayload` | 32 KiB | 256 KiB |
| decoded settlement response | 32 KiB | 256 KiB |
| requirements per quote | 8 | 32 |
| JSON nesting depth | 16 | 32 |
| string length | 8 KiB | 64 KiB |
| quote lifetime | 5 minutes | 1 hour |
| committed request arguments | 1 MiB | transport body cap, at most 16 MiB |
| unresolved attempts per subject | 16 | 256 |

Also bound catalog pages, traversal, retries, timeouts, unresolved retention,
and rates per subject/IP/peer. Amount and rolling-spend maxima are mandatory
policy values. Check bounds before expensive decoding, signature work, CID
fetch, or external calls. Clients apply equal/tighter bounds and reject a server
selection above their offer.

## 16. Version and dependency policy

Profile H `1.0` pins x402 v2 at repository commit
`0a604079aca7b5a45a2e1620ba444e13982646c8`, document
`specs/x402-specification-v2.md`, including v2 HTTP transports. Descriptors and
conformance reports MUST record this commit, exact x402 SDK packages and
lockfile-resolved versions/integrities, Profile H schema version, and vectors.

Only `x402Version: 2` is accepted. SDK patch/minor upgrades require lockfile and
SBOM updates, upstream protocol/transport review, secret/vulnerability scans,
and all upstream HTTP plus MCP++ parity vectors. Major SDK/wire changes, changed
canonical fields, or a new x402 protocol version require a new Profile H
version and negotiation. Implementations MUST NOT accept v1, translate legacy
headers, or infer protocol version from SDK version.

## 17. Protocol examples

### 17.1 HTTP exact-payment flow

```http
POST /mcp HTTP/1.1
Content-Type: application/json

{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"dataset.summary","arguments":{"dataset":"bafy..."}}}
```

```http
HTTP/1.1 402 Payment Required
PAYMENT-REQUIRED: eyJ4NDAyVmVyc2lvbiI6MiwiYWNjZXB0cyI6W3si...
Content-Type: application/json

{"jsonrpc":"2.0","id":7,"error":{"code":-32002,"message":"Payment required","data":{"code":"H_PAYMENT_REQUIRED","quoteCid":"baguq...","requestCommitment":"baguq..."}}}
```

After approval, repeat equivalent logical parameters with the v2 payload in
`PAYMENT-SIGNATURE`. A success carries both `PAYMENT-RESPONSE` and application
receipt; the header alone does not say the tool succeeded.

### 17.2 Paid-but-unauthorized (payment success ≠ execution)

Layer H is satisfied; layer A is not. Example: dataset entitlement or UCAN was
revoked after settlement but before the side-effect boundary.

```text
settlement outcome = settled
Profile C / D decision = deny (or missing)
→ decision = deny
→ code = H_PAYMENT_POLICY_DENIED
→ events include paid_access_denied
→ AccessReceipt.decision = deny
→ AccessReceipt.commercialEvidenceCid = <settlement or entitlement cid>
→ AccessReceipt.resultCid = null
→ no dataset read / no protected side effect
→ settled-but-unfulfilled recovery or refund workflow
```

Validators and seller runtimes MUST reject any attempt to record
`AccessReceipt.decision = allow` for this shape (Section 2.4–2.5). Settlement
headers or facilitator success alone MUST NOT flip the decision to allow.

### 17.3 Authorized-but-unpaid (authority ≠ payment)

Layer A would permit the invocation; layer H is not satisfied. Example: a valid
UCAN and policy allow for `tools/call`, but no matching quote-bound settlement
or usable entitlement is present for a catalog-paid operation.

```text
Profile C / D decision = allow
commercial condition = unsatisfied
→ decision = deny (no side effect)
→ code = H_PAYMENT_REQUIRED
→ HTTP 402 + PAYMENT-REQUIRED, or Profile E error with paymentRequired
→ AccessReceipt (if emitted) has decision = deny and null commercialEvidenceCid
→ no settlement, entitlement consumption, or protected side effect
```

Validators and seller runtimes MUST reject any attempt to record
`AccessReceipt.decision = allow` without commercial evidence when Profile H is
required (Section 2.4–2.5). A valid UCAN MUST NOT suppress the quote path.

### 17.4 Replay

Concurrent retries with one key/request/payment converge on one ledger record.
One worker owns settlement/execution fences; others return the same receipt.
Changed arguments with that key yield `H_REQUEST_MISMATCH` before verification.
Replays MUST re-check both layers: a payment that was previously allowed does
not authorize a later attempt if layer A now denies.

## 18. Conformance checklist

Demonstrate negotiation subset/rejection; v1 rejection; upstream HTTP vectors;
HTTP/Profile E decoded-object and decision parity; `PaymentAuthorizationBoundary@1`
non-substitution (Section 2.3); **paid-but-unauthorized** deny with
`H_PAYMENT_POLICY_DENIED` and no side effect; **authorized-but-unpaid** deny
with `H_PAYMENT_REQUIRED` / quote and no side effect; AccessReceipt structural
rejection of allow without required commercial or layer-A evidence
(Section 2.5); authorization-before-price and repeated C/D checks; strict
request/price/payee binding; signer/budget isolation; at-most-once
settlement/execution under concurrency/restart; unknown outcome recovery;
redacted CID/Profile F lineage; every stable error; parser and rate bounds; and
no paid side effect after denial. Mainnet readiness is a separate
operational/security decision, never implied by Profile H conformance.
