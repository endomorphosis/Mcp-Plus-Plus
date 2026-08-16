# MCP++

MCP++ is a documentation-first project defining **optional, backward-compatible execution profiles** for the Model Context Protocol (MCP).

The goal is to support federated, multi-agent, and parallel execution environments with:

- CID-native (content-addressed) interface contracts and execution envelopes
- Immutable event DAG provenance for audit/replay
- Capability delegation chains and policy-aware execution
- Optional P2P transport bindings

## Documentation

### MCP++ specification

Start here: [docs/index.md](docs/index.md)

### Implementation guides

- [Getting Started](GETTING_STARTED.md) — quick start for a first MCP++-aware implementation
- [Architecture](docs/ARCHITECTURE.md) — design and components
- [Architecture overview (gap-closure)](docs/architecture/overview.md) — layers, bundles, honesty rules
- [API Reference](docs/API_REFERENCE.md) — API surface documentation
- [Best Practices](docs/BEST_PRACTICES.md) — implementation patterns (guidance only; not a production admission)
- [Security](SECURITY.md) — security guidelines

### Testing and coverage (current)

**Authoritative testing status:** [docs/testing/README.md](docs/testing/README.md)

Measured suite outcomes and statement coverage come from recomputed baseline receipts (gap-closure program), not from historical “100% / complete / production-ready” narrative docs under `docs/testing/`.

| Language | Declared gate | Result (baseline) | Coverage (measured) |
| --- | --- | --- | --- |
| Python | `python -m pytest -q tests-py --maxfail=1` | 323 passed | ~96.1% statements (`tests-py/validators`) |
| TypeScript | `npm test` (Vitest) | 223 passed, 19 skipped; one disabled suite not treated as pass | ~98.1% statements (supplemental `npm run test:coverage`) |
| Go | `go test ./...` | 211 passed | ~96.9% statements overall; validators package ~97.6% |
| Rust | `cargo test` | 191 passed | **unavailable** in baseline (coverage tooling not installed); historical 100% markdown is stale only |

Evidence paths (operator forest):

- `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-python.json`
- `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-typescript.json`
- `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-go.json`
- `docs/reports/mcplusplus-1.0-gap-closure/baseline/mcpplusplus-rust.json`
- Traceability: [docs/roadmap/mcplusplus-1.0-gap-closure.md](docs/roadmap/mcplusplus-1.0-gap-closure.md)

### Explicit non-claims

This repository does **not** claim:

- **100% code coverage** for any language (current measured values are below 100%, and Rust coverage was not measured in the baseline)
- **Production readiness** or production admission of Profiles A–H
- That green structural validator suites equal cryptographic, policy-enforced, receipt-signed, or proof-verified conformance

Line coverage of structural validators is not cryptographic or production evidence. See inventory §10 and the testing README for the list of historical trophy documents retained only as non-authoritative history.

## Quick overview

### Core MCP primitives

1. **Resources**: file-like data (API responses, file contents) consumable by clients
2. **Tools**: functions that LLMs can call to perform actions (with permission)
3. **Prompts**: pre-written templates for repeated tasks or structured workflows

### MCP++ extensions

MCP++ adds optional profiles for:

- Content-addressed interface contracts (MCP-IDL)
- Immutable execution envelopes and receipts
- Capability delegation chains (UCAN)
- Temporal deontic policy evaluation
- Event DAG provenance and ordering
- P2P transport bindings

See the [specification docs](docs/index.md) for details.

## Contributing

Contributions are welcome. See [Contributing Guidelines](CONTRIBUTING.md).

## License

This project is licensed under the MIT License — see the LICENSE file for details.
