// Package validators provides type-safe validation for MCP protocol messages.
package validators

import (
	"encoding/json"
	"fmt"
	"regexp"

	"github.com/go-playground/validator/v10"
	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// BaseMCPValidator validates base MCP protocol messages.
//
// SPEC: Baseline MCP specification
// Validates JSON-RPC 2.0 structure, MCP methods, and protocol semantics.
type BaseMCPValidator struct {
	validate *validator.Validate
}

// NewBaseMCPValidator creates a new base MCP validator with custom validation rules.
func NewBaseMCPValidator() *BaseMCPValidator {
	v := validator.New()
	
	// Register custom CID validation
	v.RegisterValidation("cid", validateCID)
	
	return &BaseMCPValidator{
		validate: v,
	}
}

// validateCID validates that a string is a valid CID format.
func validateCID(fl validator.FieldLevel) bool {
	cidPattern := regexp.MustCompile(`^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[A-Za-z2-7]{58}|z[1-9A-HJ-NP-Za-km-z]{48})$`)
	return cidPattern.MatchString(fl.Field().String())
}

// ValidateJSONRPCRequest validates a JSON-RPC 2.0 request message.
//
// SPEC: JSON-RPC 2.0, MUST have jsonrpc, method, and id fields
func (v *BaseMCPValidator) ValidateJSONRPCRequest(data []byte) (*testsmcp.JSONRPCRequest, error) {
	var req testsmcp.JSONRPCRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.validate.Struct(req); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Additional validation: jsonrpc must be exactly "2.0"
	if req.JSONRPC != "2.0" {
		return nil, fmt.Errorf("jsonrpc field must be '2.0', got '%s'", req.JSONRPC)
	}
	
	return &req, nil
}

// ValidateJSONRPCResponse validates a JSON-RPC 2.0 response message.
//
// SPEC: JSON-RPC 2.0, MUST have either result or error, not both
func (v *BaseMCPValidator) ValidateJSONRPCResponse(data []byte) (*testsmcp.JSONRPCResponse, error) {
	var resp testsmcp.JSONRPCResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.validate.Struct(resp); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Additional validation: must have exactly one of result or error
	hasResult := resp.Result != nil
	hasError := resp.Error != nil
	
	if hasResult && hasError {
		return nil, fmt.Errorf("response cannot have both result and error")
	}
	if !hasResult && !hasError {
		return nil, fmt.Errorf("response must have either result or error")
	}
	
	return &resp, nil
}

// ValidateJSONRPCNotification validates a JSON-RPC 2.0 notification message.
//
// SPEC: JSON-RPC 2.0, MUST have jsonrpc and method, MUST NOT have id
func (v *BaseMCPValidator) ValidateJSONRPCNotification(data []byte) (*testsmcp.JSONRPCNotification, error) {
	var notif testsmcp.JSONRPCNotification
	if err := json.Unmarshal(data, &notif); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if err := v.validate.Struct(notif); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	// Check that method starts with "notifications/"
	if len(notif.Method) < 14 || notif.Method[:14] != "notifications/" {
		return nil, fmt.Errorf("notification method must start with 'notifications/', got '%s'", notif.Method)
	}
	
	return &notif, nil
}

// ValidateInitializeRequest validates an MCP initialize request.
//
// SPEC: MCP Baseline, initialize method MUST include protocol version and capabilities
func (v *BaseMCPValidator) ValidateInitializeRequest(data []byte) (*testsmcp.InitializeParams, error) {
	var req testsmcp.JSONRPCRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if req.Method != "initialize" {
		return nil, fmt.Errorf("expected method 'initialize', got '%s'", req.Method)
	}
	
	// Parse params as InitializeParams
	paramsJSON, err := json.Marshal(req.Params)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal params: %w", err)
	}
	
	var params testsmcp.InitializeParams
	if err := json.Unmarshal(paramsJSON, &params); err != nil {
		return nil, fmt.Errorf("invalid initialize params: %w", err)
	}
	
	if err := v.validate.Struct(params); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	return &params, nil
}

// ValidateToolCall validates an MCP tools/call request.
//
// SPEC: MCP Baseline, tools/call MUST have name and optional arguments
func (v *BaseMCPValidator) ValidateToolCall(data []byte) (*testsmcp.ToolCallParams, error) {
	var req testsmcp.JSONRPCRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if req.Method != "tools/call" {
		return nil, fmt.Errorf("expected method 'tools/call', got '%s'", req.Method)
	}
	
	// Parse params as ToolCallParams
	paramsJSON, err := json.Marshal(req.Params)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal params: %w", err)
	}
	
	var params testsmcp.ToolCallParams
	if err := json.Unmarshal(paramsJSON, &params); err != nil {
		return nil, fmt.Errorf("invalid tool call params: %w", err)
	}
	
	if err := v.validate.Struct(params); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	return &params, nil
}

// ValidateResourceRead validates an MCP resources/read request.
//
// SPEC: MCP Baseline, resources/read MUST have uri
func (v *BaseMCPValidator) ValidateResourceRead(data []byte) (*testsmcp.ResourceReadParams, error) {
	var req testsmcp.JSONRPCRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if req.Method != "resources/read" {
		return nil, fmt.Errorf("expected method 'resources/read', got '%s'", req.Method)
	}
	
	// Parse params as ResourceReadParams
	paramsJSON, err := json.Marshal(req.Params)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal params: %w", err)
	}
	
	var params testsmcp.ResourceReadParams
	if err := json.Unmarshal(paramsJSON, &params); err != nil {
		return nil, fmt.Errorf("invalid resource read params: %w", err)
	}
	
	if err := v.validate.Struct(params); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	return &params, nil
}

// ValidatePromptGet validates an MCP prompts/get request.
//
// SPEC: MCP Baseline, prompts/get MUST have name and optional arguments
func (v *BaseMCPValidator) ValidatePromptGet(data []byte) (*testsmcp.PromptGetParams, error) {
	var req testsmcp.JSONRPCRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	
	if req.Method != "prompts/get" {
		return nil, fmt.Errorf("expected method 'prompts/get', got '%s'", req.Method)
	}
	
	// Parse params as PromptGetParams
	paramsJSON, err := json.Marshal(req.Params)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal params: %w", err)
	}
	
	var params testsmcp.PromptGetParams
	if err := json.Unmarshal(paramsJSON, &params); err != nil {
		return nil, fmt.Errorf("invalid prompt get params: %w", err)
	}
	
	if err := v.validate.Struct(params); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	
	return &params, nil
}
