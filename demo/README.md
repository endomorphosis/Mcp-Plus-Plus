# Three-peer Docker Compose demonstration (ThreePeerDemo@1)

Local, repeatable MCP++ three-peer demonstration for **MCPP-076** / **MCPP-G160**.

The happy path brings up **three peers** on a single Compose bridge network, runs
the **16 required demonstration steps**, and does **not** depend on cloud-only
services or libp2p circuit relays.

Demo success is **not** production admission. A full independent evidence-bundle
verifier is delivered by **MCPP-077**.

## One-command invocation

From the MCP++ package root (`ipfs_accelerate_py/mcplusplus`):

```bash
python -m mcpp demo --peers 3 --verify
```

That CLI entry reports the demo root and whether `demo/docker-compose.yml` is
present. To run the full Compose mesh and step runner:

```bash
cd demo && docker compose up --abort-on-container-exit --exit-code-from demo-runner
```

Equivalent one-liner from the package root:

```bash
docker compose -f demo/docker-compose.yml up --abort-on-container-exit --exit-code-from demo-runner
```

Help / smoke validation (board command):

```bash
cd ipfs_accelerate_py/mcplusplus && python -m mcpp demo --help
```

## What Compose starts

| Service | Required? | Role |
| --- | --- | --- |
| `peer-a` | **yes** | Coordinator peer `did:web:peer-a.example` (HTTP `:18080`) |
| `peer-b` | **yes** | Worker peer `did:web:peer-b.example` (HTTP `:18081`) |
| `peer-c` | **yes** | Worker peer `did:web:peer-c.example` (HTTP `:18082`) |
| `demo-runner` | **yes** | Executes the 16 demonstration steps; writes evidence under the shared volume |
| `circuit-relay-v2` | **optional** | Compose profile `relays` only |
| `circuit-relay-v2-secondary` | **optional** | Compose profile `relays` only |

Shared volume `mcpp-three-peer-shared` holds:

- per-peer durable identity/store under `/var/lib/mcpp/store/<peer>/`
- mesh registry `/var/lib/mcpp/peers.json`
- step evidence `/var/lib/mcpp/evidence/demo-steps.json`

## The 16 required demonstration steps

These steps are the operator-facing contract for ThreePeerDemo@1. The
`demo-runner` service records each step in `demo-steps.json`.

| # | Step | What it proves |
| --- | --- | --- |
| 1 | **Bring up three peers** | Compose starts at least three healthy peer processes on the local mesh |
| 2 | **Capability discovery** | Peers are discoverable via the shared registry / `mcpp peer list` |
| 3 | **A2A handoff surface** | Three-peer mesh is bound for A2A task handoff (adapter coverage; no competing lifecycle) |
| 4 | **Attenuated delegation** | Authority remains capability-bound (UCAN / Profile C); demo does not mint live broad authority |
| 5 | **Policy evaluation** | Profile D fail-closed behaviour is exercised (policy denials, zero policy bypasses) |
| 6 | **Execution envelope** | A portable `ExecutionEnvelope@1` is minted via `mcpp envelope create` |
| 7 | **State + doctor** | Local doctor reports binding/schema/crypto suite versions for the mesh |
| 8 | **Simultaneous claims** | Same-epoch exclusive claims yield one deterministic winner and conflict evidence |
| 9 | **Partition fail-closed** | Isolated peer cannot resolve exclusive work (`G_COORDINATION_UNAVAILABLE`) |
| 10 | **Idempotent replay** | Replaying the same claim event does not change claim/event counts |
| 11 | **Durable restart** | Peer restart recovers accepted resolution and fencing token from the Event DAG |
| 12 | **Lease expiry + takeover** | After expiry, majority issues a higher epoch and strictly higher fencing token |
| 13 | **Stale fence rejection** | Late completion under an old fence is rejected (`G_STALE_FENCE`) |
| 14 | **Single authoritative completion** | Conflicting completion rejected; exactly one successful exclusive completion |
| 15 | **Reconciliation + Event DAG** | Partition heal converges frontiers/state roots; DAG parents precede children |
| 16 | **Signed receipt + evidence entry** | `mcpp demo --peers 3 --verify` entry for independent verification (bundle verifier: MCPP-077) |

Normative Profile G exclusive-safety mapping (spec §14.3): steps **8–15**.
G160 CLI/demo path: steps **1–7** and **16**.

## Optional relays (documented — never silently skipped)

Circuit relays are **optional** and **not** part of the happy path.

| Fact | Detail |
| --- | --- |
| Default | Relays are **not** started. Local peers use the Compose bridge (`mcpp-mesh`) with direct multiaddrs |
| Enable | `docker compose --profile relays up` |
| Services | `circuit-relay-v2`, `circuit-relay-v2-secondary` |
| Image override | `MCPP_CIRCUIT_RELAY_IMAGE` (default `libp2p/js-libp2p-relay:latest`) |
| Happy-path env | `MCPP_REQUIRE_CIRCUIT_RELAY=0`, `MCPP_OPTIONAL_RELAYS=documented-not-required` |

**Blocker policy (fail-closed documentation):**

- If WAN/NAT traversal tests need a circuit relay and the relay image cannot be
  pulled, the container fails to start, or no relay multiaddr is configured,
  record that as a **documented blocker** for those optional assertions.
- Do **not** silently skip relay-dependent checks.
- Do **not** claim the happy path used relays when the `relays` profile was not
  started.
- Missing optional relays must **never** be re-labeled as a green assertion.

Evidence written by `demo-runner` always includes an `optional_relays` object
with this policy text so later verifiers (MCPP-077) can distinguish “not
required” from “required and missing.”

## Prerequisites

- Docker Engine with Compose V2 plugin
- Ability to pull `python:3.11-slim` (or a pre-loaded mirror)
- Package tree mounted read-only at `/mcpp` (Compose bind of the parent of this
  directory)

No Kubo, Restate Cloud, paid relay, or external bootstrap is required for the
happy path.

## Manual checks

```bash
# Peer health
curl -s http://127.0.0.1:18080/ | python -m json.tool
curl -s http://127.0.0.1:18081/ | python -m json.tool
curl -s http://127.0.0.1:18082/ | python -m json.tool

# CLI from package root
python -m mcpp doctor
python -m mcpp peer list
python -m mcpp demo --peers 3 --verify

# Profile G harness alone (no Docker)
python -m pytest -q tests-py/integration/test_profile_g_three_peer.py
```

## Tear down

```bash
docker compose -f demo/docker-compose.yml down -v
```

## Interface pins

| Pin | Value |
| --- | --- |
| Interface | `ThreePeerDemo@1` |
| Task | `MCPP-076` |
| Goal | `MCPP-G160` |
| CLI | `McppCli@1` (`python -m mcpp`) |
| Harness | `ThreePeerHarness@1` (`tests-py/harness/profile_g_three_peer.py`) |
| Evidence steps schema | `mcp++/demo/three-peer-steps@1` |

## Related docs

- [Profile G three-peer conformance](../docs/testing/profile-g-three-peer-conformance.md)
- [Profile G risk-scheduling (normative exclusive safety)](../docs/spec/risk-scheduling.md)
- [P2P transport / NAT-relay guidance](../docs/spec/transport-mcp-p2p.md)
- [A2A extension](../docs/spec/a2a-extension.md)
- [Durable execution](../docs/architecture/durable-execution.md)
