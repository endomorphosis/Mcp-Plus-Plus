# Profile F Groth16 Multi-Party Ceremony

**Status:** Draft

This optional Profile F extension defines the public transcript required before
a Groth16 verification key may certify an Event DAG compaction proof. It uses
the manifest schema identifier `mcp++/groth16-mpc-ceremony@1` and remains
negotiated under the Profile F capability `mcp++/event-dag`.

## Scope

The ceremony records public artifact hashes, contributor DIDs, signed
attestations, and cryptographic transcript-verification evidence. It does not
carry witness data, proving keys, toxic waste, or a contributor's entropy.
Those values MUST NOT be transmitted through MCP, MCP+p2p, HTTP parameters,
environment variables, logs, or the ceremony manifest.

The profile name is **"Profile F: Event DAG Provenance, Archival, and
Compaction"**. A manifest MUST include that name and the capability key so a
peer can bind a compaction verification key to the profile that uses it.

## Manifest Contract

A manifest MUST contain:

- `schema`: `mcp++/groth16-mpc-ceremony@1`.
- `profile`: `{capability: "mcp++/event-dag", name: "Profile F: Event DAG Provenance, Archival, and Compaction"}`.
- `ceremonyId`, `circuitId`, and curve `bn128`.
- optional `keyFormat`: `snarkjs-zkey` or `arkworks-canonical`. New
  manifests SHOULD declare it; an implementation-specific admission gate MUST
  reject an unknown format.
- content-addressed `circuitR1cs`, `phase1Powers`, and `initialZkey` artifacts.
- a `minimumIndependentContributors` value of at least two.
- ordered contributions with a participant DID, input and output SHA-256
  values, signed attestation, declared verifier, and verification timestamp.
- for a complete ceremony, `finalZkey`, `verificationKey`, and `finalizedAt`.
  An `arkworks-canonical` admission manifest MUST additionally include a
  content-addressed `provingKey` artifact whose hash equals `finalZkey`.

Artifact CIDs use the portable `sha256:<hex>` form in version 1. Every
artifact CID MUST equal its recorded SHA-256 value. Contribution one MUST use
the `initialZkey` hash as its input; each subsequent contribution MUST use the
prior output hash. The final zkey MUST equal the final contribution output. In
an `arkworks-canonical` manifest, the legacy `finalZkey` field identifies the
terminal public transcript artifact and MUST have the same hash as `provingKey`.

The manifest CID is the SHA-256 of recursively key-sorted JSON encoded without
whitespace. It is an integrity reference for the public transcript and may be
persisted through IPFS.

## Ceremony Procedure

1. A coordinator publishes the circuit R1CS and Phase 1 powers artifact
   hashes in a `collecting` manifest.
2. The coordinator derives an initial zero-contribution zkey.
3. Each contributor independently obtains the current zkey, enters fresh
   entropy locally into the ceremony tool, and publishes the resulting zkey
   plus a DID-signed attestation.
4. A verifier cryptographically checks the complete contribution chain after
   every update. `snarkjs zkey verify` is the declared verifier for the
   SwissKnife reference workflow.
5. After the independent-contributor quorum is reached, the final zkey is
   verified again and its verification key is exported. Only then may the
   manifest be marked `complete`.

An implementation MUST reject a completed manifest that has no initial zkey,
broken artifact chain, mismatched CID/hash pair, missing attestation, missing
verification evidence, or insufficient independent contributor DIDs.

## Production Admission

`productionEligible` is true only when the manifest is complete, structurally
valid, cryptographically verified with its declared transcript verifier, and
meets its independent-contributor quorum. A deterministic seed, a collection
of seeds observed by one coordinator, a Merkle root, or a signature alone is
not a multi-party ceremony.

The current `ipfs_datasets_py` Arkworks setup backend generates parameters from
a single RNG. It MUST NOT claim that its generated keys satisfy this protocol.
When `IPFS_DATASETS_REQUIRE_MPC_CEREMONY=1`, it admits an externally generated
Arkworks key only when the manifest declares `keyFormat: "arkworks-canonical"`,
every contribution records `arkworks-mpc-verifier`, the versioned circuit ID
matches, and the manifest proving-key and verification-key hashes match the
actual local files consumed by the backend. The bundled setup command and committed seed-based artifacts remain
development-only. The external verifier is responsible for authenticating the
declared Arkworks transcript evidence; the admission gate binds that evidence
to the local key and does not manufacture an MPC proof.

## Transport

The read-only JSON-RPC method `mcp++/zk/ceremony/validate` accepts
`{manifest: <public manifest>}` and returns validation status, reasons,
contributor DIDs, and the deterministic manifest CID. The method is safe to
carry over HTTP and MCP+p2p because it neither accepts nor returns secret
ceremony material. A Profile E implementation MUST explicitly bind this method
to its libp2p JSON-RPC dispatcher before advertising it as live over MCP+p2p.
Implementations MUST perform local ceremony contribution operations; remote
peers are validators and archive providers, not entropy custodians.

## Fixture

The conformance fixture is
[`profile_f_groth16_mpc_ceremony.json`](../../tests-py/fixtures/valid/profile_f_groth16_mpc_ceremony.json).
SwissKnife and `ipfs_datasets_py` validators MUST accept it and MUST reject its
broken-chain and mismatched-CID mutations.
