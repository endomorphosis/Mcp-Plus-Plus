# Agent Start Here

This repository is currently **documentation-first**: it contains the MCP++ concept + draft spec, and is intended to become the foundation for an implementation.

## Mission

MCP++ defines **optional, backward-compatible execution profiles** for MCP (Model Context Protocol) to better support:

- Federated / multi-agent execution
- Parallelism with provenance and replayability
- Capability-based delegation and policy evaluation
- (Optional) P2P transport bindings

## Where to read first

1. [Project Overview](../architecture/overview.md)
2. [MCP++ Profiles Draft](../spec/mcp++-profiles-draft.md)

## How to contribute effectively (agent checklist)

When you’re asked to make changes, aim to:

- Keep docs **incrementally adoptable**: optional profiles, clear negotiation story, no breaking core MCP JSON-RPC semantics.
- Separate **normative** vs **non-normative** content explicitly.
- Prefer **small, linked docs** over one mega-file.
- If you introduce a new term, add it to [Glossary](../architecture/glossary.md).

## Current gaps (good next tasks)

- Clarify the profile negotiation story (what capabilities are announced, where).
- Define canonicalization rules for CID-bearing objects (JSON canonicalization, field ordering, etc.).
- Add concrete envelope examples (request/receipt) and validation steps.
- Add a threat model and non-goals.

## Source artifacts

A raw ChatGPT export exists in [docs/_archive/chatgpt.html](../_archive/chatgpt.html). It is **not canonical**; treat it as historical notes.

For completeness/alias validation, use: [docs/architecture/traceability.md](../architecture/traceability.md)
