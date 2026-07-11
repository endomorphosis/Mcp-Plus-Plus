# SwissKnife and IPFS MCP Compatibility Snapshot

**Status:** Working-draft interoperability audit

**Reference revision:** `b8843522b0f6f657f795a23816956e745c421c5e` (`main`, 2026-07-08)

**Verified:** 2026-07-11

## Scope

This is an evidence-backed statement about the configured SwissKnife
virtual-desktop gateways. It does not claim that every capability found in the
source trees of `ipfs_kit_py`, `ipfs_datasets_py`, or `ipfs_accelerate_py` is
reachable through those gateways.

| Service | MCP endpoint | libp2p peer | Live tools | Profile A interface CID |
| --- | --- | --- | ---: | --- |
| `ipfs_kit_py` | `http://127.0.0.1:8014/mcp` | `127.0.0.1:9114` | 153 | `bafkreigtrlsydtivo7l5hzgxu7eo5d633crbdjd44pdn63nkxkbsvsso2q` |
| `ipfs_datasets_py` | `http://127.0.0.1:3002/mcp` | `127.0.0.1:9112` | 275 | `bafkreiea6ifqo536vjhu5iab3gccs3e6mp2hsabokmm7juyh64wz6a2mpi` |
| `ipfs_accelerate_py` | `http://127.0.0.1:3003/mcp` | `127.0.0.1:9113` | 122 | `bafkreieforcfnzh4w7vxu34d3ihmor2tacjuwptd6slvtb7nk5tttcq2km` |

The 550 total is the sum of unique names in each service registry. The audit
executes one safe call per service; it does not invoke every tool.

## Current Result

**Full MCP++ all-profile conformance: NO-GO.**

Baseline MCP, Profiles A-B, and Profile E are live across all three configured
gateways. The full audit remains partial because Profiles C-D and Event DAG
surfaces are not available from the compatibility adapters.

| Requirement group | SwissKnife host implementation | Configured IPFS service gateways | Audit status |
| --- | --- | --- | --- |
| Baseline MCP (`initialize`, `tools/list`, `tools/call`) | Connector support and hierarchical discovery | All three gateways list tools and accept a safe call | PASS |
| Profile A: MCP-IDL | Connector performs list, get, and compatibility checks over HTTP and libp2p | Each service exposes `interfaces/list`, `interfaces/get`, `interfaces/compat`, `/mcp/interfaces`, and matching canonical descriptors | PASS |
| Profile B: CID-native artifacts | Connector sends complete execution envelopes | `mcp++/execute` and `POST /mcp/execute` produce valid CIDv1 artifacts | PASS |
| Profile C: UCAN delegation | Local UCAN/delegation code exists | `mcp++/ucan/validate` and `/mcp/ucan/*` are unavailable | GAP |
| Profile D: temporal deontic policy | Local policy and ORB enforcement code exist | `mcp++/policy/evaluate` and `/mcp/policy/evaluate` are unavailable | GAP |
| Event DAG | Local event-DAG code exists | `/mcp/dag/{frontier,history,provenance}` is unavailable | GAP |
| Profile E: `mcp+p2p` | SwissKnife connector dials framed libp2p streams and disconnects its owned node | All three peers are live, callable, and negotiate canonical MCP initialization | PASS |

## Profile A Evidence

Every backend negotiated `capabilities.experimental["mcp++/mcp-idl"]` and
returned exactly one self-compatible descriptor. The HTTP JSON-RPC and REST
results were both validated against the canonical descriptor bytes; libp2p
returned the same CID for each service.

| Service | HTTP methods | REST registry | libp2p descriptor | Method coverage |
| --- | --- | --- | --- | --- |
| `ipfs_kit_py` | list/get/compat | list/get/compat | valid, self-compatible | 153 of 153 |
| `ipfs_datasets_py` | list/get/compat | list/get/compat | valid, self-compatible | 275 of 275 |
| `ipfs_accelerate_py` | list/get/compat | list/get/compat | valid, self-compatible | 122 of 122 |

Canonical ordering is byte/code-point ordered across the Node and Python
implementations, so the HTTP and libp2p descriptor CIDs remain identical even
for the accelerate registry's uppercase aliases.

## Profile B Evidence

Each gateway negotiates `capabilities.experimental["mcp++/cid-envelope"]` and
accepts `mcp++/execute` over HTTP and libp2p, plus `POST /mcp/execute` over
HTTP. An execution result contains a CIDv1 raw artifact for the input, intent,
envelope, output, receipt, and event. The captures recompute the canonical
JSON CIDs for the output, envelope, receipt artifact, and event before marking
the result valid.

| Service | HTTP execution | libp2p execution | Deterministic parity |
| --- | --- | --- | --- |
| `ipfs_kit_py` | valid receipt | valid receipt | interface, input, envelope CIDs match |
| `ipfs_datasets_py` | valid receipt | valid receipt | interface, input, envelope CIDs match |
| `ipfs_accelerate_py` | valid receipt | valid receipt | interface, input, envelope CIDs match |

The fixed timestamp, correlation ID, and input used by the probes make the
immutable pre-execution artifacts equal on both transports. Receipt and output
CIDs may differ because each tool execution records its own observed output and
duration.

## Artifact Persistence

Profile A and Profile B artifacts are not merely locally calculated CIDs. The
gateways canonicalize each artifact, verify that its CIDv1 raw SHA-256 value
matches its bytes, and persist the raw block before returning a successful
persistence record.

| Priority | Backend | Verification and retention |
| --- | --- | --- |
| 1 | `ipfs_kit_py` artifact endpoint | Writes a Kubo raw block, checks `block/stat` and `block/get`, then pins it. |
| 2 | Direct Kubo RPC | Performs the same raw block, read-back, and pin sequence. |
| 3 | Shared local artifact cache | Atomically writes and hashes the block under `~/.cache/swissknife/mcpplusplus-artifacts` for offline recovery. |

The profile result exposes `artifact_persistence` for the Profile A descriptor
and the six Profile B artifacts: input, intent, envelope, output, receipt, and
event. `GET /mcp/artifacts/{cid}` retrieves artifacts over HTTP; the same
operation is exposed as `mcp++/artifacts/get` on the framed libp2p bridge.
SwissKnife's connector exposes `getArtifact(cid)` over either active transport.

The current evidence uses a dedicated Kubo 0.39 daemon backed by
`~/.cache/swissknife/mcpplusplus-kubo`, rather than the incompatible legacy
`~/.ipfs` repository. All three services persisted and pinned Profile A and
Profile B artifacts through `ipfs_kit_py`, then read them back from IPFS over
both HTTP and libp2p. The local cache remains an intentional offline fallback;
it is not reported as IPFS persistence.

## Profile E Evidence

SwissKnife's real `MCPPPServerConnector` connected to each peer using
`/mcp+p2p/1.0.0`, enumerated its full registry, fetched the Profile A
descriptor, checked self-compatibility, and executed a safe call without HTTP
fallback.

| Service | Safe call | Concurrent calls | HTTP fallback |
| --- | --- | ---: | --- |
| `ipfs_kit_py` | `files_stat` | 2 returned | none |
| `ipfs_datasets_py` | `list_indices` | 2 returned | none |
| `ipfs_accelerate_py` | `get_server_status` | 2 returned | none |

The bridge returns the canonical MCP `InitializeResult` with
`protocolVersion`, `serverInfo`, and negotiated experimental capabilities. Its
u32 big-endian frames are fragmented into writes no larger than 60 KiB, which
keeps Profile A descriptors below the Python Noise transport's 65,535-byte
write limit while preserving standard framed-message reassembly.

## Remaining Remediation

1. Expose and test Profile C UCAN delegation and validation endpoints.
2. Expose and test Profile D temporal deontic evaluation endpoints.
3. Expose Event DAG frontier, history, and provenance endpoints with receipts
   linked to execution artifacts.
4. Keep cross-language conformance vectors and the three-service evidence
   captures synchronized as the working draft changes.

## Verification Record

- `node swissknife/scripts/capture-swissknife-http-connector-evidence.cjs`
  writes `swissknife/test-results/virtual-desktop-ipfs-mcp-orb/swissknife-http-connector-profile-a-reachability.json`.
- `node swissknife/scripts/capture-swissknife-libp2p-connector-evidence.cjs`
  writes `swissknife/test-results/virtual-desktop-ipfs-mcp-orb/swissknife-libp2p-connector-reachability.json`.
- `node swissknife/scripts/capture-mcp-libp2p-fleet-evidence.cjs` independently
  validates Profile A descriptor bytes, Profile B artifacts, and method coverage
  over each libp2p peer.
- `node swissknife/scripts/capture-mcpplusplus-reference-conformance.cjs` writes
  `mcpplusplus-reference-conformance.json`; it exits `2` while the expected
  all-profile result remains `partial`, but records `profile_a_ready: true` and
  `profile_b_ready: true`.
- `node swissknife/scripts/ensure-mcpplusplus-artifact-kubo.cjs` starts or
  verifies the dedicated artifact Kubo daemon without mutating `~/.ipfs`.
- Focused SwissKnife connector, session, and artifact-store suites: 54 passing
  tests.

This document is a compatibility snapshot, not a substitute for the normative
profile chapters. The normative chapters remain the authority for new
implementations.
