# Glossary

- **CID**: Content Identifier; a hash-addressed identifier for canonicalized content.
- **Profile**: Optional, negotiated capability that adds semantics without changing core MCP messages.
- **Interface Descriptor**: A canonical, CID-addressed contract describing a tool/resource interface.
- **Execution Envelope**: A wrapper around an invocation referencing interface/input/intent/policy/proofs via CIDs.
- **Event DAG**: A content-addressed DAG of execution events linked by causal references.
- **Policy CID**: A content-addressed representation of policy (permissions/prohibitions/obligations + time constraints).
- **Intent CID**: A content-addressed description of a proposed action (tool/interface + input + declared side effects).
- **Decision CID**: A content-addressed outcome of policy evaluation (allow/deny/obligations + justification).
- **Receipt CID**: A content-addressed execution attestation that binds intent, output, and decision.
- **Proof CID**: A content-addressed proof bundle (e.g., a UCAN delegation chain).
- **Receipt**: A content-addressed record of execution outcome; may be signed.
- **Delegation Chain**: A verifiable chain of authority granting capabilities (e.g., UCAN-style).
- **Fibonacci Heap**: A priority-queue data structure sometimes used to optimize many priority updates (`decrease-key`). (Alias: “fibinocci heap” in the original chat export.)
- **Merkle Clock**: A Merkle-DAG-derived logical clock for establishing partial order / causality between events.
