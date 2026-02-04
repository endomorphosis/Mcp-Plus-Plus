# Profile E: `mcp+p2p` Transport Binding (libp2p)

**Status:** Draft

This document expands the optional MCP++ transport profile that carries MCP JSON-RPC semantics over a peer-to-peer substrate.

This profile is intentionally **carriage-only**: it defines how to move MCP messages between peers. It does not redefine MCP methods, tool semantics, or policy rules.

## 1. Scope

- Defines the *carriage* of MCP JSON-RPC messages over libp2p.
- Does not change MCP method semantics.
- Adds P2P-friendly discovery, multiplexing, and optional event dissemination.

## 2. Goals

- Support multi-agent, cross-org deployments (no fixed client↔server topology).
- Use secure, multiplexed streams for concurrent tool calls.
- Support bidirectional communication patterns (events/receipts/descriptor dissemination).

## 2.1 Non-goals

- Defining a global consensus mechanism.
- Replacing existing MCP client↔server transports.
- Standardizing a single network-wide discovery scheme.

## 3. Transport Overview

A conforming `mcp+p2p` implementation:

- Establishes a libp2p connection between peers.
- Opens one or more multiplexed streams for MCP JSON-RPC sessions.
- Runs the standard MCP initialization handshake over the stream (version + capability negotiation).

## 3.1 Stream Protocol Identifiers (Normative)

The binding MUST define one or more libp2p stream protocol identifiers (protocol IDs) used to negotiate the MCP carriage.

Implementations MAY use separate protocol IDs for:
- a control/session stream (initialization + capability negotiation),
- JSON-RPC request/response traffic,
- optional event dissemination.

## 3.2 Session Lifecycle (Normative)

For each MCP session carried over `mcp+p2p`, an implementation MUST:

1. Establish a libp2p connection to a remote peer (by PeerID and address material such as multiaddrs).
2. Open a stream using the `mcp+p2p` protocol ID.
3. Run the standard MCP initialization handshake over that stream.
4. Treat the resulting session as an MCP transport equivalent (requests, responses, notifications), preserving MCP JSON-RPC semantics.

## 4. Addressing and Discovery (Non-Normative)

Implementations MAY use:
- peer IDs and multiaddrs for addressing
- DHT-based discovery
- rendezvous/relay services
- LAN-local discovery (e.g., mDNS)
- pubsub topics for announcements

## 5. Message Framing

MCP JSON-RPC payloads MUST be transmitted without semantic modification.

The binding MUST define:
- how messages are delimited/framed on the stream,
- how request/response correlation is preserved,
- backpressure and flow control expectations.

### 5.1 Recommended Framing (Non-Normative)

To keep framing simple and unambiguous, implementations SHOULD use a length-prefixed framing strategy (e.g., prefix each JSON-RPC message with its byte length) rather than relying on sentinel delimiters.

## 6. Optional Event Dissemination

Implementations MAY publish/subscribe to topics for:
- `interface_cid` announcements (MCP-IDL)
- `receipt_cid` / `decision_cid` dissemination
- coordination signals for scheduling/ordering

If event dissemination is enabled, implementations SHOULD clearly separate:
- **point-to-point session traffic** (tool calls, responses), from
- **fanout traffic** (announcements, receipts, coordination),

so that session correctness does not depend on pubsub delivery.

## 7. Security Considerations

- Use authenticated/encrypted channels supported by libp2p.
- Authorization is still enforced at the application layer (e.g., UCAN + policy evaluation).
- Peers SHOULD rate-limit and validate incoming messages to mitigate abuse.

Additional considerations:

- **Peer identity:** the remote libp2p PeerID is not, by itself, sufficient authorization. Bind execution authority to explicit proofs (e.g., UCAN) and policy decisions.
- **Resource exhaustion:** protect against unbounded stream creation, oversized frames, and high-rate notifications.
- **Replay:** if receipts/decisions are disseminated, implementations SHOULD include enough context (CIDs, signatures, freshness bounds) to detect duplicates/replays.

## 8. Related Documents

- Interface contracts: [docs/spec/mcp-idl.md](mcp-idl.md)
- CID artifacts: [docs/spec/cid-native-artifacts.md](cid-native-artifacts.md)

## 9. Interop Checklist (Implementation Guidance)

This section is intended to reduce “two implementations that both claim `mcp+p2p` but can’t talk” failures. Items marked **MUST** are required for baseline interoperability; items marked **SHOULD** are strong recommendations.

### 9.1 Wire Compatibility

- Implementations **MUST** agree on the libp2p stream protocol ID(s) used for `mcp+p2p`.
- Implementations **MUST** preserve MCP JSON-RPC payload semantics (no field rewriting, no method translation).
- Implementations **MUST** define message framing unambiguously.
- Implementations **SHOULD** use length-prefixed framing.
- Implementations **MUST** define maximum frame size and behavior on violation (e.g., close stream).

### 9.2 Session Semantics

- Implementations **MUST** run MCP initialization (version + capability negotiation) at the start of each session stream.
- Implementations **MUST** preserve request/response correlation (`id`) across the transport.
- Implementations **MUST** define concurrency expectations (e.g., multiple outstanding requests per stream).
- Implementations **SHOULD** specify keepalive/idle-timeout behavior.
- Implementations **SHOULD** define retry/reconnect guidance (what is safe to retry; what requires idempotency semantics at the application layer).

### 9.3 Abuse Resistance

- Implementations **MUST** rate-limit inbound session creation and inbound message volume.
- Implementations **SHOULD** apply per-peer quotas (streams, bandwidth, frame rate, max concurrent in-flight requests).
- Implementations **MUST** validate framing before allocating large buffers.

### 9.4 Identity and Authorization

- Implementations **MUST** use authenticated/encrypted libp2p channels.
- Implementations **MUST** treat network identity (PeerID) as distinct from execution authority.
- Implementations **SHOULD** bind “who is acting” to explicit proofs (e.g., UCAN) and record those proofs in CID-native artifacts.

### 9.5 Optional Event Dissemination

- If pubsub dissemination is implemented, it **MUST NOT** be required for correctness of point-to-point MCP request/response sessions.
- Implementations **SHOULD** document topic naming, message types, and validation rules for any published events.

### 9.6 Conformance Test Ideas (Non-Normative)

1. **Handshake + capabilities**
	- Open a stream using the `mcp+p2p` protocol ID.
	- Verify MCP initialization completes and negotiated capabilities match expectations.
	- Negative case: send MCP traffic before init; verify the peer rejects/terminates the session.

2. **Framing and correlation**
	- Send multiple concurrent JSON-RPC requests with distinct `id` values.
	- Verify responses correlate correctly under reordering/latency.
	- Negative case: send an oversized frame; verify deterministic enforcement (close stream, error).

3. **Backpressure + abuse limits**
	- Flood with small frames and/or open many streams.
	- Verify rate limits/quotas trigger without crashing the process or unbounded memory growth.

4. **Authorization separation**
	- Establish a valid libp2p connection but omit UCAN/proof material in the higher-layer envelope.
	- Verify the transport succeeds while the application layer denies execution.

5. **Pubsub independence (if implemented)**
	- Disable pubsub connectivity and verify point-to-point MCP sessions still work.
	- Enable pubsub and verify published announcements are validated (schema/signature/CID checks) before acceptance.
