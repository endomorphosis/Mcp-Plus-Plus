# A2A Execution Extension (A2AExecutionExtension@1)

**Status:** Normative (MCP++ 1.0)  
**Interface labels:** `A2AExecutionExtension@1`, `AgentCardMapping@1`, `A2ATaskAdapter@1`  
**Extension URI (wire / Agent Card / `A2A-Extensions`):** `https://mcplusplus.io/extensions/execution/v1`  
**Working alias (human / internal only):** `io.mcplusplus.execution@1`  
**Authority:** Plan KD-13; goal `MCPP-G100`; tasks `MCPP-054`…`MCPP-057`; ADR-0006; MCPP-010 primary-source note  
**Related:** [execution-envelope.md](execution-envelope.md), [mcp-idl.md](mcp-idl.md), [state-ref.md](state-ref.md), [ucan-delegation.md](ucan-delegation.md), [event-dag-ordering.md](event-dag-ordering.md), ADR-0005 (DurableExecutor), ADR-0006 (bindings + A2A identifier)

Normative keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as described in RFC 2119.

---

## 1. Purpose

This chapter defines the **MCP++ A2A execution extension**: how independent A2A agents advertise and activate MCP++-aware execution, and how core A2A objects map onto MCP-IDL and MCP++ envelope, state, and receipt carriers.

MCP++ uses A2A for the **public multi-agent task lifecycle**. This extension **augments** A2A Task, Message, Part, Artifact, status, cancel, streaming, push notifications, and auth with content-addressed MCP++ evidence. It does **not** replace A2A Task status names or invent a second public task state machine.

Schemas and positive/negative vectors land in MCPP-055. The reference adapter and two-agent handoff tests land in MCPP-056. SwissKnife adaptation is MCPP-057.

---

## 2. Official extension identifier rule

### 2.1 Quoted official rule

Official A2A extension identifiers are **URIs**, advertised on the Agent Card, and activated via the `A2A-Extensions` service parameter. From the official Extensions topic (https://a2a-protocol.org/latest/topics/extensions/):

> Extensions allow for extending the A2A protocol with new data, requirements, RPC methods, and state machines. Agents declare their support for specific extensions in their Agent Card, and clients can then opt in to the behavior offered by an extension as part of requests they make to the agent. **Extensions are identified by a URI and defined by their own specification.** Anyone is able to define, publish, and implement an extension.

Agent Card field (`AgentExtension.uri`):

> `uri` — The unique URI identifying the extension.

Standard service parameter:

| Name | Description | Example value |
| --- | --- | --- |
| `A2A-Extensions` | Comma-separated list of extension URIs the client wants to use for the request | `https://example.com/extensions/geolocation/v1,https://standards.org/extensions/citations/v1` |

Activation (same official topic):

> **Client Request**: A client requests extension activation by including the `A2A-Extensions` header in the HTTP request to the agent. The value is a comma-separated list of extension URIs the client intends to activate.

Versioning (same topic):

> Use the extension's URI as the primary version identifier, ideally including a version number (for example, `https://example.com/ext/my-extension/v1`).  
> **Breaking Changes**: A new URI MUST be used when introducing a breaking change to an extension's logic, data structures, or required parameters.

Official A2A-organization extensions use the reserved prefix `https://a2a-protocol.org/extensions/`. MCP++ is a project-owned extension and **MUST NOT** claim that prefix.

Primary sources (verified MCPP-010):

| Source | URL |
| --- | --- |
| A2A 1.0.0 specification | https://a2a-protocol.org/v1.0.0/specification |
| Extensions topic | https://a2a-protocol.org/latest/topics/extensions/ |
| Extension / binding governance | https://a2a-protocol.org/latest/topics/extension-and-binding-governance/ |
| MCPP-010 verification note | `docs/reports/mcplusplus-1.0-gap-closure/baseline/official-mcp-a2a.md` |

### 2.2 Confirmed MCP++ identifier

| Role | Value | Normative? |
| --- | --- | --- |
| **Wire / Agent Card / `A2A-Extensions` identifier** | `https://mcplusplus.io/extensions/execution/v1` | **Yes — mandatory** for A2A interop claims under this chapter |
| **Working alias (human / internal only)** | `io.mcplusplus.execution@1` | Documented synonym only; **not** a wire substitute |

| Rule | Normative statement |
| --- | --- |
| URI form | Agents that claim this extension **MUST** set `AgentExtension.uri` to `https://mcplusplus.io/extensions/execution/v1`. |
| Activation | Clients that activate the extension **MUST** include that exact URI in `A2A-Extensions` (comma-separated with any other activated URIs). |
| Alias ban on wire | Using only `io.mcplusplus.execution@1` (or any reverse-DNS token without a URI scheme) as `AgentExtension.uri` or as an `A2A-Extensions` entry is **non-conformant**. |
| Breaking changes | Breaking changes to required params, metadata keys, or mapping semantics **MUST** introduce a new URI (e.g. `…/v2`), not silently redefine `/v1`. |
| Identifier vs HTTP | The URI is an **identifier**. Temporary DNS or hosting unavailability for `mcplusplus.io` does **not** rename the identifier (MCPP-010 §4.2). |
| Response echo | When the extension is successfully activated, the agent response **SHOULD** echo the URI in `A2A-Extensions` per official activation rules. |

### 2.3 What this extension is not

| Non-goal | Rationale |
| --- | --- |
| A competing public task lifecycle | A2A already owns Task, status, cancel, streaming, artifacts (KD-13; ADR-0006 §4). |
| New A2A `TaskState` enum values | Official A2A forbids extensions from adding enum values; annotate via `metadata` instead. |
| Renaming core A2A fields | Custom attributes go in `metadata` maps on core structures. |
| Replacing DurableExecutor | DurableExecutor is journal / crash-recovery authority (ADR-0005), not a multi-agent public API. |
| Merging with MCP Tasks | Official MCP Tasks (`io.modelcontextprotocol/tasks`) is an MCP capability family; its reverse-DNS id is **not** the A2A extension URI. |

---

## 3. Lifecycle ownership (no competing public task model)

### 3.1 A2A owns the public agent-task lifecycle

A2A defines:

- **Agent Card** — discovery document (identity, skills, capabilities, security, extensions).
- **Task** — stateful unit of work with server-generated `id`.
- **Message** / **Part** — conversational turns and content units.
- **Artifact** — task outputs composed of Parts.
- **TaskState** — public status vocabulary (submitted, working, completed, failed, canceled, rejected, input-required, auth-required, …).
- **Cancel Task**, **streaming** (status/artifact update events), **push notifications**, and standard auth/security schemes.

MCP++ **extends** that model. Implementations **MUST NOT**:

1. Advertise a private MCP++-only task status machine as the public multi-agent lifecycle while claiming A2A interop.
2. Fork A2A Task status names into a parallel public vocabulary peers must learn instead of A2A `TaskState`.
3. Treat DurableExecutor journal states as a substitute for A2A Task status on the wire.
4. Treat MCP Tasks (`io.modelcontextprotocol/tasks`) as the A2A extension identifier or as the cross-agent handoff lifecycle.

### 3.2 Layered responsibilities

```text
  A2A (public multi-agent lifecycle)
    Agent Card · Task · Message · Part · Artifact · TaskState
    Cancel · Stream · Push · Auth schemes
           │
           │  this extension maps / annotates (metadata + CID carriers)
           ▼
  MCP++ (portable execution evidence)
    MCP-IDL interface_cid · ExecutionEnvelope@1 · StateRef@1
    ExecutionResult@1 · ExecutionReceipt@1 · Event DAG · UCAN proofs
           │
           │  internal only (not a public multi-agent API)
           ▼
  DurableExecutor@1 (journal, fencing, crash recovery)
```

### 3.3 Official A2A TaskState (reference; not redefined)

Adapters **MUST** surface the public state using A2A `TaskState` values. Wire form may be protobuf enum names or JSON snake_case per the binding in use; both spellings below refer to the same official states:

| A2A TaskState | Kind | Notes |
| --- | --- | --- |
| `submitted` / `TASK_STATE_SUBMITTED` | non-terminal | Task accepted |
| `working` / `TASK_STATE_WORKING` | non-terminal | Actively processing |
| `input-required` / `TASK_STATE_INPUT_REQUIRED` | interrupted | Needs client input |
| `auth-required` / `TASK_STATE_AUTH_REQUIRED` | interrupted | Needs authentication / delegation |
| `completed` / `TASK_STATE_COMPLETED` | terminal success | Finished successfully |
| `failed` / `TASK_STATE_FAILED` | terminal failure | Finished with error |
| `canceled` / `TASK_STATE_CANCELED` | terminal | Canceled before completion |
| `rejected` / `TASK_STATE_REJECTED` | terminal | Agent declines the work |

MCP++ attempt outcomes (`ExecutionResult@1.status`: `succeeded`, `failed`, `cancelled`, `rejected`, `timed_out`, `compensated`) are **internal** or evidence-layer labels. They **MUST** be mapped onto the A2A states above for any public Task view (see §6.6). They **MUST NOT** appear as a second required public enum that replaces `TaskState`.

---

## 4. Extension declaration and activation

### 4.1 Agent Card declaration

Agents that support this extension **MUST** include an `AgentExtension` entry:

```json
{
  "uri": "https://mcplusplus.io/extensions/execution/v1",
  "description": "MCP++ execution mapping: envelopes, state refs, receipts, and proofs on A2A Task.",
  "required": false,
  "params": {
    "profiles": ["A", "B", "C", "D", "F", "G"],
    "envelope_schema": "mcp++/execution/envelope@1",
    "receipt_schema": "mcp++/execution/receipt@1",
    "state_ref_schema": "mcp++/state/state-ref@1",
    "mcp_bindings": [
      "mcp-binding/2026-07-28",
      "mcp-binding/legacy-2024-11-05"
    ],
    "interface_cids": [
      "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    ],
    "canonicalization": "mcpp-jcs-v1",
    "alias": "io.mcplusplus.execution@1"
  }
}
```

| `params` key | Required | Meaning |
| --- | --- | --- |
| `profiles` | SHOULD | MCP++ profile letters this agent implements under the extension |
| `envelope_schema` | SHOULD | Schema marker for request envelopes |
| `receipt_schema` | SHOULD | Schema marker for terminal receipts |
| `state_ref_schema` | SHOULD | Schema marker for StateRef handles |
| `mcp_bindings` | SHOULD | Named MCP bindings offered (ADR-0006 ids) |
| `interface_cids` | SHOULD | Primary MCP-IDL interface CIDs this agent executes |
| `canonicalization` | SHOULD | Canonicalization id for content-addressed objects (`mcpp-jcs-v1`) |
| `alias` | MAY | Non-normative short name; never a wire substitute for `uri` |

`required: true` **SHOULD** be reserved for agents whose core security or I/O shape depends on the extension (for example, agents that reject non-CID inputs). Data-only advertisement of optional MCP++ evidence **SHOULD** use `required: false`.

### 4.2 Activation

1. Client includes `A2A-Extensions: https://mcplusplus.io/extensions/execution/v1` (plus any other URIs).
2. Agent activates only extensions it supports; unsupported URIs may be ignored per official rules.
3. When this extension is required on the card and the client does not activate it, the agent **MUST** fail closed (`ExtensionSupportRequiredError` or binding-equivalent).
4. Version mismatch (client requests a different URI, e.g. a future `/v2` the agent does not support) **MUST NOT** silently fall back to `/v1` under a different URI; the unsupported URI is ignored or rejected per official versioning guidance.

### 4.3 Metadata key namespace

Extension-defined metadata keys **MUST** be namespaced under the extension URI (or a stable sub-path of it) so they do not collide with other extensions. Recommended prefix:

```text
https://mcplusplus.io/extensions/execution/v1/
```

Short local names in this document (e.g. `envelope_cid`) refer to the **suffix** after that prefix when placed in A2A `metadata` maps, unless a full URI key is shown.

---

## 5. Mapping overview (`AgentCardMapping@1` / `A2ATaskAdapter@1`)

| A2A concept | MCP++ / MCP-IDL concept | Direction | Section |
| --- | --- | --- | --- |
| Agent Card | MCP-IDL Interface Descriptors + capability advertisement | Card → IDL / IDL → Card skills | §6.1 |
| `interface_cid` on card | Profile A `interface_cid` | Card params / skill metadata | §6.1 |
| Task | TaskSpec / ExecutionEnvelope@1 intent | Task create ↔ envelope mint | §6.2 |
| `contextId` | StateRef@1 / correlation context | Context ↔ state handles | §6.3 |
| Message / Part | CID inputs (`input_cid`, file/data parts) | Message → envelope inputs | §6.4 |
| Artifact | `output_cid` / `output_cids` | Result → Artifact | §6.5 |
| TaskStatus / TaskState | Event DAG progress + result status mapping | Status ↔ events / result | §6.6 |
| Cancel Task | DurableExecutor `cancel` | Cancel → journaled cancel | §6.7 |
| Streaming updates | Progress / partial artifacts | Stream ↔ progress events | §6.8 |
| Push notifications | Receipt / terminal evidence notifications | Push ↔ receipt delivery | §6.9 |
| Auth / security schemes | UCAN delegation challenges | Auth ↔ proofs | §6.10 |
| Terminal Task | `receipt_cid`, `event_cid`, proof refs | Finals → evidence | §6.11 |

---

## 6. Detailed mappings

### 6.1 Agent Card ↔ MCP-IDL

**Goal:** Discovery of what an agent can execute, without replacing A2A skills.

| A2A surface | MCP++ mapping |
| --- | --- |
| `AgentCard.name` / `description` / `url` / `version` | Identity and endpoint advertisement (opaque to MCP-IDL content) |
| `AgentCard.skills[]` | Each skill **MAY** map to one or more MCP-IDL methods on an Interface Descriptor |
| Skill `id` / `name` / `tags` | Prefer alignment with IDL `methods[].name`, `semantic_tags[]` |
| `capabilities.extensions[]` | **MUST** include the execution extension URI when claiming MCP++ A2A interop |
| Extension `params.interface_cids` | CIDs of Interface Descriptors the agent will execute under this extension |
| Skill or card `metadata` | **MAY** carry `interface_cid`, `method`, profile letters, binding ids |

**Normative rules:**

1. When the extension is active and a skill is backed by MCP-IDL, the agent **SHOULD** expose the corresponding `interface_cid` either in extension `params.interface_cids` or in skill/task metadata.
2. Descriptors remain **not authority** (mcp-idl.md §8). UCAN / policy proofs authorize execution; the card only advertises contracts.
3. Advertisement of MCP bindings **MUST** use ADR-0006 ids (`mcp-binding/2026-07-28`, `mcp-binding/legacy-2024-11-05`) when dual-era support is claimed.
4. Follow-on discovery schemas (MCPP-G110) may refine the full advertisement object; this chapter freezes the **A2A mapping keys and URI**, not the entire discovery registry API.

**Example skill metadata (namespaced keys abbreviated):**

```json
{
  "id": "repo.status",
  "name": "Repository status",
  "description": "Return git working tree status via MCP-IDL.",
  "tags": ["vcs", "git"],
  "metadata": {
    "https://mcplusplus.io/extensions/execution/v1/interface_cid": "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
    "https://mcplusplus.io/extensions/execution/v1/method": "repo.status"
  }
}
```

### 6.2 Task ↔ TaskSpec / ExecutionEnvelope@1

**Goal:** Each A2A Task that runs under this extension corresponds to portable MCP++ execution intent.

| A2A Task field | MCP++ mapping |
| --- | --- |
| `Task.id` | Correlation id for the public task; **MAY** equal or reference `correlation_id` on the envelope; **MUST** remain the A2A task identifier peers use for Get/Cancel/Subscribe |
| `Task.contextId` | See §6.3 |
| `Task.metadata` | **MUST** be able to carry `envelope_cid` when an envelope has been minted |
| Task creation (Send Message) | Mints or accepts an `ExecutionEnvelope@1` (or adapts Profile G `TaskSpec` into Envelope@1 per envelope adapter rules) |

**Normative rules:**

1. Under an activated extension, long-running executable work **SHOULD** be represented as an A2A `Task` (not only a bare Message) so cancel, stream, and push apply.
2. When an envelope is minted, Task metadata **MUST** include:
   - `envelope_cid` — CID of `ExecutionEnvelope@1`
3. Envelope fields map as:

| Envelope field | Source under A2A handoff |
| --- | --- |
| `interface_cid` / `method` | Skill metadata or message data part |
| `input_cid` | Canonicalized Message/Part inputs (§6.4) |
| `intent_cid` | TaskSpec CID or intent object CID |
| `state_refs[]` | Context / StateRef handles (§6.3) |
| `authority.*` | UCAN / proof CIDs from auth (§6.10) |
| `policy_cid` / `decision_cid` | Policy artifacts when Profile D is used |
| `parents[]` | Prior Event DAG / receipt parents when continuing work |
| `correlation_id` | A2A `Task.id` or client correlation string |
| `requester` | Client principal DID when known |

4. Profile G `TaskSpec` remains a valid historical/coordination artifact. Adapters **MAY** bind TaskSpec CID to `intent_cid` (see envelope Profile G adapter vectors). The **public** lifecycle object remains A2A Task.

### 6.3 Context ↔ StateRef@1

**Goal:** Conversational/context grouping maps to explicit shared-state handles without inventing merge semantics.

| A2A | MCP++ |
| --- | --- |
| `contextId` | Logical grouping id for related Tasks/Messages |
| Shared mutable or causal context | One or more `StateRef@1` objects referenced by CID |

**Normative rules:**

1. `contextId` **MAY** be an opaque A2A id with no StateRef when no shared MCP++ state is required.
2. When MCP++ shared state is used under the extension, Task or Message metadata **SHOULD** include:
   - `state_ref_cids` — array of StateRef CIDs
   - and/or envelope `state_refs[]` entries with `state_ref_cid`, optional `mode`, `access`
3. Each StateRef **MUST** declare exactly one mode from the closed set: `immutable`, `single_authority`, `causal`, `crdt`, `consensus` (state-ref.md).
4. Observing the same logical state on concurrent Event DAG branches **MUST NOT** silently merge mutable values (ADR-0004 / state-ref.md §5).
5. `contextId` alone is **not** a consistency mode and **MUST NOT** be treated as authority to write state.

### 6.4 Message / Part ↔ CID inputs

**Goal:** A2A message content becomes content-addressed envelope inputs.

| A2A Part kind | MCP++ mapping |
| --- | --- |
| Text part | Canonical UTF-8 bytes → `input_cid` (or a structured input object CID that includes the text) |
| File part (URI or bytes) | File bytes or referenced blob → CID; file URI **MAY** be stored as metadata alongside the CID |
| Data part (structured JSON) | Canonicalized per `mcpp-jcs-v1` when content-addressed → `input_cid` or nested CIDs |

**Normative rules:**

1. When the extension is active and the agent claims CID-native execution, the effective invocation input **MUST** be addressable as `input_cid` on the envelope (inline-only execution without a CID is non-portable and **MUST NOT** be claimed as cross-trust MCP++ execution).
2. Multi-part messages **MAY** produce a composite input object whose CID is `input_cid`, with part digests recorded in that object.
3. Message `metadata` **MAY** carry:
   - `input_cid`
   - `intent_cid`
   - `envelope_cid` (if pre-minted by the client)
4. Clients **MAY** send a DataPart whose payload is an `ExecutionEnvelope@1` object or a reference `{ "envelope_cid": "…" }`. Agents that advertise the extension **SHOULD** accept this form when `required` semantics demand structured execution.
5. Unknown or unsupported media types fail with A2A `ContentTypeNotSupportedError` (or binding equivalent); agents **MUST NOT** coerce arbitrary parts into forged CIDs.

### 6.5 Artifact ↔ `output_cid`

**Goal:** Task outputs are portable CIDs, not only inline blobs.

| A2A | MCP++ |
| --- | --- |
| `Task.artifacts[]` | Published outputs for the task |
| Artifact parts | Bytes / data corresponding to `output_cids` |
| Artifact `metadata` | **MUST** be able to carry `output_cid` (and optional schema CID) |

**Normative rules:**

1. On successful completion under this extension, at least one Artifact **SHOULD** reference the primary output via metadata `output_cid`, aligning with `ExecutionResult@1.output_cids` / `primary_output_cid`.
2. Large binaries **SHOULD** be exchanged as CID-referenced content (file parts pointing at retrievable CIDs) rather than only unbounded inline bytes, when the agent claims Profile B CID-native behavior.
3. Artifact metadata **MAY** also include `result_cid` and, at terminal success, the final evidence keys in §6.11.
4. Multiple artifacts **MAY** map one-to-one with multiple `output_cids`.

### 6.6 Status ↔ events (no forked status names)

**Goal:** Progress and outcomes use A2A TaskState; MCP++ attaches event/receipt evidence.

| A2A TaskState | Typical MCP++ evidence / internal mapping |
| --- | --- |
| `submitted` | Envelope accepted; optional parent event recorded |
| `working` | DurableExecutor running; progress events; optional partial artifacts |
| `input-required` | Waiting on client Message; no forged completion receipt |
| `auth-required` | Missing/invalid delegation; challenge via auth mapping (§6.10) |
| `completed` | `ExecutionResult@1.status = succeeded` (+ receipt) |
| `failed` | `failed` / `timed_out` / unrecoverable error |
| `canceled` | `cancelled` after durable cancel |
| `rejected` | `rejected` (policy/authority decline) |

**Normative rules:**

1. Public Task status **MUST** use A2A `TaskState` values only.
2. Finer-grained MCP++ progress (retry attempt, fencing epoch, policy decision) **MUST** be placed in `TaskStatus.message.metadata`, `Task.metadata`, or Event DAG nodes — **not** as new TaskState enum members (official A2A limitation: extensions must not add enum values).
3. Status transitions **SHOULD** append Event DAG nodes when Profile F is in use; `event_cid` of the latest status-related node **MAY** appear in Task metadata during `working`.
4. Mapping table for `ExecutionResult@1.status` → A2A TaskState:

| `ExecutionResult@1.status` | A2A TaskState |
| --- | --- |
| `succeeded` | `completed` |
| `failed` | `failed` |
| `timed_out` | `failed` (metadata **SHOULD** note timeout) |
| `cancelled` | `canceled` |
| `rejected` | `rejected` |
| `compensated` | `completed` or `failed` per compensation policy; metadata **MUST** record compensation (do not invent a public `compensated` TaskState) |

### 6.7 Cancel ↔ DurableExecutor cancel

**Goal:** A2A Cancel Task is the public cancel API; durability is internal.

| A2A | MCP++ |
| --- | --- |
| Cancel Task operation | Request cancellation of the A2A Task |
| Terminal `canceled` | Public outcome |

**Normative rules:**

1. On Cancel Task, an agent implementing DurableExecutor **MUST** invoke durable `cancel` (or equivalent) so cancellation survives crash recovery (ADR-0005).
2. After durable cancel is accepted, subsequent side effects for that work **MUST** fail closed as cancelled.
3. The public Task state **MUST** become A2A `canceled` (when cancellation succeeds), not a private journal-only flag without Task update.
4. If the task is already terminal, return A2A `TaskNotCancelableError` (or binding equivalent).
5. DurableExecutor cancel is **not** a second public RPC surface peers must call instead of A2A Cancel Task.

### 6.8 Streaming ↔ progress

**Goal:** Real-time updates use A2A streaming events.

| A2A | MCP++ |
| --- | --- |
| Send Streaming Message / Subscribe to Task | Stream of `TaskStatusUpdateEvent` / `TaskArtifactUpdateEvent` |
| Status update events | Progress while envelope executes |
| Artifact update events | Partial or final `output_cid` artifacts |

**Normative rules:**

1. When `AgentCard.capabilities.streaming` is true and the extension is active, status updates **SHOULD** include metadata keys for `envelope_cid`, current `event_cid` (if any), and retry attempt when retries occur.
2. Partial outputs **MAY** stream as artifact updates before terminal receipt mint.
3. Stream **MUST** close when the Task reaches a terminal A2A state (`completed`, `failed`, `canceled`, `rejected`), per official A2A streaming rules.
4. Streaming is not a license to invent non-A2A status names.

### 6.9 Push notifications ↔ receipt notifications

**Goal:** Webhooks deliver terminal (and optionally intermediate) evidence references.

| A2A | MCP++ |
| --- | --- |
| Push notification config / webhook | Client-reachable HTTP endpoint |
| Push payload (`StreamResponse` family) | Status/artifact updates including receipt metadata |

**Normative rules:**

1. When push is supported and configured, terminal transitions under this extension **SHOULD** notify with Task metadata including `receipt_cid`, `event_cid`, and proof references (§6.11).
2. Intermediate `working` pushes are optional; if sent, they **MUST** still use A2A TaskState values.
3. Push is a delivery mechanism for A2A updates, not a separate MCP++ receipt protocol.

### 6.10 Auth ↔ delegation challenges

**Goal:** Authentication schemes and mid-task `auth-required` map to UCAN / proof evaluation.

| A2A | MCP++ |
| --- | --- |
| `AgentCard.securitySchemes` / `security` | Transport and HTTP-level auth to reach the agent |
| `TASK_STATE_AUTH_REQUIRED` | Interrupted state when execution-time authority is insufficient |
| Message after auth | Client supplies credentials and/or proof material |

**Normative rules:**

1. Transport authentication (TLS, bearer, OAuth, etc.) **MUST NOT** by itself grant UCAN capabilities (plan KD-14). PeerID / client cert identity is observational unless bound into a proof.
2. When Profile C authority is required and proofs are missing or invalid, the agent **SHOULD** move the Task to `auth-required` (or reject with an authorization error at create time).
3. Challenge/response material **SHOULD** be carried in Message metadata under the extension namespace, for example:
   - `required_abilities` — capabilities still needed
   - `resource` — resource URI/CID being authorized
   - `audience` — expected audience DID
4. Client continuation Message **SHOULD** attach `proof_cids` / `delegation_cids` (or a DataPart envelope authority block). The agent **MUST** validate proofs at execution time (ucan-delegation.md §6).
5. Payment (e.g. x402) **MUST NOT** substitute for authorization proofs (KD-14).

### 6.11 Terminal results → `receipt_cid` / `event_cid` / proofs

**Goal:** Final A2A results under this extension carry MCP++ evidence references without a parallel terminal-state machine.

When a Task reaches a terminal state under the activated extension, Task metadata and/or the primary Artifact metadata **MUST** be able to carry:

| Key (suffix) | Required on portable success | Meaning |
| --- | --- | --- |
| `receipt_cid` | **MUST** (cross-trust success) | CID of `ExecutionReceipt@1` |
| `event_cid` | **SHOULD** | Event DAG node linking envelope/result/receipt |
| `result_cid` | **SHOULD** | CID of `ExecutionResult@1` |
| `envelope_cid` | **MUST** when an envelope was used | Request envelope CID |
| `output_cid` or list in artifacts | **SHOULD** on success | Primary output CID(s) |
| `proof_cids` / `proof_cid` | **SHOULD** when proofs were checked or emitted | Authority / verification proofs |
| `decision_cid` | **MAY** | Policy decision CID |
| `delegation_cid` | **MAY** | Effective delegation CID |

**Normative rules:**

1. Terminal A2A state remains one of `completed` / `failed` / `canceled` / `rejected`. Evidence CIDs annotate that state; they do not replace it.
2. Cross-trust-domain success **MUST** provide a content-addressed receipt (`receipt_cid`) verifiable per execution-envelope.md / ADR-0002 conformance level claimed.
3. Same-trust-domain deployments **MAY** omit signatures on receipts but **SHOULD** still mint `receipt_cid` when claiming this extension.
4. On failure/cancel/reject, agents **SHOULD** still publish `receipt_cid` or a structured `PortableError@1` reference when an attempt ran far enough to produce a result object.
5. Clients and verifiers **MUST** treat missing required evidence on a claimed portable success as non-conformant for MCP++ A2A interop, even if A2A TaskState is `completed`.

**Example terminal Task metadata:**

```json
{
  "https://mcplusplus.io/extensions/execution/v1/envelope_cid": "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
  "https://mcplusplus.io/extensions/execution/v1/result_cid": "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti",
  "https://mcplusplus.io/extensions/execution/v1/receipt_cid": "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi",
  "https://mcplusplus.io/extensions/execution/v1/event_cid": "bafkreieventnodeexample0123456789abcdefghijklmnopqrs",
  "https://mcplusplus.io/extensions/execution/v1/output_cid": "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi",
  "https://mcplusplus.io/extensions/execution/v1/proof_cids": [
    "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
  ]
}
```

*(Example CIDs are illustrative.)*

---

## 7. End-to-end handoff sequence

```text
  Client agent                         Server agent
      |                                      |
      |-- GET Agent Card ------------------->|
      |<-- extensions: execution/v1 ---------|
      |                                      |
      |-- Send Message                      |
      |   A2A-Extensions: …/execution/v1     |
      |   parts + optional envelope_cid ---->|
      |                                      | mint/validate ExecutionEnvelope@1
      |                                      | DurableExecutor.start
      |<-- Task id, state=submitted/working -|
      |                                      |
      |   (stream / poll / push)             | progress events, partial artifacts
      |                                      |
      |   [optional auth-required loop]      | UCAN challenge / proof_cids
      |                                      |
      |-- Cancel Task (optional) ----------->| DurableExecutor.cancel
      |                                      |
      |<-- terminal TaskState + metadata ----|
      |    receipt_cid, event_cid, proofs    | ExecutionReceipt@1 + Event DAG
```

Two independently configured agents complete a handoff when:

1. Both agree on the extension URI via card + `A2A-Extensions`.
2. The server exposes A2A Task lifecycle operations.
3. Terminal metadata carries the evidence keys in §6.11 for portable claims.
4. Cancel, retry, streaming, malformed extension URI, and unsupported profile cases fail closed (proved in MCPP-056+).

---

## 8. Fail-closed rules

| Condition | Required behavior |
| --- | --- |
| Reverse-DNS-only extension id on card or `A2A-Extensions` | Non-conformant; reject interop claim |
| Required extension not activated | Reject request (`ExtensionSupportRequiredError` or equivalent) |
| Unsupported profile letter in request metadata | Reject or ignore with explicit error; **MUST NOT** silently claim success |
| Missing `input_cid` when CID-native execution is required | Reject or `failed` with portable error |
| Missing proofs when portable authority is claimed | `auth-required`, `rejected`, or authorization error — not silent success |
| Public status uses non-A2A enum as sole lifecycle | Non-conformant |
| DurableExecutor presented as public multi-agent API instead of A2A Task | Non-conformant |
| Portable `completed` without `receipt_cid` | Non-conformant for cross-trust claims |
| Silent binding downgrade (MCP) under dual-binding peers | Fail closed per ADR-0006 |
| Forged CIDs / schema markers | Structural validation fails; do not execute |

---

## 9. Relationship to MCP bindings and MCP Tasks

| Mechanism | Identifier shape | Role |
| --- | --- | --- |
| This A2A extension | URI `https://mcplusplus.io/extensions/execution/v1` | Cross-agent handoff on A2A Task |
| MCP binding current | `mcp-binding/2026-07-28` | Stateless MCP carriage (not initialize-based) |
| MCP binding legacy | `mcp-binding/legacy-2024-11-05` | Initialize-era MCP carriage |
| MCP Tasks extension | `io.modelcontextprotocol/tasks` | MCP-side long-running tasks (poll `tasks/get`, etc.) |

MCP++ peers **MAY** implement MCP Tasks on MCP bindings **and** this A2A extension. The id spaces **MUST NOT** be conflated: an MCP capability key is never a valid A2A `AgentExtension.uri`.

---

## 10. Non-goals and deferred work

| Item | Owner |
| --- | --- |
| JSON Schemas and conformance vectors for extension metadata | MCPP-055 |
| Reference adapter + two-agent handoff tests | MCPP-056 |
| SwissKnife adapter | MCPP-057 |
| Full discovery/advertisement registry beyond card mapping | MCPP-G110 / later tasks |
| Hosting the human-readable spec at the extension URI | Ops follow-on (identifier remains stable) |
| New A2A RPC methods | Not required for 1.0; core A2A operations suffice |

---

## 11. Interface checklist (`A2AExecutionExtension@1`)

A reader may treat the following as the interface label **`A2AExecutionExtension@1`**:

1. Official rule cited: extensions are **URIs** on the Agent Card, activated via **`A2A-Extensions`**.
2. Wire URI is **`https://mcplusplus.io/extensions/execution/v1`**; alias `io.mcplusplus.execution@1` is non-wire only.
3. **No competing public task lifecycle** — A2A TaskState remains public; MCP++ maps evidence onto it.
4. Mappings defined for: Agent Card ↔ MCP-IDL (+ `interface_cid`), Task ↔ TaskSpec/Envelope, context ↔ StateRef, Message/Part ↔ CID inputs, Artifact ↔ `output_cid`, status ↔ events, cancel ↔ durable cancel, streaming ↔ progress, push ↔ receipt notifications, auth ↔ delegation challenges, finals ↔ `receipt_cid` / `event_cid` / proofs.
5. Custom data lives in **metadata** (and CID-addressed objects); core A2A field definitions and TaskState enums are not rewritten.
6. DurableExecutor and MCP Tasks stay correctly scoped and non-competitive with A2A Task.

---

## 12. Acceptance (MCPP-054)

| Criterion | Status |
| --- | --- |
| Spec cites the official extension identifier rule (URI on Agent Card; `A2A-Extensions`) | Yes — §2.1 |
| Confirmed wire URI `https://mcplusplus.io/extensions/execution/v1` | Yes — §2.2 |
| Alias documented as non-wire | Yes — §2.2 |
| Does not invent a competing task lifecycle | Yes — §3, §6.6, §6.7, §11 |
| Mappings cover the MCPP-054 effects list | Yes — §5–§6 |

**Validation:**

```text
test -s ipfs_accelerate_py/mcplusplus/docs/spec/a2a-extension.md
```
