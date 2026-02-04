# MCP++ Validators - Rust Implementation

Strongly-typed Rust validators for all MCP and MCP++ protocol profiles. Provides compile-time and runtime type safety using Rust's type system and serde validation.

## Features

- **🦀 Strong Static Typing**: Rust's type system catches errors at compile time
- **✅ Runtime Validation**: `serde_valid` provides declarative validation rules
- **⚡ Zero-Cost Abstractions**: No runtime overhead for type safety
- **🔒 Memory Safety**: Guaranteed by Rust's ownership system
- **📦 Comprehensive**: All 7 MCP++ profiles supported

## Validators

| Validator | Profile | Description |
|-----------|---------|-------------|
| `MCPValidator` | Base MCP | JSON-RPC 2.0, tools, resources, prompts |
| `MCPIDLValidator` | Profile A | Interface descriptors, CID computation |
| `CIDArtifactsValidator` | Profile B | Execution envelopes, receipts |
| `UCANDelegationValidator` | Profile C | UCAN tokens, delegation chains |
| `PolicyEvaluationValidator` | Profile D | Policy definitions, decisions |
| `TransportValidator` | Profile E | mcp+p2p protocol framing |
| `EventDAGValidator` | Event DAG | Event structures, acyclicity |

## Quick Start

### Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
mcp-validators = { path = "../tests-rs" }
serde_json = "1.0"
```

### Basic Usage

```rust
use mcp_validators::validators::MCPValidator;
use serde_json::json;

fn main() {
    let validator = MCPValidator::new();
    
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    });
    
    match validator.validate_request(&payload) {
        Ok(result) => {
            if result.is_valid {
                println!("✅ Valid MCP request!");
            } else {
                println!("❌ Errors: {:?}", result.errors);
            }
        }
        Err(e) => eprintln!("Validation error: {}", e),
    }
}
```

## Examples

### Base MCP Protocol

```rust
use mcp_validators::validators::MCPValidator;
use serde_json::json;

let validator = MCPValidator::new();

// Validate request
let request = json!({
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "get_weather",
        "arguments": {"location": "San Francisco"}
    },
    "id": 1
});

let result = validator.validate_request(&request)?;
assert!(result.is_valid);

// Validate response
let response = json!({
    "jsonrpc": "2.0",
    "result": {"temperature": 72},
    "id": 1
});

let result = validator.validate_response(&response)?;
assert!(result.is_valid);
```

### MCP-IDL (Profile A)

```rust
use mcp_validators::validators::MCPIDLValidator;
use serde_json::json;

let validator = MCPIDLValidator::new();

let descriptor = json!({
    "name": "weather-api",
    "version": "1.0.0",
    "tools": [{
        "name": "get_weather",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            }
        }
    }],
    "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
});

let result = validator.validate_interface_descriptor(&descriptor)?;
assert!(result.is_valid);
```

### CID Artifacts (Profile B)

```rust
use mcp_validators::validators::CIDArtifactsValidator;
use serde_json::json;

let validator = CIDArtifactsValidator::new();

let envelope = json!({
    "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
    "input_cid": "QmZwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
    "parents": ["QmPreviousEvent"],
    "timestamp": "2024-01-01T00:00:00Z"
});

let result = validator.validate_envelope(&envelope)?;
assert!(result.is_valid);
```

### UCAN Delegation (Profile C)

```rust
use mcp_validators::validators::UCANDelegationValidator;
use serde_json::json;

let validator = UCANDelegationValidator::new();

let token = json!({
    "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
    "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
    "att": [{
        "resource": "mcp://tools/*",
        "ability": "execute"
    }],
    "exp": 1735689600
});

let result = validator.validate_ucan_token(&token)?;
assert!(result.is_valid);
```

### Policy Evaluation (Profile D)

```rust
use mcp_validators::validators::PolicyEvaluationValidator;
use serde_json::json;

let validator = PolicyEvaluationValidator::new();

let policy = json!({
    "policy_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
    "policy_type": "permission",
    "rules": [{
        "condition": "time_before('2024-12-31')",
        "action": "allow"
    }]
});

let result = validator.validate_policy(&policy)?;
assert!(result.is_valid);
```

### Transport Protocol (Profile E)

```rust
use mcp_validators::validators::TransportValidator;
use serde_json::json;

let validator = TransportValidator::new();

let message = json!({
    "protocol_id": "/mcp+p2p/1.0.0",
    "length": 256,
    "payload": {
        "jsonrpc": "2.0",
        "method": "test",
        "id": 1
    }
});

let result = validator.validate_transport_message(&message)?;
assert!(result.is_valid);
```

### Event DAG

```rust
use mcp_validators::validators::EventDAGValidator;
use serde_json::json;

let validator = EventDAGValidator::new();

let event = json!({
    "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
    "parents": ["QmPreviousEvent"],
    "payload": {"data": "test"},
    "timestamp": "2024-01-01T00:00:00Z"
});

let result = validator.validate_event(&event)?;
assert!(result.is_valid);
```

## Type Safety Features

### Compile-Time Safety

Rust's type system prevents entire classes of errors:

```rust
use mcp_validators::models::*;

// This won't compile - type mismatch
let request = JSONRPCRequest {
    jsonrpc: "2.0".to_string(),
    method: "test".to_string(),
    params: Some(json!({})),
    id: "wrong_type",  // ❌ Compile error: expected RequestId
};

// Correct usage
let request = JSONRPCRequest {
    jsonrpc: "2.0".to_string(),
    method: "test".to_string(),
    params: Some(json!({})),
    id: RequestId::String("id-1".to_string()),  // ✅ Type-safe
};
```

### Runtime Validation

serde_valid provides declarative validation:

```rust
use mcp_validators::models::JSONRPCRequest;
use serde_valid::Validate;

let request = JSONRPCRequest {
    jsonrpc: "1.0".to_string(),  // ❌ Must be "2.0"
    method: "".to_string(),      // ❌ Must be non-empty
    params: None,
    id: RequestId::Number(1),
};

// Validation fails at runtime
assert!(request.validate().is_err());
```

### Pattern Matching

Exhaustive case handling with enums:

```rust
use mcp_validators::models::DecisionType;

fn handle_decision(decision: DecisionType) {
    match decision {
        DecisionType::Allow => println!("Access allowed"),
        DecisionType::Deny => println!("Access denied"),
        DecisionType::AllowWithObligations => println!("Conditional access"),
        // Compiler ensures all cases are handled
    }
}
```

## Testing

Run all tests:

```bash
cargo test
```

Run with verbose output:

```bash
cargo test -- --nocapture
```

Run specific test:

```bash
cargo test test_base_mcp_valid_request
```

## Linting & Formatting

Format code:

```bash
cargo fmt
```

Run linter:

```bash
cargo clippy
```

Build with strict settings:

```bash
cargo build --release
```

## Performance

Rust validators provide:
- **Zero-cost abstractions**: No runtime overhead for type safety
- **Fast validation**: Compiled to native code
- **Low memory usage**: No garbage collection overhead
- **Predictable performance**: No JIT compilation

## Comparison with Other Languages

| Feature | Rust | Python | TypeScript |
|---------|------|--------|------------|
| Compile-time safety | ✅ Strong | ❌ No | ✅ Good |
| Runtime overhead | ✅ Zero | ⚠️ Interpreter | ⚠️ JIT |
| Memory safety | ✅ Guaranteed | ❌ No | ❌ No |
| Null safety | ✅ `Option<T>` | ⚠️ `None` | ⚠️ `undefined/null` |
| Pattern matching | ✅ Exhaustive | ⚠️ Limited | ⚠️ Limited |
| Performance | ✅ Native speed | ❌ Slow | ⚠️ Variable |

## Architecture

```
tests-rs/
├── src/
│   ├── models.rs              # Type definitions (40+ structs/enums)
│   ├── validators/
│   │   ├── base_mcp.rs        # Base MCP validator
│   │   ├── mcp_idl.rs         # Profile A
│   │   ├── cid_artifacts.rs   # Profile B
│   │   ├── ucan_delegation.rs # Profile C
│   │   ├── policy_evaluation.rs # Profile D
│   │   ├── transport.rs       # Profile E
│   │   ├── event_dag.rs       # Event DAG
│   │   └── mod.rs             # Module exports
│   └── lib.rs                 # Library root
├── tests/
│   └── integration_test.rs    # 23+ integration tests
├── Cargo.toml                 # Dependencies & config
└── rustfmt.toml              # Code formatting rules
```

## Dependencies

- **serde**: Serialization framework (compile-time)
- **serde_json**: JSON support
- **serde_valid**: Declarative validation rules
- **thiserror**: Error handling ergonomics
- **regex**: Pattern matching for CIDs and formats
- **lazy_static**: Compiled regex patterns

## License

Same as parent project.

## Contributing

See the main CONTRIBUTING.md in the repository root.

## References

- [Rust Book](https://doc.rust-lang.org/book/)
- [Serde Documentation](https://serde.rs/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP++ Specifications](../docs/spec/)
