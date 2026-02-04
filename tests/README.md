# MCP++ Testing Framework

This directory contains a comprehensive testing framework for validating MCP and MCP++ network payloads against the specifications defined in the `docs/` directory.

## Directory Structure

```
tests/
├── README.md                    # This file
├── validators/                  # Payload validators
│   ├── __init__.py
│   ├── base_mcp.py             # Base MCP protocol validators
│   ├── mcp_idl.py              # MCP-IDL profile validators
│   ├── cid_artifacts.py        # CID-native execution validators
│   ├── ucan_delegation.py      # UCAN capability delegation validators
│   ├── policy_evaluation.py    # Temporal deontic policy validators
│   └── event_dag.py            # Event DAG validators
├── fixtures/                    # Test data and examples
│   ├── valid/                  # Valid payloads
│   ├── invalid/                # Invalid payloads for negative testing
│   └── examples/               # Example payloads from specs
├── integration/                 # Integration tests
│   ├── test_mcp_baseline.py   # Base MCP protocol tests
│   ├── test_mcp_idl.py        # MCP-IDL profile tests
│   ├── test_cid_envelopes.py  # CID envelope tests
│   └── test_full_workflow.py  # End-to-end workflow tests
└── requirements.txt            # Test dependencies
```

## Quick Start

### Installation

```bash
# Install test dependencies
pip install -r tests/requirements.txt
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific validator tests
pytest tests/integration/test_mcp_baseline.py

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=tests --cov-report=html tests/
```

## Test Categories

### 1. Base MCP Protocol Validation

Tests baseline MCP JSON-RPC messages according to the official MCP specification.

**Validator**: `validators/base_mcp.py`  
**Tests**: `integration/test_mcp_baseline.py`

### 2. MCP-IDL Profile (Profile A)

Tests CID-addressed interface contracts as defined in `docs/spec/mcp-idl.md`.

**Validator**: `validators/mcp_idl.py`  
**Tests**: `integration/test_mcp_idl.py`  
**Spec**: `docs/spec/mcp-idl.md`

### 3. CID-Native Execution Artifacts (Profile B)

Tests execution envelopes and receipts as defined in `docs/spec/cid-native-artifacts.md`.

**Validator**: `validators/cid_artifacts.py`  
**Tests**: `integration/test_cid_envelopes.py`  
**Spec**: `docs/spec/cid-native-artifacts.md`

### 4. Capability Delegation (Profile C)

Tests UCAN-based delegation chains as defined in `docs/spec/ucan-delegation.md`.

**Validator**: `validators/ucan_delegation.py`  
**Spec**: `docs/spec/ucan-delegation.md`

### 5. Temporal Deontic Policy (Profile D)

Tests policy evaluation as defined in `docs/spec/temporal-deontic-policy.md`.

**Validator**: `validators/policy_evaluation.py`  
**Spec**: `docs/spec/temporal-deontic-policy.md`

### 6. Event DAG and Ordering

Tests event provenance as defined in `docs/spec/event-dag-ordering.md`.

**Validator**: `validators/event_dag.py`  
**Spec**: `docs/spec/event-dag-ordering.md`

## Contributing

When adding new specs or profiles, create corresponding validators, tests, and fixtures.
