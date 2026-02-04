# MCP++

MCP++ is a documentation-first project defining **optional, backward-compatible execution profiles** for the Model Context Protocol (MCP).

The goal is to support federated, multi-agent, and parallel execution environments with:

- CID-native (content-addressed) interface contracts and execution envelopes
- Immutable event DAG provenance for audit/replay
- Capability delegation chains and policy-aware execution
- Optional P2P transport bindings

## 📚 Documentation

### MCP++ Specification
Start here: [docs/index.md](docs/index.md)

### MCP Implementation Guide
For practical MCP implementation with examples and tutorials:
- [Getting Started](GETTING_STARTED.md) - Quick start guide for your first MCP implementation
- [Architecture](ARCHITECTURE.md) - Deep dive into MCP's design and components
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Best Practices](BEST_PRACTICES.md) - Production-ready implementation patterns
- [Security](SECURITY.md) - Security guidelines and best practices
- [Examples](examples/) - Sample implementations and use cases

## 🎯 Quick Overview

### Core MCP Primitives

1. **Resources**: File-like data (API responses, file contents) consumable by clients
2. **Tools**: Functions that LLMs can call to perform actions (with permission)
3. **Prompts**: Pre-written templates for repeated tasks or structured workflows

### MCP++ Extensions

MCP++ adds optional profiles for:
- Content-addressed interface contracts (MCP-IDL)
- Immutable execution envelopes and receipts
- Capability delegation chains (UCAN)
- Temporal deontic policy evaluation
- Event DAG provenance and ordering
- P2P transport bindings

See the [specification docs](docs/index.md) for complete details.

## 🤝 Contributing

We welcome contributions! See our [Contributing Guidelines](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

