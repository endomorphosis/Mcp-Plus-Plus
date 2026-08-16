# MCP++ Threat Model

**Status:** Architecture security guide (MCP++ 1.0 gap-closure)  
**Interfaces:** `ThreatModel@1`  
**Task:** MCPP-078 · Goal `MCPP-G170` · Bundle `mcplusplus/1.0/docs-architecture`  
**Authority:** Sealed plan §4 rules 8–10, §11 non-claims; KD-4, KD-6, KD-11, KD-14, KD-15, KD-17; ADR-0002…0006  
**Document class:** **normative** for threat categories and fail-closed expectations; **not production-admitted** as a security certification by itself

| Section | Authority class |
| --- | --- |
| §1 Scope and method | reference |
| §2 Assets | **normative** inventory for MCP++ 1.0 |
| §3 Actors and trust domains | **normative** role model |
| §4 Threat catalog | **normative** (expected fail-closed outcomes) |
| §5 Bundle-oriented threat coverage | **normative** packaging view (KD-17) |
| §6 Conformance mapping | **normative** (ADR-0003) |
| §7 Residual risks and non-claims | **normative** honesty rules |
| §8 Evidence and validation | reference |
| §9 Security disclosure posture | **non-normative** process pointer |

This document names what MCP++ **must resist** and how claims are scored. It does
**not** assert that every runtime currently defeats every threat. Structural
suite green is not cryptographic defense.

---

## 1. Scope and method

### 1.1 In scope

- Portable contracts and carriers: profiles A–H, Envelope@1 family, StateRef@1,
  DurableExecutor@1, Event DAG provenance
- Cryptographic identity and delegation (Ed25519 / UCAN-style chains)
- Policy evaluation and obligation lifecycle
- Transport and federation (including optional `mcp+p2p`)
- Payment paths that must not elevate authorization
- Confidential CID-native artifact references
- Documentation honesty (over-claim is a security-adjacent failure mode)

### 1.2 Out of scope (unless a later ADR expands)

- Physical host security and datacenter perimeter controls
- Full OS kernel / hypervisor assurance
- Third-party LLM provider internal safety (treated as untrusted content source)
- Guaranteeing Byzantine fault tolerance for Profile G neighborhood agreement

### 1.3 Method

Threats are grouped by classic abuse categories (spoofing, tampering,
repudiation, information disclosure, denial of service, elevation of privilege)
plus MCP++-specific categories (authority confusion, payment elevation,
proof simulation, mode-merge confusion, durable replay).

Each threat lists:

| Field | Meaning |
| --- | --- |
| **ID** | Stable identifier |
| **Asset** | What is at risk |
| **Attacker goal** | What success looks like for the adversary |
| **Expected control** | Fail-closed or detective control in MCP++ design |
| **Evidence level** | Minimum ADR-0003 level that can claim the control holds |

---

## 2. Assets

| Asset | Examples | Why it matters |
| --- | --- | --- |
| **Capability tokens / proofs** | UCAN chains, `proof_cid`, key material | Forge or replay → unauthorized tool use |
| **Policy and decisions** | `policy_cid`, decision receipts, obligations | Stale or skipped policy → prohibited actions run |
| **Execution carriers** | Envelope, result, receipt, portable error | Tampered intent/output binding breaks audit and cross-trust trust |
| **Event DAG history** | Causal parents, event CIDs | Broken causality hides or invents history |
| **Durable journal** | Journal records, fencing tokens, idempotency keys | Replay of committed side effects after crash |
| **Shared state** | StateRef roots, leases, CRDT docs, consensus evidence | Silent merge / lost update / false consensus |
| **Confidential payloads** | Ciphertext CIDs, key envelopes | Plaintext leak via logs/DAG/cache (KD-15) |
| **Payment instruments** | x402 invoices, settlement proofs | Payment mistaken for authorization |
| **Transport identity** | PeerID, TLS client cert | Confused deputy if treated as UCAN authority |
| **Binding / version metadata** | Binding ids, `protocolVersion` | Downgrade or forgery against wrong lifecycle |
| **Evidence bundles / reports** | Demo verifier outputs, matrix rows | False “implemented” claims mislead operators |

---

## 3. Actors and trust domains

| Actor | Trust posture | Notes |
| --- | --- | --- |
| **End user / operator** | Partially trusted | May misconfigure; docs must not over-claim |
| **MCP host / client** | Untrusted relative to server policy | May send malformed envelopes |
| **MCP server / tool runtime** | Trust domain for local effects | Must enforce C/D before side effects |
| **Federated peer** | Untrusted until crypto/policy checks pass | PeerID ≠ capability |
| **Payment rail / merchant** | Separate economic trust | Settlement ≠ authz |
| **Adapter / workflow engine** | Trusted only for its declared contract | SQLite journal mandatory path; external engines optional under compose rules |
| **Verifier process** | Independent checker of evidence bundles | Gates 25–26 pattern |
| **Active network adversary** | Untrusted | May reorder, inject, or drop transport frames |
| **Compromised delegate** | Previously authorized, now hostile | Attenuation + revocation must bound blast radius |

### 3.1 Trust domains (summary)

```text
[ User / Host ] --MCP binding--> [ Local runtime adapter ]
                                      |  C/D evaluate
                                      |  Envelope validate
                                      v
                               [ DurableExecutor + StateProvider ]
                                      |  journal / CAS / CRDT
                                      v
                               [ CID store + Event DAG ]
        ^                                    |
        |         optional E/G mesh          |
        +--------[ Federated peers ]---------+
                       |
                 [ Payment H ]  (orthogonal to C/D)
```

Detail: [trust-boundaries.md](trust-boundaries.md).

---

## 4. Threat catalog

### 4.1 Spoofing and authority confusion

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-SPOOF-01 | PeerID / TLS client cert presented as UCAN capability | Execute tools without valid delegation | Transport identity never grants execution authority (KD-14) | `cryptographic` for cap checks; design rule always |
| T-SPOOF-02 | Forged issuer / missing `kid` / `alg: none` | Accept unsigned or wrong-key material | Mandatory suite verify; reject (ADR-0002) | `cryptographic` |
| T-SPOOF-03 | Binding / protocolVersion forgery or silent downgrade | Force legacy initialize path against current-only peer | Named binding ids; fail closed (ADR-0006) | `structural`+ binding tests; higher when signed ads apply |
| T-SPOOF-04 | Reverse-DNS-only A2A extension id on the wire | Break interop or spoof extension activation | URI extension id only (KD-13 / MCPP-010) | binding/A2A tests |

### 4.2 Tampering

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-TAMP-01 | Mutate envelope fields after CID mint | Change intent while keeping old identity | Content addressing + canonical bytes; signature over canonical input | `canonical` / `cryptographic` |
| T-TAMP-02 | Strip or rewrite Event DAG parents | Hide causal history | Parents required; reconstruct from DAG | `structural` min; audit relies on F |
| T-TAMP-03 | Journal rewrite / fork without fence | Double-apply side effects | Append-only journal + fencing tokens | durable adapter tests (gate 17) |
| T-TAMP-04 | Silent StateRef mode merge across Event DAG branches | Invent total order for `single_authority` values | Exactly one mode; non-merge rule (KD-8) | state provider + non-merge tests |

### 4.3 Repudiation and audit gaps

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-REP-01 | Unsigned cross-trust receipt | Deny execution outcome | Receipt-signed finalize for cross-trust (gate 15) | `receipt-signed` |
| T-REP-02 | Missing decision / obligation records | Deny policy was evaluated | Policy-enforced path emits decisions; obligations lifecycle | `policy-enforced` |
| T-REP-03 | Documentation over-claim as substitute for evidence | Operator believes gates closed | Matrix + report cite commands; forbidden phrases | process / G170 |

### 4.4 Information disclosure

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-DISC-01 | Plaintext confidential artifact in logs, DAG metadata, or fallback cache | Exfiltrate protected content | Encrypted refs only; no plaintext in those channels (KD-15) | confidential-artifact tests (gate 22) |
| T-DISC-02 | Capability tokens in error messages or evidence dumps | Steal delegation | Redact secrets; CID references preferred | crypto/runtime hygiene tests |
| T-DISC-03 | Over-broad toolset exposure | Enumerate high-risk tools | IDL toolset slicing / least privilege | A + C composition |

### 4.5 Denial of service and resource abuse

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-DOS-01 | P2P framing abuse / flood | Exhaust peer resources | Profile E abuse and framing tests (gate 21) | transport tests |
| T-DOS-02 | Unbounded durable timers / retries | Starve executor | Journaled policy limits; cancel fail-closed | durable adapter |
| T-DOS-03 | Oversized non-canonical payloads | Exhaust CPU on canonicalize | Size limits at structural layer; canonical negatives | `structural` / `canonical` |

### 4.6 Elevation of privilege

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-EOP-01 | Payment settlement treated as authorization | Buy a capability without UCAN/policy allow | Payment ≠ authorization (KD-14, gate 23) | Commerce negatives |
| T-EOP-02 | Attenuation bypass / ambient authority | Use broader powers than delegated | Verify chain + attenuations; fail closed on widen | `cryptographic` |
| T-EOP-03 | Stale lease / fencing token resume | Steal exclusive task after failover | Reject stale fences (gates 17–18) | durable + Profile G fencing |
| T-EOP-04 | Revoked capability still accepted | Act after revocation | Revocation checks on verify path | `cryptographic` + policy where timed |

### 4.7 Proof simulation and Verified Execution abuse

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-PRF-01 | Simulated proof-shaped JSON claimed as verified | Fake Verified Execution bundle | Real verifier only; simulated paths not `proof-verified` (plan §11) | `proof-verified` |
| T-PRF-02 | Signature **presence** scored as signed receipt | Skip independent verify | Presence is structural; verify required for `receipt-signed` | `receipt-signed` |
| T-PRF-03 | Compaction flag claiming hidden proof without verifier | Market false privacy/proof strength | Compaction claims require real verifiable proofs when so labeled | `proof-verified` |

### 4.8 Durable replay and compensation

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-DUR-01 | Crash → restart re-dispatches committed side effect | Double charge / double write | Idempotency keys + journal commit authority | gate 17 |
| T-DUR-02 | Cancel lost across restart | Continue after user cancel | Cancel durable in journal | durable + policy obligations |
| T-DUR-03 | In-memory retry labeled crash recovery | False durability claims | Explicit non-claim (ADR-0005) | docs + tests |

### 4.9 Consensus and federation mislabeling

| ID | Threat | Attacker goal | Expected control | Evidence level |
| --- | --- | --- | --- | --- |
| T-FED-01 | Profile G neighborhood majority labeled BFT | Oversell safety | Honest labels only; G ≠ `bft` (KD-11) | consensus label tests |
| T-FED-02 | Stale fenced completion accepted | Two exclusive winners | Reject stale fenced completion (gate 18) | three-peer / G tests |

---

## 5. Bundle-oriented threat coverage

Profile bundles (KD-17) group mitigations for packaging. A bundle claim without
tests at the required levels remains **not production-admitted**.

### 5.1 Evidence Core (A, B, F)

| Focus threats | Primary mitigations |
| --- | --- |
| T-TAMP-01, T-TAMP-02, T-REP-01 (local audit), T-DISC-03 | IDL contracts; CID-native envelopes; Event DAG parents; Envelope@1 lineage |

### 5.2 Secure Delegation (C, D)

| Focus threats | Primary mitigations |
| --- | --- |
| T-SPOOF-01/02, T-EOP-02/04, T-REP-02 | UCAN verify + attenuation; temporal deontic evaluation; revocation |

### 5.3 Federated Mesh (E, G)

| Focus threats | Primary mitigations |
| --- | --- |
| T-DOS-01, T-FED-01/02, T-SPOOF-01 on the wire | Framing/abuse tests; honest guarantee labels; fencing; transport ≠ authz |

### 5.4 Commerce (H)

| Focus threats | Primary mitigations |
| --- | --- |
| T-EOP-01 | Settlement paths with explicit non-authorization; C/D still required for execution |

### 5.5 Verified Execution (signed receipts / attestations / verified proofs only)

| Focus threats | Primary mitigations |
| --- | --- |
| T-PRF-01/02/03, T-REP-01 | Independent receipt verify; real proof verifiers; no simulation leap |

---

## 6. Conformance mapping

| If you claim… | You must evidence at least… | Threat families covered |
| --- | --- | --- |
| Shape-valid profiles | `structural` | Malformed objects only |
| Cross-language CID identity | `canonical` | T-TAMP-01 (bytes) |
| Delegation security | `cryptographic` | T-SPOOF-02, T-EOP-02/04 |
| Policy actually runs | `policy-enforced` | T-REP-02, timed prohibitions |
| Cross-trust outcome binding | `receipt-signed` | T-REP-01, T-PRF-02 |
| Proof objects verified | `proof-verified` | T-PRF-01/03 |

Schema acceptance alone never closes Secure Delegation, Commerce payment≠auth,
or Verified Execution claims.

---

## 7. Residual risks and non-claims

| Residual risk | Disposition |
| --- | --- |
| Host compromise with signing keys | Outside MCP++ wire model; operators must protect keys |
| Honest-majority assumption for G neighborhoods | Documented; not BFT |
| Optional external durable engines without local compose | Not admitted for mandatory gate 17 claims |
| LLM-generated tool arguments | Treated as untrusted input; still subject to C/D |
| Incomplete forest-wide crypto while local kit crypto exists | Local ≠ forest promotion (ADR-0003) |

**This threat model does not claim:**

- That deployments have an empty residual risk surface
- That any tree meets every conformance level in ADR-0003
- That simulated proofs satisfy Verified Execution
- That documentation alone is production admission

G170 documentation policy forbids over-claim language that asserts unproven
deployment fitness, empty residual risk, universal conformance, or unverified
proof strength. Prefer conformance level identifiers and named evidence
commands.

---

## 8. Evidence and validation

| Check | Command / artifact |
| --- | --- |
| This document present | `test -s ipfs_accelerate_py/mcplusplus/docs/architecture/threat-model.md` |
| Conformance ladder | [decisions/0003-conformance-levels.md](decisions/0003-conformance-levels.md) |
| Traceability matrix | [../roadmap/mcplusplus-1.0-gap-closure.md](../roadmap/mcplusplus-1.0-gap-closure.md) |
| Trust boundaries | [trust-boundaries.md](trust-boundaries.md) |
| Crypto suite | [decisions/0002-crypto-canonical.md](decisions/0002-crypto-canonical.md) |

Gate closure requires the plan’s numbered gates (especially 13–18, 21–24, 26–28)
with current-tree commands—not this prose alone.

---

## 9. Security disclosure posture

**Authority class: non-normative.**

Operators and implementers **SHOULD**:

1. Prefer private coordinated disclosure for exploitable authz/crypto defects.
2. Include reproduction commands, affected profile bundle claims, and
   conformance level impact.
3. Update matrix rows downward if higher-level tests fail after a fix attempt
   (ADR-0003 downgrade honesty).
4. Never “fix” failed crypto tests by rewriting docs to claim success.

A formal public disclosure URL, if published later, belongs in the
implementation report release checklist—not invented here without evidence.

---

## 10. Checklist (`ThreatModel@1`)

1. Assets, actors, and trust domains named.
2. Threat catalog covers spoofing, tampering, repudiation, disclosure, DoS,
   elevation, proof simulation, durable replay, and federation mislabeling.
3. Profile bundles Evidence Core, Secure Delegation, Federated Mesh, Commerce,
   and Verified Execution each map to focus threats.
4. Conformance levels gate what “mitigated” means.
5. Residual risks and non-claims explicit; no forbidden over-claim phrases.
6. Validation points to commands and linked ADRs/specs.
