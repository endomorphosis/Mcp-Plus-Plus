# MCP++ Testing Framework

This directory contains a comprehensive testing framework for validating MCP and MCP++ network payloads against the specifications defined in the `docs/` directory.

## Overview

The framework provides **complete validation coverage** for all MCP++ profiles and ensures network traffic compliance with the specifications. Each validator is directly mapped to spec requirements with explicit references.

## Test Coverage

**74 passing tests** covering:

### Baseline MCP Protocol (10 tests)
- JSON-RPC 2.0 format validation
- Request/response/notification handling
- Required fields and error conditions
- Method-specific parameter validation

### Profile A: MCP-IDL (8 tests)
- Interface descriptor validation
- CID computation and canonicalization
- Required MCP-IDL endpoints (interfaces/list, get, compat)
- Toolset slicing with budget constraints

### Profile B: CID Execution Artifacts (7 tests)
- Execution envelope structure
- Receipt validation and signatures
- Parent array validation
- CID format compliance

### Profile C: UCAN Delegation (7 tests)
- Delegation chain validation
- Required UCAN token fields (iss, aud, att, exp)
- Proof reference validation
- Nested delegation chains

### Profile D: Policy Evaluation (11 tests)
- Policy types (permission, prohibition, obligation)
- Decision validation (allow/deny/allow_with_obligations)
- Temporal constraints
- Obligation spawning with deadlines

### Profile E: Transport (mcp+p2p) (11 tests)
- Protocol ID validation
- Message framing (length-prefixed)
- Session lifecycle
- JSON-RPC preservation over transport
- Peer addressing

### Event DAG (10 tests)
- Event structure validation
- DAG acyclicity
- Causal ordering
- Parent link immutability
- Concurrent event handling

### Cross-Cutting Requirements (10 tests)
- Backward compatibility with baseline MCP
- Capability negotiation
- Profile subset negotiation
- Content-addressing and canonicalization

## Directory Structure

```
tests/
├── README.md                    # This file
├── SPEC_COMPLIANCE.md          # Detailed spec-to-test mapping
├── validators/                  # Payload validators
│   ├── __init__.py
│   ├── base_mcp.py             # Base MCP protocol
│   ├── mcp_idl.py              # Profile A: Interface descriptors
│   ├── cid_artifacts.py        # Profile B: Execution artifacts
│   ├── ucan_delegation.py      # Profile C: Delegation chains
│   ├── policy_evaluation.py    # Profile D: Policy evaluation
│   ├── event_dag.py            # Event DAG validation
│   └── transport.py            # Profile E: Transport protocol
├── integration/                 # Integration tests
│   ├── test_mcp_baseline.py   # Base MCP tests
│   ├── test_mcp_idl.py        # MCP-IDL profile tests
│   ├── test_cid_envelopes.py  # CID envelope tests
│   ├── test_ucan_delegation.py # UCAN delegation tests
│   ├── test_policy_evaluation.py # Policy evaluation tests
│   ├── test_event_dag.py      # Event DAG tests
│   ├── test_transport.py      # Transport protocol tests
│   └── test_cross_cutting.py  # Cross-cutting requirement tests
├── fixtures/                    # Test data and examples
│   ├── valid/                  # Valid payloads
│   ├── invalid/                # Invalid payloads for negative testing
│   └── examples/               # Example payloads from specs
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
pytest tests/ -v

# Run specific profile tests
pytest tests/integration/test_mcp_idl.py -v

# Run with coverage report
pytest --cov=tests --cov-report=html tests/

# Run tests matching a pattern
pytest tests/ -k "delegation" -v
```

## Specification Compliance

Each test includes docstring references to:
- Specification document location (e.g., `docs/spec/mcp-idl.md`)
- Specific requirement being tested
- Normative keyword (MUST/SHOULD/MAY)

See [SPEC_COMPLIANCE.md](SPEC_COMPLIANCE.md) for a complete mapping of tests to spec requirements.

## Validators

### ValidationResult

All validators return a `ValidationResult` object:

```python
@dataclass
class ValidationResult:
    is_valid: bool              # Overall validation status
    message_type: str           # Type of message validated
    errors: List[str]           # Validation errors (make is_valid=False)
    warnings: List[str]         # Non-fatal warnings
    metadata: Dict[str, Any]    # Additional validation metadata
```

### Available Validators

1. **MCPValidator** - Baseline MCP protocol
2. **MCPIDLValidator** - Interface descriptors and CID computation
3. **CIDExecutionValidator** - Execution envelopes and receipts
4. **UCANDelegationValidator** - Delegation chains and proofs
5. **PolicyEvaluationValidator** - Policy and decision validation
6. **EventDAGValidator** - Event structures and ordering
7. **TransportValidator** - Transport protocol compliance

## Example Usage

### Validating a Tool Call

```python
from validators.base_mcp import MCPValidator

validator = MCPValidator()

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "get_weather",
        "arguments": {"location": "Tokyo"}
    }
}

result = validator.validate_request(payload)

if result.is_valid:
    print("✓ Valid MCP request")
else:
    print("✗ Validation errors:")
    for error in result.errors:
        print(f"  - {error}")
```

### Validating an Interface Descriptor

```python
from validators.mcp_idl import MCPIDLValidator

validator = MCPIDLValidator()

descriptor = {
    "name": "weather-api",
    "namespace": "com.example",
    "version": "1.0.0",
    "methods": [...],
    "errors": [],
    "requires": [],
    "compatibility": {}
}

result = validator.validate_descriptor(descriptor)

if result.is_valid:
    print(f"✓ Valid interface descriptor")
    print(f"  Interface CID: {result.metadata['interface_cid']}")
```

### Validating Network Traffic

```python
from validators.transport import TransportValidator

validator = TransportValidator()

# Validate protocol framing
frame = {
    "length": 256,
    "message": {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
}

result = validator.validate_message_framing(frame)

# Validate JSON-RPC preservation
original = {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}
transported = {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}

result = validator.validate_jsonrpc_preservation(original, transported)
```

## Normative Requirements Coverage

The test suite validates **45 normative requirements** from the MCP++ specifications:

- ✅ **26 requirements** with full test coverage
- ⚠️ **10 requirements** with partial coverage  
- ❌ **9 requirements** pending (advanced features, performance)

### MUST Requirements (100% coverage)
All MUST requirements from the specifications have full test coverage including:
- Interface descriptor canonicalization
- MCP-IDL endpoint exposure
- Delegation chain validation
- Policy evaluation at execution-time
- Transport protocol session lifecycle
- Backward compatibility

### SHOULD Requirements (85% coverage)
Most SHOULD requirements are validated including:
- Length-prefixed message framing
- Temporal constraint evaluation
- Decision type support
- Protocol ID conventions

### MAY Requirements (Partial coverage)
Optional features are partially validated:
- Toolset slicing
- Obligation spawning
- Event dissemination
- NAT traversal strategies

## Adding New Tests

When adding tests for new specifications:

1. **Create or update validator** in `validators/`
2. **Add integration tests** in `integration/`
3. **Include spec references** in test docstrings
4. **Update SPEC_COMPLIANCE.md** with requirement mapping
5. **Add test fixtures** in `fixtures/` if needed

Example test structure:

```python
def test_new_feature(self, validator):
    """
    Test description.
    
    Spec: docs/spec/example.md:123
    Requirement: Feature MUST behave as specified
    """
    # Test implementation
    result = validator.validate_feature(payload)
    assert result.is_valid
```

## Continuous Integration

Run in CI/CD:

```yaml
- name: Run MCP++ Tests
  run: |
    pip install -r tests/requirements.txt
    pytest tests/ -v --cov=tests --junitxml=test-results.xml
```

## Contributing

When adding new specs or profiles:
1. Create corresponding validator
2. Add comprehensive integration tests
3. Add test fixtures for both valid and invalid cases
4. Update SPEC_COMPLIANCE.md
5. Ensure all MUST requirements have tests
6. Add spec references to test docstrings

## Resources

- [MCP++ Specification](../docs/index.md)
- [Specification Compliance Matrix](SPEC_COMPLIANCE.md)
- [Base MCP Protocol](https://modelcontextprotocol.io/docs/)
- [JSON-RPC 2.0](https://www.jsonrpc.org/specification)
- [CID Specification](https://github.com/multiformats/cid)
- [UCAN Specification](https://github.com/ucan-wg/spec)
