# Profile E: `mcp+p2p` Transport Binding (libp2p)

**Status:** Draft

This document expands the optional MCP++ transport profile that carries MCP JSON-RPC semantics over a peer-to-peer substrate.

## 1. Scope

- Defines the *carriage* of MCP JSON-RPC messages over libp2p.
- Does not change MCP method semantics.
- Adds P2P-friendly discovery, multiplexing, and optional event dissemination.

## 2. Goals

- Support multi-agent, cross-org deployments (no fixed client↔server topology).
- Use secure, multiplexed streams for concurrent tool calls.
- Support bidirectional communication patterns (events/receipts/descriptor dissemination).

## 3. Transport Overview

A conforming `mcp+p2p` implementation:

- Establishes a libp2p connection between peers.
- Opens one or more multiplexed streams for MCP JSON-RPC sessions.
- Runs the standard MCP initialization handshake over the stream (version + capability negotiation).

## 4. Addressing and Discovery (Non-Normative)

Implementations MAY use:
- peer IDs and multiaddrs for addressing
- DHT-based discovery
- pubsub topics for announcements

## 5. Message Framing

MCP JSON-RPC payloads MUST be transmitted without semantic modification.

The binding MUST define:
- how messages are delimited/framed on the stream,
- how request/response correlation is preserved,
- backpressure and flow control expectations.

## 6. Optional Event Dissemination

Implementations MAY publish/subscribe to topics for:
- `interface_cid` announcements (MCP-IDL)
- `receipt_cid` / `decision_cid` dissemination
- coordination signals for scheduling/ordering

## 7. Security Considerations

- Use authenticated/encrypted channels supported by libp2p.
- Authorization is still enforced at the application layer (e.g., UCAN + policy evaluation).
- Peers SHOULD rate-limit and validate incoming messages to mitigate abuse.

## 8. Related Documents

- Interface contracts: [docs/spec/mcp-idl.md](mcp-idl.md)
- CID artifacts: [docs/spec/cid-native-artifacts.md](cid-native-artifacts.md)
