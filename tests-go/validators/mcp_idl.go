package validators

import (
	"encoding/json"
	"fmt"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// MCPIDLValidator validates MCP-IDL (Profile A) messages.
//
// SPEC: MCP-IDL.md § Interface Descriptors
// Validates interface descriptors, CID computation, and compatibility checking.
type MCPIDLValidator struct {
	base *BaseMCPValidator
}

// NewMCPIDLValidator creates a new MCP-IDL validator.
func NewMCPIDLValidator() *MCPIDLValidator {
	return &MCPIDLValidator{
		base: NewBaseMCPValidator(),
	}
}

// ValidateInterfaceDescriptor validates an interface descriptor.
//
// SPEC: MCP-IDL.md, MUST have interface_name, version, and methods
func (v *MCPIDLValidator) ValidateInterfaceDescriptor(data []byte) (*testsmcp.InterfaceDescriptor, error) {
	var descriptor testsmcp.InterfaceDescriptor
	if err := json.Unmarshal(data, &descriptor); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(descriptor); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Validate that each method has at least a name and return type
	for i, method := range descriptor.Methods {
		if method.Name == "" {
			return nil, fmt.Errorf("method %d has empty name", i)
		}
		if method.ReturnType == "" {
			return nil, fmt.Errorf("method %s has empty return_type", method.Name)
		}
	}
	
	return &descriptor, nil
}

// ValidateCompatibilityCheck validates an interface compatibility check result.
//
// SPEC: MCP-IDL.md, compatibility checking between interface versions
func (v *MCPIDLValidator) ValidateCompatibilityCheck(data []byte) (*testsmcp.InterfaceCompatibility, error) {
	var compat testsmcp.InterfaceCompatibility
	if err := json.Unmarshal(data, &compat); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.base.validate.Struct(compat); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	return &compat, nil
}
