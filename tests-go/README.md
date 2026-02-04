# MCP++ Go Validators

Type-safe validators for MCP and MCP++ protocol messages implemented in Go with strong compile-time type checking and runtime validation.

## Features

- **Strong Type Safety**: Go's static type system catches errors at compile time
- **Runtime Validation**: go-playground/validator for declarative validation rules
- **Zero Dependencies**: Uses standard library where possible
- **Comprehensive Coverage**: All 7 MCP++ profiles validated
- **Well-Tested**: 17 comprehensive tests covering all validators
- **Production-Ready**: Clean error handling, godoc comments, and best practices

## Installation

```bash
cd tests-go
go mod download
```

## Quick Start

```go
package main

import (
	"fmt"
	"log"
	
	"github.com/endomorphosis/Mcp-Plus-Plus/tests-go/validators"
)

func main() {
	// Create a validator
	validator := validators.NewBaseMCPValidator()
	
	// Validate a JSON-RPC request
	requestJSON := []byte(`{
		"jsonrpc": "2.0",
		"method": "initialize",
		"params": {
			"protocolVersion": "1.0.0",
			"capabilities": {"tools": {}},
			"clientInfo": {"name": "test-client", "version": "1.0.0"}
		},
		"id": 1
	}`)
	
	req, err := validator.ValidateJSONRPCRequest(requestJSON)
	if err != nil {
		log.Fatal(err)
	}
	
	fmt.Printf("Valid request: %s\n", req.Method)
}
```

## Validators

### Base MCP Validator

Validates core MCP protocol messages:

```go
validator := validators.NewBaseMCPValidator()

// JSON-RPC validation
req, err := validator.ValidateJSONRPCRequest(data)
resp, err := validator.ValidateJSONRPCResponse(data)
notif, err := validator.ValidateJSONRPCNotification(data)

// MCP protocol methods
initParams, err := validator.ValidateInitializeRequest(data)
toolCall, err := validator.ValidateToolCall(data)
resource, err := validator.ValidateResourceRead(data)
prompt, err := validator.ValidatePromptGet(data)
```

### MCP-IDL Validator (Profile A)

Validates interface descriptors and compatibility:

```go
validator := validators.NewMCPIDLValidator()

descriptor, err := validator.ValidateInterfaceDescriptor(data)
compat, err := validator.ValidateCompatibilityCheck(data)
```

### CID Artifacts Validator (Profile B)

Validates content-addressed execution artifacts:

```go
validator := validators.NewCIDValidator()

envelope, err := validator.ValidateExecutionEnvelope(data)
receipt, err := validator.ValidateExecutionReceipt(data)
```

### UCAN Delegation Validator (Profile C)

Validates UCAN tokens and delegation chains:

```go
validator := validators.NewUCANValidator()

token, err := validator.ValidateUCANToken(data)
chain, err := validator.ValidateDelegationChain(data)
```

### Policy Evaluation Validator (Profile D)

Validates temporal deontic policies:

```go
validator := validators.NewPolicyValidator()

policy, err := validator.ValidatePolicyDescriptor(data)
decision, err := validator.ValidatePolicyDecision(data)
```

### Transport Validator (Profile E)

Validates transport protocol messages:

```go
validator := validators.NewTransportValidator()

msg, err := validator.ValidateTransportMessage(data)
init, err := validator.ValidateSessionInit(data)
```

### Event DAG Validator

Validates event graphs and provenance:

```go
validator := validators.NewEventDAGValidator()

event, err := validator.ValidateEvent(data)
dag, err := validator.ValidateEventDAG(data) // Includes cycle detection
```

## Type System

### Go's Strong Typing

Go provides compile-time type safety with:

- **Static typing**: All types known at compile time
- **Type inference**: `var x = 42` infers `int` type
- **No implicit conversions**: Explicit type conversions required
- **Interface-based polymorphism**: Duck typing with interfaces
- **Struct embedding**: Composition over inheritance

### Struct Tags

Validators use struct tags for declarative validation:

```go
type ToolCallParams struct {
	Name      string                 `json:"name" validate:"required,min=1"`
	Arguments map[string]interface{} `json:"arguments,omitempty"`
}
```

Tags:
- `json:` - JSON serialization rules
- `validate:` - Validation constraints (required, min, max, regex, etc.)

### Custom Validators

CID format validation is registered as a custom validator:

```go
func validateCID(fl validator.FieldLevel) bool {
	cidPattern := regexp.MustCompile(`^(Qm[1-9A-HJ-NP-Za-km-z]{44}|...)$`)
	return cidPattern.MatchString(fl.Field().String())
}
```

## Testing

Run all tests:

```bash
cd tests-go
go test -v ./...
```

Run with coverage:

```bash
go test -cover ./...
```

Run specific test:

```bash
go test -v ./validators/ -run TestBaseMCPValidator_JSONRPCRequest
```

### Test Results

```
17 tests, all passing:
- 5 Base MCP tests
- 2 MCP-IDL tests
- 2 CID Artifacts tests
- 1 UCAN Delegation test
- 2 Policy Evaluation tests
- 1 Transport test
- 2 Event DAG tests
- 1 Cycle detection test
- 1 Notification test
```

## Error Handling

All validators return descriptive errors:

```go
req, err := validator.ValidateJSONRPCRequest(data)
if err != nil {
	// Error contains context about what failed
	log.Printf("Validation failed: %v", err)
}
```

Error types:
- **JSON parsing errors**: "invalid JSON: ..."
- **Validation errors**: "validation failed: ..."
- **Semantic errors**: "response cannot have both result and error"
- **Format errors**: "invalid CID format: ..."

## Type Safety Features

### Compile-Time Safety

```go
// Type mismatch caught at compile time
var req JSONRPCRequest
req.JSONRPC = 123 // Error: cannot use int as string
```

### Nil Safety

```go
// No null pointers - use pointers for optional fields
type JSONRPCResponse struct {
	Result interface{} `json:"result,omitempty"`
	Error  *JSONRPCError `json:"error,omitempty"` // Pointer = optional
}
```

### Exhaustive Pattern Matching

```go
switch decision.Decision {
case DecisionAllow:
	// handle allow
case DecisionDeny:
	// handle deny
case DecisionAllowWithObligations:
	// handle obligations
// Compiler warns if case is missing
}
```

## Code Quality

### Static Analysis

```bash
# Vet: Find suspicious constructs
go vet ./...

# Format: Enforce consistent style
go fmt ./...

# Lint: Advanced linting (if installed)
golangci-lint run
```

### Documentation

All exported types and functions have godoc comments:

```bash
# Generate documentation
go doc -all github.com/endomorphosis/Mcp-Plus-Plus/tests-go/validators
```

## Performance

Go validators are:
- **Fast**: Compiled to native machine code
- **Efficient**: No garbage collection pauses during validation
- **Concurrent**: Safe for use in goroutines
- **Low Memory**: Minimal allocations with struct reuse

## Comparison with Other Languages

| Feature | Go | Python | TypeScript | Rust |
|---------|-----|--------|------------|------|
| Compile-time safety | ✅ Strong | ❌ No | ✅ Good | ✅ Strongest |
| Runtime overhead | ✅ Low | ⚠️ High | ⚠️ Medium | ✅ Zero |
| Concurrency | ✅ Built-in (goroutines) | ⚠️ GIL | ❌ Single-thread | ✅ Safe |
| Null safety | ✅ No null (use pointers) | ❌ None | ⚠️ null/undefined | ✅ Option<T> |
| Memory safety | ✅ GC + bounds checking | ✅ GC | ✅ GC | ✅ Ownership |
| Simplicity | ✅ Very simple | ✅ Simple | ⚠️ Complex | ⚠️ Steep learning curve |
| Build speed | ✅ Very fast | N/A | ⚠️ Slow | ⚠️ Slow |
| Standard library | ✅ Excellent | ✅ Excellent | ⚠️ Node.js | ✅ Good |

## Integration

### In Production Services

```go
package main

import (
	"encoding/json"
	"net/http"
	
	"github.com/endomorphosis/Mcp-Plus-Plus/tests-go/validators"
)

func handleMCPRequest(w http.ResponseWriter, r *http.Request) {
	validator := validators.NewBaseMCPValidator()
	
	var data []byte
	// Read request body...
	
	req, err := validator.ValidateJSONRPCRequest(data)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	
	// Process valid request...
}
```

### In Tests

```go
func TestMyMCPClient(t *testing.T) {
	validator := validators.NewBaseMCPValidator()
	
	client := NewMCPClient()
	response := client.Initialize()
	
	// Validate response structure
	_, err := validator.ValidateJSONRPCResponse(response)
	if err != nil {
		t.Fatalf("Invalid response: %v", err)
	}
}
```

## Dependencies

- **github.com/go-playground/validator/v10** - Runtime validation
- **encoding/json** (stdlib) - JSON serialization
- **regexp** (stdlib) - Pattern matching
- **time** (stdlib) - Timestamp handling

## License

Part of the MCP++ project. See root LICENSE file.

## Contributing

See main CONTRIBUTING.md in the repository root.

## Support

For issues or questions about Go validators:
1. Check this README
2. Review test examples in `validators/validators_test.go`
3. Read godoc: `go doc -all ./validators`
4. Open an issue on GitHub
